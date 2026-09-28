"""TradeMapProcessor — orkestrasi pipeline end-to-end.

Raw file -> Parser -> Normalizer -> Master Mapping -> HS Harmonization
-> Validation -> Duplicate Check -> trademap_trade (+ raw metadata/lineage).

Default dry-run (tidak menulis DB); gunakan commit=True untuk menyimpan.
Idempotensi: trademap_raw di-upsert per file_hash; trademap_trade memakai
unique key (reporter, partner, flow, product_code, year, id_trademap_raw)
dengan ON DUPLICATE KEY UPDATE (processing ulang tidak menggandakan baris).
"""
import json
import os
import uuid

from backend.db import get_connection
from backend.trademap.mapper import TradeMapMapper
from backend.trademap.models import NormalizedRecord, ProcessResult, ProcessStats
from backend.trademap.normalizer import TradeMapNormalizer
from backend.trademap.parser import TradeMapParser
from backend.trademap.validator import TradeMapValidator


class TradeMapProcessor:
    def __init__(self, conn=None):
        self._conn = conn
        self._owns_conn = conn is None
        self.parser = TradeMapParser()
        self.normalizer = TradeMapNormalizer()
        self.validator = TradeMapValidator()

    def _connect(self):
        if self._conn is None:
            self._conn = get_connection()
        return self._conn

    def close(self):
        if self._conn is not None and self._owns_conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    def process(self, path, source="TradeMap ITC", commit=False, download_log_id=None):
        conn = self._connect()
        mapper = TradeMapMapper(conn)
        stats = ProcessStats()

        parsed = self.parser.parse(path)
        if not parsed.ok:
            result = ProcessResult(ok=False, commit=commit, stats=stats,
                                   file_hash=parsed.file_hash,
                                   error=";".join(parsed.errors))
            if commit:
                self._fail_job(path, source, parsed)
            return result

        stats.total_rows = len(parsed.records)

        # --- pipeline per baris -------------------------------------------
        records = []
        seen_keys = {}
        issues = []
        for raw in parsed.records:
            nr = NormalizedRecord(raw=raw, **self.normalizer.normalize(raw))

            id_rep, _ = mapper.map_country(nr.reporter_code)
            id_par, _ = mapper.map_country(nr.partner_code)
            nr.id_ms_negara_reporter = id_rep
            nr.id_ms_negara = id_par
            for field, raw_val, mid in (("reporter", nr.reporter_code, id_rep),
                                        ("partner", nr.partner_code, id_par)):
                iss = mapper.country_issue(raw_val, mid, field)
                if iss:
                    iss.row_ref = raw.row_ref
                    nr.issues.append(iss)

            hs = mapper.map_hs(nr.product_code, nr.hs_version)
            nr.id_ms_hscode = hs.id_ms_hscode
            nr.id_ms_komoditas = hs.id_ms_komoditas
            nr.hs_mapping_status = hs.status
            nr.hs_candidates = hs.candidates

            bk = (nr.reporter_code, nr.partner_code, nr.raw.flow, nr.product_code, nr.year)
            if bk in seen_keys:
                nr.duplicate = True
                stats.duplicate_rows += 1
            seen_keys.setdefault(bk, raw.row_ref)

            row_issues = self.validator.validate(nr)
            issues.extend(row_issues)
            self._tally(stats, nr)
            records.append(nr)

        stats.mapped_rows = sum(
            1 for r in records if r.id_ms_negara_reporter and r.id_ms_negara and r.hs_mapping_status == "MAPPED")
        stats.unmapped_rows = stats.total_rows - stats.mapped_rows

        result = ProcessResult(ok=True, commit=commit, stats=stats,
                               file_hash=parsed.file_hash, issues=issues, records=records)
        if not commit:
            return result

        # --- persist -------------------------------------------------------
        conn = self._connect()
        job_id = self._start_job(path, source, parsed, stats)
        raw_id = self._upsert_raw(conn, parsed, source, stats, job_id, download_log_id)
        self._replace_validation(conn, raw_id, job_id, issues)
        for code, hs_version in {(r.product_code, r.hs_version) for r in records}:
            mapper.record_hs_mapping(mapper.map_hs(code, hs_version), source)
        ins, upd = self._persist_trade(conn, raw_id, records)
        stats.inserted_rows, stats.updated_rows = ins, upd
        self._finish_raw(conn, raw_id, parsed, source, stats, job_id)
        self._finish_job(conn, job_id, stats)
        conn.commit()

        result.raw_id, result.job_id = raw_id, job_id
        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _tally(stats, nr):
        if nr.validation_status == "INVALID":
            stats.invalid_rows += 1
        elif nr.validation_status == "WARNING":
            stats.warning_rows += 1
        else:
            stats.valid_rows += 1

    # --- DB helpers ----------------------------------------------------
    def _start_job(self, path, source, parsed, stats):
        cur = self._connect().cursor()
        cur.execute(
            "INSERT INTO automation_jobs (job_type, status, params_json, correlation_id, started_at) "
            "VALUES ('trademap_process','RUNNING',%s,%s,NOW())",
            (json.dumps({"file": parsed.file_name, "source": source,
                         "format": parsed.file_format, "total_rows": stats.total_rows}),
             uuid.uuid4().hex))
        job_id = cur.lastrowid
        cur.execute("INSERT INTO automation_job_logs (id_job, level, message) VALUES (%s,'info',%s)",
                    (job_id, "mulai process %s (%d baris)" % (parsed.file_name, stats.total_rows)))
        return job_id

    def _fail_job(self, path, source, parsed):
        try:
            cur = self._connect().cursor()
            cur.execute(
                "INSERT INTO automation_jobs (job_type, status, params_json, correlation_id, "
                "started_at, finished_at, error_message) "
                "VALUES ('trademap_process','FAILED',%s,%s,NOW(),NOW(),%s)",
                (json.dumps({"file": parsed.file_name, "source": source}),
                 uuid.uuid4().hex, ";".join(parsed.errors)))
            jid = cur.lastrowid
            cur.execute("INSERT INTO automation_job_logs (id_job, level, message) VALUES (%s,'error',%s)",
                        (jid, "gagal: " + ";".join(parsed.errors)))
            self._connect().commit()
        except Exception:  # noqa: BLE001
            self._connect().rollback()

    def _upsert_raw(self, conn, parsed, source, stats, job_id, download_log_id):
        years = sorted({r.year for r in parsed.records if r.year})
        reporters = sorted({r.reporter for r in parsed.records if r.reporter})
        partners = sorted({r.partner for r in parsed.records if r.partner})
        flows = sorted({r.flow for r in parsed.records if r.flow})
        period_label = parsed.metadata.get("year") or parsed.metadata.get("period") \
            or ("%s-%s" % (years[0], years[-1]) if years else None)
        payload = {
            "headers": parsed.headers,
            "metadata": parsed.metadata,
            "value_header": parsed.value_header,
            "sample": [r.__dict__ for r in parsed.records[:20]],
        }
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO trademap_raw
               (id_download_log, id_job, source, file_path, file_name, file_format, file_hash,
                row_count, period_label, reporter_scope, partner_scope, flow_scope,
                payload_json, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'raw')
               ON DUPLICATE KEY UPDATE
                 id_job=VALUES(id_job), source=VALUES(source), file_path=VALUES(file_path),
                 file_name=VALUES(file_name), file_format=VALUES(file_format),
                 row_count=VALUES(row_count), period_label=VALUES(period_label),
                 reporter_scope=VALUES(reporter_scope), partner_scope=VALUES(partner_scope),
                 flow_scope=VALUES(flow_scope), payload_json=VALUES(payload_json)""",
            (download_log_id, job_id, source, parsed.path, parsed.file_name, parsed.file_format,
             parsed.file_hash, stats.total_rows, period_label,
             ",".join(reporters)[:50] or None, ",".join(partners)[:50] or None,
             ",".join(flows)[:20] or None, json.dumps(payload, ensure_ascii=False, default=str)))
        cur.execute("SELECT id FROM trademap_raw WHERE file_hash=%s", (parsed.file_hash,))
        return cur.fetchone()["id"]

    def _replace_validation(self, conn, raw_id, job_id, issues):
        cur = conn.cursor()
        cur.execute("DELETE FROM trademap_validation_results WHERE id_trademap_raw=%s", (raw_id,))
        for i in issues:
            cur.execute(
                """INSERT INTO trademap_validation_results
                   (id_job, id_trademap_raw, row_ref, field, kode, source_value, severity, reason, recommended)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (job_id, raw_id, i.row_ref, i.field, i.kode,
                 (None if i.source_value is None else str(i.source_value)[:255]),
                 i.severity, i.reason[:500], i.recommended[:500]))

    def _persist_trade(self, conn, raw_id, records):
        cur = conn.cursor()
        ins = upd = 0
        for nr in records:
            if nr.validation_status == "INVALID":
                continue  # tidak masuk processed dataset (tercatat di validation results)
            if nr.duplicate:
                continue  # duplikat dalam file: baris pertama yang disimpan
            cur.execute(
                """INSERT INTO trademap_trade
                   (reporter, partner, id_ms_negara_reporter, id_ms_negara, flow, flow_norm,
                    product_code, product_desc, id_ms_hscode, id_ms_komoditas, hs_version,
                    hs_mapping_status, year, qty, qty_unit, value_usd, value_unit_source,
                    value_usd_norm, validation_status, validation_notes, row_ref, id_trademap_raw)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE
                     id_ms_negara_reporter=VALUES(id_ms_negara_reporter),
                     id_ms_negara=VALUES(id_ms_negara), flow_norm=VALUES(flow_norm),
                     product_desc=VALUES(product_desc), id_ms_hscode=VALUES(id_ms_hscode),
                     id_ms_komoditas=VALUES(id_ms_komoditas), hs_version=VALUES(hs_version),
                     hs_mapping_status=VALUES(hs_mapping_status), qty=VALUES(qty),
                     qty_unit=VALUES(qty_unit), value_usd=VALUES(value_usd),
                     value_unit_source=VALUES(value_unit_source), value_usd_norm=VALUES(value_usd_norm),
                     validation_status=VALUES(validation_status),
                     validation_notes=VALUES(validation_notes), row_ref=VALUES(row_ref)""",
                (nr.reporter_code, nr.partner_code or None, nr.id_ms_negara_reporter, nr.id_ms_negara,
                 nr.raw.flow or "", nr.flow_norm or None, nr.product_code, nr.raw.product_desc or None,
                 nr.id_ms_hscode, nr.id_ms_komoditas, nr.hs_version or None, nr.hs_mapping_status,
                 nr.year, nr.qty, nr.qty_unit, nr.value, nr.value_unit_source, nr.value_usd_norm,
                 nr.validation_status, nr.validation_notes, nr.raw.row_ref, raw_id))
            if cur.rowcount == 1:
                ins += 1
            elif cur.rowcount >= 2:
                upd += 1
        return ins, upd

    def _finish_raw(self, conn, raw_id, parsed, source, stats, job_id):
        cur = conn.cursor()
        cur.execute(
            "UPDATE trademap_raw SET row_count=%s, total_rows=%s, valid_rows=%s, warning_rows=%s, "
            "invalid_rows=%s, duplicate_rows=%s, mapped_rows=%s, unmapped_rows=%s, "
            "status='processed', processed_at=NOW() WHERE id=%s",
            (stats.total_rows, stats.total_rows, stats.valid_rows, stats.warning_rows,
             stats.invalid_rows, stats.duplicate_rows, stats.mapped_rows, stats.unmapped_rows, raw_id))

    def _finish_job(self, conn, job_id, stats):
        cur = conn.cursor()
        cur.execute("UPDATE automation_jobs SET status='SUCCESS', finished_at=NOW() WHERE id=%s", (job_id,))
        cur.execute(
            "INSERT INTO automation_job_logs (id_job, level, message, data_json) VALUES (%s,'info',%s,%s)",
            (job_id, "selesai: %d disimpan, %d diperbarui, %d invalid, %d duplikat" % (
                stats.inserted_rows, stats.updated_rows, stats.invalid_rows, stats.duplicate_rows),
             json.dumps(stats.as_dict())))

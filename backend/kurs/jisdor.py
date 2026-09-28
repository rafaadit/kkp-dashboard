"""Downloader Kurs JISDOR Bank Indonesia — ambil data otomatis + catat lineage.

Sumber: web service resmi BI `https://www.bi.go.id/biwebservice/wskursbi.asmx`,
fungsi `getSubKursJisdor3` (GET, publik, tanpa API key; butuh User-Agent).

JISDOR = Jakarta Interbank Spot Dollar Rate (USD/IDR, harga spot acuan BI),
diterbitkan tiap hari kerja. Robot:

  1. fetch XML (rentang tanggal) -> simpan mentah ke BI_JISDOR_DIR
  2. parse baris harian (tgl_subkursasing / beli_subkursasing)
  3. catat automation_jobs 'jisdor_download' + automation_download_logs
     (PENDING -> DOWNLOADED -> VALIDATED)
  4. proses (commit=True): simpan jisdor_daily + rata-rata bulanan ke ms_kurs
     (sumber 'JISDOR Bank Indonesia') -> raw_exim bisa dihitung ulang.

Mode fixture (--fixture path) untuk uji deterministik. URL base dibaca dari env
BI_JISDOR_URL (default https://www.bi.go.id/biwebservice/wskursbi.asmx),
direktori tujuan dari BI_JISDOR_DIR (default ./data/kurs).
"""
import hashlib
import json
import os
import shutil
import uuid
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from backend.db import get_connection

USER_AGENT = "KKP-EXIM/1.0 (+https://github.com/; kurs JISDOR automation)"


class JisdorError(RuntimeError):
    """Error fetch/parse yang harus ditandai FAILED di lineage."""


def _sha256(path, chunk=1 << 16):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def parse_xml(data):
    """Parse respons wsKursBI -> list dict {tanggal: date, kurs: Decimal}.

    Format: <DataSet><Table>
      <tgl_subkursasing>2026-09-25T00:00:00+07:00</tgl_subkursasing>
      <beli_subkursasing>17917.00</beli_subkursasing>
      <jual_subkursasing>17917.00</jual_subkursasing>
    (JISDOR: beli == jual == kurs acuan).
    """
    root = ET.fromstring(data)
    ns = {"d": "http://www.w3.org/2001/XMLSchema"}
    rows = []
    for el in root.iter():
        if el.tag.split("}")[-1] != "Table":
            continue
        tag_date = tag_beli = None
        for child in el:
            name = child.tag.split("}")[-1]
            if name == "tgl_subkursasing":
                tag_date = child.text
            elif name == "beli_subkursasing":
                tag_beli = child.text
        if not tag_date or not tag_beli:
            continue
        d = date.fromisoformat(tag_date[:10])
        rows.append({"tanggal": d, "kurs": Decimal(tag_beli)})
    rows.sort(key=lambda r: r["tanggal"])
    return rows


class JisdorDownloader:
    """Unduh kurs JISDOR BI dan catat automation_jobs + automation_download_logs."""

    def __init__(self, conn=None):
        self._conn = conn
        self._owns_conn = conn is None

    def _connect(self):
        if self._conn is None:
            self._conn = get_connection()
        return self._conn

    def close(self):
        if self._conn is not None and self._owns_conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    @staticmethod
    def download_dir():
        return os.environ.get("BI_JISDOR_DIR", "./data/kurs")

    @staticmethod
    def api_base():
        return os.environ.get("BI_JISDOR_URL",
                              "https://www.bi.go.id/biwebservice/wskursbi.asmx").rstrip("/")

    def target_path(self, start, end):
        d = self.download_dir()
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        return os.path.join(d, "jisdor_%s_%s.xml" % (start, end))

    @staticmethod
    def build_url(base, mts, start, end):
        qs = urllib.parse.urlencode({"mts": mts, "startDate": start, "endDate": end})
        return f"{base}/getSubKursJisdor3?{qs}"

    def fetch(self, url, out_path):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
        except urllib.error.URLError as e:
            raise JisdorError(f"unduh gagal: {e}") from e
        with open(out_path, "wb") as fh:
            fh.write(data)
        return data

    # ------------------------------------------------------------------
    def run(self, mts="USD", start=None, end=None, source="Bank Indonesia JISDOR",
            fixture=None, process=True, commit=False, job_id=None):
        """Jalankan satu sesi unduhan JISDOR (+ opsional proses ke DB).

        Return: dict {ok, job_id, download_log_id, file_path, file_hash,
                      file_size, days, months, message}.
        """
        if start is None:
            start = date.today().replace(day=1).isoformat()
        if end is None:
            end = date.today().isoformat()
        cur = self._connect().cursor()
        job_id = self._begin_job(cur, job_id, mts, start, end, source, fixture, process)
        dl_id = self._insert_download_log(cur, job_id, source, start, end, mts)
        try:
            if fixture:
                out = self.target_path(start, end)
                shutil.copyfile(fixture, out)
                raw = open(out, "rb").read()
            else:
                out = self.target_path(start, end)
                url = self.build_url(self.api_base(), mts, start, end)
                raw = self.fetch(url, out)
            rows = parse_xml(raw)
            if not rows:
                raise JisdorError("tidak ada baris kurs pada rentang %s..%s" % (start, end))
            size = os.path.getsize(out)
            fhash = _sha256(out)
            self._mark_downloaded(cur, dl_id, out, size, fhash)

            summary = {
                "ok": True,
                "job_id": job_id,
                "download_log_id": dl_id,
                "file_path": out,
                "file_hash": fhash,
                "file_size": size,
                "days": len(rows),
            }
            if process:
                months = self._store(cur, rows, mts, source, dl_id, commit)
                summary["months"] = months
                cur.execute(
                    "UPDATE automation_download_logs SET status='VALIDATED' WHERE id=%s",
                    (dl_id,))
                self._connect().commit()
            self._finish_job(cur, job_id, True, None)
            summary["message"] = ("unduh sukses (%d hari) + proses selesai (%d bulan)"
                                  % (len(rows), summary.get("months", 0))) if process else \
                "unduh sukses (%d hari)" % len(rows)
            return summary
        except JisdorError as e:
            self._mark_failed(cur, job_id, dl_id, str(e))
            return {"ok": False, "job_id": job_id, "download_log_id": dl_id,
                    "error": str(e)}

    def _store(self, cur, rows, mts, source, dl_id, commit):
        """Simpan harian -> jisdor_daily; rata-rata bulanan -> ms_kurs (commit)."""
        cur.execute("SELECT id, tahun, bulan FROM ms_period")
        period = {(r["tahun"], r["bulan"]): r["id"] for r in cur.fetchall()}
        by_month = {}
        for r in rows:
            by_month.setdefault((r["tanggal"].year, r["tanggal"].month), []).append(r["kurs"])
            if commit:
                cur.execute(
                    """INSERT INTO jisdor_daily
                         (tanggal, mata_uang, kurs, sumber, id_download_log, downloaded_at)
                       VALUES (%s,%s,%s,%s,%s,NOW())
                       ON DUPLICATE KEY UPDATE kurs=VALUES(kurs), sumber=VALUES(sumber),
                           id_download_log=VALUES(id_download_log), downloaded_at=NOW()""",
                    (r["tanggal"].isoformat(), mts, r["kurs"], source, dl_id))
        months = 0
        for (yi, mi), vals in sorted(by_month.items()):
            avg = (sum(vals) / Decimal(len(vals))).quantize(Decimal("0.0001"), ROUND_HALF_UP)
            pid = period.get((yi, mi))
            if pid is None:
                continue
            months += 1
            if commit:
                cur.execute(
                    """INSERT INTO ms_kurs (id_ms_period, rata_rata_kurs, sumber, keterangan)
                       VALUES (%s,%s,'JISDOR Bank Indonesia',
                               'Rata-rata bulanan JISDOR harian (ws BI otomatis)')
                       ON DUPLICATE KEY UPDATE rata_rata_kurs=VALUES(rata_rata_kurs),
                           sumber=VALUES(sumber), keterangan=VALUES(keterangan)""",
                    (pid, avg))
        if commit:
            self._connect().commit()
        return months

    # --- lineage helpers -------------------------------------------------
    def _begin_job(self, cur, job_id, mts, start, end, source, fixture, process):
        params = {"mts": mts, "start": start, "end": end, "source": source,
                  "fixture": os.path.basename(fixture) if fixture else None,
                  "process": process}
        if job_id is None:
            cur.execute(
                "INSERT INTO automation_jobs (job_type, status, params_json, "
                "correlation_id, started_at, attempts) "
                "VALUES ('jisdor_download','RUNNING',%s,%s,NOW(),1)",
                (json.dumps(params, ensure_ascii=False), uuid.uuid4().hex))
            job_id = cur.lastrowid
            cur.execute(
                "INSERT INTO automation_job_logs (id_job, level, message) "
                "VALUES (%s,'info',%s)",
                (job_id, "mulai unduhan JISDOR %s..%s (%s)" % (start, end, mts)))
        else:
            cur.execute(
                "UPDATE automation_jobs SET status='RUNNING', started_at=NOW(), "
                "attempts=COALESCE(attempts,0)+1 WHERE id=%s", (job_id,))
            cur.execute(
                "INSERT INTO automation_job_logs (id_job, level, message) "
                "VALUES (%s,'info','resume unduhan JISDOR dari antrian')", (job_id,))
        self._connect().commit()
        return job_id

    def _insert_download_log(self, cur, job_id, source, start, end, mts="USD"):
        cur.execute(
            "INSERT INTO automation_download_logs (id_job, sumber, url, status) "
            "VALUES (%s,%s,%s,'PENDING')",
            (job_id, "%s %s..%s" % (source, start, end),
             self.build_url(self.api_base(), mts, start, end)))
        dl_id = cur.lastrowid
        self._connect().commit()
        return dl_id

    def _mark_downloaded(self, cur, dl_id, out, size, fhash):
        cur.execute(
            "UPDATE automation_download_logs SET status='DOWNLOADED', file_path=%s, "
            "file_name=%s, file_size=%s, file_hash=%s, downloaded_at=NOW() WHERE id=%s",
            (out, os.path.basename(out), size, fhash, dl_id))
        self._connect().commit()

    def _finish_job(self, cur, job_id, ok, error):
        if ok:
            cur.execute("UPDATE automation_jobs SET status='SUCCESS', finished_at=NOW() "
                        "WHERE id=%s", (job_id,))
            cur.execute(
                "INSERT INTO automation_job_logs (id_job, level, message) "
                "VALUES (%s,'info','unduhan JISDOR selesai')", (job_id,))
        else:
            cur.execute("UPDATE automation_jobs SET status='FAILED', finished_at=NOW(), "
                        "error_message=%s WHERE id=%s", (error, job_id))
            cur.execute(
                "INSERT INTO automation_job_logs (id_job, level, message) "
                "VALUES (%s,'error',%s)", (job_id, error))
        self._connect().commit()

    def _mark_failed(self, cur, job_id, dl_id, error):
        cur.execute(
            "UPDATE automation_download_logs SET status='FAILED', error_message=%s "
            "WHERE id=%s", (error[:1000], dl_id))
        self._finish_job(cur, job_id, False, error)
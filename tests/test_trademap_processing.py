#!/usr/bin/env python3
"""PHASE 9 — Test pipeline pemrosesan & harmonisasi TradeMap.

Cakupan (mengikuti PHASE 9 §16):
1. valid file        2. malformed file     3. missing column
4. invalid HS        5. unknown country    6. unknown commodity
7. invalid trade flow 8. invalid numeric   9. duplicate record
10. idempotency      11. HS version mismatch  12. empty file
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_connection
from backend.trademap.models import HSResult
from backend.trademap.normalizer import TradeMapNormalizer
from backend.trademap.mapper import TradeMapMapper
from backend.trademap.parser import TradeMapParser
from backend.trademap.processor import TradeMapProcessor

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "trademap")
SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "trademap_sample.csv")

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def lerp(fn):
    return os.path.join(FIX, fn)


def get_raw_id(conn, file_hash):
    cur = conn.cursor()
    cur.execute("SELECT id FROM trademap_raw WHERE file_hash=%s", (file_hash,))
    r = cur.fetchone()
    return r["id"] if r else None


def cleanup_file(conn, file_hash):
    cur = conn.cursor()
    cur.execute("SELECT id FROM trademap_raw WHERE file_hash=%s", (file_hash,))
    r = cur.fetchone()
    if not r:
        return
    rid = r["id"]
    cur.execute("DELETE FROM trademap_trade WHERE id_trademap_raw=%s", (rid,))
    cur.execute("DELETE FROM trademap_validation_results WHERE id_trademap_raw=%s", (rid,))
    cur.execute("DELETE FROM trademap_raw WHERE id=%s", (rid,))
    conn.commit()


def main():
    conn = get_connection()

    print("== 1. Parser (valid + struktur file) ==")
    p = TradeMapParser()
    r = p.parse(SAMPLE)
    check("valid: ok", r.ok, ";".join(r.errors))
    check("valid: 8 record", len(r.records) == 8, str(len(r.records)))
    check("valid: file_hash 64hex", len(r.file_hash) == 64, r.file_hash)
    check("valid: format csv", r.file_format == "csv")
    check("valid: value_header terdeteksi", "Thousand" in r.value_header, r.value_header)
    check("valid: header lengkap", "product code" in " ".join([h.lower() for h in r.headers]), str(r.headers))
    check("valid: row pertama", r.records[0].partner == "US" and r.records[0].product_code == "030617")

    print("== 2. Parser (error handling) ==")
    check("malformed: tidak ok", not p.parse(lerp("malformed.csv")).ok)
    check("missing column: HEADER_NOT_FOUND", "HEADER_NOT_FOUND" in p.parse(lerp("missing_column.csv")).errors)
    check("empty file: FILE_EMPTY", "FILE_EMPTY" in p.parse(lerp("empty.csv")).errors)
    check("headers only: NO_DATA_ROWS", "NO_DATA_ROWS" in p.parse(lerp("headers_only.csv")).errors)
    check("file tidak ada: FILE_NOT_FOUND", "FILE_NOT_FOUND" in p.parse("/tmp/tidak_ada.csv").errors)
    import tempfile
    tmp = tempfile.mktemp(suffix=".xls")
    with open(tmp, "wb") as f:
        f.write(b"x")
    check("format .xls: FORMAT_UNSUPPORTED", any(e.startswith("FORMAT_UNSUPPORTED") for e in p.parse(tmp).errors))
    os.remove(tmp)
    # metadata "Reporter:"/"Year:" di atas header
    meta_fixture = os.path.join(FIX, "..", "trademap_meta.csv")
    with open(meta_fixture, "w") as f:
        f.write("Reporter: Indonesia\nYear: 2024\n")
        f.write("Reporter,Partner,Flow,Product code,Product Label,Year,Quantity,Trade Value (US$ Thousand)\n")
        f.write("ID,US,Export,030617,Shrimps,2024,10,5\n")
    rm = p.parse(meta_fixture)
    check("metadata diekstrak", rm.ok and rm.metadata.get("reporter") == "Indonesia" and rm.metadata.get("year") == "2024", str(rm.metadata))
    check("metadata: 1 record", len(rm.records) == 1, str(len(rm.records)))
    os.remove(meta_fixture)

    print("== 3. Normalizer ==")
    n = TradeMapNormalizer()
    rec = next(rr for rr in p.parse(SAMPLE).records if rr.partner == "US" and rr.product_code == "030617" and rr.year == "2024")
    d = n.normalize(rec)
    check("flow Export -> EXPORT", d["flow_norm"] == "EXPORT", d["flow_norm"])
    check("value diskalakan thousand", d["value_usd_norm"] == 980000 * 1000, str(d["value_usd_norm"]))
    check("unit value terdeteksi", d["value_unit_source"] == "US$ THOUSAND", str(d["value_unit_source"]))
    check("qty decimal", d["qty"] == 135000, str(d["qty"]))
    check("qty unit kosong -> WARNING", any(i.kode == "QTY_UNIT_UNKNOWN" for i in d["issues"]))
    check("year 2024", d["year"] == 2024)

    n2 = TradeMapNormalizer().normalize(p.parse(lerp("invalid_numeric.csv")).records[0])
    check("numeric invalid", any(i.kode == "VALUE_NOT_NUMERIC" and i.severity == "INVALID" for i in n2["issues"]))
    n3 = TradeMapNormalizer().normalize(p.parse(lerp("invalid_flow.csv")).records[0])
    check("flow invalid", any(i.kode == "FLOW_INVALID" and i.severity == "INVALID" for i in n3["issues"]))
    # re-export perlu validasi
    rx = TradeMapNormalizer().normalize(_make_flow_record("Re-Export"))
    check("re-export dinormalisasi+WARNING", rx["flow_norm"] == "EXPORT" and any(i.kode == "FLOW_NEEDS_VALIDATION" for i in rx["issues"]))

    print("== 4. Mapper (master mapping) ==")
    m = TradeMapMapper(conn)
    id_us, _ = m.map_country("us")
    check("country ID mapped", m.map_country("ID")[0] is not None, str(m.map_country("ID")))
    check("country lowercase", id_us is not None, str(id_us))
    check("country nama (INDONESIA)", m.map_country("INDONESIA")[0] == m.map_country("ID")[0])
    check("country unknown ZZ", m.map_country("ZZ")[0] is None)
    hs = m.map_hs("030461")
    check("hs 030461 MAPPED", hs.status == "MAPPED" and hs.candidate_count == 1, str(hs))
    hs2 = m.map_hs("030617")
    check("hs 030617 AMBIGUOUS (7)", hs2.status == "AMBIGUOUS" and hs2.candidate_count == 7, str(hs2))
    check("hs 030617 komoditas resolusi", hs2.id_ms_komoditas is not None, str(hs2))
    hs3 = m.map_hs("999999")
    check("hs 999999 HS_MAPPING_REQUIRED", hs3.status == "HS_MAPPING_REQUIRED" and hs3.candidate_count == 0, str(hs3))
    hs4 = m.map_hs("020850")
    check("hs 020850 MAPPED, komoditas kosong", hs4.status == "MAPPED" and hs4.id_ms_komoditas is None, str(hs4))
    hs5 = m.map_hs("030461", "HS2017")
    check("version mismatch -> NEEDS_VALIDATION", hs5.status == "NEEDS_VALIDATION", str(hs5))

    print("== 5. Processor dry-run (tipe-tipe record) ==")
    proc = TradeMapProcessor(conn)
    res = proc.process(SAMPLE)
    check("fixture: ok", res.ok)
    check("fixture: total 8", res.stats.total_rows == 8, str(res.stats.as_dict()))
    check("fixture: warning 8", res.stats.warning_rows == 8, str(res.stats.as_dict()))
    check("fixture: duplicate 0", res.stats.duplicate_rows == 0)
    check("fixture: hs ambiguous ada", any(i.kode == "HS_AMBIGUOUS" for i in res.issues))

    r = proc.process(lerp("invalid_hs.csv"))
    check("invalid HS: WARNING + HS_MAPPING_REQUIRED",
          r.records[0].validation_status == "WARNING" and r.records[0].hs_mapping_status == "HS_MAPPING_REQUIRED",
          str((r.records[0].validation_status, r.records[0].hs_mapping_status)))

    r = proc.process(lerp("unknown_country.csv"))
    check("unknown country: WARNING + COUNTRY_UNMAPPED",
          any(i.kode == "COUNTRY_UNMAPPED" for i in r.records[0].issues), str(r.records[0].issues))

    r = proc.process(lerp("unknown_commodity.csv"))
    check("unknown commodity: WARNING + COMMODITY_UNMAPPED",
          any(i.kode == "COMMODITY_UNMAPPED" for i in r.records[0].issues), str(r.records[0].issues))

    r = proc.process(lerp("invalid_flow.csv"))
    check("invalid flow: INVALID", r.records[0].validation_status == "INVALID", r.records[0].validation_status)

    r = proc.process(lerp("invalid_numeric.csv"))
    check("invalid numeric: INVALID", r.records[0].validation_status == "INVALID")

    r = proc.process(lerp("duplicate.csv"))
    check("duplicate: 1 duplikat terdeteksi", r.stats.duplicate_rows == 1, str(r.stats.as_dict()))
    check("duplicate: baris duplikat ditandai", all(x.duplicate for x in r.records if x is not r.records[0]),
          str([(x.raw.row_ref, x.duplicate) for x in r.records]))

    r = proc.process(lerp("hs_version.csv"))
    check("HS version mismatch: NEEDS_VALIDATION + warning",
          r.records[0].hs_mapping_status == "NEEDS_VALIDATION" and r.records[0].validation_status == "WARNING",
          r.records[0].hs_mapping_status)

    print("== 6. Processor commit + idempotency ==")
    res1 = proc.process(SAMPLE, commit=True)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) n FROM trademap_trade")
    n_before = cur.fetchone()["n"]
    res2 = proc.process(SAMPLE, commit=True)  # idempotent
    cur.execute("SELECT COUNT(*) n FROM trademap_trade")
    n_after = cur.fetchone()["n"]
    check("commit: total rows 8", res1.stats.total_rows == 8)
    check("idempotent: trade count tidak bertambah", n_after == n_before, f"{n_before} -> {n_after}")
    check("idempotent: run ke-2 tidak insert/update", res2.stats.inserted_rows == 0 and res2.stats.updated_rows == 0, str(res2.stats.as_dict()))
    raw_id = get_raw_id(conn, res1.file_hash)
    cur.execute("SELECT status, invalid_rows, warning_rows, duplicate_rows FROM trademap_raw WHERE id=%s", (raw_id,))
    raw = cur.fetchone()
    check("raw status processed", raw and raw["status"] == "processed", str(raw))
    cur.execute("SELECT COUNT(*) n FROM trademap_validation_results WHERE id_trademap_raw=%s", (raw_id,))
    n_val = cur.fetchone()["n"]
    check("validation results tersimpan", n_val >= 8, str(n_val))
    cur.execute("SELECT COUNT(*) n FROM trademap_hs_mapping WHERE mapping_status IN ('MAPPED','AMBIGUOUS')")
    check("hs_mapping cache terisi", cur.fetchone()["n"] >= 3)
    cur.execute("SELECT status FROM automation_jobs WHERE job_type='trademap_process' ORDER BY id DESC LIMIT 1")
    check("job tercatat SUCCESS", cur.fetchone()["status"] == "SUCCESS")

    print("== 7. Record INVALID tidak masuk processed ==")
    res3 = proc.process(lerp("invalid_flow.csv"), commit=True)
    cur.execute("SELECT COUNT(*) n FROM trademap_trade WHERE id_trademap_raw=%s", (get_raw_id(conn, res3.file_hash),))
    check("INVALID tidak ada di trademap_trade", cur.fetchone()["n"] == 0)
    cur.execute("SELECT severity FROM trademap_validation_results WHERE id_trademap_raw=%s", (get_raw_id(conn, res3.file_hash),))
    sev = [x["severity"] for x in cur.fetchall()]
    check("INVALID tercatat di validation", "INVALID" in sev and all(s in ("INVALID", "WARNING") for s in sev), str(sev))
    cleanup_file(conn, res3.file_hash)

    print("== 8. Duplicate commit ==")
    res4 = proc.process(lerp("duplicate.csv"), commit=True)
    rid = get_raw_id(conn, res4.file_hash)
    cur.execute("SELECT COUNT(*) n FROM trademap_trade WHERE id_trademap_raw=%s", (rid,))
    check("duplicate: hanya 1 baris masuk", cur.fetchone()["n"] == 1)
    cur.execute("SELECT duplicate_rows FROM trademap_raw WHERE id=%s", (rid,))
    check("duplicate tercatat di raw", cur.fetchone()["duplicate_rows"] == 1)
    cleanup_file(conn, res4.file_hash)

    conn.close()
    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


def _make_flow_record(flow):
    from backend.trademap.models import RawRecord
    return RawRecord(row_ref="#t", reporter="ID", partner="US", flow=flow,
                     product_code="030617", year="2024", qty="1", value="1")


if __name__ == "__main__":
    sys.exit(main())
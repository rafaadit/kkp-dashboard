#!/usr/bin/env python3
"""
PHASE 2 — BPS ETL verification tests.
Jalankan: python3 tests/test_etl.py

Menggunakan koneksi dari .env bila ada, jika tidak fallback ke DB lokal (DBngin).
Angka baseline PPT diverifikasi hanya untuk periode Jan–Jun 2026; periode
setelahnya boleh bertambah saat BPS periode baru diunggah.
"""
import os
import sys

import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from backend.db import load_dotenv
    load_dotenv()
except ImportError:
    pass

if os.environ.get("DB_HOST"):
    DB = dict(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "kkp_exim_platform"),
        charset="utf8mb4",
        autocommit=True,
    )
else:
    DB = dict(host="127.0.0.1", user="root", password="", database="kkp_exim_platform",
              unix_socket="/tmp/mysql_3306.sock", charset="utf8mb4", autocommit=True)

errors = []


def check(name, cond, detail=""):
    if cond:
        print(f"  OK: {name}" + (f" ({detail})" if detail else ""))
    else:
        errors.append(name)
        print(f"  FAIL: {name}" + (f" ({detail})" if detail else ""))


def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    print("=== 1. Upload records ===")
    cur.execute("SELECT id, exim_type, row_count, status FROM bps_upload ORDER BY id")
    ups = cur.fetchall()
    processed = {}
    for _, exim, row_count, status in ups:
        if status == "processed" and row_count and row_count > 0:
            processed[exim] = processed.get(exim, 0) + 1
    check("upload ekspor & impor pernah diproses",
          processed.get("ekspor", 0) > 0 and processed.get("impor", 0) > 0,
          f"ekspor={processed.get('ekspor', 0)} impor={processed.get('impor', 0)}")
    check("semua upload berstatus processed punya baris",
          all(not (u[3] == "processed" and not u[2]) for u in ups),
          f"{len(ups)} upload")

    print("\n=== 2. Staging raw ===")
    cur.execute("SELECT COUNT(*), SUM(is_valid), SUM(NOT is_valid) FROM bps_export_raw")
    n, v, inv = cur.fetchone()
    check("export_raw punya data", n and n > 0, f"{n}")
    check("export_raw all valid", inv == 0, f"invalid={inv}")
    cur.execute("SELECT COUNT(*), SUM(is_valid), SUM(NOT is_valid) FROM bps_import_raw")
    ni, vi, invi = cur.fetchone()
    check("import_raw punya data", ni and ni > 0, f"{ni}")
    check("import_raw all valid", invi == 0, f"invalid={invi}")

    print("\n=== 3. Fact tables ===")
    cur.execute("SELECT COUNT(*) FROM bps_export")
    n_fact = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bps_import")
    ni_fact = cur.fetchone()[0]
    check("bps_export = jumlah baris raw valid", n_fact == v, f"{n_fact} vs {v}")
    check("bps_import = jumlah baris raw valid", ni_fact == vi, f"{ni_fact} vs {vi}")

    print("\n=== 4. Rekonsiliasi angka vs PPT (kelompok I, Jan–Jun 2026) ===")
    for fact, expected, label in [("bps_export", 2995.2, "ekspor"),
                                  ("bps_import", 379.6, "impor")]:
        cur.execute(f"""
            SELECT ROUND(SUM(f.nilai_usd)/1000000, 1)
            FROM {fact} f
            JOIN ms_period p ON p.id = f.id_ms_period
            JOIN ms_hscode h ON h.id = f.id_ms_hscode
            WHERE p.tahun = 2026 AND p.bulan BETWEEN 1 AND 6
              AND h.kode_kelompok = 'I'
        """)
        val = float(cur.fetchone()[0] or 0)
        check(f"{label} kelp I 2026 = {expected} juta USD (PPT)",
              abs(val - expected) < 0.1, f"{val}")

    print("\n=== 5. FK integritas fact -> master ===")
    for fact, cols in [("bps_export", ["id_ms_period", "id_ms_hscode", "kode_provinsi_asal",
                                        "kode_provinsi_muat", "kode_pelabuhan_muat", "kode_negara"]),
                       ("bps_import", ["id_ms_period", "id_ms_hscode", "kode_provinsi_bongkar",
                                        "kode_pelabuhan_bongkar", "kode_negara_asal"])]:
        for col in cols:
            cur.execute(f"SELECT COUNT(*) FROM {fact} WHERE {col} IS NULL")
            chk = cur.fetchone()[0]
            check(f"{fact}.{col} no NULL", chk == 0, f"null={chk}")

    print("\n=== 6. Idempotency (hash anti-duplikat & grain) ===")
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT file_hash) FROM bps_upload")
    total, distinct = cur.fetchone()
    check("file upload tidak duplikat", total == distinct, f"{total} vs {distinct}")

    grains = {
        "bps_export": ("id_ms_period, id_ms_hscode, kode_provinsi_asal, kode_provinsi_muat, "
                       "kode_pelabuhan_muat, kode_negara, volume_kg, nilai_usd"),
        "bps_import": ("id_ms_period, id_ms_hscode, kode_provinsi_bongkar, "
                       "kode_pelabuhan_bongkar, kode_negara_asal, volume_kg, nilai_usd"),
    }
    for fact, cols in grains.items():
        cur.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM {fact} GROUP BY {cols} HAVING COUNT(*) > 1
            ) d
        """)
        dup = cur.fetchone()[0]
        check(f"{fact} tidak ada grain duplikat", dup == 0, f"dup={dup}")

    conn.close()
    print(f"\n{'=' * 50}")
    if errors:
        print(f"RESULT: {len(errors)} FAIL(S)")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    print("RESULT: ALL TESTS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
PHASE 2 — BPS ETL verification tests.
Jalankan: python3 tests/test_etl.py
Requires: pymysql, py dash, database kkp_exim_platform ETL selesai dijalankan (etl_bps.py).
"""
import sys
import pymysql

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
    cur.execute("SELECT id, exim_type, row_count, status, periode_mulai, periode_akhir FROM bps_upload ORDER BY id")
    ups = cur.fetchall()
    check("2 upload (ekspor+impor)", len(ups) == 2, f"{len(ups)}")
    for u in ups:
        check(f"upload {u[1]} processed", u[3] == "processed", f"status={u[3]} row_count={u[2]}")

    print("\n=== 2. Staging raw ===")
    cur.execute("SELECT COUNT(*), SUM(is_valid), SUM(NOT is_valid) FROM bps_export_raw")
    n, v, inv = cur.fetchone()
    check("export_raw = 189.001", n == 189001, f"{n}")
    check("export_raw all valid", inv == 0, f"invalid={inv}")
    cur.execute("SELECT COUNT(*), SUM(is_valid), SUM(NOT is_valid) FROM bps_import_raw")
    n, v, inv = cur.fetchone()
    check("import_raw = 53.668", n == 53668, f"{n}")
    check("import_raw all valid", inv == 0, f"invalid={inv}")

    print("\n=== 3. Fact tables ===")
    cur.execute("SELECT COUNT(*) FROM bps_export")
    check("bps_export = 189.001", cur.fetchone()[0] == 189001)
    cur.execute("SELECT COUNT(*) FROM bps_import")
    check("bps_import = 53.668", cur.fetchone()[0] == 53668)

    print("\n=== 4. Rekonsiliasi angka vs PPT (kelompok I, 2026) ===")
    cur.execute("""
        SELECT ROUND(SUM(f.nilai_usd)/1000000,1)
        FROM bps_export f
        JOIN ms_period p ON p.id=f.id_ms_period
        JOIN ms_hscode h ON h.id=f.id_ms_hscode
        WHERE p.tahun=2026 AND h.kode_kelompok='I'
    """)
    eks = float(cur.fetchone()[0])
    check("ekspor kelp I 2026 = 2.995,2 juta USD (PPT)", abs(eks - 2995.2) < 0.1, f"{eks}")
    cur.execute("""
        SELECT ROUND(SUM(f.nilai_usd)/1000000,1)
        FROM bps_import f
        JOIN ms_period p ON p.id=f.id_ms_period
        JOIN ms_hscode h ON h.id=f.id_ms_hscode
        WHERE p.tahun=2026 AND h.kode_kelompok='I'
    """)
    imp = float(cur.fetchone()[0])
    check("impor kelp I 2026 = 379,65 juta USD (PPT)", abs(imp - 379.65) < 0.1, f"{imp}")

    print("\n=== 5. FK integritas fact -> master ===")
    for fact, cols in [("bps_export", ["id_ms_period","id_ms_hscode","kode_provinsi_asal",
                                        "kode_provinsi_muat","kode_pelabuhan_muat","kode_negara"]),
                       ("bps_import", ["id_ms_period","id_ms_hscode","kode_provinsi_bongkar",
                                       "kode_pelabuhan_bongkar","kode_negara_asal"])]:
        for col in cols:
            cur.execute(f"SELECT COUNT(*) FROM {fact} WHERE {col} IS NULL")
            chk = cur.fetchone()[0]
            check(f"{fact}.{col} no NULL", chk == 0, f"null={chk}")

    print("\n=== 6. Idempotency (hash anti-duplikat) ===")
    cur.execute("SELECT COUNT(*) FROM bps_upload WHERE status='processed'")
    check("2 files processed, no dup", cur.fetchone()[0] == 2)

    conn.close()
    print(f"\n{'='*50}")
    if errors:
        print(f"RESULT: {len(errors)} FAIL(S)")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    print("RESULT: ALL TESTS PASSED")
    sys.exit(0)

if __name__ == "__main__":
    main()
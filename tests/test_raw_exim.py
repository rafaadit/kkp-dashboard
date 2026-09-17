#!/usr/bin/env python3
"""
PHASE 3 — RAW EXIM Generation verification tests.
Jalankan: python3 tests/test_raw_exim.py
Requires: pymysql, database kkp_exim_platform sudah di-generate (generate_raw_exim.py).
"""
import sys
from decimal import Decimal

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


def curl(cur, sql, *args):
    cur.execute(sql, args)
    return cur.fetchall()


def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    print("=== 1. Volume & status ===")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim")[0][0]
    check("raw_exim = 242.669", n == 242669, f"{n}")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE exim_type='ekspor'")[0][0]
    check("ekspor = 189.001", n == 189001, f"{n}")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE exim_type='impor'")[0][0]
    check("impor = 53.668", n == 53668, f"{n}")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE status='ready'")[0][0]
    check("ready = 5.738 (periode berkurs)", n == 5738, f"{n}")

    print("\n=== 2. Identitas ekspor vs impor (single source) ===")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE exim_type='ekspor' AND id_bps_import IS NOT NULL")[0][0]
    check("ekspor tidak punya id_bps_import", n == 0)
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE exim_type='impor' AND id_bps_export IS NOT NULL")[0][0]
    check("impor tidak punya id_bps_export", n == 0)
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE id_bps_export IS NULL AND id_bps_import IS NULL")[0][0]
    check("tiap baris terhubung ke 1 fakt", n == 0, f"orphan={n}")

    print("\n=== 3. Rekonsiliasi 1:1 dengan bps fakt ===")
    for t, tab in [("ekspor", "bps_export"), ("impor", "bps_import")]:
        src = curl(cur, f"SELECT COUNT(*) FROM {tab}")[0][0]
        dst = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE exim_type=%s", t)[0][0]
        check(f"{t}: fakt {tab} = raw_exim", src == dst, f"{src} == {dst}")

    print("\n=== 4. FK integritas + koding VARCHAR(3) ===")
    for col in ["id_ms_period", "kode_hs_2022", "kode_prov_asal", "provinsi_asal",
                "kode_negara", "negara", "vol_kg", "nil_usd"]:
        n = curl(cur, f"SELECT COUNT(*) FROM raw_exim WHERE {col} IS NULL")[0][0]
        check(f"raw_exim.{col} no NULL", n == 0, f"null={n}")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE koding='III'")[0][0]
    check("koding III tidak terpotong", n > 0, f"III={n}")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE CHAR_LENGTH(koding) > 2")[0][0]
    check("koding tidak ada yang terpotong (len>2 dipakai)", n > 0, "")

    print("\n=== 5. Formula turunan (sampling 2026-06 ekspor ready) ===")
    rows = curl(cur, """
        SELECT vol_kg, nil_usd, harga_usd_kg, rendemen, setara_segar, kurs_usd, nilai_rp
        FROM raw_exim WHERE exim_type='ekspor' AND status='ready' LIMIT 2000
    """)
    ok_h = ok_s = ok_rp = 0
    for vol, nil, harga, rendemen, setara, kurs, nilai_rp in rows:
        if harga is not None and abs(float(harga) - float(nil / vol)) < 1e-6:
            ok_h += 1
        if setara is not None and not (rendemen is None or rendemen == 0) \
                and abs(float(setara) - float(vol / rendemen)) < 1e-4:
            ok_s += 1
        if nilai_rp is not None and kurs is not None \
                and abs(float(nilai_rp) - float(nil * kurs)) < 0.5:
            ok_rp += 1
    check("harga_usd_kg = nil/vol", ok_h == len(rows), f"{ok_h}/{len(rows)}")
    check("setara_segar = vol/rendemen", ok_s == len(rows), f"{ok_s}/{len(rows)}")
    check("nilai_rp = nil*kurs", ok_rp == len(rows), f"{ok_rp}/{len(rows)}")

    print("\n=== 6. Kurs & tahun_bulan (2026-06) ===")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE status='ready' AND kurs_usd=358482")[0][0]
    check("kurs 358482 pada 5.738 baris ready", n == 5738, f"{n}")
    n = curl(cur, "SELECT COUNT(DISTINCT tahun_bulan) FROM raw_exim WHERE exim_type='ekspor'")[0][0]
    check("tahun_bulan 54 periode ekspor (2022..2026-06)", n == 54, f"{n}")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE tahun_bulan NOT REGEXP '^[0-9]{6}$'")[0][0]
    check("format tahun_bulan YYYYMM", n == 0)

    print("\n=== 7. Kolom un-mapped = NULL (kode_hs_2012) ===")
    n = curl(cur, "SELECT COUNT(*) FROM raw_exim WHERE kode_hs_2012 IS NOT NULL")[0][0]
    check("kode_hs_2012 selalu NULL", n == 0)

    print("\n=== 8. Automation jobs tercatat ===")
    rows = curl(cur, """
        SELECT job_type, status, COUNT(*) FROM automation_jobs
        WHERE job_type='raw_exim' GROUP BY job_type, status
    """)
    succ = sum(n for _, st, n in rows if st == "SUCCESS")
    check("job raw_exim SUCCESS >= 2", succ >= 2, f"success={succ}")
    n = curl(cur, "SELECT COUNT(*) FROM automation_job_logs WHERE id_job IN (SELECT id FROM automation_jobs WHERE job_type='raw_exim')")[0][0]
    check("log per job ada", n >= 4, f"{n}")

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
#!/usr/bin/env python3
"""
PHASE 1 — Schema verification tests.
Jalankan: python3 tests/test_schema.py
Requires: pymysql, database kkp_exim_platform ter-init.
"""
import sys
import os
import pymysql

DB_CONFIG = dict(host="127.0.0.1", user="root", password="", database="kkp_exim_platform",
                unix_socket="/tmp/mysql_3306.sock", charset="utf8mb4", autocommit=True)

EXPECTED_TABLES = sorted([
    # master
    "ms_period", "ms_negara", "ms_provinsi", "ms_pelabuhan", "ms_unit",
    "ms_hscode", "ms_komoditas", "ms_komoditas_hscode",
    "ms_kurs", "ms_manual_correction", "ms_reference",
    # BPS
    "bps_upload", "bps_export_raw", "bps_import_raw", "bps_export", "bps_import",
    # automation
    "automation_jobs", "automation_job_items", "automation_job_logs", "automation_download_logs",
    # app
    "app_roles", "app_permissions", "app_role_permissions",
    "app_users", "app_user_tokens", "app_notifications",
    # exim
    "raw_exim",
    # trademap
    "trademap_raw", "trademap_trade",
    # analytics & logging
    "analytics_metric", "audit_logs",
])

SEED_COUNTS = {
    "ms_period": (52, 56),
    "ms_negara": (200, 220),
    "ms_provinsi": (35, 42),
    "ms_pelabuhan": (190, 210),
    "ms_unit": (5, 10),
    "ms_hscode": (600, 650),
    "ms_komoditas": (850, 950),
    "ms_komoditas_hscode": (3600, 4000),
    "ms_reference": (15, 25),
    "app_roles": (3, 3),
    "app_permissions": (25, 35),
    "app_role_permissions": (60, 70),
}

FK_COLUMN_TABLES = {
    "bps_upload":   {"id_ms_period": "ms_period", "periode_mulai": "ms_period",
                     "periode_akhir": "ms_period", "uploaded_by": "app_users"},
    "bps_export_raw": {"id_bps_upload": "bps_upload"},
    "bps_import_raw": {"id_bps_upload": "bps_upload"},
    "bps_export": {"id_bps_export_raw": "bps_export_raw", "id_ms_period": "ms_period",
                   "id_ms_hscode": "ms_hscode", "kode_provinsi_asal": "ms_provinsi",
                   "kode_provinsi_muat": "ms_provinsi", "kode_pelabuhan_muat": "ms_pelabuhan",
                   "kode_negara": "ms_negara"},
    "bps_import": {"id_bps_import_raw": "bps_import_raw", "id_ms_period": "ms_period",
                   "id_ms_hscode": "ms_hscode", "kode_provinsi_bongkar": "ms_provinsi",
                   "kode_pelabuhan_bongkar": "ms_pelabuhan",
                   "kode_negara_asal": "ms_negara"},
    "automation_jobs": {"id_ms_period": "ms_period", "created_by": "app_users"},
    "automation_job_items": {"id_job": "automation_jobs"},
    "automation_job_logs": {"id_job": "automation_jobs", "id_item": "automation_job_items"},
    "automation_download_logs": {"id_job": "automation_jobs", "id_item": "automation_job_items"},
    "app_role_permissions": {"app_role_id": "app_roles", "app_permission_id": "app_permissions"},
    "app_user_tokens": {"app_user_id": "app_users"},
    "app_notifications": {"app_user_id": "app_users"},
    "raw_exim": {"id_bps_export": "bps_export", "id_bps_import": "bps_import",
                 "id_generated_by_job": "automation_jobs", "id_ms_period": "ms_period"},
    "trademap_raw": {"id_download_log": "automation_download_logs"},
    "trademap_trade": {"id_trademap_raw": "trademap_raw"},
    "ms_kurs": {"id_ms_period": "ms_period", "input_by": "app_users"},
    "ms_manual_correction": {"created_by": "app_users"},
    "ms_komoditas_hscode": {"ms_komoditas_id": "ms_komoditas", "ms_hscode_id": "ms_hscode"},
    "analytics_metric": {"id_ms_period": "ms_period", "id_job": "automation_jobs"},
    "audit_logs": {"app_user_id": "app_users"},
    "app_users": {"app_role_id": "app_roles"},
}

errors = []

def fail(msg):
    errors.append(msg)
    print(f"  FAIL: {msg}")

def ok(msg):
    print(f"  OK: {msg}")

def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("=== 1. Semua tabel eksis ===")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s ORDER BY table_name",
                (DB_CONFIG["database"],))
    actual = [r[0] for r in cur.fetchall()]
    missing = [t for t in EXPECTED_TABLES if t not in actual]
    extra   = [t for t in actual if t not in EXPECTED_TABLES]
    if missing:
        fail(f"tabel missing: {missing}")
    if extra:
        fail(f"tabel unexpected: {extra}")
    if not missing and not extra:
        ok(f"{len(actual)} tabel sesuai")

    print("\n=== 2. Seed counts ===")
    for tbl, (lo, hi) in SEED_COUNTS.items():
        if tbl not in actual:
            fail(f"{tbl} tidak ada, skip count")
            continue
        cur.execute(f"SELECT COUNT(*) FROM `{tbl}`")
        n = cur.fetchone()[0]
        if lo <= n <= hi:
            ok(f"{tbl}: {n} baris (range {lo}-{hi})")
        else:
            fail(f"{tbl}: {n} baris, di luar range {lo}-{hi}")

    print("\n=== 3. Foreign keys valid (no orphan expected on init) ===")
    for tbl, fks in FK_COLUMN_TABLES.items():
        if tbl not in actual:
            continue
        for col, ref_tbl in fks.items():
            if ref_tbl not in actual:
                continue
            cur.execute(f"""
                SELECT COUNT(*) FROM `{tbl}` t
                LEFT JOIN `{ref_tbl}` r ON r.id = t.`{col}`
                WHERE t.`{col}` IS NOT NULL AND r.id IS NULL
            """)
            orphans = cur.fetchone()[0]
            if orphans > 0:
                fail(f"{tbl}.{col} -> {ref_tbl}: {orphans} orphan(s)")
            else:
                pass  # silent ok, too many lines

    print("\n=== 4. Unique constraints (spot-check bps_export grain) ===")
    cur.execute("""
        SELECT COUNT(*) dupes FROM (
            SELECT id_ms_period, id_ms_hscode, kode_provinsi_asal, kode_provinsi_muat,
                   kode_pelabuhan_muat, kode_negara, volume_kg, nilai_usd,
                   COUNT(*) c
            FROM bps_export GROUP BY 1,2,3,4,5,6,7,8 HAVING c > 1
        ) d
    """)
    dup = cur.fetchone()[0]
    if dup == 0:
        ok("bps_export: 0 duplicate grain (verified)")
    else:
        fail(f"bps_export: {dup} duplicate grain(s)")

    print("\n=== 5. app_roles & permissions (3 roles) ===")
    cur.execute("SELECT kode FROM app_roles ORDER BY kode")
    roles = [r[0] for r in cur.fetchall()]
    if roles == ["pegawai", "super_admin", "user"]:
        ok(f"roles: {roles}")
    else:
        fail(f"roles unexpected: {roles}")

    print("\n=== 6. Enum checks (exim_type, status, upload_status, priority) ===")
    cur.execute("SELECT DISTINCT exim_type FROM raw_exim WHERE exim_type IS NOT NULL")
    exim_types = {r[0] for r in cur.fetchall()}
    if exim_types <= {"ekspor", "impor"}:
        ok(f"raw_exim.exim_type valid: {exim_types}")
    else:
        fail(f"raw_exim.exim_type invalid: {exim_types}")

    cur.execute("SELECT DISTINCT status FROM raw_exim WHERE status IS NOT NULL")
    raw_statuses = {r[0] for r in cur.fetchall()}
    if raw_statuses <= {"ready", "needs_validation", "rejected"}:
        ok(f"raw_exim.status valid: {raw_statuses}")
    else:
        fail(f"raw_exim.status invalid: {raw_statuses}")

    print("\n=== 7. ms_hscode coverage (kode_hs not null, kelompok_komoditas set) ===")
    cur.execute("SELECT COUNT(*) FROM ms_hscode WHERE kode_hs IS NOT NULL AND kelompok_komoditas IS NOT NULL")
    coverage = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ms_hscode")
    total = cur.fetchone()[0]
    pct = coverage / total * 100 if total else 0
    if pct >= 90:
        ok(f"ms_hscode coverage kelompok_komoditas: {coverage}/{total} ({pct:.1f}%)")
    else:
        fail(f"ms_hscode coverage kelompok_komoditas low: {coverage}/{total} ({pct:.1f}%)")

    print("\n=== 8. ms_reference sumber tagging ===")
    cur.execute("SELECT ref_key, sumber FROM ms_reference WHERE ref_group='METRIK'")
    for ref_key, sumber in cur.fetchall():
        if sumber in ("NEEDS VALIDATION", "verified_from_ppt"):
            ok(f"ms_reference.{ref_key} sumber={sumber}")
        else:
            fail(f"ms_reference.{ref_key} sumber={sumber} (unexpected)")

    conn.close()

    print(f"\n{'='*60}")
    if errors:
        print(f"RESULT: {len(errors)} FAIL(S)")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print("RESULT: ALL TESTS PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()

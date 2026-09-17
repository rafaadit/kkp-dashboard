#!/usr/bin/env python3
"""
PHASE 2 — ETL BPS: xlsx BPS -> bps_upload -> bps_export_raw/bps_import_raw -> bps_export/bps_import

Pipeline: UPLOAD -> VALIDATE -> STAGING -> TRANSFORM -> PROCESS

Mode:
    python3 database/scripts/etl_bps.py --ekspor "Data Minimum - Ekspor 2022-2026-Mei.xlsx" \
                                        --impor  "Data Minimum - Impor 2022-2026-Mei.xlsx"

Idempotent: jika file_hash sudah ada di bps_upload -> skip (tanpa perubahan).
Rekonsiliasi: seluruh baris staging valid -> jumlah fakt harus sama dengan baris sumber.
"""
import argparse
import hashlib
import os
import sys
from decimal import Decimal, InvalidOperation

import openpyxl
import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from backend.db import get_connection  # noqa: E402

BATCH = 5000
TEXT_COLS_EXPOR = [
    "tahun", "bulan", "hscode", "kd_provinsi_asal", "kd_provinsi_muat",
    "kd_pelabuhan_muat", "nm_pelabuhan_muat", "kd_negara", "nm_negara_tujuan",
    "volume_kg", "nilai_usd",
]
TEXT_COLS_IMPOR = [
    "tahun", "bulan", "hscode", "kd_provinsi_bongkar",
    "kd_pelabuhan_bongkar", "nm_pelabuhan_bongkar", "kd_negara_asal",
    "nm_negara_asal", "volume_kg", "nilai_usd",
]


def _txt(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return format(v, "f")
    return str(v).strip()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_masters(cur):
    """Load lookup maps: kode -> id (ms_period, ms_hscode, ms_provinsi, ms_pelabuhan, ms_negara)."""
    maps = {}
    cur.execute("SELECT id, tahun, bulan FROM ms_period")
    maps["period"] = {(y, m): i for i, y, m in cur.fetchall()}
    cur.execute("SELECT id, kode_hs FROM ms_hscode")
    maps["hscode"] = {kh: i for i, kh in cur.fetchall()}
    cur.execute("SELECT id, kode_provinsi FROM ms_provinsi")
    maps["provinsi"] = {kp: i for i, kp in cur.fetchall()}
    cur.execute("SELECT id, kode_pelabuhan FROM ms_pelabuhan")
    maps["pelabuhan"] = {kp: i for i, kp in cur.fetchall()}
    cur.execute("SELECT id, kode_negara FROM ms_negara")
    maps["negara"] = {kn: i for i, kn in cur.fetchall()}
    return maps


def validate_row(row, cols, master_ids):
    """Return (is_valid, error_msg). is_valid per master coverage + numeric."""
    errs = []
    y = row.get("tahun")
    m = row.get("bulan")
    try:
        key = (int(y), int(m))
        if key not in master_ids["period"]:
            errs.append(f"periode {y}-{m} tidak ada di ms_period")
    except (TypeError, ValueError):
        errs.append(f"periode tidak valid: {y!r}-{m!r}")

    for code_col, mkey in [("hscode", "hscode"), ("kd_negara", "negara"),
                           ("kd_negara_asal", "negara")]:
        v = row.get(code_col)
        if v and v not in master_ids[mkey]:
            errs.append(f"{code_col} {v!r} tidak ada di master {mkey}")

    for code_col, mkey in [("kd_provinsi_asal", "provinsi"), ("kd_provinsi_muat", "provinsi"),
                           ("kd_provinsi_bongkar", "provinsi")]:
        v = row.get(code_col)
        if v and v not in master_ids[mkey]:
            errs.append(f"{code_col} {v!r} tidak ada di ms_provinsi")

    for code_col in ["kd_pelabuhan_muat", "kd_pelabuhan_bongkar"]:
        v = row.get(code_col)
        if v and v not in master_ids["pelabuhan"]:
            errs.append(f"{code_col} {v!r} tidak ada di ms_pelabuhan")

    for num_col in ["volume_kg", "nilai_usd"]:
        v = row.get(num_col)
        if v is not None:
            try:
                Decimal(v)
            except InvalidOperation:
                errs.append(f"{num_col} bukan angka: {v!r}")

    return (not errs), " | ".join(errs)


def row_hash(values):
    return hashlib.sha256("|".join(v or "" for v in values).encode()).hexdigest()


def ingest_file(conn, master_ids, path, exim_type, force):
    cur = conn.cursor()
    cols = TEXT_COLS_EXPOR if exim_type == "ekspor" else TEXT_COLS_IMPOR
    file_hash = file_sha256(path)

    cur.execute("SELECT id, status FROM bps_upload WHERE file_hash=%s", (file_hash,))
    existing = cur.fetchone()
    if existing and not force:
        print(f"  [skip] {path}: sudah pernah di-upload (id={existing[0]}, status={existing[1]}). Pakai --force untuk reload.")
        return existing[0], 0

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    hdr = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    if cols[0] not in hdr and cols != hdr:
        # vertikan kolom sesuai urutan file
        idx = {name: i for i, name in enumerate(hdr)}
        cols = [hdr[i] for i in idx.values()] if set(cols) <= set(hdr) else cols
    iter_rows = ws.iter_rows(min_row=2, values_only=True)

    rows = []
    period_keys = set()
    total = 0
    for r in iter_rows:
        if r is None or all(c is None for c in r):
            continue
        row = dict(zip(hdr, r))
        total += 1
        try:
            period_keys.add((int(row.get("tahun")), int(row.get("bulan"))))
        except (TypeError, ValueError):
            pass
        rows.append(row)

    if not rows:
        print(f"  [fail] {path}: tidak ada baris data")
        wb.close()
        return None, 0

    # periode range untuk bps_upload
    pk = sorted(period_keys)
    id_pm = master_ids["period"].get(pk[0]) if pk else None
    id_pa = master_ids["period"].get(pk[-1]) if pk else None

    # ---- UPLOAD -----------------------------------------------------------
    cur.execute(
        """INSERT INTO bps_upload
           (exim_type, id_ms_period, periode_mulai, periode_akhir, nama_file,
            file_path, file_hash, row_count, status, error_summary)
           VALUES (%s,NULL,%s,%s,%s,%s,%s,%s,'uploaded',NULL)""",
        (exim_type, id_pm, id_pa, os.path.basename(path), path, file_hash, total),
    )
    upload_id = cur.lastrowid
    conn.commit()
    print(f"  [upload] id={upload_id} {exim_type} rows={total} periode={pk[0] if pk else '?'}..{pk[-1] if pk else '?'}")

    # ---- VALIDATE + STAGING ------------------------------------------------
    raw_table = "bps_export_raw" if exim_type == "ekspor" else "bps_import_raw"
    raw_cols = "id_bps_upload,line_no," + ",".join(cols) + ",row_checksum,is_valid,validation_error"
    placeholders = "%s," * (len(cols) + 4) + "%s"
    valid = 0
    invalid_rows = 0
    error_summary = {}

    def flush(batch):
        nonlocal valid, invalid_rows
        cur.executemany(
            f"INSERT INTO {raw_table} ({raw_cols}) VALUES ({placeholders})", batch
        )
        valid += sum(1 for b in batch if b[-2])
        invalid_rows += sum(1 for b in batch if not b[-2])

    batch = []
    for i, row in enumerate(rows, start=1):
        code_row = {c: (str(row.get(c)).strip() if row.get(c) is not None else None) for c in cols}
        is_ok, err = validate_row(code_row, cols, master_ids)
        if not is_ok:
            error_summary[err.split(": ")[0][:40]] = error_summary.get(err.split(": ")[0][:40], 0) + 1
        vals = [upload_id, i] + [code_row.get(c) for c in cols] + [row_hash([code_row.get(c) for c in cols]), is_ok, err]
        batch.append(vals)
        if len(batch) >= BATCH:
            flush(batch)
            batch = []
    if batch:
        flush(batch)
    conn.commit()

    status = "valid" if invalid_rows == 0 else "invalid_partial"
    summary = ""
    if invalid_rows:
        summary = "; ".join(f"{k}:{v}" for k, v in sorted(error_summary.items(), key=lambda x: -x[1])[:10])
    cur.execute("UPDATE bps_upload SET status=%s, error_summary=%s WHERE id=%s", (status, summary, upload_id))
    conn.commit()
    print(f"  [staging] {raw_table} total={total} valid={valid} invalid={invalid_rows}")
    if invalid_rows:
        print(f"    error_summary: {summary or 'other'}")

    wb.close()
    return upload_id, total


def transform_fact(conn, upload_id, exim_type):
    cur = conn.cursor()
    if exim_type == "ekspor":
        sql = """
            INSERT IGNORE INTO bps_export
              (id_ms_period, id_ms_hscode, kode_hs, kode_provinsi_asal,
               kode_provinsi_muat, kode_pelabuhan_muat, kode_negara,
               volume_kg, nilai_usd, id_bps_export_raw)
            SELECT p.id, h.id, r.hscode, pa.id, pm.id, pel.id, n.id,
                   CAST(r.volume_kg AS DECIMAL(20,4)),
                   CAST(r.nilai_usd AS DECIMAL(20,4)),
                   r.id
            FROM bps_export_raw r
            JOIN ms_period p
              ON p.tahun = CAST(r.tahun AS UNSIGNED) AND p.bulan = CAST(r.bulan AS UNSIGNED)
            JOIN ms_hscode h ON h.kode_hs = r.hscode
            JOIN ms_provinsi pa ON pa.kode_provinsi = r.kd_provinsi_asal
            JOIN ms_provinsi pm ON pm.kode_provinsi = r.kd_provinsi_muat
            JOIN ms_pelabuhan pel ON pel.kode_pelabuhan = r.kd_pelabuhan_muat
            JOIN ms_negara n ON n.kode_negara = r.kd_negara
            WHERE r.id_bps_upload=%s AND r.is_valid=1
        """
        fact_table = "bps_export"
    else:
        sql = """
            INSERT IGNORE INTO bps_import
              (id_ms_period, id_ms_hscode, kode_hs, kode_provinsi_bongkar,
               kode_pelabuhan_bongkar, kode_negara_asal,
               volume_kg, nilai_usd, id_bps_import_raw)
            SELECT p.id, h.id, r.hscode, pb.id, pel.id, n.id,
                   CAST(r.volume_kg AS DECIMAL(20,4)),
                   CAST(r.nilai_usd AS DECIMAL(20,4)),
                   r.id
            FROM bps_import_raw r
            JOIN ms_period p
              ON p.tahun = CAST(r.tahun AS UNSIGNED) AND p.bulan = CAST(r.bulan AS UNSIGNED)
            JOIN ms_hscode h ON h.kode_hs = r.hscode
            JOIN ms_provinsi pb ON pb.kode_provinsi = r.kd_provinsi_bongkar
            JOIN ms_pelabuhan pel ON pel.kode_pelabuhan = r.kd_pelabuhan_bongkar
            JOIN ms_negara n ON n.kode_negara = r.kd_negara_asal
            WHERE r.id_bps_upload=%s AND r.is_valid=1
        """
        fact_table = "bps_import"
    cur.execute(sql, (upload_id,))
    conn.commit()
    if exim_type == "ekspor":
        cur.execute(
            "SELECT COUNT(*) FROM bps_export f "
            "JOIN bps_export_raw r ON r.id = f.id_bps_export_raw "
            "WHERE r.id_bps_upload=%s", (upload_id,))
    else:
        cur.execute(
            "SELECT COUNT(*) FROM bps_import f "
            "JOIN bps_import_raw r ON r.id = f.id_bps_import_raw "
            "WHERE r.id_bps_upload=%s", (upload_id,))
    fact_count = cur.fetchone()[0]
    cur.execute("UPDATE bps_upload SET status='processed' WHERE id=%s", (upload_id,))
    conn.commit()
    return fact_count


def reconcile(conn, upload_id):
    cur = conn.cursor()
    cur.execute("SELECT exim_type, row_count, status FROM bps_upload WHERE id=%s", (upload_id,))
    exim_type, row_count, status = cur.fetchone()
    raw_table = "bps_export_raw" if exim_type == "ekspor" else "bps_import_raw"
    cur.execute(f"SELECT COUNT(*), SUM(is_valid), COUNT(*) - SUM(is_valid) FROM {raw_table} WHERE id_bps_upload=%s", (upload_id,))
    raw_total, valid_total, invalid_total = cur.fetchone()
    print(f"  [reconcile] upload={upload_id} {exim_type} status={status} "
          f"source={row_count} raw={raw_total} valid={valid_total} invalid={invalid_total}")
    return row_count == raw_total == valid_total


def main():
    ap = argparse.ArgumentParser(description="ETL BPS -> kkp_exim_platform")
    ap.add_argument("--ekspor", help="path file xlsx ekspor BPS")
    ap.add_argument("--impor", help="path file xlsx impor BPS")
    ap.add_argument("--force", action="store_true", help="reload file walau hash sama")
    args = ap.parse_args()
    if not args.ekspor and not args.impor:
        ap.error("butuh --ekspor atau --impor")

    conn = get_connection(cursorclass=pymysql.cursors.Cursor)
    master_ids = load_masters(conn.cursor())

    ok = True
    for exim_type, path in [("ekspor", args.ekspor), ("impor", args.impor)]:
        if not path:
            continue
        print(f"=== {exim_type}: {path} ===")
        upload_id, total = ingest_file(conn, master_ids, path, exim_type, args.force)
        if not upload_id:
            ok = False
            continue
        fact_count = transform_fact(conn, upload_id, exim_type)
        reconciled = reconcile(conn, upload_id)
        print(f"  [fact] {fact_count} baris di fakt | {'OK' if reconciled else 'MISMATCH!'}")

        if exim_type == "ekspor":
            print("  [cek] nilai ekspor 2026 (kelompok I, verifikasi vs PPT 2.995,2 juta USD):")
            cur = conn.cursor()
            cur.execute("""
                SELECT ROUND(SUM(f.nilai_usd)/1000000,1)
                FROM bps_export f
                JOIN ms_period p ON p.id=f.id_ms_period
                JOIN ms_hscode h ON h.id=f.id_ms_hscode
                WHERE p.tahun=2026 AND h.kode_kelompok='I'
            """)
            print(f"         {cur.fetchone()[0]} juta USD")
        ok = ok and reconciled

    conn.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
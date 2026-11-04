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
import re
import sys
from decimal import Decimal, InvalidOperation
from itertools import chain

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

# Header BPS punya dua bentuk:
#   1. "Data Minimum" (kumulatif) -> header di baris 1, nama kolom kanonik.
#   2. file bulanan BPS -> baris 1 judul, baris 2 kosong, header di baris 3,
#      nama kolom berbeda (mis. "HS 2022", "Berat (Kg)", "FOB (USD)").
# Alias di bawah memetakan keduanya ke kolom kanonik tabel staging.
HEADER_SCAN_ROWS = 30

HEADER_ALIASES = {
    "ekspor": {
        "tahun": ("tahun",),
        "bulan": ("bulan",),
        "hscode": ("hscode", "hs", "hs 2022", "kode hs"),
        "kd_provinsi_asal": ("kd_provinsi_asal", "provinsi asal", "kode provinsi asal"),
        "kd_provinsi_muat": ("kd_provinsi_muat", "provinsi muat", "kode provinsi muat"),
        "kd_pelabuhan_muat": ("kd_pelabuhan_muat", "kode pel muat", "kode pelabuhan muat"),
        "nm_pelabuhan_muat": ("nm_pelabuhan_muat", "pelabuhan muat", "nama pelabuhan muat"),
        "kd_negara": ("kd_negara", "kode negara", "negara tujuan", "negara"),
        "nm_negara_tujuan": ("nm_negara_tujuan", "negara tujuan", "negara"),
        "volume_kg": ("volume_kg", "volume kg", "volume", "berat kg", "berat"),
        "nilai_usd": ("nilai_usd", "nilai usd", "nilai", "fob usd", "fob"),
    },
    "impor": {
        "tahun": ("tahun",),
        "bulan": ("bulan",),
        "hscode": ("hscode", "hs", "hs 2022", "kode hs"),
        "kd_provinsi_bongkar": ("kd_provinsi_bongkar", "provinsi", "kode provinsi bongkar"),
        "kd_pelabuhan_bongkar": ("kd_pelabuhan_bongkar", "kode pelabuhan", "kode pelabuhan bongkar"),
        "nm_pelabuhan_bongkar": ("nm_pelabuhan_bongkar", "pelabuhan bongkar", "nama pelabuhan bongkar"),
        "kd_negara_asal": ("kd_negara_asal", "kode negara asal", "negara wilayah entitas asal", "negara asal", "negara"),
        "nm_negara_asal": ("nm_negara_asal", "negara wilayah entitas asal", "negara asal", "negara"),
        "volume_kg": ("volume_kg", "volume kg", "volume", "berat kg", "berat"),
        "nilai_usd": ("nilai_usd", "nilai usd", "nilai", "fob usd", "fob"),
    },
}

REQUIRED_COLS = {
    "ekspor": (
        "tahun", "bulan", "hscode", "kd_provinsi_asal", "kd_provinsi_muat",
        "kd_pelabuhan_muat", "kd_negara", "volume_kg", "nilai_usd",
    ),
    "impor": (
        "tahun", "bulan", "hscode", "kd_provinsi_bongkar",
        "kd_pelabuhan_bongkar", "kd_negara_asal", "volume_kg", "nilai_usd",
    ),
}

# Nama negara di file BPS kadang berbeda dengan master ms_negara.
COUNTRY_ALIASES = {
    "VIETNAM": "VIET NAM",
    "USA": "UNITED STATES",
    "UNITED STATES OF AMERICA": "UNITED STATES",
    "UAE": "UNITED ARAB EMIRATES",
    "SOUTH KOREA": "KOREA, REPUBLIC OF",
    "NORTH KOREA": "KOREA, DEM. PEOPLE'S REP.",
    "RUSSIA": "RUSSIA FEDERATION",
    "CZECHIA": "CZECH REPUBLIC",
    "TURKIYE": "TURKEY",
    "BRUNEI": "BRUNEI DARUSSALAM",
}


def _norm_label(value):
    """Normalisasi judul kolom: huruf kecil, spasi tunggal, tanpa simbol."""
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _country_key(value):
    """Kunci nama negara: uppercase + spasi tunggal, lalu alias umum."""
    key = re.sub(r"\s+", " ", str(value or "").strip().upper())
    return COUNTRY_ALIASES.get(key, key)


def _to_int(value):
    """Konversi tahun/bulan dari file (bisa string, float, atau '07')."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError, OverflowError):
        return None


def map_columns(header_row, exim_type):
    """Petakan header file ke nama kolom kanonik. Raise bila kolom wajib hilang."""
    labels = {_norm_label(c): i for i, c in enumerate(header_row or ())}
    mapping = {}
    for canonical, aliases in HEADER_ALIASES[exim_type].items():
        for alias in aliases:
            idx = labels.get(_norm_label(alias))
            if idx is not None:
                mapping[canonical] = idx
                break

    missing = [c for c in REQUIRED_COLS[exim_type] if c not in mapping]
    if missing:
        raise ValueError(
            f"kolom wajib {exim_type} tidak ditemukan di header file: "
            + ", ".join(missing)
        )
    return mapping


def iter_canonical_rows(path, exim_type):
    """Yield baris data dari workbook BPS sebagai dict kolom kanonik.

    Header dideteksi otomatis (baris 1 atau setelah baris judul). Baris judul,
    baris kosong, baris metadata (mis. -1, -2, ...), dan baris total dilewati
    karena tahun/bulan-nya tidak valid.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        iterator = ws.iter_rows(values_only=True)
        buffered = []
        header_idx = None
        header_row = None
        for i, row in enumerate(iterator):
            buffered.append(row)
            labels = {_norm_label(c) for c in (row or ())}
            if "tahun" in labels and "bulan" in labels:
                header_idx = i
                header_row = row
                break
            if i >= HEADER_SCAN_ROWS:
                break
        if header_idx is None:
            raise ValueError(
                "header kolom 'tahun'/'bulan' tidak ditemukan pada "
                f"{HEADER_SCAN_ROWS} baris pertama file"
            )

        mapping = map_columns(header_row, exim_type)
        i_tahun = mapping["tahun"]
        i_bulan = mapping["bulan"]

        for raw in chain(buffered[header_idx + 1:], iterator):
            if raw is None or all(c is None or str(c).strip() == "" for c in raw):
                continue
            tahun = _to_int(raw[i_tahun] if i_tahun < len(raw) else None)
            bulan = _to_int(raw[i_bulan] if i_bulan < len(raw) else None)
            if tahun is None or bulan is None or not (2000 <= tahun <= 2100 and 1 <= bulan <= 12):
                continue

            row = {canon: (raw[idx] if idx < len(raw) else None) for canon, idx in mapping.items()}
            row["tahun"] = str(tahun)
            row["bulan"] = f"{bulan:02d}"
            yield row
    finally:
        wb.close()


def periods_in_file(path, exim_type):
    """Kumpulkan pasangan (tahun, bulan) unik dari workbook BPS."""
    return {(int(row["tahun"]), int(row["bulan"])) for row in iter_canonical_rows(path, exim_type)}


def resolve_country_code(raw_code, raw_name, master_ids):
    """Ubah kode/nama negara BPS menjadi kode_negara master ms_negara."""
    code = _txt(raw_code)
    if code:
        code = code.upper()
        if code in master_ids["negara"]:
            return code

    for candidate in (raw_name, raw_code):
        key = _country_key(candidate)
        if key and key in master_ids.get("negara_nama", {}):
            return master_ids["negara_nama"][key]

    # Tidak boleh memasukkan nama negara mentah ke kolom kode VARCHAR(10).
    # Kosongkan nilai agar validate_row menandainya sebagai master negara hilang,
    # alih-alih MySQL gagal Data too long saat staging batch.
    return ""


def canonicalize_row(row, exim_type, master_ids):
    """Normalisasi nilai baris: kode negara, HS/Provinsi, dan teks staging."""
    row = dict(row)
    if exim_type == "ekspor":
        row["kd_negara"] = resolve_country_code(
            row.get("kd_negara"), row.get("nm_negara_tujuan"), master_ids
        )
    else:
        row["kd_negara_asal"] = resolve_country_code(
            row.get("kd_negara_asal"), row.get("nm_negara_asal"), master_ids
        )

    # Sebagian export Excel menyimpan HS/provinsi sebagai angka sehingga nol
    # di depan hilang (01062000 -> 1062000). Kembalikan panjang kanonik.
    hs = _txt(row.get("hscode"))
    if hs and hs.isdigit() and len(hs) < 8:
        hs = hs.zfill(8)
    row["hscode"] = hs

    for col in ("kd_provinsi_asal", "kd_provinsi_muat", "kd_provinsi_bongkar"):
        if col in row:
            value = _txt(row.get(col))
            if value and value.isdigit() and len(value) < 2:
                value = value.zfill(2)
            row[col] = value

    cols = TEXT_COLS_EXPOR if exim_type == "ekspor" else TEXT_COLS_IMPOR
    for col in cols:
        row[col] = _txt(row.get(col))
    return row


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
    cur.execute("SELECT id, kode_negara, nama_negara FROM ms_negara")
    negara = {}
    negara_nama = {}
    for i, kode, nama in cur.fetchall():
        negara[kode] = i
        key = _country_key(nama)
        if key:
            negara_nama[key] = kode
    maps["negara"] = negara
    maps["negara_nama"] = negara_nama
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

    for code_col in ("hscode", "kd_negara", "kd_negara_asal", "kd_provinsi_asal",
                     "kd_provinsi_muat", "kd_provinsi_bongkar", "kd_pelabuhan_muat",
                     "kd_pelabuhan_bongkar", "volume_kg", "nilai_usd"):
        if code_col in cols and not row.get(code_col):
            errs.append(f"{code_col} kosong")

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

    cur.execute(
        "SELECT id, status, row_count FROM bps_upload WHERE file_hash=%s "
        "ORDER BY id DESC LIMIT 1",
        (file_hash,),
    )
    existing = cur.fetchone()
    if existing and not force:
        existing_id = existing[0]
        existing_status = existing[1]
        existing_rows = int(existing[2] or 0)
        if existing_status == "processed" and existing_rows > 0:
            print(f"  [skip] {path}: sudah pernah di-upload (id={existing_id}, status={existing_status}, rows={existing_rows}). Pakai --force untuk reload.")
            return existing_id, 0
        print(f"  [retry] {path}: upload lama id={existing_id} tidak valid (status={existing_status}, rows={existing_rows}); diproses ulang")

    # Baca header dulu sebelum membuat baris upload supaya file tanpa data tidak
    # meninggalkan bps_upload kosong.
    row_iter = iter_canonical_rows(path, exim_type)
    try:
        first_row = next(row_iter)
    except StopIteration:
        print(f"  [fail] {path}: tidak ada baris data")
        return None, 0

    # ---- UPLOAD / RETRY ---------------------------------------------------
    retry_upload_id = existing[0] if existing else None
    if retry_upload_id:
        raw_table = "bps_export_raw" if exim_type == "ekspor" else "bps_import_raw"
        fact_table = "bps_export" if exim_type == "ekspor" else "bps_import"
        raw_fk_col = "id_bps_export_raw" if exim_type == "ekspor" else "id_bps_import_raw"
        cur.execute(
            f"DELETE FROM {fact_table} WHERE {raw_fk_col} IN "
            f"(SELECT id FROM {raw_table} WHERE id_bps_upload=%s)",
            (retry_upload_id,),
        )
        cur.execute(f"DELETE FROM {raw_table} WHERE id_bps_upload=%s", (retry_upload_id,),)
        cur.execute(
            """UPDATE bps_upload
               SET id_ms_period=NULL, periode_mulai=NULL, periode_akhir=NULL,
                   nama_file=%s, file_path=%s, row_count=0,
                   status='uploaded', error_summary=NULL
               WHERE id=%s""",
            (os.path.basename(path), path, retry_upload_id),
        )
        upload_id = retry_upload_id
        conn.commit()
        print(f"  [retry] upload lama id={upload_id} dibersihkan dan diproses ulang")
    else:
        cur.execute(
            """INSERT INTO bps_upload
               (exim_type, id_ms_period, periode_mulai, periode_akhir, nama_file,
                file_path, file_hash, row_count, status, error_summary)
               VALUES (%s,NULL,NULL,NULL,%s,%s,%s,0,'uploaded',NULL)""",
            (exim_type, os.path.basename(path), path, file_hash),
        )
        upload_id = cur.lastrowid
        conn.commit()

    # ---- VALIDATE + STAGING ------------------------------------------------
    raw_table = "bps_export_raw" if exim_type == "ekspor" else "bps_import_raw"
    raw_cols = "id_bps_upload,line_no," + ",".join(cols) + ",row_checksum,is_valid,validation_error"
    placeholders = "%s," * (len(cols) + 4) + "%s"
    valid = 0
    invalid_rows = 0
    error_summary = {}
    period_keys = set()
    total = 0

    def flush(batch):
        nonlocal valid, invalid_rows
        cur.executemany(
            f"INSERT INTO {raw_table} ({raw_cols}) VALUES ({placeholders})", batch
        )
        valid += sum(1 for b in batch if b[-2])
        invalid_rows += sum(1 for b in batch if not b[-2])

    batch = []
    for raw_row in chain([first_row], row_iter):
        row = canonicalize_row(raw_row, exim_type, master_ids)
        total += 1
        period_keys.add((int(row["tahun"]), int(row["bulan"])))
        code_row = {c: _txt(row.get(c)) for c in cols}
        is_ok, err = validate_row(code_row, cols, master_ids)
        if not is_ok:
            key = err.split(" | ")[0][:60]
            error_summary[key] = error_summary.get(key, 0) + 1
        vals = [upload_id, total] + [code_row.get(c) for c in cols] + [
            row_hash([code_row.get(c) for c in cols]), is_ok, err
        ]
        batch.append(vals)
        if len(batch) >= BATCH:
            flush(batch)
            batch = []
    if batch:
        flush(batch)
    conn.commit()

    pk = sorted(period_keys)
    id_pm = master_ids["period"].get(pk[0]) if pk else None
    id_pa = master_ids["period"].get(pk[-1]) if pk else None
    id_period = id_pm if len(pk) == 1 else None
    status = "valid" if invalid_rows == 0 else "invalid_partial"
    summary = ""
    if invalid_rows:
        summary = "; ".join(f"{k}:{v}" for k, v in sorted(error_summary.items(), key=lambda x: -x[1])[:10])
    cur.execute(
        """UPDATE bps_upload
           SET id_ms_period=%s, periode_mulai=%s, periode_akhir=%s,
               row_count=%s, status=%s, error_summary=%s
           WHERE id=%s""",
        (id_period, id_pm, id_pa, total, status, summary, upload_id),
    )
    conn.commit()
    print(f"  [upload] id={upload_id} {exim_type} rows={total} "
          f"periode={pk[0] if pk else '?'}..{pk[-1] if pk else '?'}")
    print(f"  [staging] {raw_table} total={total} valid={valid} invalid={invalid_rows}")
    if invalid_rows:
        print(f"    error_summary: {summary or 'other'}")

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
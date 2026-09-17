#!/usr/bin/env python3
"""
PHASE 6 — Import data TradeMap (ITC) dari file export CSV/XLSX → trademap_*.

Sumber: file unduhan dari TradeMap (ITC) — mis. hasil query "International Trade
and Market Access Data". Format yang bisa dibaca:
  CSV (koma/tab/titik-koma)      → header otomatis
  XLSX (kolom ekspor ITC)        → dibaca per sheet pertama

Kolom yang dipetakan (case-insensitive, alias umum):
  reporter / rep / reporter iso
  partner / par / partner iso
  flow         (Export / Import / Re-Export ...)
  product_code / product code / product
  product_desc / product description
  year / years
  qty / quantity
  qty_unit / quantity unit
  value_usd / trade value / value (US$ Thousand) / total value

Nilai 'Reporter:'/'Year:' baris metadata TIDAK di-skip (ditangani dengan
mengabaikan baris yang tidak memiliki product_code).

Pencatatan: automation_jobs(job_type='trademap_import') + automation_job_logs.
Idempotent: file yang sama (sha256) tidak diimport ulang; baris per (file-hash,
reporter, partner, flow, product_code, year) memakai INSERT IGNORE.

Usage:
  python3 database/scripts/import_trademap.py data/trademap/myexport.csv \
      --source nama_sumber --commit
  python3 database/scripts/import_trademap.py data/trademap/myexport.xlsx --commit
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import uuid
from decimal import Decimal, InvalidOperation

sys.path.insert(0, "/".join(__file__.split("/")[:-3]) or ".")

import openpyxl  # noqa: E402


ALIAS = {
    "reporter": ["reporter", "rep", "reporter iso", "reporting country"],
    "partner": ["partner", "par", "partner iso", "counterpart"],
    "flow": ["flow", "trade flow", "flow type"],
    "product_code": ["product code", "product_code", "product", "hs code", "commodity code"],
    "product_desc": ["product description", "product_desc", "product label"],
    "year": ["year", "years", "period", "year(s)"],
    "qty": ["quantity", "qty", "trade quantity"],
    "qty_unit": ["quantity unit", "qty_unit", "unit"],
    "value_usd": ["trade value", "value (us$ thousand)", "value_usd", "total value", "trade value (us$ thousand)"],
}

REQUIRED = ["product_code"]


def pw_line(s, w):
    return s.strip().lower()


def detect_headers(fields):
    fmap = {}
    norm = {}
    for i, f in enumerate(fields):
        n = pw_line(f, 1)
        norm[i] = n
        for key, aliases in ALIAS.items():
            if n in [pw_line(a, 1) for a in aliases] or n.replace("_", " ") in [pw_line(a, 1) for a in aliases]:
                fmap[key] = i
                break
    return fmap, norm


def parse_rows(rows, fmap, norm):
    out = []
    for r_i, row in enumerate(rows):
        cells = row
        if isinstance(row, tuple):
            cells = list(row)
        if len(cells) <= max([fmap.get("product_code", 0), fmap.get("value_usd", 0)]):
            continue  # baris header/metadata/kosong
        rec = {}
        for key, idx in fmap.items():
            if idx < len(cells):
                v = cells[idx]
                rec[key] = "" if v is None else str(v).strip()
        if not rec.get("product_code"):
            continue  # baris non-data (metadata "Reporter:", dsb.)
        if rec.get("value_usd", "").lower() in ("", "n.a.", "na", "-"):
            rec["value_usd"] = ""
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", help="file export TradeMap (.csv/.tsv/.xlsx)")
    ap.add_argument("--source", default="TradeMap ITC", help="nama sumber (keterangan)")
    ap.add_argument("--commit", action="store_true", help="simpan ke DB (default: dry-run)")
    args = ap.parse_args()

    path = args.file
    if not os.path.exists(path):
        print(f"file tidak ditemukan: {path}")
        sys.exit(1)
    blob = open(path, "rb").read()
    file_hash = hashlib.sha256(blob).hexdigest()

    # --- baca file ----------------------------------------------------------
    headers, rows = None, []
    ext = path.rsplit(".", 1)[-1].lower()
    if ext in ("csv", "tsv", "txt"):
        with open(path, newline="", encoding="utf-8-sig") as f:
            sniff = csv.Sniffer()
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = sniff.sniff(sample)
            except csv.Error:
                dialect = csv.excel
            rd = csv.reader(f, dialect)
            all_rows = [r for r in rd]
        if all_rows:
            headers = all_rows[0]
            rows = all_rows[1:]
    elif ext == "xlsx":
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        headers = next(it, None)
        rows = list(it)
        wb.close()
    else:
        print(f"format tidak didukung: {ext} (csv/tsv/xlsx)")
        sys.exit(1)

    if not headers:
        print("file kosong")
        sys.exit(1)
    fmap, norm = detect_headers(headers)
    missing = [k for k in REQUIRED if k not in fmap]
    if missing:
        print(f"header diperlukan tidak ditemukan: {missing}")
        print("  header terdeteksi:", list(norm.values()))
        sys.exit(1)
    recs = parse_rows(rows, fmap, norm)
    print(f"file: {path} ({os.path.basename(path)})")
    print(f"sha256: {file_hash[:16]}...  record data: {len(recs)}")

    if not args.commit:
        print("\n[DRY-RUN] dicetak 5 contoh record:")
        for r in recs[:5]:
            print("  ", {k: r.get(k) for k in ("reporter", "partner", "flow", "product_code", "year", "value_usd")})
        print("Jalankan ulang dengan --commit untuk menyimpan.")
        sys.exit(0)

    # --- simpan -------------------------------------------------------------
    from backend.db import get_connection

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO automation_jobs (job_type, status, params_json, correlation_id, started_at) "
        "VALUES ('trademap_import', 'RUNNING', %s, %s, NOW())",
        (json.dumps({"file": os.path.basename(path), "source": args.source}), uuid.uuid4().hex),
    )
    job_id = cur.lastrowid
    cur.execute("INSERT INTO automation_job_logs (id_job, level, message) VALUES (%s,%s,%s)",
                (job_id, "info", f"mulai import {os.path.basename(path)} ({len(recs)} records)"))
    conn.commit()

    cur.execute("SELECT id FROM trademap_raw WHERE file_hash = %s", (file_hash,))
    existing = cur.fetchone()
    if existing:
        print(f"file sudah pernah diimport (trademap_raw id={existing['id']}) - skip")
        cur.execute("UPDATE automation_jobs SET status='SUCCESS', finished_at=NOW() WHERE id=%s", (job_id,))
        conn.commit()
        conn.close()
        sys.exit(0)

    # payload ringkas utk audit (bukan blob file mentah — file_path/hash)
    sample = recs[:20]
    payload = {
        "file_name": os.path.basename(path),
        "record_count": len(recs),
        "headers": [norm.get(i) for i in sorted(norm)],
        "source": args.source,
"sample": [{k: (r.get(k) or "")[:120] for k in ("reporter", "partner", "flow", "product_code", "year", "value_usd")} for r in sample],
    }

    cur.execute(
        "INSERT INTO trademap_raw (file_path, file_hash, row_count, payload_json, status) "
        "VALUES (%s, %s, %s, %s, 'validated')",
        (path, file_hash, len(recs), json.dumps(payload)),
    )
    raw_id = cur.lastrowid

    inserted = skipped = 0
    for r in recs:
        try:
            year = int(r.get("year") or "") if r.get("year") else None
            if year is None:
                skipped += 1
                continue
            value = None
            qty = None
            raw_v = r.get("value_usd") or ""
            if raw_v:
                try:
                    value = Decimal(raw_v.replace(",", "").replace("$", "").strip())
                except InvalidOperation:
                    value = None
            raw_q = r.get("qty") or ""
            if raw_q:
                try:
                    qty = Decimal(raw_q.replace(",", "").strip())
                except InvalidOperation:
                    qty = None
            cur.execute(
                """INSERT IGNORE INTO trademap_trade
                   (reporter, partner, flow, product_code, product_desc, year, qty, qty_unit,
                    value_usd, id_trademap_raw)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (r.get("reporter") or "", r.get("partner") or None, r.get("flow") or "",
                 r["product_code"], r.get("product_desc") or None, year, qty,
                 r.get("qty_unit") or None, value, raw_id),
            )
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:  # noqa: BLE001
            skipped += 1
            cur.execute("INSERT INTO automation_job_logs (id_job, level, message) VALUES (%s,%s,%s)",
                        (job_id, "error", f"baris skip: {e}"))
    cur.execute("UPDATE trademap_raw SET row_count=%s WHERE id=%s", (inserted, raw_id))
    cur.execute("UPDATE automation_jobs SET status='SUCCESS', finished_at=NOW() WHERE id=%s", (job_id,))
    cur.execute("INSERT INTO automation_job_logs (id_job, level, message, data_json) VALUES (%s,%s,%s,%s)",
                (job_id, "info", f"selesai: {inserted} inserted, {skipped} skipped",
                 json.dumps({"inserted": inserted, "skipped": skipped, "raw_id": raw_id})))
    conn.commit()
    conn.close()
    print(f"SUKSES: {inserted} baris disimpan (skip {skipped}), raw id={raw_id}")


if __name__ == "__main__":
    main()
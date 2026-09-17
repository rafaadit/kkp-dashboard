#!/usr/bin/env python3
"""
Kurs JISDOR per bulan (website Bank Indonesia) -> ms_kurs.

Sumber resmi: kurs JISDOR di website Bank Indonesia (https://www.bi.go.id),
rata-rata per bulan; nilai BERBEDA tiap bulan.

CSV input (comma, header opsional):
    tahun,bulan,kurs
    2026,1,16101.23
    2026,2,16250.00

Baris dengan kurs kosong / 0 -> di-skip (periode tsb tetap tanpa kurs,
sehingga raw_exim periode tsb status='needs_validation').

Usage:
    python3 database/scripts/import_jisdor.py jisdor_kurs.csv
    python3 database/scripts/import_jisdor.py jisdor_kurs.csv --commit
"""
import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation

import pymysql

sys.path.insert(0, "/".join(__file__.split("/")[:-3]))
from backend.db import get_connection  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Import kurs JISDOR per bulan ke ms_kurs")
    ap.add_argument("csv_path", help="file CSV: tahun,bulan,kurs")
    ap.add_argument("--commit", action="store_true", help="jalankan INSERT (default: dry-run)")
    args = ap.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, tahun, bulan FROM ms_period")
    period = {(r["tahun"], r["bulan"]): r["id"] for r in cur.fetchall()}

    inserted = skipped = unknown = 0
    with open(args.csv_path, newline="", encoding="utf-8-sig") as f:
        for raw in csv.reader(f):
            if len(raw) < 3:
                continue
            y, m, k = raw[0], raw[1], raw[2]
            if y.strip().lower() in ("tahun", "year", "period") or m.strip().lower() in ("bulan", "month"):
                continue
            try:
                yi, mi = int(y), int(m)
                kurs = Decimal(k)
                if kurs <= 0:
                    raise InvalidOperation
            except (ValueError, InvalidOperation):
                print(f"  skip baris tidak valid: {raw!r}")
                skipped += 1
                continue
            pid = period.get((yi, mi))
            if pid is None:
                print(f"  skip periode tidak ada di ms_period: {yi}-{mi:02d}")
                unknown += 1
                continue
            if args.commit:
                cur.execute(
                    """INSERT INTO ms_kurs (id_ms_period, rata_rata_kurs, sumber, keterangan)
                       VALUES (%s,%s,'JISDOR Bank Indonesia','Kurs rata-rata bulanan JISDOR')
                       ON DUPLICATE KEY UPDATE rata_rata_kurs=VALUES(rata_rata_kurs),
                           sumber=VALUES(sumber), keterangan=VALUES(keterangan)""",
                    (pid, kurs),
                )
                conn.commit()
            else:
                print(f"  [dry-run] {yi}-{mi:02d} kurs={kurs}")
            inserted += 1

    if not args.commit:
        print(f"\n{dry_msg('DRY-RUN')} kurs={inserted} skip={skipped} periode_unknown={unknown}")
        print("Jalankan ulang dengan --commit untuk menyimpan.")
    else:
        print(f"\nSUKSES: kurs={inserted} disimpan ({skipped} skip, {unknown} periode tak dikenal)")
    conn.close()


def dry_msg(tag):
    return tag


if __name__ == "__main__":
    main()
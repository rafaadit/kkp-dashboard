#!/usr/bin/env python3
"""PHASE 9c — Robot unduhan Kurs JISDOR Bank Indonesia.

Mengambil kurs harian USD/IDR dari web service resmi BI (wskursbi.asmx,
getSubKursJisdor3) dan mencatat lineage:
  automation_jobs         (job_type='jisdor_download')
  automation_download_logs     (PENDING -> DOWNLOADED -> VALIDATED)

Proses (--commit): simpan harian ke jisdor_daily + rata-rata bulanan ke ms_kurs
(sumber 'JISDOR Bank Indonesia') so raw_exim bisa dihitung ulang.

Contoh:
  # bulan berjalan (default), dry-run (belum nulis DB)
  .venv/bin/python database/scripts/download_jisdor.py

  # rentang bulan Juni 2026, simpan hasil
  .venv/bin/python database/scripts/download_jisdor.py --start 2026-06-01 --end 2026-06-30 --commit

  # uji/lokal tanpa akses internet: pakai fixture XML
  .venv/bin/python database/scripts/download_jisdor.py --fixture tests/fixtures/jisdor_sample.xml --commit --json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.kurs.jisdor import JisdorDownloader  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--mts", default="USD", help="kode mata uang (default USD = JISDOR)")
    ap.add_argument("--start", default=None, help="tanggal awal YYYY-MM-DD (default awal bulan ini)")
    ap.add_argument("--end", default=None, help="tanggal akhir YYYY-MM-DD (default hari ini)")
    ap.add_argument("--source", default="Bank Indonesia JISDOR", help="nama sumber")
    ap.add_argument("--fixture", default=None, help="file XML lokal pengganti web service (uji tanpa internet)")
    ap.add_argument("--no-process", action="store_true", help="hanya unduh; lewati proses ke DB")
    ap.add_argument("--json", action="store_true", help="cetak ringkasan JSON")
    ap.add_argument("--commit", action="store_true", help="simpan jisdor_daily + ms_kurs (default dry-run)")
    args = ap.parse_args()

    dl = JisdorDownloader()
    try:
        res = dl.run(mts=args.mts, start=args.start, end=args.end, source=args.source,
                     fixture=args.fixture, process=not args.no_process, commit=args.commit)
    finally:
        dl.close()

    if args.json:
        print(json.dumps(res, indent=2, default=str))
    else:
        if res["ok"]:
            print("SUKSES: %d hari (%s bytes) — job %s, download_log %s%s"
                  % (res.get("days"), res.get("file_size"), res["job_id"],
                     res["download_log_id"],
                     " (%d bulan ke ms_kurs)" % res.get("months", 0) if res.get("months") else ""))
        else:
            print("GAGAL: %s" % res.get("error"))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
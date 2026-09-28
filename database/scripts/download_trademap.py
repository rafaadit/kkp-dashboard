#!/usr/bin/env python3
"""PHASE 9 — Robot unduhan TradeMap (ITC).

Mengambil file data TradeMap dan mencatat lineage:
  automation_jobs      (job_type='trademap_download')
  automation_download_logs  (PENDING -> DOWNLOADED -> VALIDATED)

Tanpa TRADEMAP_API_KEY dan tanpa --fixture, job diberi status FAILED
(robot aman, tidak nge-crash). Untuk uji tanpa kunci nyata gunakan --fixture.

Contoh:
  .venv/bin/python database/scripts/download_trademap.py --flow Export --year 2024 --commit
  .venv/bin/python database/scripts/download_trademap.py --fixture tests/fixtures/trademap_sample.csv \
      --no-process --commit
  .venv/bin/python database/scripts/download_trademap.py --fixture x.csv --commit
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.trademap.downloader import TradeMapDownloader  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flow", default="Export", choices=["Export", "Import"], help="jenis arus (Export/Import)")
    ap.add_argument("--year", type=int, default=None, help="tahun data (opsional)")
    ap.add_argument("--partner", default=None, help="kode partner (opsional)")
    ap.add_argument("--source", default="TradeMap ITC", help="nama sumber")
    ap.add_argument("--fixture", default=None, help="file lokal sebagai pengganti unduhan (uji tanpa API key)")
    ap.add_argument("--no-process", action="store_true", help="hanya unduh; lewati pipeline pemrosesan")
    ap.add_argument("--no-commit", action="store_true", help="dry-run pipeline (hanya unduh yang dicatat ke DB)")
    ap.add_argument("--json", action="store_true", help="cetak ringkasan JSON")
    args = ap.parse_args()

    dl = TradeMapDownloader()
    try:
        res = dl.run(flow=args.flow, year=args.year, partner=args.partner,
                     source=args.source, fixture=args.fixture,
                     process=not args.no_process, commit=not args.no_commit)
    finally:
        dl.close()

    if args.json:
        print(json.dumps(res, indent=2, default=str))
    else:
        if res["ok"]:
            print("SUKSES: %s (%d bytes, job %s, download_log %s)"
                  % (res.get("file_path"), res.get("file_size"), res["job_id"], res["download_log_id"]))
        else:
            print("GAGAL: %s" % res.get("error"))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
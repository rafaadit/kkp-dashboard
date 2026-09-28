#!/usr/bin/env python3
"""PHASE 9 — Pipeline pemrosesan & harmonisasi TradeMap.

Alur: parse -> normalize -> master mapping -> HS harmonization -> validation
-> duplicate check -> trademap_trade (+ trademap_raw metadata/lineage).

Default DRY-RUN (tidak menulis DB). Gunakan --commit untuk menyimpan.

Contoh:
  .venv/bin/python database/scripts/process_trademap.py tests/fixtures/trademap_sample.csv
  .venv/bin/python database/scripts/process_trademap.py data/trademap/export.csv --commit
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.trademap.processor import TradeMapProcessor  # noqa: E402


def summarize(res):
    return {
        "ok": res.ok,
        "commit": res.commit,
        "file_hash": res.file_hash[:16] + "..." if res.file_hash else "",
        "raw_id": res.raw_id,
        "job_id": res.job_id,
        "error": res.error,
        "stats": res.stats.as_dict(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="file TradeMap (.csv/.tsv/.xlsx)")
    ap.add_argument("--source", default="TradeMap ITC", help="nama sumber")
    ap.add_argument("--download-log-id", type=int, default=None, help="id automation_download_logs (opsional)")
    ap.add_argument("--commit", action="store_true", help="simpan ke DB (default dry-run)")
    ap.add_argument("--json", action="store_true", help="cetak ringkasan JSON")
    args = ap.parse_args()

    rc = 0
    summaries = []
    for path in args.files:
        proc = TradeMapProcessor()
        try:
            res = proc.process(path, source=args.source, commit=args.commit,
                               download_log_id=args.download_log_id)
        finally:
            proc.close()
        summaries.append(summarize(res))
        if not res.ok:
            rc = 1
        if not args.json:
            mode = "COMMIT" if res.commit else "DRY-RUN"
            print("[%s] %s -> ok=%s %s" % (mode, os.path.basename(path), res.ok, res.error or ""))
            if res.ok:
                print("  stats:", json.dumps(res.stats.as_dict()))
                codes = {}
                for i in res.issues:
                    codes[i.kode] = codes.get(i.kode, 0) + 1
                if codes:
                    print("  temuan:", json.dumps(codes, sort_keys=True))
    if args.json:
        print(json.dumps(summaries if len(summaries) > 1 else summaries[0], indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())

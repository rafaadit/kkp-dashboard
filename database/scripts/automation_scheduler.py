#!/usr/bin/env python3
"""PHASE 9 — Scheduler automation: jalankan job PENDING yang jatuh tempo.

Dispatch per job_type:
  trademap_download -> TradeMapDownloader.run(...) memakai params_json job.

CLI:
  --once        jalankan satu sweep lalu keluar (cocok untuk cron)
  --every N     loop tiap N detik (default 300)
  --job-type T  batasi ke job_type tertentu (default: semua yang dikenal)

Job yang dianggap jatuh tempo: status='PENDING' dan (scheduled_at IS NULL
atau scheduled_at <= NOW()); diurutkan paling tua dulu. Downloader yang
mengelola transisi status (RUNNING -> SUCCESS/FAILED) + retry counter.

Contoh (cron tiap jam):
  0 * * * * cd /path/project && .venv/bin/python database/scripts/automation_scheduler.py --once
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.db import get_connection  # noqa: E402

KNOWN_JOB_TYPES = {"trademap_download"}


def dispatch(conn, job):
    """Tangani satu job; return True bila berhasil dispatch utuh."""
    jt = job["job_type"]
    params = job.get("params_json") or {}
    if isinstance(params, str):
        params = json.loads(params or "{}")
    if jt == "trademap_download":
        from backend.trademap.downloader import TradeMapDownloader

        dl = TradeMapDownloader(conn)
        res = dl.run(
            flow=params.get("flow", "Export"),
            year=params.get("year"),
            partner=params.get("partner"),
            source=params.get("source", "TradeMap ITC"),
            fixture=params.get("fixture"),
            process=bool(params.get("process", True)),
            commit=True,
            job_id=job["id"],
        )
        dl.close()
        return res.get("ok")
    return False


def sweep(conn, job_types=None):
    """Jalankan semua job PENDING jatuh tempo; return jumlah job yang diproses."""
    where = ["status = 'PENDING'", "(scheduled_at IS NULL OR scheduled_at <= NOW())"]
    params = []
    if job_types:
        where.append("job_type IN (%s)" % ",".join(["%s"] * len(job_types)))
        params += list(job_types)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, job_type, params_json FROM automation_jobs WHERE %s "
        "ORDER BY COALESCE(scheduled_at, created_at) LIMIT 20" % " AND ".join(where),
        params)
    jobs = [dict(r) for r in cur.fetchall()]
    done = 0
    for job in jobs:
        try:
            if dispatch(conn, job):
                done += 1
        except Exception as e:  # noqa: BLE001
            cur.execute("UPDATE automation_jobs SET status='FAILED', finished_at=NOW(), "
                        "error_message=%s WHERE id=%s", (str(e)[:1000], job["id"]))
            cur.execute("INSERT INTO automation_job_logs (id_job, level, message) "
                        "VALUES (%s,'error',%s)", (job["id"], str(e)))
            conn.commit()
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true", help="satu sweep lalu keluar")
    ap.add_argument("--every", type=int, default=300, help="interval loop (detik), default 300")
    ap.add_argument("--job-type", action="append", default=None,
                    help="job_type yang ditangani (bisa diulang); default semua yang dikenal")
    args = ap.parse_args()

    job_types = args.job_type or sorted(KNOWN_JOB_TYPES)
    unknown = set(job_types) - KNOWN_JOB_TYPES
    if unknown:
        print("JOB_TYPE tidak dikenal: %s (kenal: %s)" % (", ".join(sorted(unknown)),
                                                          ", ".join(sorted(KNOWN_JOB_TYPES))), file=sys.stderr)
        return 2

    conn = get_connection()
    try:
        while True:
            n = sweep(conn, job_types)
            print("[scheduler] %d job diproses pada %s" % (n, time.strftime("%Y-%m-%d %H:%M:%S")))
            if args.once:
                break
            time.sleep(args.every)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
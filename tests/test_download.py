#!/usr/bin/env python3
"""PHASE 9 — Test robot unduhan TradeMap + scheduler automation.

Menggunakan fixture lokal (tanpa API key nyata). Data trade yang diproses
TIDAK disentuh (mode no-process) supaya tidak mengganggu hitungan
test_trademap/test_trademap_processing.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_connection  # noqa: E402

PASS = 0
FAIL = 0
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "trademap_sample.csv")
TMPDIR = tempfile.mkdtemp(prefix="kkp_dl_")


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def main():
    os.environ["TRADEMAP_DOWNLOAD_DIR"] = TMPDIR
    os.environ["TRADEMAP_API_KEY"] = ""

    conn = get_connection()

    from backend.trademap.downloader import TradeMapDownloader

    print("== unduhan via fixture (no-process) ==")
    dl = TradeMapDownloader(conn)
    res = dl.run(flow="Export", year=2023, partner="RU", source="synthetic download test",
                 fixture=FIXTURE, process=False, commit=True)
    check("unduh ok", res["ok"], str(res))
    check("file tersalin", os.path.isfile(res.get("file_path", "")), str(res.get("file_path")))
    check("hash cocok fixture", sha256(res["file_path"]) == sha256(FIXTURE))
    check("download_log id terisi", res.get("download_log_id"))
    dl.close()

    cur = conn.cursor()
    cur.execute("SELECT status, file_hash FROM automation_download_logs WHERE id=%s",
                (res["download_log_id"],))
    dlrow = cur.fetchone()
    cur.execute("SELECT status, attempts FROM automation_jobs WHERE id=%s", (res["job_id"],))
    job = cur.fetchone()
    check("download_log DOWNLOADED", dlrow and dlrow["status"] == "DOWNLOADED", str(dlrow))
    check("job SUCCESS", job and job["status"] == "SUCCESS", str(job))

    print("== resume job dari antrian (attempts bertambah) ==")
    dl2 = TradeMapDownloader(conn)
    res2 = dl2.run(flow="Export", year=2023, partner="RU", source="synthetic download test",
                   fixture=FIXTURE, process=False, commit=True, job_id=res["job_id"])
    dl2.close()
    check("resume ok", res2["ok"])
    cur.execute("SELECT status, attempts FROM automation_jobs WHERE id=%s", (res["job_id"],))
    job2 = cur.fetchone()
    check("attempts bertambah", job2 and job2["attempts"] == 2, str(job2))

    print("== unduh + proses dry-run -> download_log VALIDATED ==")
    dlv = TradeMapDownloader(conn)
    resv = dlv.run(flow="Export", year=2023, source="synthetic dryrun", fixture=FIXTURE,
                   process=True, commit=False)
    dlv.close()
    check("validated ok", resv["ok"], str(resv))
    cur.execute("SELECT status FROM automation_download_logs WHERE id=%s", (resv["download_log_id"],))
    check("download_log VALIDATED", cur.fetchone()["status"] == "VALIDATED")

    print("== tanpa API key & tanpa fixture -> FAILED ==")
    dl3 = TradeMapDownloader(conn)
    res3 = dl3.run(flow="Export", year=2024, source="synthetic", process=False, commit=True)
    dl3.close()
    check("gagal aman", not res3["ok"] and "TRADEMAP_API_KEY" in res3.get("error", ""), str(res3))
    cur.execute("SELECT status, error_message FROM automation_jobs WHERE id=%s", (res3["job_id"],))
    jf = cur.fetchone()
    check("job tercatat FAILED", jf and jf["status"] == "FAILED", str(jf))
    conn.close()

    print("== scheduler: job PENDING jatuh tempo didispatch ==")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO automation_jobs (job_type, status, params_json, correlation_id) "
        "VALUES ('trademap_download','PENDING',%s,%s)",
        (json.dumps({"flow": "Export", "year": 2023, "fixture": os.path.abspath(FIXTURE),
                     "process": False, "partner": "JP"}),
         "schedtest-" + __import__("uuid").uuid4().hex))
    jid = cur.lastrowid
    conn.commit()

    from database.scripts.automation_scheduler import sweep

    n = sweep(conn, job_types=["trademap_download"])
    check("scheduler memproses 1", n == 1, str(n))
    cur.execute("SELECT status FROM automation_jobs WHERE id=%s", (jid,))
    check("job scheduler SUCCESS", cur.fetchone()["status"] == "SUCCESS")
    cur.execute("SELECT status, file_hash FROM automation_download_logs WHERE id_job=%s", (jid,))
    dlrow = cur.fetchone()
    check("download log tercatat", dlrow and dlrow["status"] in ("DOWNLOADED", "VALIDATED"), str(dlrow))
    conn.close()

    print("== CLI download_trademap.py (fixture) ==")
    r = subprocess.run(
        [sys.executable, os.path.join("database", "scripts", "download_trademap.py"),
         "--fixture", FIXTURE, "--flow", "Export", "--year", "2023",
         "--partner", "AU", "--no-process", "--json"],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    check("CLI exit 0", r.returncode == 0, r.stderr[-300:])
    out = json.loads(r.stdout)
    check("CLI ok=true", out.get("ok") is True, r.stdout[:300])

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""PHASE 9c — Test robot unduhan Kurs JISDOR + scheduler automation.

Menggunakan fixture XML lokal (struktur web service BI); tidak menyentuh
network. Menyimpan jisdor_daily + rata-rata bulanan ke ms_kurs (commit).
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_connection  # noqa: E402

PASS = 0
FAIL = 0
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "jisdor_sample.xml")
TMPDIR = tempfile.mkdtemp(prefix="kkp_jisdor_")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(name, cond, detail="", reset=False):
    global PASS, FAIL
    if reset:
        PASS = 0
        FAIL = 0
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


def kurs_juni(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT k.rata_rata_kurs FROM ms_kurs k JOIN ms_period p ON p.id=k.id_ms_period "
        "WHERE p.tahun=2026 AND p.bulan=6")
    r = cur.fetchone()
    return float(r["rata_rata_kurs"]) if r else None


def snapshot_kurs_juni(conn):
    cur = conn.cursor()
    cur.execute("SELECT id_ms_period, rata_rata_kurs FROM ms_kurs k JOIN ms_period p ON p.id=k.id_ms_period "
                "WHERE p.tahun=2026 AND p.bulan=6")
    r = cur.fetchone()
    return (r["id_ms_period"], float(r["rata_rata_kurs"])) if r else None


def snapshot_jisdor(conn):
    cur = conn.cursor()
    cur.execute("SELECT tanggal, mata_uang, kurs, sumber, id_download_log FROM jisdor_daily "
                "WHERE tanggal BETWEEN '2026-06-01' AND '2026-06-03'")
    return [dict(r) for r in cur.fetchall()]


def restore(conn, snap_kurs, snap_jisdor):
    cur = conn.cursor()
    cur.execute("DELETE FROM jisdor_daily WHERE tanggal BETWEEN '2026-06-01' AND '2026-06-03'")
    for r in snap_jisdor:
        cur.execute(
            "INSERT INTO jisdor_daily (tanggal, mata_uang, kurs, sumber, id_download_log) "
            "VALUES (%s,%s,%s,%s,%s)",
            (r["tanggal"], r["mata_uang"], r["kurs"], r["sumber"], r["id_download_log"]))
    if snap_kurs:
        cur.execute("UPDATE ms_kurs SET rata_rata_kurs=%s WHERE id_ms_period=%s",
                    (snap_kurs[1], snap_kurs[0]))
    else:
        cur.execute("DELETE k FROM ms_kurs k JOIN ms_period p ON p.id=k.id_ms_period "
                    "WHERE p.tahun=2026 AND p.bulan=6")
    conn.commit()


def count_jisdor(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM jisdor_daily")
    return cur.fetchone()["n"]


def main():
    os.environ["BI_JISDOR_DIR"] = TMPDIR
    conn = get_connection()
    snap_kurs = snapshot_kurs_juni(conn)
    snap_jisdor = snapshot_jisdor(conn)
    conn.close()
    try:
        run_all()
    finally:
        conn = get_connection()
        restore(conn, snap_kurs, snap_jisdor)
        conn.close()


def run_all():
    conn = get_connection()
    from backend.kurs.jisdor import JisdorDownloader

    SRC = "synthetic jisdor test"

    print("== unduh via fixture (no-process) ==")
    dl = JisdorDownloader(conn)
    res = dl.run(mts="USD", start="2026-06-01", end="2026-06-03",
                 source=SRC, fixture=FIXTURE,
                 process=False, commit=False)
    check("unduh ok", res["ok"], str(res))
    check("file tersalin", os.path.isfile(res.get("file_path", "")), str(res.get("file_path")))
    check("hash cocok fixture", sha256(res["file_path"]) == sha256(FIXTURE))
    check("3 hari kurs", res.get("days") == 3, str(res.get("days")))
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
    kur_before = kurs_juni(conn)
    dl2 = JisdorDownloader(conn)
    res2 = dl2.run(mts="USD", start="2026-06-01", end="2026-06-03",
                   source=SRC, fixture=FIXTURE,
                   process=False, commit=False, job_id=res["job_id"])
    dl2.close()
    check("resume ok", res2["ok"])
    cur.execute("SELECT attempts FROM automation_jobs WHERE id=%s", (res["job_id"],))
    check("attempts bertambah", cur.fetchone()["attempts"] == 2)

    print("== proses dry-run (commit=False): ms_kurs tidak berubah ==")
    dl3 = JisdorDownloader(conn)
    res3 = dl3.run(mts="USD", start="2026-06-01", end="2026-06-03",
                   source=SRC, fixture=FIXTURE,
                   process=True, commit=False)
    dl3.close()
    check("proses ok", res3["ok"] and res3["days"] == 3 and res3["months"] == 1, str(res3))
    check("ms_kurs Juni tidak berubah (dry-run)", kurs_juni(conn) == kur_before,
          f"before={kur_before} after={kurs_juni(conn)}")
    cur.execute("SELECT status FROM automation_download_logs WHERE id=%s", (res3["download_log_id"],))
    check("download_log VALIDATED", cur.fetchone()["status"] == "VALIDATED")

    print("== proses commit: jisdor_daily + ms_kurs ==")
    dl4 = JisdorDownloader(conn)
    res4 = dl4.run(mts="USD", start="2026-06-01", end="2026-06-03",
                   source=SRC, fixture=FIXTURE,
                   process=True, commit=True)
    dl4.close()
    conn.commit()
    check("commit ok", res4["ok"] and res4["months"] == 1, str(res4))
    check("ms_kurs Juni = rata2 (16250)", kurs_juni(conn) == 16250.0, str(kurs_juni(conn)))
    cur.execute("SELECT COUNT(*) AS n FROM jisdor_daily WHERE tanggal BETWEEN '2026-06-01' AND '2026-06-03'")
    check("3 baris jisdor_daily", cur.fetchone()["n"] == 3)
    conn.close()

    print("== scheduler: job PENDING 'jisdor_download' didispatch ==")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO automation_jobs (job_type, status, params_json, correlation_id) "
        "VALUES ('jisdor_download','PENDING',%s,%s)",
        (json.dumps({"mts": "USD", "start": "2026-06-02", "end": "2026-06-03",
                     "fixture": os.path.abspath(FIXTURE), "process": True,
                     "source": SRC}),
         "jisdor-sched-" + uuid.uuid4().hex))
    jid = cur.lastrowid
    conn.commit()

    from database.scripts.automation_scheduler import sweep

    n = sweep(conn, job_types=["jisdor_download"])
    check("scheduler memproses 1", n == 1, str(n))
    cur.execute("SELECT status FROM automation_jobs WHERE id=%s", (jid,))
    check("job scheduler SUCCESS", cur.fetchone()["status"] == "SUCCESS")
    cur.execute("SELECT status FROM automation_download_logs WHERE id_job=%s", (jid,))
    check("download log scheduler VALIDATED", cur.fetchone()["status"] == "VALIDATED")
    conn.close()

    print("== CLI download_jisdor.py (fixture) ==")
    r = subprocess.run(
        [sys.executable, os.path.join("database", "scripts", "download_jisdor.py"),
         "--fixture", FIXTURE, "--start", "2026-06-01", "--end", "2026-06-03",
         "--source", SRC, "--commit", "--json"],
        capture_output=True, text=True, cwd=ROOT)
    check("CLI exit 0", r.returncode == 0, r.stderr[-300:])
    out = json.loads(r.stdout)
    check("CLI ok=true days=3", out.get("ok") is True and out.get("days") == 3, r.stdout[:300])

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
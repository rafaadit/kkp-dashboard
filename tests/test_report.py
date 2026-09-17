#!/usr/bin/env python3
"""PHASE 7 — Test generator + API laporan PPT."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.app import create_app
from backend.db import get_connection

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def main():
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    tok = c.post("/api/auth/login", json={"email": "admin@kkp.local", "password": "admin123"}).get_json()["token"]
    H = {"Authorization": f"Bearer {tok}"}

    print("== proteksi ==")
    check("list tanpa token 401", c.get("/api/report/list").status_code == 401)
    check("generate tanpa token 401", c.post("/api/report/generate_ppt", json={}).status_code == 401)

    print("== generate ==")
    r = c.post("/api/report/generate_ppt", json={"tahun": 2026, "bulan_awal": 1, "bulan_akhir": 6}, headers=H)
    check("generate 200", r.status_code == 200, r.get_data(as_text=True)[:200])
    d = r.get_json()
    check("file ada di disk", os.path.isfile(d.get("file", "")), str(d))
    if os.path.isfile(d.get("file", "")):
        from pptx import Presentation
        prs = Presentation(d["file"])
        check("PPT 11 slide", len(prs.slides) == 11, str(len(prs.slides)))
        jenis = sum(1 for s in prs.slides for sh in s.shapes if sh.has_chart)
        tabel = sum(1 for s in prs.slides for sh in s.shapes if sh.has_table)
        check("PPT punya chart", jenis >= 3, str(jenis))
        check("PPT punya tabel", tabel >= 5, str(tabel))

    print("== validasi job tercatat ==")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM automation_jobs WHERE job_type='report_ppt' ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    check("job SUCCESS", row and row["status"] == "SUCCESS", str(row))

    print("== input tidak valid ==")
    check("bulan salah 400", c.post("/api/report/generate_ppt", json={"tahun": 2026, "bulan_awal": 6, "bulan_akhir": 1}, headers=H).status_code == 400)
    check("tahun ngawur 400", c.post("/api/report/generate_ppt", json={"tahun": 99, "bulan_awal": 1, "bulan_akhir": 6}, headers=H).status_code == 400)

    print("== list ==")
    r = c.get("/api/report/list", headers=H)
    check("list 200", r.status_code == 200)
    d = r.get_json()
    check("list ada isi", len(d["reports"]) >= 1)
    check("report punya file valid", any(x["downloadable"] for x in d["reports"]))

    print("== download ==")
    jid = d["reports"][0]["id"]
    r = c.get(f"/api/report/download?job_id={jid}", headers=H)
    check("download 200", r.status_code == 200, str(r.status_code))
    check("content-type pptx", "presentation" in r.headers.get("Content-Type", "") or "octet-stream" in r.headers.get("Content-Type", ""), r.headers.get("Content-Type", ""))
    check("download job ngawur 404", c.get("/api/report/download?job_id=999999", headers=H).status_code == 404)

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
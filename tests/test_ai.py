#!/usr/bin/env python3
"""PHASE 8 — Test AI assistant (mode lokal deterministik)."""
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

    print("== proteksi ==")
    check("tanpa token 401", c.post("/api/ai/ask", json={"question": "hai"}).status_code == 401)

    tok = c.post("/api/auth/login", json={"email": "admin@kkp.local", "password": "admin123"}).get_json()["token"]
    H = {"Authorization": f"Bearer {tok}"}

    print("== validasi ==")
    check("question kosong 400", c.post("/api/ai/ask", json={}, headers=H).status_code == 400)

    print("== jawaban lokal ==")
    r = c.post("/api/ai/ask", json={"question": "berapa total ekspor?", "exim": "ekspor",
                                    "mulai": "2026-01", "akhir": "2026-06"}, headers=H)
    check("ask 200", r.status_code == 200, r.get_data(as_text=True)[:200])
    d = r.get_json()
    check("mode lokal", d.get("mode") == "lokal", str(d.get("mode")))
    check("ada jawaban", bool(d.get("answer")))
    check("konteks punya totals", "totals" in d.get("konteks", {}))

    # konsistensi angka dgn DB
    tb = d["konteks"]["totals"]["nilai_usd"]
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ROUND(SUM(nil_usd),2) s FROM raw_exim WHERE exim_type='ekspor' "
                "AND tahun=2026 AND bulan BETWEEN 1 AND 6")
    db_val = cur.fetchone()["s"]
    conn.close()
    check("angka cocok dgn DB", abs(float(tb) - float(db_val)) < 0.01, f"{tb} vs {db_val}")

    print("== intent komoditas & negara ==")
    d1 = c.post("/api/ai/ask", json={"question": "komoditas utama ekspor 2026"}, headers=H).get_json()
    check("sebut Udang", "Udang" in d1["answer"], d1["answer"][:120])
    d2 = c.post("/api/ai/ask", json={"question": "negara tujuan utama", "exim": "ekspor"}, headers=H).get_json()
    check("sebut negara", any(x in d2["answer"] for x in ("UNITED STATES", "CHINA", "JAPAN")), d2["answer"][:120])

    print("== audit log ==")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) n FROM audit_logs WHERE action='ai.ask'")
    n = cur.fetchone()["n"]
    conn.close()
    check("tercatat di audit_logs", n >= 3, str(n))

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
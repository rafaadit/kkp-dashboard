#!/usr/bin/env python3
"""PHASE 8 — Test AI assistant (mode lokal deterministik)."""
import os
import sys

# Paksa mode lokal deterministik: jangan pakai LLM eksternal saat testing,
# walaupun AI_API_KEY terisi di .env.
os.environ["AI_API_KEY"] = ""

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

    print("== konteks per tahun & selaras arus ==")
    d3 = c.post("/api/ai/ask", json={"question": "berapa total ekspor 2026", "exim": "ekspor"}, headers=H).get_json()
    check("tahun dari pertanyaan ter-scope", d3["konteks"]["periode"]["mulai"] == [2026, 1], str(d3["konteks"]["periode"]))
    check("konteks punya per_tahun", bool(d3["konteks"].get("per_tahun")), str(d3["konteks"].get("per_tahun"))[:80])
    d4 = c.post("/api/ai/ask", json={"question": "berapa total impor 2025", "exim": "ekspor"}, headers=H).get_json()
    check("arus ikut kata pertanyaan (impor)", d4["exim"] == "impor", str(d4["exim"]))

    print("== tampilkan data mentah per periode ==")
    d5 = c.post("/api/ai/ask", json={"question": "tampilkan data ekspor Juni 2026", "exim": "ekspor"}, headers=H).get_json()
    check("ada objek tabel", isinstance(d5.get("tabel"), dict), str(type(d5.get("tabel"))))
    check("kolom terisi", bool(d5["tabel"]["kolom"]), str(d5["tabel"].get("kolom")))
    check("ada baris ditampilkan", d5["tabel"]["ditampilkan"] > 0, str(d5["tabel"]["ditampilkan"]))
    check("periode Juni 2026", d5["tabel"]["periode"] == {"mulai": [2026, 6], "akhir": [2026, 6]},
          str(d5["tabel"]["periode"]))
    check("baris memang Juni 2026", all(r["periode"] == "2026-06" for r in d5["tabel"]["rows"]),
          str(d5["tabel"]["rows"][:1]))
    check("jawaban sebut menampilkan", "Menampilkan" in d5["answer"], d5["answer"][:80])

    d6 = c.post("/api/ai/ask", json={"question": "berapa total ekspor 2026", "exim": "ekspor"}, headers=H).get_json()
    check("pertanyaan biasa tanpa tabel", d6.get("tabel") is None, str(d6.get("tabel")))

    d7 = c.post("/api/ai/ask", json={"question": "tampilkan data impor 2025-03", "exim": "ekspor"}, headers=H).get_json()
    check("tabel ikut arus impor", d7.get("tabel") is not None and d7["exim"] == "impor", str(d7.get("exim")))
    check("periode 2025-03", d7["tabel"]["periode"] == {"mulai": [2025, 3], "akhir": [2025, 3]},
          str(d7["tabel"].get("periode")))

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
#!/usr/bin/env python3
"""PHASE 6 — Test TradeMap API + pipeline (fixture sintetis, bukan data pasar nyata)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.app import create_app
from backend.db import get_connection

PASS = 0
FAIL = 0
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "trademap_sample.csv")


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

    # pipeline: import fixture (idempotent -> skip bila sudah ada)
    r = subprocess.run([sys.executable, os.path.join("database", "scripts", "import_trademap.py"),
                        FIXTURE, "--source", "synthetic test", "--commit"],
                       capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    check("import pipeline exit 0", r.returncode == 0, r.stderr[-300:])
    check("import sukses/skip", "SUKSES" in r.stdout or "sudah pernah" in r.stdout, r.stdout[-200:])

    print("== validasi DB pipeline ==")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) n FROM trademap_trade")
    n_trade = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) n FROM trademap_raw WHERE status='validated'")
    n_raw = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) n FROM trademap_trade WHERE id_trademap_raw IS NULL")
    n_orphan = cur.fetchone()["n"]
    cur.execute("SELECT value_usd, qty, product_code FROM trademap_trade WHERE reporter='ID' AND partner='US' AND product_code='030617' AND year=2024")
    row = cur.fetchone()
    conn.close()
    check("trade terisi (8)", n_trade == 8, str(n_trade))
    check("raw validated ada", n_raw >= 1, str(n_raw))
    check("tidak ada orphan raw", n_orphan == 0, str(n_orphan))
    check("value & qty tersimpan benar",
          row and str(row["value_usd"]) == "980000.0000" and str(row["qty"]) == "135000.0000",
          str(dict(row) if row else None))

    print("== API /api/trademap/summary ==")
    r = c.get("/api/trademap/summary", headers=H)
    check("summary 200", r.status_code == 200, r.get_data(as_text=True)[:150])
    d = r.get_json()
    check("summary total 8", d["totals"]["baris"] == 8, str(d["totals"]))
    check("summary produk unik 3", d["totals"]["produk_unik"] == 3, str(d["totals"]["produk_unik"]))
    check("summary top partner US", d["top_partner"][0]["partner"] == "US", str(d["top_partner"][:1]))
    check("summary per_tahun 2", len(d["per_tahun"]) == 2)

    r = c.get("/api/trademap/summary?product_code=030617&year_min=2024", headers=H)
    d = r.get_json()
    check("filter product+year", d["totals"]["baris"] == 2, str(d["totals"]))

    print("== API /api/trademap/rows ==")
    r = c.get("/api/trademap/rows?limit=3&page=1", headers=H)
    check("rows 200", r.status_code == 200)
    d = r.get_json()
    check("rows total 8", d["total"] == 8)
    check("rows len 3", len(d["rows"]) == 3)
    check("rows punya value_usd", all("value_usd" in x for x in d["rows"]))

    print("== proteksi ==")
    check("summary tanpa token 401", c.get("/api/trademap/summary").status_code == 401)
    check("summary token asal 401", c.get("/api/trademap/summary", headers={"Authorization": "Bearer x"}).status_code == 401)

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
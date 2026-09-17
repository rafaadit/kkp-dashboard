#!/usr/bin/env python3
"""PHASE 5 — Test auth backend (login/me/logout + proteksi endpoint)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.app import create_app

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

    # --- login sukses -------------------------------------------------------
    r = c.post("/api/auth/login", json={"email": "admin@kkp.local", "password": "admin123"})
    check("login 200", r.status_code == 200, r.get_data(as_text=True)[:200])
    d = r.get_json()
    check("token non-empty", bool(d.get("token")))
    check("user email benar", d["user"]["email"] == "admin@kkp.local")
    H = {"Authorization": f"Bearer {d['token']}"}

    # --- login gagal --------------------------------------------------------
    check("password salah 401",
          c.post("/api/auth/login", json={"email": "admin@kkp.local", "password": "x12345"}).status_code == 401)
    check("email tak ada 401",
          c.post("/api/auth/login", json={"email": "none@kkp.local", "password": "admin123"}).status_code == 401)
    check("body kosong 400",
          c.post("/api/auth/login", json={}).status_code == 400)
    check("format bukan json 400",
          c.post("/api/auth/login", data="not json", content_type="application/json").status_code in (400, 415))

    # --- me ----------------------------------------------------------------
    r = c.get("/api/auth/me", headers=H)
    check("me 200", r.status_code == 200)
    me = r.get_json()["user"]
    check("role super_admin", me["role"] == "super_admin")
    check("permissions non-empty", len(me["permissions"]) > 10)
    check("punya explore.view", "explore.view" in me["permissions"])
    check("punya admin.users", "admin.users" in me["permissions"])

    # --- proteksi endpoint --------------------------------------------------
    check("tanpa token 401", c.get("/api/explore/overview").status_code == 401)
    check("token asal 401", c.get("/api/explore/overview", headers={"Authorization": "Bearer abc"}).status_code == 401)

    # --- logout -> token tidak valid lagi -----------------------------------
    r = c.post("/api/auth/logout", headers=H)
    check("logout 200", r.status_code == 200)
    check("me setelah logout 401", c.get("/api/auth/me", headers=H).status_code == 401)
    check("explore setelah logout 401", c.get("/api/explore/overview", headers=H).status_code == 401)

    # token asli masih hidup? (simulasi token lain)
    r2 = c.post("/api/auth/login", json={"email": "admin@kkp.local", "password": "admin123"})
    H2 = {"Authorization": f"Bearer {r2.get_json()['token']}"}
    check("login kedua 200", c.get("/api/auth/me", headers=H2).status_code == 200)

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
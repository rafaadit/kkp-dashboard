#!/usr/bin/env python3
"""PHASE 8 — Test RBAC: admin kelola akun + batas akses user/pegawai/super_admin."""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.app import create_app
from backend.db import get_connection

PASS = 0
FAIL = 0
CREATED = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None
    return {"Authorization": f"Bearer {r.get_json()['token']}"}


def cleanup():
    if not CREATED:
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        for uid in CREATED:
            cur.execute("DELETE FROM app_user_tokens WHERE app_user_id=%s", (uid,))
            cur.execute("DELETE FROM app_users WHERE id=%s", (uid,))
        conn.commit()
    finally:
        conn.close()


def main():
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    H = login(c, "admin@kkp.local", "admin123")
    check("login admin", H is not None)
    if not H:
        return 1

    # --- role katalog -------------------------------------------------------
    r = c.get("/api/admin/roles", headers=H)
    check("roles 200", r.status_code == 200, r.get_data(as_text=True)[:200])
    roles = {x["kode"]: x for x in r.get_json().get("roles", [])}
    check("3 role tersedia", set(roles) >= {"user", "pegawai", "super_admin"}, roles.keys())
    check("user 13 izin", roles.get("user", {}).get("jumlah_permission") == 13,
          roles.get("user"))
    check("pegawai 23 izin", roles.get("pegawai", {}).get("jumlah_permission") == 23,
          roles.get("pegawai"))
    check("super_admin 28 izin", roles.get("super_admin", {}).get("jumlah_permission") == 28,
          roles.get("super_admin"))

    # --- buat akun user & pegawai ------------------------------------------
    tag = uuid.uuid4().hex[:8]
    accounts = {}
    for role in ("user", "pegawai"):
        email = f"rbac_{role}_{tag}@kkp.local"
        r = c.post("/api/admin/users", headers=H, json={
            "nama": f"RBAC {role}",
            "email": email,
            "password": "rahasia123",
            "role": role,
        })
        check(f"create {role} 201", r.status_code == 201, r.get_data(as_text=True)[:200])
        if r.status_code == 201:
            accounts[role] = {"id": r.get_json()["user"]["id"], "email": email}
            CREATED.append(accounts[role]["id"])
    check("create 2 akun", len(accounts) == 2)

    dup = accounts.get("user", {}).get("email")
    if dup:
        r = c.post("/api/admin/users", headers=H, json={
            "nama": "Dup", "email": dup, "password": "rahasia123", "role": "user"})
        check("email duplikat 409", r.status_code == 409, r.status_code)

    r = c.get("/api/admin/users?q=" + tag, headers=H)
    check("list users terfilter", r.status_code == 200 and r.get_json()["total"] == 2,
          r.get_data(as_text=True)[:200])

    # --- permission matrix --------------------------------------------------
    hu = login(c, accounts["user"]["email"], "rahasia123")
    hp = login(c, accounts["pegawai"]["email"], "rahasia123")
    check("login user", hu is not None)
    check("login pegawai", hp is not None)

    checks = [
        ("user explore.view", c.get("/api/explore/overview", headers=hu).status_code, 200),
        ("user data.view", c.get("/api/data/raw_exim?limit=1", headers=hu).status_code, 200),
        ("user tidak boleh admin", c.get("/api/admin/users", headers=hu).status_code, 403),
        ("user tidak boleh generate PPT", c.post(
            "/api/report/generate_ppt", headers=hu,
            json={"tahun": 2026, "bulan_awal": 1, "bulan_akhir": 6}).status_code, 403),
        ("user tidak boleh upload BPS", c.post(
            "/api/data/bps/upload", headers=hu, data={},
            content_type="multipart/form-data").status_code, 403),
        ("pegawai boleh lihat BPS", c.get("/api/data/bps/summary", headers=hp).status_code, 200),
        ("pegawai tidak boleh admin", c.get("/api/admin/users", headers=hp).status_code, 403),
        ("pegawai upload tanpa file 400", c.post(
            "/api/data/bps/upload", headers=hp, data={},
            content_type="multipart/form-data").status_code, 400),
    ]
    for name, got, want in checks:
        check(name, got == want, f"got {got}, want {want}")

    # --- update role --------------------------------------------------------
    uid = accounts["user"]["id"]
    r = c.put(f"/api/admin/users/{uid}", headers=H, json={"role": "pegawai"})
    check("promote user->pegawai", r.status_code == 200 and r.get_json()["user"]["role"] == "pegawai",
          r.get_data(as_text=True)[:200])
    r = c.get("/api/admin/users/" + str(uid), headers=H)
    perms = r.get_json().get("user", {}).get("permissions", [])
    check("permission ikut berubah", "data.update_bps_export" in perms, perms[:5])

    # --- reset password -----------------------------------------------------
    r = c.post(f"/api/admin/users/{uid}/reset-password", headers=H,
               json={"password": "barupass123"})
    check("reset password 200", r.status_code == 200, r.get_data(as_text=True)[:200])
    check("login pass lama 401",
          c.post("/api/auth/login", json={"email": accounts["user"]["email"],
                                          "password": "rahasia123"}).status_code == 401)
    check("login pass baru 200",
          c.post("/api/auth/login", json={"email": accounts["user"]["email"],
                                          "password": "barupass123"}).status_code == 200)

    # --- nonaktifkan akun ---------------------------------------------------
    r = c.put(f"/api/admin/users/{uid}", headers=H, json={"is_active": False})
    check("nonaktifkan 200", r.status_code == 200 and r.get_json()["user"]["is_active"] is False,
          r.get_data(as_text=True)[:200])
    check("login nonaktif 401",
          c.post("/api/auth/login", json={"email": accounts["user"]["email"],
                                          "password": "barupass123"}).status_code == 401)
    r = c.put(f"/api/admin/users/{uid}", headers=H, json={"is_active": True})
    check("aktifkan lagi 200", r.status_code == 200 and r.get_json()["user"]["is_active"] is True)

    # --- guard akun sendiri -------------------------------------------------
    me = c.get("/api/auth/me", headers=H).get_json()["user"]
    r = c.put(f"/api/admin/users/{me['user_id']}", headers=H, json={"role": "user"})
    check("tidak bisa demote diri", r.status_code == 400, r.status_code)
    r = c.put(f"/api/admin/users/{me['user_id']}", headers=H, json={"is_active": False})
    check("tidak bisa nonaktifkan diri", r.status_code == 400, r.status_code)

    # --- validasi input -----------------------------------------------------
    r = c.post("/api/admin/users", headers=H, json={
        "nama": "X", "email": "bukan-email", "password": "123456", "role": "user"})
    check("email invalid 400", r.status_code == 400, r.status_code)
    r = c.post("/api/admin/users", headers=H, json={
        "nama": "Nama Ok", "email": f"rbac_bad_{tag}@kkp.local",
        "password": "123", "role": "user"})
    check("password pendek 400", r.status_code == 400, r.status_code)
    r = c.post("/api/admin/users", headers=H, json={
        "nama": "Nama Ok", "email": f"rbac_bad2_{tag}@kkp.local",
        "password": "123456", "role": "tidak_ada"})
    check("role invalid 400", r.status_code == 400, r.status_code)

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        cleanup()
    sys.exit(code)

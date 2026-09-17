#!/usr/bin/env python3
"""
Bootstrap user admin (super_admin) — dibuat via script, BUKAN di-seed (anti plaintext password).

Usage:
    python3 database/scripts/create_admin.py --email admin@kkp.local --password 'S3cret!' --nama 'Admin KKP'
    python3 database/scripts/create_admin.py            # pakai ADMIN_EMAIL/ADMIN_PASSWORD dari .env

Idempotent: jika email sudah ada, password & role di-update (bukan duplikat).
"""
import argparse
import os
import sys

sys.path.insert(0, "/".join(__file__.split("/")[:-3]))
sys.path.insert(0, "backend")  # backend/db.py

import bcrypt
import pymysql  # noqa: F401  (di-import db.py)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", "admin@kkp.local"))
    ap.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", "admin123"))
    ap.add_argument("--nama", default="Admin KKP")
    args = ap.parse_args()

    if len(args.password) < 6:
        print("PASSWORD terlalu pendek (min 6 karakter)")
        sys.exit(1)

    from backend.db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM app_roles WHERE kode = 'super_admin'")
    role = cur.fetchone()
    if not role:
        print("role super_admin tidak ditemukan — jalankan database/seeds/010_app_roles_permissions.sql dulu")
        sys.exit(1)

    pw_hash = bcrypt.hashpw(args.password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    email = args.email.strip().lower()
    cur.execute(
        """INSERT INTO app_users (nama, email, password_hash, app_role_id, is_active)
           VALUES (%s, %s, %s, %s, 1)
           ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash),
               nama = VALUES(nama), app_role_id = VALUES(app_role_id), is_active = 1""",
        (args.nama, email, pw_hash, role["id"]),
    )
    conn.commit()
    n = cur.rowcount
    conn.close()
    print(f"OK: user {email} → super_admin ({'inserted' if n == 1 else 'updated'})")


if __name__ == "__main__":
    main()
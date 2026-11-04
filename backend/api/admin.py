"""PHASE 8 — Administrasi akun & role (khusus super_admin / admin.users).

Endpoint:
    GET    /api/admin/roles                 daftar role + jumlah permission
    GET    /api/admin/users                 daftar akun (filter q/role/active)
    GET    /api/admin/users/<id>            detail satu akun
    POST   /api/admin/users                 buat akun baru
    PUT    /api/admin/users/<id>            ubah nama/email/role/status
    POST   /api/admin/users/<id>/reset-password
    GET    /api/admin/audit                 audit log terbaru (admin.users)

Semua aksi tulis dicatat di audit_logs. Guard:
    * tidak boleh menonaktifkan / menurunkan role akun sendiri
    * tidak boleh menghilangkan super_admin aktif terakhir
"""
import json
import re

from flask import Blueprint, jsonify, request

from backend.db import get_connection
from backend.api.auth import require_perm, session_context
from backend.api.helpers import ApiError, require_limit, require_page

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD = 6


def _iso(v):
    return v.isoformat(sep=" ") if hasattr(v, "isoformat") else v


def _user_row(row):
    """Serialize baris app_users (tanpa password_hash)."""
    return {
        "id": row["id"],
        "nama": row["nama"],
        "email": row["email"],
        "role": row["role_kode"],
        "role_nama": row["role_nama"],
        "app_role_id": row["app_role_id"],
        "is_active": bool(row["is_active"]),
        "last_login_at": _iso(row.get("last_login_at")),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


_USER_SELECT = """
    SELECT u.id, u.nama, u.email, u.app_role_id, u.is_active,
           u.last_login_at, u.created_at, u.updated_at,
           r.kode AS role_kode, r.nama AS role_nama
    FROM app_users u
    JOIN app_roles r ON r.id = u.app_role_id
"""


def _audit(cur, user_id, action, entity, entity_id=None, before=None, after=None):
    cur.execute(
        """INSERT INTO audit_logs
           (app_user_id, action, entity, entity_id, before_data, after_data,
            ip_address, user_agent, correlation_id)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            user_id,
            action,
            entity,
            str(entity_id) if entity_id is not None else None,
            json.dumps(before, default=str) if before is not None else None,
            json.dumps(after, default=str) if after is not None else None,
            (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:45],
            (request.headers.get("User-Agent") or "")[:255],
            None,
        ),
    )


def _active_super_admins(cur, exclude_id=None):
    sql = (
        "SELECT COUNT(*) AS n FROM app_users u "
        "JOIN app_roles r ON r.id = u.app_role_id "
        "WHERE r.kode='super_admin' AND u.is_active=1"
    )
    params = []
    if exclude_id is not None:
        sql += " AND u.id<>%s"
        params.append(exclude_id)
    cur.execute(sql, params)
    return cur.fetchone()["n"]


def _role_by_kode(cur, kode):
    cur.execute(
        "SELECT id, kode, nama FROM app_roles WHERE kode=%s AND is_active=1",
        (kode,),
    )
    return cur.fetchone()


def _parse_user_id(raw):
    try:
        uid = int(raw)
    except (TypeError, ValueError):
        raise ApiError("id akun tidak valid")
    if uid < 1:
        raise ApiError("id akun tidak valid")
    return uid


def _norm_email(raw):
    email = (raw or "").strip().lower()
    if not email or not _EMAIL_RE.match(email):
        raise ApiError("email tidak valid")
    return email


def _norm_nama(raw):
    nama = (raw or "").strip()
    if len(nama) < 2:
        raise ApiError("nama minimal 2 karakter")
    return nama[:150]


def _check_password(raw):
    pw = raw or ""
    if len(pw) < _MIN_PASSWORD:
        raise ApiError(f"password minimal {_MIN_PASSWORD} karakter")
    return pw


def _hash_password(pw):
    import bcrypt

    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


@admin_bp.get("/roles")
@require_perm("admin.users")
def roles():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT r.id, r.kode, r.nama, r.deskripsi,
                      COUNT(rp.id) AS jumlah_permission
               FROM app_roles r
               LEFT JOIN app_role_permissions rp ON rp.app_role_id = r.id
               WHERE r.is_active = 1
               GROUP BY r.id, r.kode, r.nama, r.deskripsi
               ORDER BY r.id"""
        )
        data = [
            {
                "id": r["id"],
                "kode": r["kode"],
                "nama": r["nama"],
                "deskripsi": r["deskripsi"],
                "jumlah_permission": int(r["jumlah_permission"] or 0),
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
    return jsonify({"roles": data})


@admin_bp.get("/users")
@require_perm("admin.users")
def list_users():
    limit = require_limit(request, default=25, maximum=200)
    page = require_page(request)
    where, params = [], []

    q = (request.args.get("q") or "").strip()
    if q:
        where.append("(u.nama LIKE %s OR u.email LIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    role = (request.args.get("role") or "").strip()
    if role:
        where.append("r.kode = %s")
        params.append(role)
    active = request.args.get("active")
    if active in ("0", "1"):
        where.append("u.is_active = %s")
        params.append(int(active))

    w = (" WHERE " + " AND ".join(where)) if where else ""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) AS n FROM app_users u JOIN app_roles r ON r.id=u.app_role_id{w}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            _USER_SELECT + w + " ORDER BY u.is_active DESC, u.nama ASC LIMIT %s OFFSET %s",
            params + [limit, (page - 1) * limit],
        )
        users = [_user_row(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(
        {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total else 0,
            "users": users,
        }
    )


@admin_bp.get("/users/<uid>")
@require_perm("admin.users")
def get_user(uid):
    uid = _parse_user_id(uid)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_USER_SELECT + " WHERE u.id=%s", (uid,))
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise ApiError("akun tidak ditemukan", 404)
    data = _user_row(row)
    data["permissions"] = _permissions_for_role(data["app_role_id"])
    return jsonify({"user": data})


def _permissions_for_role(role_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT p.kode FROM app_role_permissions rp "
            "JOIN app_permissions p ON p.id = rp.app_permission_id "
            "WHERE rp.app_role_id=%s AND p.is_active=1 ORDER BY p.kode",
            (role_id,),
        )
        return [r["kode"] for r in cur.fetchall()]
    finally:
        conn.close()


@admin_bp.post("/users")
@require_perm("admin.users")
def create_user():
    body = request.get_json(silent=True) or {}
    nama = _norm_nama(body.get("nama"))
    email = _norm_email(body.get("email"))
    password = _check_password(body.get("password"))
    role = _role_by_kode_or_error(body.get("role"))

    actor = session_context()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM app_users WHERE email=%s", (email,))
        if cur.fetchone():
            raise ApiError("email sudah digunakan", 409)
        cur.execute(
            "INSERT INTO app_users (nama, email, password_hash, app_role_id, is_active) "
            "VALUES (%s,%s,%s,%s,1)",
            (nama, email, _hash_password(password), role["id"]),
        )
        uid = cur.lastrowid
        _audit(cur, actor["user_id"], "admin.user.create", "app_users", uid,
               after={"nama": nama, "email": email, "role": role["kode"]})
        conn.commit()
        cur.execute(_USER_SELECT + " WHERE u.id=%s", (uid,))
        user = _user_row(cur.fetchone())
    finally:
        conn.close()
    return jsonify({"user": user}), 201


def _role_by_kode_or_error(kode):
    kode = (kode or "").strip()
    if not kode:
        raise ApiError("role wajib dipilih")
    conn = get_connection()
    try:
        role = _role_by_kode(conn.cursor(), kode)
    finally:
        conn.close()
    if not role:
        raise ApiError(f"role tidak dikenal: {kode}")
    return role


@admin_bp.put("/users/<uid>")
@require_perm("admin.users")
def update_user(uid):
    uid = _parse_user_id(uid)
    body = request.get_json(silent=True) or {}
    actor = session_context()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_USER_SELECT + " WHERE u.id=%s", (uid,))
        row = cur.fetchone()
        if not row:
            raise ApiError("akun tidak ditemukan", 404)
        before = _user_row(row)

        fields, params, after = [], [], {}
        if "nama" in body and body.get("nama") is not None:
            fields.append("nama=%s")
            params.append(_norm_nama(body.get("nama")))
            after["nama"] = params[-1]
        if "email" in body and body.get("email") is not None:
            email = _norm_email(body.get("email"))
            cur.execute("SELECT id FROM app_users WHERE email=%s AND id<>%s", (email, uid))
            if cur.fetchone():
                raise ApiError("email sudah digunakan", 409)
            fields.append("email=%s")
            params.append(email)
            after["email"] = email

        new_role = before["role"]
        if "role" in body and body.get("role") is not None:
            role = _role_by_kode_or_error(body.get("role"))
            new_role = role["kode"]
            fields.append("app_role_id=%s")
            params.append(role["id"])
            after["role"] = new_role

        new_active = before["is_active"]
        if "is_active" in body and body.get("is_active") is not None:
            raw = body.get("is_active")
            if isinstance(raw, str):
                raw = raw.lower() in ("1", "true", "ya", "yes", "on")
            new_active = bool(raw)
            fields.append("is_active=%s")
            params.append(1 if new_active else 0)
            after["is_active"] = new_active

        if not fields:
            raise ApiError("tidak ada perubahan")

        is_self = uid == actor["user_id"]
        if is_self and (new_role != before["role"] or new_active != before["is_active"]):
            raise ApiError("tidak boleh mengubah role/status akun sendiri")

        # Jangan sampai super_admin aktif terakhir hilang.
        if (before["role"] == "super_admin" and before["is_active"]
                and (new_role != "super_admin" or not new_active)
                and _active_super_admins(cur, exclude_id=uid) == 0):
            raise ApiError("harus ada minimal satu super_admin aktif")

        params.append(uid)
        cur.execute(f"UPDATE app_users SET {', '.join(fields)} WHERE id=%s", params)

        # Akun dinonaktifkan -> cabut semua token agar sesi berjalan langsung putus.
        if before["is_active"] and not new_active:
            cur.execute(
                "UPDATE app_user_tokens SET revoked_at=NOW() "
                "WHERE app_user_id=%s AND revoked_at IS NULL",
                (uid,),
            )

        _audit(cur, actor["user_id"], "admin.user.update", "app_users", uid,
               before=before, after=after)
        conn.commit()
        cur.execute(_USER_SELECT + " WHERE u.id=%s", (uid,))
        user = _user_row(cur.fetchone())
    finally:
        conn.close()
    return jsonify({"user": user})


@admin_bp.post("/users/<uid>/reset-password")
@require_perm("admin.users")
def reset_password(uid):
    uid = _parse_user_id(uid)
    body = request.get_json(silent=True) or {}
    password = _check_password(body.get("password"))
    actor = session_context()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, email FROM app_users WHERE id=%s", (uid,))
        row = cur.fetchone()
        if not row:
            raise ApiError("akun tidak ditemukan", 404)
        cur.execute("UPDATE app_users SET password_hash=%s WHERE id=%s", (_hash_password(password), uid))
        cur.execute(
            "UPDATE app_user_tokens SET revoked_at=NOW() "
            "WHERE app_user_id=%s AND revoked_at IS NULL",
            (uid,),
        )
        _audit(cur, actor["user_id"], "admin.user.reset_password", "app_users", uid,
               after={"email": row["email"]})
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "password diperbarui", "id": uid})


@admin_bp.get("/audit")
@require_perm("admin.users")
def audit_list():
    limit = require_limit(request, default=25, maximum=100)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT a.id, a.app_user_id, u.nama AS user_nama, a.action, a.entity,
                      a.entity_id, a.before_data, a.after_data, a.ip_address,
                      a.created_at
               FROM audit_logs a
               LEFT JOIN app_users u ON u.id = a.app_user_id
               ORDER BY a.id DESC LIMIT %s""",
            (limit,),
        )
        rows = []
        for r in cur.fetchall():
            rows.append({
                "id": r["id"],
                "app_user_id": r["app_user_id"],
                "user_nama": r["user_nama"],
                "action": r["action"],
                "entity": r["entity"],
                "entity_id": r["entity_id"],
                "ip_address": r["ip_address"],
                "created_at": _iso(r["created_at"]),
            })
    finally:
        conn.close()
    return jsonify({"audit": rows})

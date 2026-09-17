"""PHASE 5 — Auth API (login/logout/me) + helper proteksi endpoint.

Token disimpan sebagai SHA-256 hash (bukan plaintext) di app_user_tokens;
password diverifikasi dengan bcrypt (12 rounds).
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, jsonify, request

from backend.db import get_connection
from backend.api.helpers import ApiError, row_to_dict
from backend.api.auth_config import TOKEN_TTL_HOURS

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_HEADER_PREFIX = "Bearer "


def _hash_token(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _token_from_request():
    h = request.headers.get("Authorization", "")
    if h and h.startswith(_HEADER_PREFIX):
        return h[len(_HEADER_PREFIX):].strip()
    # fallback param (mudah diuji via curl)
    return request.args.get("token", "").strip() or None


def _load_session(raw_token):
    """Validasi token -> dict user + set permission, atau None."""
    if not raw_token:
        return None
    token_hash = _hash_token(raw_token)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT t.token_hash, t.expires_at, t.revoked_at, u.id, u.nama, u.email,
                      u.is_active, u.app_role_id, r.kode AS role_kode, r.nama AS role_nama
               FROM app_user_tokens t
               JOIN app_users u ON u.id = t.app_user_id
               JOIN app_roles r ON r.id = u.app_role_id
               WHERE t.token_hash = %s""",
            (token_hash,),
        )
        row = cur.fetchone()
        if not row:
            return None
        expired = (row["expires_at"] and row["expires_at"] < datetime.utcnow() - timedelta(hours=0))
        if row["revoked_at"] or expired or not row["is_active"]:
            return None
        cur.execute(
            "SELECT p.kode FROM app_role_permissions rp "
            "JOIN app_permissions p ON p.id = rp.app_permission_id "
            "WHERE rp.app_role_id = %s AND p.is_active = 1",
            (row["app_role_id"],),
        )
        perms = [r["kode"] for r in cur.fetchall()]
        return {
            "user_id": row["id"],
            "nama": row["nama"],
            "email": row["email"],
            "role": row["role_kode"],
            "role_nama": row["role_nama"],
            "permissions": perms,
        }
    finally:
        conn.close()


def require_auth(fn):
    """Wajib login (token valid). Inject context via request.environ['auth_session']."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        sess = _load_session(_token_from_request())
        if not sess:
            return jsonify({"error": "unauthorized: token tidak valid atau kedaluwarsa"}), 401
        request.environ["auth_session"] = sess
        return fn(*args, **kwargs)

    return wrapper


def require_perm(*kodes):
    """Wajib login + minimal salah satu permission (atau super_admin)."""

    def deco(fn):
        @wraps(fn)
        @require_auth
        def wrapper(*args, **kwargs):
            sess = request.environ["auth_session"]
            if sess["role"] != "super_admin" and not set(kodes) & set(sess["permissions"]):
                return jsonify({"error": "forbidden: permission diperlukan: " + ", ".join(kodes)}), 403
            return fn(*args, **kwargs)

        return wrapper

    return deco


def session_context():
    return request.environ.get("auth_session")


@auth_bp.get("/me")
@require_auth
def me():
    sess = session_context()
    return jsonify({"user": sess})


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        raise ApiError("email dan password wajib diisi", 400)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nama, email, password_hash, app_role_id, is_active "
            "FROM app_users WHERE email = %s",
            (email,),
        )
        user = cur.fetchone()
        if not user or not user["is_active"]:
            conn.close()
            raise ApiError("email atau password salah", 401)

        import bcrypt

        if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            conn.close()
            raise ApiError("email atau password salah", 401)

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires = datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)
        cur.execute(
            "INSERT INTO app_user_tokens (app_user_id, token_hash, token_type, expires_at) "
            "VALUES (%s, %s, 'session', %s)",
            (user["id"], token_hash, expires),
        )
        cur.execute("UPDATE app_users SET last_login_at = NOW() WHERE id = %s", (user["id"],))
        conn.commit()
        conn.close()
        return jsonify({"token": raw_token, "expires_at": expires.isoformat() + "Z", "user": {"id": user["id"], "nama": user["nama"], "email": user["email"]}})
    finally:
        try:
            conn.close()
        except Exception:
            pass


@auth_bp.post("/logout")
@require_auth
def logout():
    raw = _token_from_request()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE app_user_tokens SET revoked_at = NOW() WHERE token_hash = %s",
            (_hash_token(raw),),
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "logged out"})
    finally:
        try:
            conn.close()
        except Exception:
            pass
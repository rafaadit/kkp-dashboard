"""
PROJECT KKP — shared DB connection / env helpers.
Sumber konfigurasi: environment (.env) dengan default dev (DBngin local).
"""
import json
import os
from urllib.parse import urlparse

import pymysql


def load_dotenv(path=None):
    """Load key=value dari file .env (tanpa dependency python-dotenv)."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("\"'")
            os.environ.setdefault(key, val)


load_dotenv()


def get_connection(cursorclass=None):
    """Koneksi pymysql ke database utama (kkp_exim_platform)."""
    kwargs = dict(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "kkp_exim_platform"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=cursorclass or pymysql.cursors.DictCursor,
    )
    sock = os.environ.get("DB_SOCKET")
    if sock:
        kwargs["unix_socket"] = sock
        kwargs.pop("host", None)
        kwargs.pop("port", None)
    return pymysql.connect(**kwargs)


def get_legacy_connection():
    """Koneksi ke database legacy eksim_system (read-only reference)."""
    kwargs = dict(
        host=os.environ.get("LEGACY_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("LEGACY_DB_PORT", "3306")),
        user=os.environ.get("LEGACY_DB_USER", "root"),
        password=os.environ.get("LEGACY_DB_PASSWORD", ""),
        database=os.environ.get("LEGACY_DB_NAME", "eksim_system"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )
    sock = os.environ.get("LEGACY_DB_SOCKET")
    if sock:
        kwargs["unix_socket"] = sock
        kwargs.pop("host", None)
        kwargs.pop("port", None)
    return pymysql.connect(**kwargs)
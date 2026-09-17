"""Konfigurasi auth (dibaca dari .env, default aman)."""
import os

TOKEN_TTL_HOURS = int(os.environ.get("TOKEN_TTL_HOURS", "24"))
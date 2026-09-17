#!/usr/bin/env python3
"""
PHASE 4 — Backend API eksplorasi data.

Framework: Flask (Python).  Data: kkp_exim_platform (bps_export/bps_import/raw_exim).

Endpoint (JSON):
    GET /health                       status server + versi
    GET /api/explore/overview         Total nilai/volume ekspor-impor + breakdown kelompok
    GET /api/explore/komoditas        Top komoditas_5_2026 (nilai, volume, tren)
    GET /api/explore/negara           Top negara tujuan/asal + kelompok negara
    GET /api/explore/perbandingan     Perbandingan 2 rentang periode (nilai, pertumbuhan)
    GET /api/explore/kelompok         Big 4 kode_kelompok ekspor (verifikasi vs PPT)
    GET /api/data/raw_exim            Browse baris raw_exim (pagination + filter)

Common query params:
    exim           ekspor|impor            (default ekspor)
    mulai          YYYY-MM periode awal    (default earliest)
    akhir          YYYY-MM periode akhir   (default latest)
    kelompok       I|II|III|IV             (opsional)
    komoditas      nama komoditas_5_2026   (opsional, LIKE)
    negara         kode_negara             (opsional)
    limit / page   (untuk list)

Jalankan:
    .venv/bin/python backend/api/app.py [--port 8000]
Test:
    python3 tests/test_api.py
"""
import os
import sys

from flask import Flask, jsonify, request

# biarkan import kompatibel: `python backend/api/app.py` dan `python -m backend.api.app`
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.db import get_connection  # noqa: E402
from backend.api.explore import explore_bp  # noqa: E402
from backend.api.data import data_bp  # noqa: E402
from backend.api.auth import auth_bp  # noqa: E402
from backend.api.trademap import trademap_bp  # noqa: E402
from backend.api.report import report_bp  # noqa: E402
from backend.api.ai import ai_bp  # noqa: E402
from backend.api.helpers import ApiError  # noqa: E402

API_VERSION = "1.0.0"


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    @app.get("/health")
    def health():
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            conn.close()
            db = "ok"
        except Exception as e:  # noqa: BLE001
            db = f"error: {e}"
        return jsonify({"status": "ok", "api_version": API_VERSION, "db": db})

    app.register_blueprint(explore_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(trademap_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(ai_bp)

    @app.errorhandler(ApiError)
    def handle_apierror(err):
        return jsonify({"error": err.message}), err.status

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "endpoint tidak ditemukan"}), 404

    @app.errorhandler(Exception)
    def unhandled(err):  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"internal error: {err}"}), 500

    return app


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=int(os.environ.get("APP_PORT", "8000")))
    args = ap.parse_args()
    app = create_app()
    print(f"[api] KKP EXIM API v{API_VERSION} di 127.0.0.1:{args.port}")
    # access log membantu debugging; cukup concise
    app.run(host="127.0.0.1", port=args.port, debug=(os.environ.get("APP_DEBUG") == "true"))


if __name__ == "__main__":
    main()
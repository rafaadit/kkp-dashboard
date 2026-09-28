"""PHASE 4 — Endpoint browse/data mentah raw_exim (pagination + filter)."""
from flask import Blueprint, jsonify, request

from backend.db import get_connection
from backend.api.auth import require_perm
from backend.api.explore import _filters
from backend.api.helpers import (
    require_limit,
    require_page,
    row_to_dict,
)

data_bp = Blueprint("data", __name__, url_prefix="/api/data")

_BROWSE_COLS = [
    "r.id",
    "r.exim_type",
    "r.tahun",
    "r.bulan",
    "r.tahun_bulan AS periode",
    "r.kode_hs_2022 AS kode_hs",
    "r.kode_hs_2dg",
    "h.kelompok_komoditas AS komoditas",
    "h.jenis_produk AS jenis",
    "h.bentuk_produk_id AS bentuk",
    "h.bentuk_produk_en AS bentuk_en",
    "h.jenis_pengolahan AS pengolahan",
    "r.uraian",
    "r.non_konsumsi_konsumsi",
    "r.olahan_bukan",
    "h.asal_bahan_baku AS asal_bahan_baku",
    "r.kode_prov_asal",
    "r.provinsi_asal",
    "r.pulau_prov_asal",
    "r.kode_pelabuhan_muat",
    "r.pelabuhan_muat_bongkar",
    "r.moda",
    "r.kode_provinsi_pelabuhan",
    "r.provinsi_pelabuhan",
    "r.pulau_prov_pelabuhan",
    "r.kode_negara",
    "r.negara",
    "r.kelompok_negara",
    "r.vol_kg",
    "r.nil_usd",
    "r.harga_usd_kg",
    "r.ttc",
    "r.rendemen",
    "r.setara_segar",
    "r.koding",
    "r.kurs_usd",
    "r.nilai_rp",
    "r.status",
]


@data_bp.get("/raw_exim")
@require_perm("data.view", "exim.view")
def raw_exim():
    """Browse baris raw_exim (default: ekspor). Filter: exim, mulai, akhir, kelompok,
    negara, komoditas, status. Pagination: page & limit."""
    limit = require_limit(request, default=20, maximum=200)
    page = require_page(request)

    where, params = _filters(request)
    if request.args.get("status"):
        where.append("r.status = %s")
        params.append(request.args["status"].strip())
    w = " AND ".join(where)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) AS n FROM raw_exim r WHERE {w}", params)
        total = cur.fetchone()["n"]
        offset = (page - 1) * limit
        cur.execute(
            f"SELECT {', '.join(_BROWSE_COLS)} FROM raw_exim r "
            f"JOIN ms_hscode h ON h.kode_hs = r.kode_hs_2022 "
            f"WHERE {w} ORDER BY r.tahun DESC, r.bulan DESC, r.id DESC "
            "LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        rows = [row_to_dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify(
            {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total else 0,
                "filter": {
                    "exim": request.args.get("exim", "ekspor"),
                    "mulai": request.args.get("mulai"),
                    "akhir": request.args.get("akhir"),
                    "kelompok": request.args.get("kelompok"),
                    "negara": request.args.get("negara"),
                    "komoditas": request.args.get("komoditas"),
                    "status": request.args.get("status"),
                },
                "rows": rows,
            }
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass
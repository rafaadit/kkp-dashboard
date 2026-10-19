"""PHASE 4 — Endpoint browse/data mentah raw_exim (pagination + filter)."""
import io

import pymysql
from flask import Blueprint, jsonify, request, send_file

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

_EXPORT_LABELS = {
    "id": "ID", "exim_type": "Exim", "tahun": "Tahun", "bulan": "Bulan",
    "periode": "Periode", "kode_hs": "Kode HS", "kode_hs_2dg": "HS 2dg",
    "komoditas": "Komoditas", "jenis": "Jenis", "bentuk": "Bentuk",
    "bentuk_en": "Bentuk (EN)", "pengolahan": "Pengolahan", "uraian": "Uraian",
    "non_konsumsi_konsumsi": "Konsumsi/K", "olahan_bukan": "Olahan",
    "asal_bahan_baku": "Asal Bahan Baku", "kode_prov_asal": "Kode Prov Asal",
    "provinsi_asal": "Provinsi Asal", "pulau_prov_asal": "Pulau Prov Asal",
    "kode_pelabuhan_muat": "Kode Pelabuhan",
    "pelabuhan_muat_bongkar": "Pelabuhan Muat/Bongkar", "moda": "Moda",
    "kode_provinsi_pelabuhan": "Kode Prov Pelabuhan",
    "provinsi_pelabuhan": "Provinsi Pelabuhan",
    "pulau_prov_pelabuhan": "Pulau Prov Pelabuhan",
    "kode_negara": "Kode Negara", "negara": "Negara",
    "kelompok_negara": "Kelompok Negara", "vol_kg": "Vol (kg)",
    "nil_usd": "Nilai USD", "harga_usd_kg": "Harga USD/kg", "ttc": "TTC",
    "rendemen": "Rendemen", "setara_segar": "Setara Segar", "koding": "Koding",
    "kurs_usd": "Kurs USD", "nilai_rp": "Nilai Rp", "status": "Status",
}


def _col_key(expr):
    """Ambil nama keluaran (alias) dari ekspresi kolom SELECT."""
    if " AS " in expr:
        return expr.split(" AS ")[-1].strip()
    return expr.split(".")[-1].strip()


def _where(request):
    """Bangun klausa WHERE + params (filter umum + status)."""
    where, params = _filters(request)
    if request.args.get("status"):
        where.append("r.status = %s")
        params.append(request.args["status"].strip())
    return " AND ".join(where), params


@data_bp.get("/raw_exim")
@require_perm("data.view", "exim.view")
def raw_exim():
    """Browse baris raw_exim (default: ekspor). Filter: exim, mulai, akhir, kelompok,
    negara, komoditas, status. Pagination: page & limit."""
    limit = require_limit(request, default=20, maximum=200)
    page = require_page(request)

    w, params = _where(request)

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


@data_bp.get("/raw_exim.xlsx")
@require_perm("data.view", "exim.view")
def raw_exim_xlsx():
    """Export Excel (.xlsx) SELURUH baris raw_exim sesuai filter (tnp pagination).

    Kolom sama dengan endpoint browse; header memakai label Indonesia.
    """
    from openpyxl import Workbook

    w, params = _where(request)
    keys = [_col_key(c) for c in _BROWSE_COLS]
    headers = [_EXPORT_LABELS.get(k, k) for k in keys]

    conn = get_connection(cursorclass=pymysql.cursors.SSDictCursor)
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {', '.join(_BROWSE_COLS)} FROM raw_exim r "
            f"JOIN ms_hscode h ON h.kode_hs = r.kode_hs_2022 "
            f"WHERE {w} ORDER BY r.tahun DESC, r.bulan DESC, r.id DESC",
            params,
        )
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("raw_exim")
        ws.append(headers)
        n = 0
        for row in cur:
            d = row_to_dict(row)
            ws.append([d.get(k) for k in keys])
            n += 1
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        exim = request.args.get("exim", "ekspor")
        mulai = request.args.get("mulai") or "awal"
        akhir = request.args.get("akhir") or "akhir"
        fname = f"raw_exim_{exim}_{mulai}_{akhir}.xlsx"
        return send_file(
            buf,
            mimetype=("application/vnd.openxmlformats-officedocument"
                      ".spreadsheetml.sheet"),
            as_attachment=True,
            download_name=fname,
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass
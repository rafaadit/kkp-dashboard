# -*- coding: utf-8 -*-
"""PHASE 6 — Endpoint TradeMap (ITC): ringkasan + browse trademap_trade."""
import re

from flask import Blueprint, jsonify, request

from backend.db import get_connection
from backend.api.auth import require_perm
from backend.api.explore import _row
from backend.api.helpers import ApiError, require_limit, require_page, row_to_dict

trademap_bp = Blueprint("trademap", __name__, url_prefix="/api/trademap")


def _filters(request):
    where, params = [], []
    if request.args.get("reporter"):
        where.append("reporter = %s")
        params.append(request.args["reporter"].strip())
    if request.args.get("partner"):
        where.append("partner = %s")
        params.append(request.args["partner"].strip())
    if request.args.get("flow"):
        where.append("flow = %s")
        params.append(request.args["flow"].strip())
    if request.args.get("product_code"):
        where.append("product_code LIKE %s")
        params.append(f"%{request.args['product_code'].strip()}%")
    if request.args.get("year_min"):
        where.append("year >= %s")
        params.append(int(request.args["year_min"]))
    if request.args.get("year_max"):
        where.append("year <= %s")
        params.append(int(request.args["year_max"]))
    return where, params


@trademap_bp.get("/summary")
@require_perm("trademap.view")
def summary():
    where, params = _filters(request)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    totals = _row(
        "SELECT COUNT(*) AS baris, COUNT(DISTINCT partner) AS partner_unik, "
        "       COUNT(DISTINCT product_code) AS produk_unik, "
        "       MIN(year) AS tahun_min, MAX(year) AS tahun_max, "
        "       COALESCE(SUM(value_usd),0) AS nilai_usd, COALESCE(SUM(qty),0) AS qty "
        f"FROM trademap_trade{w}",
        params,
    )[0]
    by_year = _row(
        "SELECT year, COUNT(*) AS baris, COALESCE(SUM(value_usd),0) AS nilai_usd, "
        f"COALESCE(SUM(qty),0) AS qty FROM trademap_trade{w} GROUP BY year ORDER BY year",
        params,
    )
    top_partner = _row(
        "SELECT partner, COALESCE(SUM(value_usd),0) AS nilai_usd, COALESCE(SUM(qty),0) AS qty "
        f"FROM trademap_trade{w} GROUP BY partner ORDER BY nilai_usd DESC LIMIT 15",
        params,
    )
    top_product = _row(
        "SELECT product_code, MAX(product_desc) AS product_desc, "
        "       COALESCE(SUM(value_usd),0) AS nilai_usd, COALESCE(SUM(qty),0) AS qty "
        f"FROM trademap_trade{w} GROUP BY product_code ORDER BY nilai_usd DESC LIMIT 15",
        params,
    )
    return jsonify({"totals": totals, "per_tahun": by_year, "top_partner": top_partner, "top_produk": top_product})


@trademap_bp.get("/rows")
@require_perm("trademap.view")
def rows():
    limit = require_limit(request, default=25, maximum=200)
    page = require_page(request)
    where, params = _filters(request)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) AS n FROM trademap_trade{w}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            "SELECT reporter, partner, flow, product_code, product_desc, year, qty, qty_unit, value_usd "
            f"FROM trademap_trade{w} ORDER BY year DESC, value_usd DESC LIMIT %s OFFSET %s",
            params + [limit, (page - 1) * limit],
        )
        data = [row_to_dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({"page": page, "limit": limit, "total": total,
                        "pages": (total + limit - 1) // limit if total else 0, "rows": data})
    finally:
        try:
            conn.close()
        except Exception:
            pass


_FLOW_TM = {"ekspor": "Export", "impor": "Import"}


def _nk(s):
    """Kunci pembanding nama (BPS <-> TradeMap) via normalisasi case/whitespace."""
    return re.sub(r"\s+", " ", s or "").strip().upper()


@trademap_bp.get("/banding")
@require_perm("trademap.view")
def banding():
    """Bandingkan BPS (raw_exim) vs TradeMap (trademap_trade) SISI BERSEBELAHAN.

    Kedua sumber DIBIARKAN terpisah (tidak digabung): BPS = data faktur Bea
    Cukai/BPS (vol kg + nilai USD); TradeMap = data ITC/Comtrade nilai USD
    ternormalisasi dari satuan sumber (mis. US$ thousand). Tabel "banding"
    hanya memasangkan nilai masing-masing sumber pada kunci nama yang sama.
    """
    flow = (request.args.get("flow") or "ekspor").lower()
    if flow not in _FLOW_TM:
        raise ApiError("flow harus ekspor|impor")
    tm_flow = _FLOW_TM[flow]

    tahun = None
    if request.args.get("tahun"):
        tahun = int(request.args["tahun"])
        if tahun < 1900 or tahun > 2100:
            raise ApiError("tahun tidak valid")

    komoditas = (request.args.get("komoditas") or "").strip()
    negara = (request.args.get("negara") or "").strip()
    if not komoditas and not negara:
        raise ApiError("pilih minimal komoditas atau negara sebagai kunci banding")

    # --- blok BPS (raw_exim) ---
    bps_where = ["exim_type = %s"]
    bps_params = [flow]
    if tahun:
        bps_where.append("tahun = %s")
        bps_params.append(tahun)
    if komoditas:
        bps_where.append("komoditas_5_2026 LIKE %s")
        bps_params.append(f"%{komoditas}%")
    if negara:
        bps_where.append("negara LIKE %s")
        bps_params.append(f"%{negara}%")
    bw = " AND ".join(bps_where)

    bps_total = _row(
        "SELECT COUNT(*) AS baris, COALESCE(SUM(vol_kg),0) AS volume_kg, "
        f"COALESCE(SUM(nil_usd),0) AS nilai_usd FROM raw_exim WHERE {bw}",
        bps_params,
    )[0]
    bps_komoditas = _row(
        "SELECT komoditas_5_2026 AS komoditas, COALESCE(SUM(nil_usd),0) AS nilai_usd, "
        "COALESCE(SUM(vol_kg),0) AS volume_kg "
        f"FROM raw_exim WHERE {bw} GROUP BY komoditas_5_2026 "
        "ORDER BY nilai_usd DESC LIMIT 12",
        bps_params,
    )
    bps_negara = _row(
        "SELECT negara, NULLIF(kelompok_negara,'') AS kelompok_negara, "
        "COALESCE(SUM(nil_usd),0) AS nilai_usd, COALESCE(SUM(vol_kg),0) AS volume_kg "
        f"FROM raw_exim WHERE {bw} GROUP BY negara, kelompok_negara "
        "ORDER BY nilai_usd DESC LIMIT 15",
        bps_params,
    )

    # --- blok TradeMap (trademap_trade) ---
    tm_where = ["reporter = 'ID'", "flow = %s"]
    tm_params = [tm_flow]
    if tahun:
        tm_where.append("year = %s")
        tm_params.append(tahun)
    if komoditas:
        tm_where.append("(product_desc LIKE %s OR id_ms_komoditas IN "
                        "(SELECT m.id FROM ms_komoditas m WHERE m.nama LIKE %s))")
        tm_params += [f"%{komoditas}%", f"%{komoditas}%"]
    if negara:
        tm_where.append("(partner LIKE %s OR id_ms_negara IN "
                        "(SELECT n.id FROM ms_negara n WHERE n.nama_negara LIKE %s))")
        tm_params += [f"%{negara}%", f"%{negara}%"]
    tw = " AND ".join(tm_where)

    tm_total = _row(
        "SELECT COUNT(*) AS baris, "
        "COALESCE(SUM(COALESCE(value_usd_norm, value_usd)),0) AS nilai_usd "
        f"FROM trademap_trade WHERE {tw}",
        tm_params,
    )[0]
    tm_komoditas = _row(
        "SELECT m.nama AS komoditas, "
        "COALESCE(SUM(COALESCE(tt.value_usd_norm, tt.value_usd)),0) AS nilai_usd "
        f"FROM trademap_trade tt LEFT JOIN ms_komoditas m ON m.id = tt.id_ms_komoditas "
        f"WHERE {tw} GROUP BY m.nama ORDER BY nilai_usd DESC LIMIT 12",
        tm_params,
    )
    tm_negara = _row(
        "SELECT n.nama_negara AS negara, "
        "COALESCE(SUM(COALESCE(tt.value_usd_norm, tt.value_usd)),0) AS nilai_usd "
        f"FROM trademap_trade tt LEFT JOIN ms_negara n ON n.id = tt.id_ms_negara "
        f"WHERE {tw} GROUP BY n.nama_negara ORDER BY nilai_usd DESC LIMIT 15",
        tm_params,
    )

    # --- pasangan sisi-ber-sisi (tanpa penggabungan nilai) ---
    tm_k = {_nk(r["komoditas"]): r["nilai_usd"] for r in tm_komoditas}
    banding_komoditas = []
    for r in bps_komoditas:
        tmv = tm_k.get(_nk(r["komoditas"]))
        if tmv is None:
            continue
        banding_komoditas.append({
            "komoditas": r["komoditas"],
            "bps_nilai_usd": r["nilai_usd"],
            "bps_volume_kg": r["volume_kg"],
            "trademap_nilai_usd": tmv,
            "rasio_trademap_bps": round(tmv / r["nilai_usd"], 4) if r["nilai_usd"] else None,
        })
    tm_n = {_nk(r["negara"]): r["nilai_usd"] for r in tm_negara}
    banding_negara = []
    for r in bps_negara:
        tmv = tm_n.get(_nk(r["negara"]))
        if tmv is None:
            continue
        banding_negara.append({
            "negara": r["negara"],
            "bps_nilai_usd": r["nilai_usd"],
            "bps_volume_kg": r["volume_kg"],
            "trademap_nilai_usd": tmv,
            "rasio_trademap_bps": round(tmv / r["nilai_usd"], 4) if r["nilai_usd"] else None,
        })

    return jsonify({
        "flow": flow,
        "tahun": tahun,
        "filter": {"komoditas": komoditas or None, "negara": negara or None},
        "catatan": [
            "BPS/Bea Cukai: data faktur ekspor-impor Indonesia (vol kg + nilai USD).",
            "TradeMap (ITC/Comtrade): nilai USD ternormalisasi dari satuan sumber "
            "(mis. US$ thousand); cakupan & metode berbeda dengan BPS.",
            "Kedua sumber dijaga terpisah; tabel banding hanya menyandingkan nilai "
            "masing-masing sumber yang nama kuncinya cocok.",
        ],
        "bps": {"nilai_usd": bps_total["nilai_usd"], "volume_kg": bps_total["volume_kg"],
                "baris": bps_total["baris"],
                "per_komoditas": bps_komoditas, "per_negara": bps_negara},
        "trademap": {"nilai_usd": tm_total["nilai_usd"], "baris": tm_total["baris"],
                     "per_komoditas": tm_komoditas, "per_negara": tm_negara},
        "banding_komoditas": banding_komoditas,
        "banding_negara": banding_negara,
    })
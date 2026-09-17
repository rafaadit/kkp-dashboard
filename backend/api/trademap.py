"""PHASE 6 — Endpoint TradeMap (ITC): ringkasan + browse trademap_trade."""
from flask import Blueprint, jsonify, request

from backend.db import get_connection
from backend.api.auth import require_perm
from backend.api.explore import _row
from backend.api.helpers import require_limit, require_page, row_to_dict

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
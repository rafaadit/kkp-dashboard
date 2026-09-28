"""PHASE 4 — Endpoint eksplorasi data (overview/komoditas/negara/perbandingan).

Sumber data: raw_exim (satu baris == satu fakt BPS, verified 1:1, tanpa duplikasi).
Semua filter parameterized (tanpa string concatenation nilai pengguna).
"""
from flask import Blueprint, jsonify, request

from backend.db import get_connection
from backend.api.auth import require_perm
from backend.api.helpers import (
    ApiError,
    parse_exim,
    parse_bulan,
    require_limit,
    row_to_dict,
)

explore_bp = Blueprint("explore", __name__, url_prefix="/api/explore")


def _filters(request):
    """
    Bangun (where_list, params) dari query-param umum:
      exim, mulai, akhir, kelompok (csv koding), negara, komoditas.
    """
    exim = parse_exim(request)
    where = ["r.exim_type = %s"]
    params = [exim]

    mulai = parse_bulan(request.args.get("mulai"))
    akhir = parse_bulan(request.args.get("akhir"))

    if mulai and akhir and (mulai[0], mulai[1] or 1) > (akhir[0], akhir[1] or 12):
        raise ApiError("'mulai' tidak boleh setelah 'akhir'")

    if mulai:
        where.append("(r.tahun, r.bulan) >= (%s, %s)")
        params += [mulai[0], mulai[1] or 1]
    if akhir:
        where.append("(r.tahun, r.bulan) <= (%s, %s)")
        params += [akhir[0], akhir[1] or 12]

    if request.args.get("kelompok"):
        grups = [g.strip().upper() for g in request.args["kelompok"].split(",") if g.strip()]
        if grups:
            where.append("r.koding IN (%s)" % ",".join(["%s"] * len(grups)))
            params += grups
    if request.args.get("negara"):
        where.append("r.kode_negara = %s")
        params.append(request.args["negara"].strip())
    if request.args.get("komoditas"):
        where.append("r.komoditas_5_2026 LIKE %s")
        params.append(f"%{request.args['komoditas'].strip()}%")
    return where, params


def _row(sql, params):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        res = cur.fetchall()
        return [row_to_dict(r) for r in res]
    finally:
        conn.close()


@explore_bp.get("/overview")
@require_perm("explore.view")
def overview():
    """Ringkasan: total nilai/volume, breakdown per bulan, breakdown koding I-IV."""
    where, params = _filters(request)
    w = " AND ".join(where)
    totals = _row(
        "SELECT COUNT(*) AS baris, "
        "       COALESCE(SUM(r.vol_kg), 0) AS volume_kg, "
        "       COALESCE(SUM(r.nil_usd), 0) AS nilai_usd, "
        "       COALESCE(SUM(r.setara_segar), 0) AS setara_segar, "
        "       COUNT(DISTINCT r.kode_hs_2022) AS hs_unik, "
        "       COUNT(DISTINCT r.kode_negara) AS negara_unik "
        f"FROM raw_exim r WHERE {w}",
        params,
    )
    perbulan = _row(
        "SELECT r.tahun, r.bulan, CONCAT(r.tahun,'-',LPAD(r.bulan,2,'0')) AS periode, "
        "       COUNT(*) AS baris, COALESCE(SUM(r.vol_kg),0) AS volume_kg, "
        "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd "
        f"FROM raw_exim r WHERE {w} "
        "GROUP BY r.tahun, r.bulan, periode ORDER BY r.tahun, r.bulan",
        params,
    )
    koding = _row(
        "SELECT r.koding, COUNT(*) AS baris, COALESCE(SUM(r.vol_kg),0) AS volume_kg, "
        "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd "
        f"FROM raw_exim r WHERE {w} "
        "GROUP BY r.koding ORDER BY NULLIF(r.koding,''), r.koding",
        params,
    )
    return jsonify(
        {
            "exim": request.args.get("exim", "ekspor").lower(),
            "periode": {"mulai": request.args.get("mulai"), "akhir": request.args.get("akhir")},
            "totals": totals[0],
            "perbulan": perbulan,
            "kelompok": koding,
        }
    )


@explore_bp.get("/komoditas")
@require_perm("explore.commodity")
def komoditas():
    """Top komoditas_5_2026: volume, nilai, harga avg, share nilai."""
    limit = require_limit(request, default=15, maximum=50)
    where, params = _filters(request)
    w = " AND ".join(where) + " AND NULLIF(r.komoditas_5_2026,'') IS NOT NULL"
    rows = _row(
        "SELECT r.komoditas_5_2026 AS komoditas, "
        "       NULLIF(r.komoditas_2_2017,'') AS komoditas_2_2017, "
        "       COUNT(DISTINCT r.kode_hs_2022) AS hs_unik, "
        "       COUNT(*) AS baris, "
        "       COALESCE(SUM(r.vol_kg),0) AS volume_kg, "
        "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd, "
        "       CASE WHEN SUM(r.vol_kg) > 0 "
        "            THEN SUM(r.nil_usd)/SUM(r.vol_kg) ELSE NULL END AS harga_usd_kg "
        f"FROM raw_exim r WHERE {w} "
        "GROUP BY r.komoditas_5_2026, r.komoditas_2_2017 "
        "ORDER BY nilai_usd DESC LIMIT %s",
        params + [limit],
    )
    total = _row(
        f"SELECT COALESCE(SUM(r.nil_usd),0) AS total FROM raw_exim r WHERE {w}", params
    )[0]["total"] or 0
    for r in rows:
        r["share_nilai_persen"] = (r["nilai_usd"] / total * 100) if total else None
    return jsonify({"limit": limit, "total_nilai_usd": total, "komoditas": rows})


@explore_bp.get("/komoditas_list")
@require_perm("explore.view")
def komoditas_list():
    """Daftar komoditas_5_2026 unik (urut A-Z) + jumlah baris, untuk navigasi sidebar."""
    exim = parse_exim(request)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT komoditas_5_2026 AS komoditas, COUNT(*) AS baris "
            "FROM raw_exim "
            "WHERE exim_type=%s AND NULLIF(komoditas_5_2026,'') IS NOT NULL "
            "GROUP BY komoditas_5_2026 ORDER BY komoditas_5_2026",
            (exim,),
        )
        rows = [row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify({"jenis": "komoditas_list", "komoditas": rows})


@explore_bp.get("/negara")
@require_perm("explore.country")
def negara():
    """Top negara tujuan (ekspor) / asal (impor) + ringkasan kelompok negara."""
    limit = require_limit(request, default=15, maximum=50)
    where, params = _filters(request)
    w = " AND ".join(where) + " AND NULLIF(r.kode_negara,'') IS NOT NULL"
    rows = _row(
        "SELECT r.kode_negara, r.negara, r.kelompok_negara, "
        "       COUNT(*) AS baris, COALESCE(SUM(r.vol_kg),0) AS volume_kg, "
        "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd "
        f"FROM raw_exim r WHERE {w} GROUP BY r.kode_negara, r.negara, r.kelompok_negara "
        "ORDER BY nilai_usd DESC LIMIT %s",
        params + [limit],
    )
    kelompok = _row(
        "SELECT NULLIF(r.kelompok_negara,'') AS kelompok_negara, COUNT(*) AS baris, "
        "       COALESCE(SUM(r.vol_kg),0) AS volume_kg, "
        "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd "
        f"FROM raw_exim r WHERE {w} "
        "GROUP BY NULLIF(r.kelompok_negara,'') ORDER BY nilai_usd DESC",
        params,
    )
    return jsonify({"limit": limit, "negara": rows, "kelompok_negara": kelompok})


@explore_bp.get("/provinsi")
@require_perm("explore.view")
def provinsi():
    """Top provinsi asal (ekspor) / bongkar (impor) + share nilai."""
    limit = require_limit(request, default=15, maximum=50)
    by = request.args.get("by", "asal").strip().lower()
    if by not in ("asal", "pelabuhan"):
        raise ApiError("'by' harus 'asal' atau 'pelabuhan'")
    name_col = "provinsi_asal" if by == "asal" else "provinsi_pelabuhan"
    where, params = _filters(request)
    w = " AND ".join(where) + f" AND NULLIF(r.{name_col},'') IS NOT NULL"
    rows = _row(
        f"SELECT r.{name_col} AS provinsi, "
        "       COUNT(*) AS baris, "
        "       COUNT(DISTINCT r.kode_hs_2022) AS hs_unik, "
        "       COALESCE(SUM(r.vol_kg),0) AS volume_kg, "
        "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd, "
        "       COALESCE(SUM(r.setara_segar),0) AS setara_segar "
        f"FROM raw_exim r WHERE {w} "
        f"GROUP BY r.{name_col} ORDER BY nilai_usd DESC LIMIT %s",
        params + [limit],
    )
    total = _row(
        f"SELECT COALESCE(SUM(r.nil_usd),0) AS total FROM raw_exim r WHERE {w}", params
    )[0]["total"] or 0
    for r in rows:
        r["share_nilai_persen"] = (r["nilai_usd"] / total * 100) if total else None
        r["harga_usd_kg"] = (r["nilai_usd"] / r["volume_kg"]) if r["volume_kg"] else None
    return jsonify({"by": by, "limit": limit, "total_nilai_usd": total, "provinsi": rows})


@explore_bp.get("/negara_list")
@require_perm("explore.view")
def negara_list():
    """Daftar kode+negara unik (urut A-Z) untuk dropdown Country Compare."""
    exim = parse_exim(request)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT kode_negara, negara, COUNT(*) AS baris "
            "FROM raw_exim "
            "WHERE exim_type=%s AND NULLIF(kode_negara,'') IS NOT NULL "
            "GROUP BY kode_negara, negara ORDER BY negara",
            (exim,),
        )
        rows = [row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return jsonify({"jenis": "negara_list", "negara": rows})


@explore_bp.get("/country_compare")
@require_perm("explore.comparison")
def country_compare():
    """Bandingkan kinerja ekspor/impor RI ke 2 negara dalam rentang periode."""
    exim = parse_exim(request)
    a = (request.args.get("negara_a") or "").strip().upper()
    b = (request.args.get("negara_b") or "").strip().upper()
    if not a or not b:
        raise ApiError("'negara_a' dan 'negara_b' wajib diisi")
    if a == b:
        raise ApiError("negara_a dan negara_b harus berbeda")
    mulai = parse_bulan(request.args.get("mulai"))
    akhir = parse_bulan(request.args.get("akhir"))
    if mulai and akhir and (mulai[0], mulai[1] or 1) > (akhir[0], akhir[1] or 12):
        raise ApiError("'mulai' tidak boleh setelah 'akhir'")

    period_conds = []
    p = [exim]
    if mulai:
        period_conds.append("(r.tahun, r.bulan) >= (%s, %s)")
        p += [mulai[0], mulai[1] or 1]
    if akhir:
        period_conds.append("(r.tahun, r.bulan) <= (%s, %s)")
        p += [akhir[0], akhir[1] or 12]

    def _agg(kode):
        w = " AND ".join(["r.exim_type=%s", "r.kode_negara=%s"] + period_conds)
        rows = _row(
            f"SELECT r.kode_negara, r.negara, r.kelompok_negara, "
            "       COUNT(*) AS baris, COUNT(DISTINCT r.kode_hs_2022) AS hs_unik, "
            "       COALESCE(SUM(r.vol_kg),0) AS volume_kg, "
            "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd, "
            "       COALESCE(SUM(r.setara_segar),0) AS setara_segar "
            f"FROM raw_exim r WHERE {w} "
            "GROUP BY r.kode_negara, r.negara, r.kelompok_negara",
            [exim, kode] + p[1:],
        )
        return rows[0] if rows else None

    def _top_comms(kode, n=6):
        w = " AND ".join(["r.exim_type=%s", "r.kode_negara=%s"] + period_conds)
        return _row(
            f"SELECT r.komoditas_5_2026 AS komoditas, "
            "       COUNT(*) AS baris, COALESCE(SUM(r.vol_kg),0) AS volume_kg, "
            "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd "
            f"FROM raw_exim r WHERE {w} "
            "       AND NULLIF(r.komoditas_5_2026,'') IS NOT NULL "
            "GROUP BY r.komoditas_5_2026 ORDER BY nilai_usd DESC LIMIT %s",
            [exim, kode] + p[1:] + [n],
        )

    def _series(kode):
        w = " AND ".join(["r.exim_type=%s", "r.kode_negara=%s"] + period_conds)
        return _row(
            f"SELECT r.kode_negara AS kode_negara, r.tahun, r.bulan, "
            "       CONCAT(r.tahun,'-',LPAD(r.bulan,2,'0')) AS periode, "
            "       COUNT(*) AS baris, COALESCE(SUM(r.vol_kg),0) AS volume_kg, "
            "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd "
            f"FROM raw_exim r WHERE {w} "
            "GROUP BY r.tahun, r.bulan ORDER BY r.tahun, r.bulan",
            [exim, kode] + p[1:],
        )

    agg_a = _agg(a)
    agg_b = _agg(b)
    if agg_a is None:
        raise ApiError(f"negara '{a}' tidak ditemukan pada periode ini")
    if agg_b is None:
        raise ApiError(f"negara '{b}' tidak ditemukan pada periode ini")

    total = _row(
        f"SELECT COALESCE(SUM(r.nil_usd),0) AS total FROM raw_exim r "
        f"WHERE {' AND '.join(['r.exim_type=%s'] + period_conds)}",
        p,
    )[0]["total"] or 0
    for g in (agg_a, agg_b):
        g["share_nilai_persen"] = (g["nilai_usd"] / total * 100) if total else None
        g["harga_usd_kg"] = (g["nilai_usd"] / g["volume_kg"]) if g["volume_kg"] else None
        g["top_komoditas"] = _top_comms(g["kode_negara"])

    by_periode = {}
    for s in _series(a) + _series(b):
        key = s["periode"]
        by_periode.setdefault(key, {"periode": key, "a": None, "b": None})
        slot = "a" if s["kode_negara"] == a else "b"
        by_periode[key][slot] = {
            "baris": s["baris"],
            "volume_kg": s["volume_kg"],
            "nilai_usd": s["nilai_usd"],
        }
    merged = [{"periode": k, "a": v["a"], "b": v["b"]} for k, v in sorted(by_periode.items())]

    return jsonify({
        "exim": exim,
        "negara_a": agg_a,
        "negara_b": agg_b,
        "per_bulan": merged,
        "selisih_nilai_usd": round(agg_a["nilai_usd"] - agg_b["nilai_usd"], 4),
    })


def _pos2ym(pos):
    return pos // 12, pos % 12 + 1


@explore_bp.get("/kompetitor_scope")
@require_perm("explore.view")
def kompetitor_scope():
    """Cakupan data yang tersedia untuk profil kompetitor (scaffold jujur)."""
    cakupan = _row(
        "SELECT reporter, flow, NULLIF(TRIM(product_code),'') AS hs, year AS tahun, "
        "       COUNT(*) AS baris, COALESCE(SUM(value_usd),0) AS nilai_usd "
        "FROM trademap_trade GROUP BY reporter, flow, product_code, year ORDER BY reporter, flow, tahun",
        [],
    )
    partner_ekspor = _row(
        "SELECT t.partner, COALESCE(n.nama_negara, t.partner) AS nama_partner, "
        "       COALESCE(SUM(t.value_usd),0) AS nilai_usd "
        "FROM trademap_trade t LEFT JOIN ms_negara n ON n.kode_negara = t.partner "
        "WHERE t.reporter='ID' AND t.flow='Export' "
        "GROUP BY t.partner, n.nama_negara ORDER BY nilai_usd DESC",
        [],
    )
    return jsonify({
        "sumber_kompetitor": [
            "impor dunia per negara-penjual (TradeMap, butuh key) — belum tersedia",
            "posisi RI vs kompetitor per produk di pasar tujuan (TradeMap) — belum tersedia",
        ],
        "cakupan_trademap": cakupan,
        "partner_ekspor_id": partner_ekspor,
    })


@explore_bp.get("/potensi")
@require_perm("explore.view")
def potensi():
    """Potensi ekspor/impor: momentum pasar 6-bulan terakhir (BPS riil)
    + snapshot pangsa pasar dari data TradeMap yang tersedia."""
    exim = parse_exim(request)
    qmax = _row(
        "SELECT tahun AS y, bulan AS m FROM raw_exim "
        "WHERE exim_type=%s ORDER BY tahun DESC, bulan DESC LIMIT 1",
        [exim],
    )[0]
    if not qmax["y"]:
        return jsonify({"ref_periode": None, "top_market": [], "momentum": [], "trademap": None})

    pos = qmax["y"] * 12 + (qmax["m"] - 1)
    ref_start, ref_end = _pos2ym(pos - 5), _pos2ym(pos)
    prev_start, prev_end = _pos2ym(pos - 11), _pos2ym(pos - 6)

    def _win(ps, pe):
        return _row(
            "SELECT r.kode_negara, r.negara, COALESCE(SUM(r.nil_usd),0) AS nilai_usd "
            "FROM raw_exim r WHERE r.exim_type=%s "
            "AND (r.tahun, r.bulan) >= (%s,%s) AND (r.tahun, r.bulan) <= (%s,%s) "
            "GROUP BY r.kode_negara, r.negara",
            [exim, ps[0], ps[1], pe[0], pe[1]],
        )

    def _win_comms(kode, ps, pe):
        return _row(
            "SELECT NULLIF(r.komoditas_5_2026,'') AS komoditas, "
            "       COALESCE(SUM(r.nil_usd),0) AS nilai_usd "
            "FROM raw_exim r WHERE r.exim_type=%s AND r.kode_negara=%s "
            "AND (r.tahun, r.bulan) >= (%s,%s) AND (r.tahun, r.bulan) <= (%s,%s) "
            "AND NULLIF(r.komoditas_5_2026,'') IS NOT NULL "
            "GROUP BY NULLIF(r.komoditas_5_2026,'')",
            [exim, kode, ps[0], ps[1], pe[0], pe[1]],
        )

    ref_rows = _win(ref_start, ref_end)
    prev_map = {r["kode_negara"]: r["nilai_usd"] for r in _win(prev_start, prev_end)}

    markets = []
    for r in ref_rows:
        pv = prev_map.get(r["kode_negara"])
        markets.append({
            "kode_negara": r["kode_negara"],
            "negara": r["negara"],
            "nilai_usd": r["nilai_usd"],
            "prev_nilai_usd": pv,
            "pertumbuhan_persen": round((r["nilai_usd"] - pv) / pv * 100, 2) if pv else None,
        })
    markets.sort(key=lambda x: x["nilai_usd"], reverse=True)
    top_market = markets[:10]

    momentum = [m for m in markets if m["pertumbuhan_persen"] is not None and (m["prev_nilai_usd"] or 0) >= 500_000]
    momentum.sort(key=lambda x: x["pertumbuhan_persen"], reverse=True)
    momentum = momentum[:10]
    for m in momentum[:5]:
        refc = _win_comms(m["kode_negara"], ref_start, ref_end)
        prevc = {c["komoditas"]: c["nilai_usd"] for c in _win_comms(m["kode_negara"], prev_start, prev_end)}
        kom = []
        for c in refc:
            pv = prevc.get(c["komoditas"])
            g = round((c["nilai_usd"] - pv) / pv * 100, 2) if pv else None
            if g is not None and g > 0 and (pv or 0) >= 100_000:
                kom.append({
                    "komoditas": c["komoditas"],
                    "nilai_usd": c["nilai_usd"],
                    "prev_nilai_usd": pv,
                    "pertumbuhan_persen": g,
                })
        kom.sort(key=lambda x: x["pertumbuhan_persen"], reverse=True)
        m["komoditas_momentum"] = kom[:5]

    td_year = _row(
        "SELECT year AS tahun, COUNT(*) AS baris, COALESCE(SUM(value_usd),0) AS nilai_usd "
        "FROM trademap_trade WHERE reporter='ID' AND flow='Export' GROUP BY year ORDER BY year",
        [],
    )
    td_partner = _row(
        "SELECT t.partner, COALESCE(n.nama_negara, t.partner) AS nama_partner, "
        "       COALESCE(SUM(t.value_usd),0) AS nilai_usd "
        "FROM trademap_trade t LEFT JOIN ms_negara n ON n.kode_negara = t.partner "
        "WHERE t.reporter='ID' AND t.flow='Export' "
        "GROUP BY t.partner, n.nama_negara, t.partner ORDER BY nilai_usd DESC",
        [],
    )
    total_td = sum(float(p["nilai_usd"]) for p in td_partner)
    for p in td_partner:
        p["share_persen"] = round(p["nilai_usd"] / total_td * 100, 2) if total_td else None

    return jsonify({
        "exim": exim,
        "ref_periode": {"mulai": f"{ref_start[0]:04d}-{ref_start[1]:02d}", "akhir": f"{ref_end[0]:04d}-{ref_end[1]:02d}"},
        "prev_periode": f"{prev_start[0]:04d}-{prev_start[1]:02d}..{prev_end[0]:04d}-{prev_end[1]:02d}",
        "top_market": top_market,
        "momentum": momentum,
        "trademap": ({"per_tahun": td_year, "per_partner": td_partner, "total_usd": round(total_td, 2)}
                     if td_year else None),
    })


def _selisih(a, b):
    if a is None or b is None or b == 0:
        return None
    return round((a - b) / b * 100, 2)


@explore_bp.get("/perbandingan")
@require_perm("explore.comparison")
def perbandingan():
    """
    Perbandingan 2 rentang periode.
      periode_a_mulai / periode_a_akhir   (default: semua data)
      periode_b_mulai / periode_b_akhir   (default: setahun sebelum A)
    """
    a_mulai = parse_bulan(request.args.get("periode_a_mulai"))
    a_akhir = parse_bulan(request.args.get("periode_a_akhir"))
    b_mulai = parse_bulan(request.args.get("periode_b_mulai"))
    b_akhir = parse_bulan(request.args.get("periode_b_akhir"))
    if (a_mulai is None) != (a_akhir is None) or (b_mulai is None) != (b_akhir is None):
        raise ApiError("rentang periode harus lengkap (mulai+akhir) atau keduanya kosong")
    if b_mulai is None and a_mulai is not None:
        b_mulai = (a_mulai[0] - 1, a_mulai[1])
        b_akhir = (a_akhir[0] - 1, a_akhir[1])

    exim = parse_exim(request)

    def agg(mulai, akhir):
        if mulai is None:
            return _row(
                "SELECT COUNT(*) AS baris, COALESCE(SUM(vol_kg),0) AS volume_kg, "
                "       COALESCE(SUM(nil_usd),0) AS nilai_usd, "
                "       COALESCE(SUM(setara_segar),0) AS setara_segar "
                "FROM raw_exim WHERE exim_type=%s",
                [exim],
            )[0]
        w = "exim_type=%s AND (tahun, bulan) >= (%s,%s) AND (tahun, bulan) <= (%s,%s)"
        return _row(
            "SELECT COUNT(*) AS baris, COALESCE(SUM(vol_kg),0) AS volume_kg, "
            "       COALESCE(SUM(nil_usd),0) AS nilai_usd, "
            "       COALESCE(SUM(setara_segar),0) AS setara_segar "
            f"FROM raw_exim WHERE {w}",
            [exim, mulai[0], mulai[1] or 1, akhir[0], akhir[1] or 12],
        )[0]

    a = agg(a_mulai, a_akhir)
    b = agg(b_mulai, b_akhir)
    return jsonify(
        {
            "exim": exim,
            "periode_a": {
                "mulai": to_ym_str(a_mulai),
                "akhir": to_ym_str(a_akhir),
                **a,
            },
            "periode_b": {"mulai": to_ym_str(b_mulai), "akhir": to_ym_str(b_akhir), **b},
            "delta": {
                "nilai_usd": value_delta(a["nilai_usd"], b["nilai_usd"]),
                "volume_kg": value_delta(a["volume_kg"], b["volume_kg"]),
                "baris": value_delta(a["baris"], b["baris"]),
                "pertumbuhan_nilai_persen": _selisih(a["nilai_usd"], b["nilai_usd"]),
                "pertumbuhan_volume_persen": _selisih(a["volume_kg"], b["volume_kg"]),
            },
        }
    )


def value_delta(a, b):
    return round(a - b, 4)


def to_ym_str(rec):
    if rec is None:
        return None
    t, b = rec
    return f"{t:04d}-{(b or 1):02d}"
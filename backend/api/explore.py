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
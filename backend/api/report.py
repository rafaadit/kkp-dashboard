"""PHASE 7 — Endpoint laporan PPT: generate, list, download."""
import json
import os

from flask import Blueprint, jsonify, request, send_file

from backend.db import get_connection
from backend.api.auth import require_perm
from backend.api.helpers import ApiError

report_bp = Blueprint("report", __name__, url_prefix="/api/report")

BULAN_ID = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def _parse_periode():
    """Baca & validasi tahun/bulan_awal/bulan_akhir dari query string."""
    try:
        tahun = int(request.args.get("tahun", 2026))
    except (TypeError, ValueError):
        raise ApiError("tahun harus angka")
    try:
        b1 = int(request.args.get("bulan_awal", 1))
    except (TypeError, ValueError):
        raise ApiError("bulan_awal harus angka")
    try:
        b2 = int(request.args.get("bulan_akhir", 6))
    except (TypeError, ValueError):
        raise ApiError("bulan_akhir harus angka")
    if not (1 <= b1 <= 12 and 1 <= b2 <= 12) or b1 > b2:
        raise ApiError("rentang bulan tidak valid")
    if not (2000 <= tahun <= 2100):
        raise ApiError("tahun tidak valid")
    return tahun, b1, b2


@report_bp.get("/exec_summary")
@require_perm("report.view")
def exec_summary():
    """Ringkasan eksekutif untuk periode terpilih (dipakai halaman laporan)."""
    tahun, b1, b2 = _parse_periode()
    conn = get_connection()
    try:
        cur = conn.cursor()

        def agg(_tahun):
            cur.execute(
                """SELECT exim_type,
                          COALESCE(SUM(nil_usd),0)      AS nilai_usd,
                          COALESCE(SUM(vol_kg),0)       AS volume_kg,
                          COALESCE(SUM(setara_segar),0) AS setara_segar,
                          COUNT(DISTINCT kode_hs_2022)  AS hs,
                          COUNT(DISTINCT kode_negara)   AS negara
                   FROM raw_exim WHERE tahun=%s AND bulan BETWEEN %s AND %s
                   GROUP BY exim_type""",
                (_tahun, b1, b2),
            )
            d = {"ekspor": {}, "impor": {}}
            for r in cur.fetchall():
                t = r["exim_type"]
                if t in d:
                    d[t] = {k: float(r[k] or 0) for k in ("nilai_usd", "volume_kg", "setara_segar")}
                    d[t]["hs"] = int(r["hs"] or 0)
                    d[t]["negara"] = int(r["negara"] or 0)
            return d

        cur_agg = agg(tahun)
        prev_agg = agg(tahun - 1)

        def yoy_persen(cur, prev):
            if not prev:
                return None
            return (cur - prev) / prev * 100

        def top_sql(name_col, exim):
            cur.execute(
                f"SELECT r.{name_col} AS name, COALESCE(SUM(r.nil_usd),0) AS v "
                "FROM raw_exim r "
                f"WHERE r.exim_type=%s AND r.tahun=%s AND r.bulan BETWEEN %s AND %s "
                f"AND NULLIF(r.{name_col},'') IS NOT NULL "
                f"GROUP BY r.{name_col} ORDER BY v DESC LIMIT 10",
                (exim, tahun, b1, b2),
            )
            return cur.fetchall()

        eks_nilai = cur_agg["ekspor"].get("nilai_usd", 0)
        imp_nilai = cur_agg["impor"].get("nilai_usd", 0)

        rows_negara = top_sql("negara", "ekspor")
        rows_kom_eks = top_sql("komoditas_5_2026", "ekspor")
        rows_kom_imp = top_sql("komoditas_5_2026", "impor")

        def decorate(rows, total):
            out = []
            for r in rows:
                v = float(r["v"] or 0)
                out.append({"name": r["name"],
                            "nilai_usd": v,
                            "share": v / total * 100 if total else None})
            return out

        cur.execute(
            """SELECT r.tahun, r.bulan,
                      COALESCE(SUM(CASE WHEN r.exim_type='ekspor' THEN r.nil_usd ELSE 0 END),0) AS ekspor_usd,
                      COALESCE(SUM(CASE WHEN r.exim_type='impor'  THEN r.nil_usd ELSE 0 END),0) AS impor_usd
               FROM raw_exim r WHERE r.tahun=%s AND r.bulan BETWEEN %s AND %s
               GROUP BY r.tahun, r.bulan ORDER BY r.bulan""",
            (tahun, b1, b2),
        )
        perbulan = []
        for r in cur.fetchall():
            e = float(r["ekspor_usd"] or 0)
            i = float(r["impor_usd"] or 0)
            perbulan.append({"periode": f"{r['tahun']}-{r['bulan']:02d}",
                             "ekspor_usd": e, "impor_usd": i, "neraca_usd": round(e - i, 4)})
    finally:
        conn.close()

    empty = not (cur_agg["ekspor"] or cur_agg["impor"])
    return jsonify({
        "tahun": tahun, "bulan_awal": b1, "bulan_akhir": b2,
        "periode_label": f"{BULAN_ID[b1].upper()} – {BULAN_ID[b2].upper()} {tahun}",
        "empty": empty,
        "ekspor": {**cur_agg["ekspor"],
                   "prev_nilai_usd": prev_agg["ekspor"].get("nilai_usd", 0),
                   "yoy_persen": yoy_persen(eks_nilai, prev_agg["ekspor"].get("nilai_usd", 0))},
        "impor": {**cur_agg["impor"],
                  "prev_nilai_usd": prev_agg["impor"].get("nilai_usd", 0),
                  "yoy_persen": yoy_persen(imp_nilai, prev_agg["impor"].get("nilai_usd", 0))},
        "neraca": {"nilai_usd": round(eks_nilai - imp_nilai, 4),
                   "yoy_persen": yoy_persen(eks_nilai - imp_nilai,
                                            prev_agg["ekspor"].get("nilai_usd", 0) - prev_agg["impor"].get("nilai_usd", 0))},
        "top_negara": decorate(rows_negara, eks_nilai),
        "top_komoditas_ekspor": decorate(rows_kom_eks, eks_nilai),
        "top_komoditas_impor": decorate(rows_kom_imp, imp_nilai),
        "perbulan": perbulan,
    })


@report_bp.get("/preview")
@require_perm("report.view")
def preview():
    """Data infografis laporan eksekutif untuk periode terpilih (11 slide deck)."""
    tahun, b1, b2 = _parse_periode()
    from backend.report.template_fill import collect_data

    conn = get_connection()
    try:
        data = collect_data(conn, tahun, b1, b2)
    except RuntimeError as e:
        return jsonify({"ok": False, "message": str(e),
                        "tahun": tahun, "bulan_awal": b1, "bulan_akhir": b2})
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return jsonify({"ok": True, "data": data})


@report_bp.get("/list")
@require_perm("report.view")
def list_reports():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT j.id, j.status, j.params_json, j.error_message, j.started_at, j.finished_at,
                      l.data_json AS file_data
               FROM automation_jobs j
               LEFT JOIN automation_job_logs l
                      ON l.id_job = j.id AND l.message='PPT tersimpan'
               WHERE j.job_type='report_ppt'
               ORDER BY j.id DESC LIMIT 50"""
        )
        reports = []
        for r in cur.fetchall():
            file_path = None
            if r.get("file_data"):
                try:
                    file_path = json.loads(r["file_data"]).get("file")
                except Exception:
                    file_path = None
            reports.append({
                "id": r["id"], "status": r["status"], "params": r["params_json"],
                "error": r["error_message"], "started_at": str(r["started_at"] or ""),
                "finished_at": str(r["finished_at"] or ""), "file": file_path,
                "downloadable": bool(file_path and os.path.isfile(file_path)),
            })
    finally:
        conn.close()
    return jsonify({"reports": reports})


@report_bp.post("/generate_ppt")
@require_perm("report.generate_ppt")
def generate_ppt():
    body = request.get_json(silent=True) or {}
    try:
        tahun = int(body.get("tahun", 2026))
        b1 = int(body.get("bulan_awal", 1))
        b2 = int(body.get("bulan_akhir", 6))
    except (TypeError, ValueError):
        raise ApiError("tahun/bulan harus angka")
    if not (1 <= b1 <= 12 and 1 <= b2 <= 12) or b1 > b2:
        raise ApiError("rentang bulan tidak valid")
    if not (2000 <= tahun <= 2100):
        raise ApiError("tahun tidak valid")

    from backend.report.generate_ppt import generate

    try:
        out, job_id = generate(tahun, b1, b2)
    except Exception as e:  # noqa: BLE001
        raise ApiError(f"gagal membuat PPT: {e}", 500)
    return jsonify({"job_id": job_id, "file": out, "tahun": tahun, "bulan_awal": b1, "bulan_akhir": b2})


@report_bp.get("/download")
@require_perm("report.view")
def download():
    job_id = request.args.get("job_id", "").strip()
    if not job_id.isdigit():
        raise ApiError("job_id wajib")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT l.data_json FROM automation_job_logs l
               JOIN automation_jobs j ON j.id = l.id_job
               WHERE j.id=%s AND j.job_type='report_ppt' AND l.message='PPT tersimpan'
               ORDER BY l.id DESC LIMIT 1""",
            (int(job_id),),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise ApiError("file laporan tidak ditemukan", 404)
    path = json.loads(row["data_json"])["file"]
    if not os.path.isfile(path):
        raise ApiError("file sudah tidak ada di disk", 404)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))
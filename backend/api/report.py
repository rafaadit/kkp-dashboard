"""PHASE 7 — Endpoint laporan PPT: generate, list, download."""
import json
import os

from flask import Blueprint, jsonify, request, send_file

from backend.db import get_connection
from backend.api.auth import require_perm
from backend.api.helpers import ApiError

report_bp = Blueprint("report", __name__, url_prefix="/api/report")


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
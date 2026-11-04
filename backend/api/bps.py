"""PHASE 8 — Update data BPS periode baru (khusus pegawai / super_admin).

Alur:
    POST /api/data/bps/upload   (multipart: ekspor / impor .xlsx)
        -> simpan file di data/bps_uploads/
        -> buat automation_jobs (job_type='bps_update', PENDING)
        -> jalankan database/scripts/update_bps.py di background
    GET  /api/data/bps/jobs             riwayat job update BPS
    GET  /api/data/bps/jobs/<id>        status + log job (untuk polling)
    GET  /api/data/bps/uploads          riwayat file BPS yang diproses
    GET  /api/data/bps/summary          ringkasan periode & jumlah baris

Permission:
    data.update_bps_export  -> boleh unggah file ekspor
    data.update_bps_import  -> boleh unggah file impor
    data.view / exim.view   -> boleh melihat status
"""
import json
import os
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime

from flask import Blueprint, jsonify, request

from backend.db import get_connection
from backend.api.auth import require_perm, session_context
from backend.api.helpers import ApiError, require_limit, require_page

bps_bp = Blueprint("bps", __name__, url_prefix="/api/data/bps")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(ROOT, "data", "bps_uploads")
SCRIPT = os.path.join(ROOT, "database", "scripts", "update_bps.py")
ALLOWED_EXT = (".xlsx", ".xlsm")
MAX_FILE_BYTES = 250 * 1024 * 1024  # 250 MB per file


def _safe_name(name, exim_type):
    base = os.path.basename(name or "bps.xlsx")
    cleaned = "".join(c for c in base if c.isalnum() or c in "._- ").strip()
    if not cleaned:
        cleaned = f"bps_{exim_type}.xlsx"
    cleaned = cleaned[-120:]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}_{exim_type}_{cleaned}"


def _can(sess, kode):
    return sess["role"] == "super_admin" or kode in sess["permissions"]


def _iso(v):
    return v.isoformat(sep=" ") if hasattr(v, "isoformat") else v


def _reap_stale_jobs(cur):
    """Tandai job PENDING yang tak pernah mulai sebagai FAILED.

    Subprocess bisa mati sebelum sempat menulis status RUNNING (mis. crash saat
    import). Tanpa ini, job tersebut memblokir update BPS selanjutnya selamanya.
    """
    cur.execute(
        "UPDATE automation_jobs SET status='FAILED', "
        "error_message=COALESCE(error_message, 'Job terhenti: proses tidak pernah mulai'), "
        "finished_at=NOW() "
        "WHERE job_type='bps_update' AND status='PENDING' AND started_at IS NULL "
        "AND created_at < (NOW() - INTERVAL 15 MINUTE)"
    )


@bps_bp.get("/summary")
@require_perm("data.view", "exim.view", "data.update_bps_export", "data.update_bps_import")
def summary():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, tahun, bulan, label FROM ms_period "
            "ORDER BY tahun DESC, bulan DESC LIMIT 1"
        )
        latest = cur.fetchone()

        counts = {}
        for key, sql in {
            "bps_export": "SELECT COUNT(*) AS n FROM bps_export",
            "bps_import": "SELECT COUNT(*) AS n FROM bps_import",
            "raw_exim": "SELECT COUNT(*) AS n FROM raw_exim",
            "bps_upload": "SELECT COUNT(*) AS n FROM bps_upload",
        }.items():
            cur.execute(sql)
            counts[key] = int(cur.fetchone()["n"] or 0)

        cur.execute(
            "SELECT id, status, params_json, error_message, started_at, finished_at "
            "FROM automation_jobs WHERE job_type='bps_update' "
            "ORDER BY id DESC LIMIT 1"
        )
        last_job = cur.fetchone()
        if last_job:
            import json

            params = last_job["params_json"]
            try:
                params = json.loads(params) if isinstance(params, str) else params
            except Exception:  # noqa: BLE001
                params = None
            last_job = {
                "id": last_job["id"],
                "status": last_job["status"],
                "params": params,
                "error": last_job["error_message"],
                "started_at": _iso(last_job["started_at"]),
                "finished_at": _iso(last_job["finished_at"]),
            }
    finally:
        conn.close()

    return jsonify(
        {
            "latest_period": {
                "id": latest["id"],
                "tahun": latest["tahun"],
                "bulan": latest["bulan"],
                "label": latest["label"],
            } if latest else None,
            "counts": counts,
            "last_job": last_job,
        }
    )


@bps_bp.get("/uploads")
@require_perm("data.view", "exim.view", "data.update_bps_export", "data.update_bps_import")
def uploads():
    limit = require_limit(request, default=15, maximum=100)
    page = require_page(request)
    where, params = [], []
    if request.args.get("exim") in ("ekspor", "impor"):
        where.append("b.exim_type=%s")
        params.append(request.args["exim"])
    if request.args.get("status"):
        where.append("b.status=%s")
        params.append(request.args["status"])
    w = (" WHERE " + " AND ".join(where)) if where else ""

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) AS n FROM bps_upload b{w}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""SELECT b.id, b.exim_type, b.nama_file, b.row_count, b.status,
                       b.error_summary, b.created_at, b.updated_at,
                       pm.label AS periode_mulai_label,
                       pa.label AS periode_akhir_label,
                       u.nama AS uploaded_by_nama, u.email AS uploaded_by_email
                FROM bps_upload b
                LEFT JOIN ms_period pm ON pm.id = b.periode_mulai
                LEFT JOIN ms_period pa ON pa.id = b.periode_akhir
                LEFT JOIN app_users u ON u.id = b.uploaded_by
                {w} ORDER BY b.id DESC LIMIT %s OFFSET %s""",
            params + [limit, (page - 1) * limit],
        )
        rows = [
            {
                "id": r["id"],
                "exim_type": r["exim_type"],
                "nama_file": r["nama_file"],
                "row_count": int(r["row_count"] or 0),
                "status": r["status"],
                "error_summary": r["error_summary"],
                "created_at": _iso(r["created_at"]),
                "updated_at": _iso(r["updated_at"]),
                "periode_mulai": r["periode_mulai_label"],
                "periode_akhir": r["periode_akhir_label"],
                "uploaded_by": r["uploaded_by_nama"] or r["uploaded_by_email"],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
    return jsonify({"page": page, "limit": limit, "total": total, "uploads": rows})


@bps_bp.get("/jobs")
@require_perm("data.view", "exim.view", "jobs.view")
def list_jobs():
    limit = require_limit(request, default=10, maximum=100)
    conn = get_connection()
    try:
        cur = conn.cursor()
        _reap_stale_jobs(cur)
        conn.commit()
        cur.execute(
            """SELECT j.id, j.status, j.params_json, j.error_message, j.attempts,
                      j.started_at, j.finished_at, j.created_at,
                      u.nama AS created_by_nama, u.email AS created_by_email
               FROM automation_jobs j
               LEFT JOIN app_users u ON u.id = j.created_by
               WHERE j.job_type='bps_update'
               ORDER BY j.id DESC LIMIT %s""",
            (limit,),
        )
        jobs = []
        import json

        for r in cur.fetchall():
            params = r["params_json"]
            try:
                params = json.loads(params) if isinstance(params, str) else params
            except Exception:  # noqa: BLE001
                params = None
            jobs.append({
                "id": r["id"],
                "status": r["status"],
                "params": params,
                "error": r["error_message"],
                "attempts": r["attempts"],
                "started_at": _iso(r["started_at"]),
                "finished_at": _iso(r["finished_at"]),
                "created_at": _iso(r["created_at"]),
                "created_by": r["created_by_nama"] or r["created_by_email"],
            })
    finally:
        conn.close()
    return jsonify({"jobs": jobs})


@bps_bp.get("/jobs/<jid>")
@require_perm("data.view", "exim.view", "jobs.view")
def job_detail(jid):
    try:
        jid = int(jid)
    except (TypeError, ValueError):
        raise ApiError("id job tidak valid")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT j.id, j.status, j.params_json, j.error_message, j.attempts,
                      j.started_at, j.finished_at, j.created_at, j.id_ms_period,
                      u.nama AS created_by_nama, u.email AS created_by_email
               FROM automation_jobs j
               LEFT JOIN app_users u ON u.id = j.created_by
               WHERE j.id=%s AND j.job_type='bps_update'""",
            (jid,),
        )
        r = cur.fetchone()
        if not r:
            raise ApiError("job tidak ditemukan", 404)
        import json

        params = r["params_json"]
        try:
            params = json.loads(params) if isinstance(params, str) else params
        except Exception:  # noqa: BLE001
            params = None
        cur.execute(
            "SELECT id, level, message, data_json, created_at "
            "FROM automation_job_logs WHERE id_job=%s ORDER BY id ASC LIMIT 500",
            (jid,),
        )
        logs = []
        for lg in cur.fetchall():
            data = lg["data_json"]
            try:
                data = json.loads(data) if isinstance(data, str) else data
            except Exception:  # noqa: BLE001
                data = None
            logs.append({
                "id": lg["id"],
                "level": lg["level"],
                "message": lg["message"],
                "data": data,
                "created_at": _iso(lg["created_at"]),
            })
    finally:
        conn.close()
    return jsonify(
        {
            "job": {
                "id": r["id"],
                "status": r["status"],
                "params": params,
                "error": r["error_message"],
                "attempts": r["attempts"],
                "started_at": _iso(r["started_at"]),
                "finished_at": _iso(r["finished_at"]),
                "created_at": _iso(r["created_at"]),
                "created_by": r["created_by_nama"] or r["created_by_email"],
            },
            "logs": logs,
        }
    )


@bps_bp.post("/upload")
@require_perm("data.update_bps_export", "data.update_bps_import")
def upload():
    sess = session_context()
    files = {}
    for exim_type, perm in (
        ("ekspor", "data.update_bps_export"),
        ("impor", "data.update_bps_import"),
    ):
        f = request.files.get(exim_type)
        if f is None or not f.filename:
            continue
        if not _can(sess, perm):
            raise ApiError(f"tidak punya izin upload data BPS {exim_type}", 403)
        files[exim_type] = f

    if not files:
        raise ApiError("unggah minimal satu file ekspor atau impor (.xlsx)")

    for exim_type, f in files.items():
        if not f.filename.lower().endswith(ALLOWED_EXT):
            raise ApiError(f"file {exim_type} harus .xlsx/.xlsm")

    # Hanya satu update BPS pada satu waktu.
    conn = get_connection()
    try:
        cur = conn.cursor()
        _reap_stale_jobs(cur)
        conn.commit()
        cur.execute(
            "SELECT id FROM automation_jobs WHERE job_type='bps_update' "
            "AND status IN ('PENDING','RUNNING') ORDER BY id DESC LIMIT 1"
        )
        running = cur.fetchone()
    finally:
        conn.close()
    if running:
        raise ApiError(
            f"update BPS sedang berjalan (job #{running['id']}). Tunggu sampai selesai.",
            409,
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved = {}
    try:
        for exim_type, f in files.items():
            name = _safe_name(f.filename, exim_type)
            path = os.path.join(UPLOAD_DIR, name)
            f.save(path)
            size = os.path.getsize(path)
            if size < 32:
                raise ApiError(f"file {exim_type} kosong / tidak valid")
            if size > MAX_FILE_BYTES:
                raise ApiError(f"file {exim_type} terlalu besar (maks 250 MB)")
            if not zipfile.is_zipfile(path):
                raise ApiError(f"file {exim_type} bukan workbook Excel yang valid")
            saved[exim_type] = {
                "path": path,
                "name": f.filename,
                "size": size,
            }
    except Exception:
        for item in saved.values():
            try:
                os.unlink(item["path"])
            except OSError:
                pass
        raise

    force = str(request.form.get("force", "")).lower() in ("1", "true", "yes", "on")
    params = {
        "files": {k: {"original_name": v["name"], "size": v["size"]} for k, v in saved.items()},
        "force": force,
        "requested_by": sess["email"],
        "requested_by_id": sess["user_id"],
    }
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO automation_jobs
               (job_type, status, params_json, attempts, correlation_id, created_by)
               VALUES ('bps_update', 'PENDING', %s, 0, %s, %s)""",
            (json.dumps(params), uuid.uuid4().hex, sess["user_id"]),
        )
        job_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    cmd = [sys.executable, SCRIPT, "--job-id", str(job_id)]
    if "ekspor" in saved:
        cmd += ["--ekspor", saved["ekspor"]["path"]]
    if "impor" in saved:
        cmd += ["--impor", saved["impor"]["path"]]
    if force:
        cmd.append("--force")

    log_path = os.path.join(UPLOAD_DIR, f"job_{job_id}.log")
    try:
        logf = open(log_path, "ab")
        try:
            subprocess.Popen(
                cmd,
                cwd=ROOT,
                stdout=logf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            logf.close()
    except Exception as e:  # noqa: BLE001
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE automation_jobs SET status='FAILED', error_message=%s, "
                "finished_at=NOW() WHERE id=%s",
                (f"gagal menjalankan proses: {e}", job_id),
            )
            conn.commit()
        finally:
            conn.close()
        raise ApiError(f"gagal menjalankan proses update BPS: {e}", 500)

    return jsonify({
        "job_id": job_id,
        "status": "PENDING",
        "files": {k: v["name"] for k, v in saved.items()},
        "log": os.path.relpath(log_path, ROOT),
    }), 202


@bps_bp.post("/jobs/<jid>/cancel")
@require_perm("jobs.run")
def cancel_job(jid):
    try:
        jid = int(jid)
    except (TypeError, ValueError):
        raise ApiError("id job tidak valid")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM automation_jobs WHERE id=%s AND job_type='bps_update'", (jid,))
        r = cur.fetchone()
        if not r:
            raise ApiError("job tidak ditemukan", 404)
        if r["status"] != "PENDING":
            raise ApiError("hanya job PENDING yang bisa dibatalkan", 409)
        cur.execute(
            "UPDATE automation_jobs SET status='CANCELLED', finished_at=NOW() WHERE id=%s",
            (jid,),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "CANCELLED", "id": jid})

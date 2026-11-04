#!/usr/bin/env python3
"""PHASE 8 — Wrapper update data BPS periode baru.

Dijalankan oleh API (background) setelah pegawai mengunggah file BPS:

    python3 database/scripts/update_bps.py --job-id 12 \
        --ekspor data/bps_uploads/..._ekspor.xlsx \
        --impor  data/bps_uploads/..._impor.xlsx

Langkah:
    1. Pastikan semua (tahun, bulan) di file ada di ms_period (buat otomatis).
    2. ETL BPS (upload -> validasi -> staging -> fact) memakai etl_bps.py.
    3. Regenerasi raw_exim HANYA untuk periode yang benar-benar mendapat baris
       fact baru (file BPS biasanya kumulatif).
    4. Catat progres ke automation_job_logs, status akhir ke automation_jobs.

Catatan: wrapper ini fokus pada penambahan periode baru. Mengunggah ulang file
lama dengan nilai yang direvisi belum menghapus fact lama (di luar scope).
"""
import argparse
import calendar
import json
import os
import sys
import traceback

import openpyxl
import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "database", "scripts")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from backend.db import get_connection  # noqa: E402
import etl_bps  # noqa: E402
import generate_raw_exim as gre  # noqa: E402


def log(conn, job_id, level, message, data=None):
    print(f"[{level}] {message}" + (f" {data}" if data else ""), flush=True)
    if job_id is None:
        return
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO automation_job_logs (id_job, level, message, data_json) "
        "VALUES (%s,%s,%s,%s)",
        (job_id, level, message, json.dumps(data, default=str) if data else None),
    )
    conn.commit()


def file_periods(path):
    """Kumpulkan pasangan (tahun, bulan) unik dari workbook BPS."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None) or ()
        names = [str(c or "").strip().lower() for c in header]
        try:
            i_tahun = names.index("tahun")
            i_bulan = names.index("bulan")
        except ValueError:
            raise RuntimeError("kolom 'tahun'/'bulan' tidak ditemukan di header file")

        periods = set()
        for row in rows:
            if row is None:
                continue
            try:
                tahun = int(row[i_tahun])
                bulan = int(row[i_bulan])
            except (TypeError, ValueError, IndexError):
                continue
            if 2000 <= tahun <= 2100 and 1 <= bulan <= 12:
                periods.add((tahun, bulan))
        return periods
    finally:
        wb.close()


def ensure_periods(conn, periods):
    """Buat ms_period yang belum ada. Return jumlah baris baru."""
    cur = conn.cursor()
    created = 0
    for tahun, bulan in sorted(periods):
        last_day = calendar.monthrange(tahun, bulan)[1]
        label = f"{tahun:04d}-{bulan:02d}"
        cur.execute(
            "SELECT id FROM ms_period WHERE tahun=%s AND bulan=%s",
            (tahun, bulan),
        )
        if cur.fetchone():
            continue
        cur.execute(
            """INSERT INTO ms_period
               (tahun, bulan, label, tanggal_mulai, tanggal_akhir, is_active)
               VALUES (%s,%s,%s,%s,%s,1)""",
            (
                tahun,
                bulan,
                label,
                f"{tahun:04d}-{bulan:02d}-01",
                f"{tahun:04d}-{bulan:02d}-{last_day:02d}",
            ),
        )
        created += 1
    conn.commit()
    return created


def affected_periods(conn, upload_id, exim_type):
    """Periode yang mendapat baris fact baru dari upload ini."""
    cur = conn.cursor()
    if exim_type == "ekspor":
        sql = """SELECT DISTINCT f.id_ms_period
                 FROM bps_export f
                 JOIN bps_export_raw r ON r.id = f.id_bps_export_raw
                 WHERE r.id_bps_upload=%s
                 ORDER BY f.id_ms_period"""
    else:
        sql = """SELECT DISTINCT f.id_ms_period
                 FROM bps_import f
                 JOIN bps_import_raw r ON r.id = f.id_bps_import_raw
                 WHERE r.id_bps_upload=%s
                 ORDER BY f.id_ms_period"""
    cur.execute(sql, (upload_id,))
    return [r[0] for r in cur.fetchall()]


def set_job(conn, job_id, status, error=None, finished=False, params=None):
    cur = conn.cursor()
    sets = ["status=%s", "error_message=%s"]
    vals = [status, error]
    if status == "RUNNING":
        sets.append("started_at=COALESCE(started_at, NOW())")
        sets.append("attempts=attempts+1")
    if finished:
        sets.append("finished_at=NOW()")
    if params is not None:
        sets.append("params_json=%s")
        vals.append(json.dumps(params, default=str))
    vals.append(job_id)
    cur.execute(f"UPDATE automation_jobs SET {', '.join(sets)} WHERE id=%s", vals)
    conn.commit()


def main():
    ap = argparse.ArgumentParser(description="Update data BPS periode baru")
    ap.add_argument("--ekspor", help="path file xlsx BPS ekspor")
    ap.add_argument("--impor", help="path file xlsx BPS impor")
    ap.add_argument("--job-id", type=int, required=True,
                    help="automation_jobs.id (dibuat API)")
    ap.add_argument("--force", action="store_true", help="reload walau hash file sama")
    args = ap.parse_args()
    if not args.ekspor and not args.impor:
        ap.error("butuh --ekspor atau --impor")

    job_id = args.job_id
    conn = get_connection(cursorclass=pymysql.cursors.Cursor)
    params = {}
    try:
        cur = conn.cursor()
        cur.execute("SELECT params_json FROM automation_jobs WHERE id=%s", (job_id,))
        row = cur.fetchone()
        if not row:
            print(f"ERROR: job #{job_id} tidak ditemukan", file=sys.stderr)
            sys.exit(1)
        try:
            params = json.loads(row[0]) if row[0] else {}
        except Exception:  # noqa: BLE001
            params = {}

        set_job(conn, job_id, "RUNNING")
        log(conn, job_id, "info", "Update BPS dimulai", {
            "ekspor": os.path.basename(args.ekspor) if args.ekspor else None,
            "impor": os.path.basename(args.impor) if args.impor else None,
            "force": args.force,
        })

        # 1) Pastikan periode baru tersedia sebelum validasi ETL.
        input_periods = set()
        for path in (args.ekspor, args.impor):
            if not path:
                continue
            if not os.path.isfile(path):
                raise RuntimeError(f"file tidak ditemukan: {path}")
            periods = file_periods(path)
            input_periods |= periods
            log(conn, job_id, "info",
                f"{os.path.basename(path)}: {len(periods)} periode terdeteksi",
                {"periode": [f"{y:04d}-{m:02d}" for y, m in sorted(periods)]})
        if not input_periods:
            raise RuntimeError("tidak ada periode valid di file BPS")

        created = ensure_periods(conn, input_periods)
        if created:
            log(conn, job_id, "info", f"{created} periode baru ditambahkan ke ms_period")
        else:
            log(conn, job_id, "info", "semua periode sudah ada di ms_period")

        # 2) ETL memakai cursor tuple (etl_bps.py), generation memakai DictCursor.
        master_ids = etl_bps.load_masters(conn.cursor())
        affected = {}
        uploads = {}

        for exim_type, path in (("ekspor", args.ekspor), ("impor", args.impor)):
            if not path:
                continue
            log(conn, job_id, "info", f"ETL {exim_type} dimulai")
            upload_id, total = etl_bps.ingest_file(
                conn, master_ids, path, exim_type, args.force
            )
            if not upload_id:
                raise RuntimeError(f"ingest {exim_type} gagal: tidak ada baris data")

            cur = conn.cursor()
            cur.execute("SELECT status, row_count FROM bps_upload WHERE id=%s", (upload_id,))
            upload_status, row_count = cur.fetchone()
            cur.execute(
                "UPDATE bps_upload SET uploaded_by=COALESCE(uploaded_by, %s) WHERE id=%s",
                (params.get("requested_by_id"), upload_id),
            )
            conn.commit()

            if total == 0 and upload_status == "processed":
                log(conn, job_id, "info",
                    f"{exim_type}: file sudah pernah diproses (upload #{upload_id}), dilewati",
                    {"upload_id": upload_id, "status": upload_status})
                continue

            fact_count = etl_bps.transform_fact(conn, upload_id, exim_type)
            reconciled = etl_bps.reconcile(conn, upload_id)
            log(conn, job_id, "info" if reconciled else "warn",
                f"{exim_type}: {fact_count} baris fact (upload #{upload_id})",
                {"upload_id": upload_id, "row_count": row_count,
                 "fact_count": fact_count, "reconciled": reconciled})
            uploads[exim_type] = {
                "upload_id": upload_id,
                "row_count": row_count,
                "fact_count": fact_count,
                "reconciled": bool(reconciled),
            }
            if not reconciled:
                raise RuntimeError(
                    f"rekonsiliasi {exim_type} tidak cocok "
                    f"(sumber={row_count}, fact={fact_count}) — periksa file BPS"
                )
            affected[exim_type] = affected_periods(conn, upload_id, exim_type)

        # 3) Regenerasi raw_exim untuk periode yang berubah.
        if not affected:
            log(conn, job_id, "info", "tidak ada periode baru yang perlu diregenerasi")
            summary = {"uploads": uploads, "regenerated": {}, "created_periods": created}
            params["result"] = summary
            set_job(conn, job_id, "SUCCESS", finished=True, params=params)
            log(conn, job_id, "info", "Update BPS selesai (tanpa perubahan data)")
            return

        conn_gen = get_connection()
        try:
            masters = gre.load_masters(conn_gen)
            regenerated = {}
            for exim_type, period_ids in affected.items():
                for period_id in period_ids:
                    cur = conn_gen.cursor()
                    cur.execute(
                        "SELECT tahun, bulan, label FROM ms_period WHERE id=%s",
                        (period_id,),
                    )
                    p = cur.fetchone()
                    label = p["label"] if p else str(period_id)
                    cur.execute(
                        "DELETE FROM raw_exim WHERE exim_type=%s AND id_ms_period=%s",
                        (exim_type, period_id),
                    )
                    conn_gen.commit()
                    res = gre.generate(
                        conn_gen, exim_type, masters, job_id, period_id, force=True
                    )
                    log(conn_gen, job_id, "info" if res["errors"] == 0 else "warn",
                        f"raw_exim {exim_type} {label} dibuat ulang",
                        res)
                    regenerated.setdefault(exim_type, {})[label] = {
                        "src_total": res["src_total"],
                        "attempted": res["attempted"],
                        "errors": res["errors"],
                    }
                    if res["errors"]:
                        raise RuntimeError(
                            f"gagal membuat raw_exim {exim_type} {label}: "
                            f"{res['errors']} baris error"
                        )
        finally:
            conn_gen.close()

        summary = {"uploads": uploads, "regenerated": regenerated,
                   "created_periods": created}
        params["result"] = summary
        set_job(conn, job_id, "SUCCESS", finished=True, params=params)
        log(conn, job_id, "info", "Update BPS selesai", summary)
    except Exception as e:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        detail = traceback.format_exc()
        print(detail, flush=True)
        try:
            log(conn, job_id, "error", f"Update BPS gagal: {e}")
            params["error"] = str(e)
            set_job(conn, job_id, "FAILED", error=str(e)[:4000],
                    finished=True, params=params)
        except Exception:  # noqa: BLE001
            pass
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

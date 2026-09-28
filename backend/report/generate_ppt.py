#!/usr/bin/env python3
"""
Template-driven laporan PPT (rework PHASE 7 per arahan pengguna).

PPT dihasilkan dengan mengisi data dari DB raw_exim ke dalam TEMPLATE resmi:
`Draft_EKSIM_Jan-Juni_2026_06082026 (1).pptx` (isi angka/teks/chart diganti;
layout, gambar, dan desain deck dipertahankan). Bukan membangun slide dari nol.

Mesin filler: backend/report/template_fill.py (fill spec berbasis konten,
cocokkan teks referensi deck -> nilai hasil perhitungan DB).

  .venv/bin/python backend/report/generate_ppt.py --tahun 2026 --bulan-awal 1 --bulan-akhir 6
  .venv/bin/python backend/report/generate_ppt.py --tahun 2026 --bulan-awal 1 --bulan-akhir 6 --output myreport.pptx
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pptx import Presentation  # noqa: E402
from pptx.util import Emu  # noqa: E402

from backend.db import get_connection  # noqa: E402
from backend.report.template_fill import (  # noqa: E402
    collect_data,
    fill_presentation,
)

BULAN_ID = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

REPORT_DIR = os.environ.get("PATH_REPORT", os.path.join(ROOT, "data", "reports"))

TEMPLATE_PATH = os.environ.get(
    "TEMPLATE_PPT",
    os.path.join(ROOT, "Draft_EKSIM_Jan-Juni_2026_06082026 (1).pptx"),
)


def generate(tahun, b1, b2, output=None, created_by=None):
    conn = get_connection()
    cur = conn.cursor()
    corr = uuid.uuid4().hex
    cur.execute(
        """INSERT INTO automation_jobs (job_type, status, params_json, attempts, correlation_id, started_at, created_by)
           VALUES ('report_ppt', 'RUNNING', %s, 1, %s, NOW(), %s)""",
        (json.dumps({"tahun": tahun, "bulan_awal": b1, "bulan_akhir": b2}), corr, created_by),
    )
    job_id = cur.lastrowid
    conn.commit()

    def log(level, msg, data=None):
        c2 = conn.cursor()
        c2.execute("INSERT INTO automation_job_logs (id_job, level, message, data_json) VALUES (%s,%s,%s,%s)",
                   (job_id, level, msg, json.dumps(data) if data else None))
        conn.commit()

    try:
        if not os.path.isfile(TEMPLATE_PATH):
            raise RuntimeError(f"template PPT tidak ditemukan: {TEMPLATE_PATH}")
        data = collect_data(conn, tahun, b1, b2)
        log("info", "data terkumpul", {"tahun": tahun, "b1": b1, "b2": b2})

        prs = Presentation(TEMPLATE_PATH)
        stats = fill_presentation(prs, data)
        log("info", "template terisi", {"per_slide": stats, "total": sum(stats.values())})

        os.makedirs(REPORT_DIR, exist_ok=True)
        if output is None:
            fname = f"EKSIM_{BULAN_ID[b1]}-{BULAN_ID[b2]}_{tahun}_{datetime.now():%Y%m%d_%H%M%S}.pptx"
            output = os.path.join(REPORT_DIR, fname)
        prs.save(output)
        log("info", "PPT tersimpan", {"file": output})

        cur.execute("UPDATE automation_jobs SET status='SUCCESS', finished_at=NOW() WHERE id=%s", (job_id,))
        conn.commit()
        conn.close()
        return output, job_id
    except Exception as e:  # noqa: BLE001
        log("error", str(e))
        cur.execute("UPDATE automation_jobs SET status='FAILED', finished_at=NOW(), error_message=%s WHERE id=%s",
                    (str(e), job_id))
        conn.commit()
        conn.close()
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tahun", type=int, default=2026)
    ap.add_argument("--bulan-awal", type=int, default=1)
    ap.add_argument("--bulan-akhir", type=int, default=6)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()
    out, job_id = generate(args.tahun, args.bulan_awal, args.bulan_akhir, args.output)
    print(f"SUKSES: {out} (job {job_id}, template: {TEMPLATE_PATH})")


if __name__ == "__main__":
    main()
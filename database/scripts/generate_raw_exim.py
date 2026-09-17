#!/usr/bin/env python3
"""
PHASE 3 — RAW EXIM Generation

Pipeline: bps_export/bps_import + master/bridge -> raw_exim (46 kolom).

Setiap baris fakt (grain periode+HS+prov+pelabuhan+negara+vol+nilai) diturunkan
menjadi 1 baris raw_exim sesuai format file referensi `Raw_Eksim_Expor .xlsx`.

Sumber nilai (terverifikasi audit 2026-06, 4.114 baris):
    kode_hs_2dg              <- ms_hscode.hs_bab_2digit
    non_konsumsi_konsumsi    <- ms_hscode.kategori_konsumsi (Konsumsi->K, Non-Konsumsi->N)
    olahan_bukan             <- ms_hscode.status_olahan (Olahan->O, Non-Olahan->N)
    asalbahanbaku            <- ms_hscode.asal_bahan_baku
    komoditas_1_2017         <- bridge ms_komoditas_hscode (kolom_sumber='komoditas_1_2017').nama
    komoditas_2_2017         <- bridge komoditas_1_2017.nama_en
    komoditas_4_2024         <- bridge kolom_sumber='komoditas_4_2024'.nama
    bentuk_1/bentuk_2        <- bridge 'bentuk_1'.nama / .nama_en
    jenis                    <- bridge 'jenis'.nama
    uraian                   <- uraian_id + '/' + lower(uraian_en)  (format file)
    uraian_2                 <- ms_hscode.uraian_en
    provinsi/pelabuhan/negara<- ms_provinsi / ms_pelabuhan / ms_negara
    harga_usd_kg             <- nil_usd / vol_kg
    ttc                      <- ms_hscode.kategori_tuna ('Bukan TTC'->'0')
    rendemen                 <- ms_hscode.rendemen
    setara_segar             <- vol_kg / rendemen
    moda                     <- ms_pelabuhan.moda
    koding                   <- ms_hscode.kode_kelompok
    tahun_bulan              <- f'{tahun}{bulan:02d}'
    kurs_usd                 <- ms_kurs.rata_rata_kurs per periode
    nilai_rp                 <- nil_usd * kurs_usd (round 2)
    komoditas_5_2026         <- ms_hscode.kelompok_komoditas
    bentuk_3_2026/bentuk_4_2026 <- bridge 'bentuk_3_2026'.nama / .nama_en
    jenis_2_2026             <- bridge 'jenis_2_2026'.nama
    uraian_id_en_2_2026      <- sama dengan uraian
    bentuk_5_2026            <- bridge 'bentuk_5_2026'.nama

Kolom tanpa sumber (mis. KODE HS 2012 selalu kosong di file) -> NULL.

NEEDS VALIDATION (selaras audit, lihat ms_reference):
    - kurs_usd: nilai placeholder dari file referensi; periode lain tanpa ms_kurs -> NULL
    - uraian/uraian_id_en_2_2026: file memakai teks "master HS v2" yang beda utk sebagian HS
    - pelabuhan_muat_bongkar/pelabuhan nama: sebagian file memakai nama master v2
    - kode_provinsi_pelabuhan: kita pakai relasi benar (ms_pelabuhan->ms_provinsi);
      file referensi memakai sumber lain yg tidak konsisten

Idempotent: UNIQUE(id_bps_export)/(id_bps_import) + INSERT IGNORE.
Setiap run tercatat di automation_jobs + automation_job_logs.

Usage:
    python3 database/scripts/generate_raw_exim.py [--force] [--period 2026-06] [--job-user ID]
"""
import argparse
import json
import os
import sys
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from backend.db import get_connection  # noqa: E402

BATCH = 2000

KONSUMSI_MAP = {"Konsumsi": "K", "Non-Konsumsi": "N"}
OLAHAN_MAP = {"Olahan": "O", "Non-Olahan": "N"}
TTC_MAP = {"Tuna": "Tuna", "Cakalang-Tongkol": "Cakalang-Tongkol", "Bukan TTC": "0"}

COLS = [
    "exim_type", "id_ms_period", "id_bps_export", "id_bps_import", "tahun", "bulan",
    "kode_hs_2012", "kode_hs_2022", "kode_hs_2dg", "non_konsumsi_konsumsi", "olahan_bukan",
    "asalbahanbaku", "komoditas_1_2017", "komoditas_2_2017", "komoditas_4_2024",
    "bentuk_1", "bentuk_2", "jenis", "uraian", "uraian_2",
    "kode_prov_asal", "provinsi_asal", "pulau_prov_asal",
    "kode_pelabuhan_muat", "pelabuhan_muat_bongkar",
    "kode_provinsi_pelabuhan", "provinsi_pelabuhan", "pulau_prov_pelabuhan",
    "kode_negara", "negara", "kelompok_negara",
    "vol_kg", "nil_usd", "harga_usd_kg", "ttc", "rendemen", "setara_segar", "moda", "koding",
    "tahun_bulan", "kurs_usd", "nilai_rp",
    "asalbahanbaku_2_2026", "komoditas_5_2026",
    "bentuk_3_2026", "bentuk_4_2026", "jenis_2_2026", "uraian_id_en_2_2026", "bentuk_5_2026",
    "status", "id_generated_by_job",
]


def d(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def dec_or_none(v, places=None):
    x = d(v)
    if x is None:
        return None
    if places is not None:
        x = x.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return x


def load_masters(conn):
    cur = conn.cursor()
    m = {}

    cur.execute("SELECT id, tahun, bulan FROM ms_period")
    m["period"] = {r["id"]: r for r in cur.fetchall()}

    cur.execute("""
        SELECT id, kode_hs, hs_bab_2digit, uraian_id, uraian_en, kelompok_komoditas,
               kategori_konsumsi, status_olahan, asal_bahan_baku, rendemen, kategori_tuna,
               kode_kelompok
        FROM ms_hscode
    """)
    m["hscode"] = {r["id"]: r for r in cur.fetchall()}

    cur.execute("SELECT id, kode_provinsi, nama_provinsi, pulau FROM ms_provinsi")
    m["provinsi"] = {r["id"]: r for r in cur.fetchall()}

    cur.execute("SELECT id, kode_pelabuhan, nama_pelabuhan, moda, id_provinsi FROM ms_pelabuhan")
    m["pelabuhan"] = {r["id"]: r for r in cur.fetchall()}

    cur.execute("SELECT id, kode_negara, nama_negara, kelompok_negara FROM ms_negara")
    m["negara"] = {r["id"]: r for r in cur.fetchall()}

    cur.execute("SELECT id_ms_period, rata_rata_kurs FROM ms_kurs")
    m["kurs"] = {r["id_ms_period"]: r["rata_rata_kurs"] for r in cur.fetchall()}

    cur.execute("""
        SELECT kh.ms_hscode_id, kh.kolom_sumber, k.nama, k.nama_en
        FROM ms_komoditas_hscode kh
        JOIN ms_komoditas k ON k.id = kh.ms_komoditas_id
    """)
    bridge = {}
    for r in cur.fetchall():
        bridge.setdefault(r["ms_hscode_id"], {})[r["kolom_sumber"]] = (r["nama"], r["nama_en"])
    m["bridge"] = bridge

    return m


def prov_of(m, prov_id):
    p = m["provinsi"].get(prov_id)
    if not p:
        return (None, None, None)
    return (p["kode_provinsi"], p["nama_provinsi"], p["pulau"])


def build_row(exim_type, src, m, job_id):
    hs = m["hscode"].get(src["id_ms_hscode"])
    if not hs:
        return None, "hscode tidak ditemukan"

    period = m["period"].get(src["id_ms_period"])
    if not period:
        return None, "periode tidak ditemukan"
    tahun, bulan = period["tahun"], period["bulan"]

    if exim_type == "ekspor":
        prov_id = src["kode_provinsi_asal"]
        pel_id = src["kode_pelabuhan_muat"]
        negara_id = src["kode_negara"]
    else:
        prov_id = src["kode_provinsi_bongkar"]
        pel_id = src["kode_pelabuhan_bongkar"]
        negara_id = src["kode_negara_asal"]

    pu = m["provinsi"].get(prov_id)
    pel = m["pelabuhan"].get(pel_id)
    neg = m["negara"].get(negara_id)

    kode_prov_asal, provinsi_asal, pulau_asal = prov_of(m, prov_id)

    kode_pel = kode_pel_nama = moda = None
    kode_prov_pel = prov_pel = pulau_pel = None
    if pel:
        kode_pel = pel["kode_pelabuhan"]
        kode_pel_nama = pel["nama_pelabuhan"]
        moda = pel["moda"]
        kode_prov_pel, prov_pel, pulau_pel = prov_of(m, pel["id_provinsi"])

    kode_neg = nama_neg = kelompok_neg = None
    if neg:
        kode_neg = neg["kode_negara"]
        nama_neg = neg["nama_negara"]
        kelompok_neg = neg["kelompok_negara"]

    br = m["bridge"].get(src["id_ms_hscode"], {})

    def b(kolom, idx):
        v = br.get(kolom)
        return v[idx] if v else None

    uraian = None
    if hs["uraian_id"] is not None or hs["uraian_en"] is not None:
        uraian = f"{hs['uraian_id'] or ''}/{(hs['uraian_en'] or '').lower()}"

    vol = d(src["volume_kg"])
    nil = d(src["nilai_usd"])
    harga = None
    if vol is not None and vol > 0 and nil is not None:
        harga = dec_or_none(nil / vol, 6)

    rendemen = d(hs["rendemen"])
    setara = None
    if vol is not None and rendemen is not None and rendemen > 0:
        setara = dec_or_none(vol / rendemen, 4)

    kurs = m["kurs"].get(src["id_ms_period"])
    nilai_rp = None
    if kurs is not None and nil is not None:
        nilai_rp = dec_or_none(nil * d(kurs), 2)

    asal = hs["asal_bahan_baku"]
    komoditas_5 = hs["kelompok_komoditas"]

    status = "ready"
    if kurs is None:
        status = "needs_validation"
    if not (hs and pu and pel and neg):
        status = "needs_validation"

    row = (
        exim_type, src["id_ms_period"],
        src["id"] if exim_type == "ekspor" else None,
        src["id"] if exim_type == "impor" else None,
        tahun, bulan,
        None, hs["kode_hs"], hs["hs_bab_2digit"],
        KONSUMSI_MAP.get(hs["kategori_konsumsi"]),
        OLAHAN_MAP.get(hs["status_olahan"]),
        asal,
        b("komoditas_1_2017", 0), b("komoditas_1_2017", 1), b("komoditas_4_2024", 0),
        b("bentuk_1", 0), b("bentuk_1", 1), b("jenis", 0),
        uraian, hs["uraian_en"],
        kode_prov_asal, provinsi_asal, pulau_asal,
        kode_pel, kode_pel_nama,
        kode_prov_pel, prov_pel, pulau_pel,
        kode_neg, nama_neg, kelompok_neg,
        vol, nil, harga,
        TTC_MAP.get(hs["kategori_tuna"]),
        rendemen, setara, moda, hs["kode_kelompok"],
        f"{tahun}{bulan:02d}", dec_or_none(kurs, 4) if kurs is not None else None, nilai_rp,
        asal, komoditas_5,
        b("bentuk_3_2026", 0), b("bentuk_3_2026", 1), b("jenis_2_2026", 0),
        uraian, b("bentuk_5_2026", 0),
        status, job_id,
    )
    return row, None


def fetch_batch(cur, table, last_id, exim_type):
    if table == "bps_export":
        cur.execute("""
            SELECT id, id_ms_period, id_ms_hscode, kode_provinsi_asal, kode_provinsi_muat,
                   kode_pelabuhan_muat, kode_negara, volume_kg, nilai_usd
            FROM bps_export WHERE id > %s ORDER BY id LIMIT %s
        """, (last_id, BATCH))
    else:
        cur.execute("""
            SELECT id, id_ms_period, id_ms_hscode, kode_provinsi_bongkar,
                   kode_pelabuhan_bongkar, kode_negara_asal, volume_kg, nilai_usd
            FROM bps_import WHERE id > %s ORDER BY id LIMIT %s
        """, (last_id, BATCH))
    return cur.fetchall()


def generate(conn, exim_type, m, job_id, period_filter=None, force=False):
    cur = conn.cursor()
    table = "bps_export" if exim_type == "ekspor" else "bps_import"

    generated = 0
    errors = 0
    error_examples = []

    cur.execute(
        f"SELECT COUNT(*) AS n FROM {table}" + (
            " WHERE id_ms_period=%s" if period_filter else ""),
        (period_filter,) if period_filter else ())
    src_total = cur.fetchone()["n"]

    last_id = 0
    while True:
        rows = fetch_batch(cur, table, last_id, exim_type)
        if not rows:
            break
        last_id = rows[-1]["id"]

        payload = []
        for src in rows:
            if period_filter and src["id_ms_period"] != period_filter:
                continue
            row, err = build_row(exim_type, src, m, job_id)
            if row is None:
                errors += 1
                if len(error_examples) < 5:
                    error_examples.append(f"id={src['id']}: {err}")
                continue
            payload.append(row)

        if payload:
            placeholders = "(" + ",".join(["%s"] * len(COLS)) + ")"
            cur.executemany(
                f"INSERT IGNORE INTO raw_exim ({','.join(COLS)}) VALUES {placeholders}",
                payload,
            )
            generated += len(payload)
        conn.commit()

    cur.execute("SELECT COUNT(*) AS n FROM raw_exim WHERE exim_type=%s", (exim_type,))
    inserted = cur.fetchone()["n"]
    return {
        "src_total": src_total, "attempted": generated, "inserted": inserted,
        "errors": errors, "error_examples": error_examples,
    }


def log(conn, job_id, level, message, data=None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO automation_job_logs (id_job, level, message, data_json) VALUES (%s,%s,%s,%s)",
        (job_id, level, message, json.dumps(data) if data else None),
    )
    conn.commit()


def create_job(conn, exim_type, period, created_by):
    cur = conn.cursor()
    corr = uuid.uuid4().hex
    cur.execute(
        """INSERT INTO automation_jobs
           (job_type, id_ms_period, status, params_json, attempts, correlation_id,
            started_at, created_by)
           VALUES ('raw_exim', %s, 'RUNNING', %s, 1, %s, NOW(), %s)""",
        (period, json.dumps({"exim_type": exim_type}), corr, created_by),
    )
    job_id = cur.lastrowid
    conn.commit()
    return job_id, corr


def finish_job(conn, job_id, status, error=None):
    cur = conn.cursor()
    cur.execute(
        "UPDATE automation_jobs SET status=%s, finished_at=NOW(), error_message=%s WHERE id=%s",
        (status, error, job_id),
    )
    conn.commit()


def main():
    ap = argparse.ArgumentParser(description="Generate raw_exim dari bps_export/bps_import")
    ap.add_argument("--force", action="store_true",
                    help="hapus raw_exim (scope terpilih) sebelum generate")
    ap.add_argument("--period", help="filter periode YYYY-MM (mis. 2026-06)")
    ap.add_argument("--job-user", type=int, default=None, help="created_by (app_users.id)")
    ap.add_argument("--ekspor-only", action="store_true")
    ap.add_argument("--impor-only", action="store_true")
    args = ap.parse_args()

    period_id = None
    if args.period:
        y, mo = args.period.split("-")
        conn0 = get_connection()
        cur0 = conn0.cursor()
        cur0.execute("SELECT id FROM ms_period WHERE tahun=%s AND bulan=%s", (int(y), int(mo)))
        r = cur0.fetchone()
        if not r:
            print(f"ERROR: periode {args.period} tidak ada di ms_period")
            sys.exit(1)
        period_id = r["id"]
        conn0.close()

    conn = get_connection()
    m = load_masters(conn)
    print(f"[load] hscode={len(m['hscode'])} provinsi={len(m['provinsi'])} "
          f"pelabuhan={len(m['pelabuhan'])} negara={len(m['negara'])} kurs={len(m['kurs'])}")

    types = ["ekspor", "impor"]
    if args.ekspor_only:
        types = ["ekspor"]
    if args.impor_only:
        types = ["impor"]

    ok = True
    for exim_type in types:
        job_id, corr = create_job(conn, exim_type, period_id, args.job_user)
        print(f"\n=== {exim_type} (job={job_id} corr={corr[:12]}...) ===")
        log(conn, job_id, "info", f"generate {exim_type} mulai",
            {"period": args.period, "force": args.force})

        if args.force:
            cur = conn.cursor()
            if period_id:
                cur.execute("DELETE FROM raw_exim WHERE exim_type=%s AND id_ms_period=%s",
                            (exim_type, period_id))
            else:
                cur.execute("DELETE FROM raw_exim WHERE exim_type=%s", (exim_type,))
            conn.commit()
            print(f"  [force] hapus {cur.rowcount} baris raw_exim {exim_type}")

        try:
            res = generate(conn, exim_type, m, job_id, period_id, args.force)
            status = "SUCCESS" if res["errors"] == 0 else "FAILED"
            finish_job(conn, job_id, status)
            log(conn, job_id, "info", f"generate {exim_type} selesai", res)
            print(f"  [src] {res['src_total']} baris fakt -> [attempted] {res['attempted']} "
                  f"-> [raw_exim] {res['inserted']} (error={res['errors']})")
            if res["error_examples"]:
                print("  error contoh:", res["error_examples"])
            cur = conn.cursor()
            cur.execute("""
                SELECT status, COUNT(*) n FROM raw_exim WHERE exim_type=%s
                GROUP BY status ORDER BY n DESC
            """, (exim_type,))
            for r in cur.fetchall():
                print(f"    status {r['status']}: {r['n']}")
            if status == "FAILED":
                ok = False
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            finish_job(conn, job_id, "FAILED", str(e))
            log(conn, job_id, "error", f"generate {exim_type} gagal: {e}")
            print(f"  [ERROR] {e}")
            ok = False

    conn.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

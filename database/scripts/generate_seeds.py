#!/usr/bin/env python3
"""
PROJECT KKP — Seed Generator

Membaca file data verify dari audit dan menghasilkan seed SQL idempotent (INSERT IGNORE):

  master_exim_reference.xlsx   -> ms_negara, ms_provinsi, ms_pelabuhan, ms_hscode,
                                  ms_komoditas, ms_komoditas_hscode
  Raw_Eksim_Expor .xlsx        -> taksonomi 2017/2024/2026 yang TIDAK ada di master
                                  (KOMODITAS-1/2-2017, KOMODITAS-4-2024, KOMODITAS-5-2026,
                                   BENTUK-1/3/4-2026/5, JENIS, JENIS-2-2026)

Output ditulis ke database/seeds/*.sql.
Masuk akal dijalankan ulang setiap master/lookup diperbarui (PHASE 2 memakai hasil sama).

Usage:
    python3 database/scripts/generate_seeds.py [path_project]
"""

import calendar
import os
import sys
from datetime import date

from openpyxl import load_workbook

PROJECT = sys.argv[1] if len(sys.argv) > 1 else "/Users/rapotatto/Documents/project-kkp"
SEEDS = os.path.join(PROJECT, "database", "seeds")
MASTER = os.path.join(PROJECT, "master_exim_reference.xlsx")
RAW = os.path.join(PROJECT, "Raw_Eksim_Expor .xlsx")
os.makedirs(SEEDS, exist_ok=True)

W = 82  # wrapping width


def esc(v):
    if v is None:
        return "NULL"
    s = str(v).strip()
    if s == "":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def sql_decimal(v):
    if v is None or str(v).strip() == "":
        return "NULL"
    return str(v)


def load_sheets(path):
    wb = load_workbook(path, data_only=True, read_only=True)
    out = {}
    for sn in wb.sheetnames:
        ws = wb[sn]
        rows = list(ws.iter_rows(values_only=True))
        out[sn] = {"header": rows[0], "rows": rows[1:]}
    return out


def write(name, header_comment, body):
    path = os.path.join(SEEDS, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("-- ==================================================================\n")
        for line in header_comment:
            f.write("-- " + line + "\n")
        f.write("-- Idempotent (INSERT IGNORE).\n")
        f.write("-- ==================================================================\n")
        f.write("USE kkp_exim_platform;\n\n")
        f.write(body)
    print(f"  wrote {name}")


def main():
    print("Loading master_exim_reference.xlsx ...")
    M = load_sheets(MASTER)
    hs = M["ms_hscode"]
    H = {c: i for i, c in enumerate(hs["header"])}
    negara = M["ms_negara"]
    N = {c: i for i, c in enumerate(negara["header"])}
    provinsi = M["ms_provinsi"]
    P = {c: i for i, c in enumerate(provinsi["header"])}
    pelabuhan = M["ms_pelabuhan"]
    PL = {c: i for i, c in enumerate(pelabuhan["header"])}

    # ---- 001 ms_period (rentang data BPS verified: 2022-01 .. 2026-06) -------------
    r_start, r_end = 2022, 2026

    def last_day(y, m):
        return date(y, m, calendar.monthrange(y, m)[1])

    rows = []
    for y in range(r_start, r_end + 1):
        for m in range(1, 13):
            if (y, m) > (2026, 6):
                break
            fm = date(y, m, 1)
            rows.append(
                f"({y}, {m}, {esc(f'{y}-{m:02d}')}, {esc(fm.isoformat())}, {esc(last_day(y, m).isoformat())})"
            )
    body = (
        "INSERT IGNORE INTO ms_period (tahun, bulan, label, tanggal_mulai, tanggal_akhir) VALUES\n"
        + ",\n".join(rows)
        + ";\n"
    )
    write(
        "001_ms_period.sql",
        ["ms_period: periode bulanan 2022-01..2026-06 (rentang data BPS verified)."],
        body,
    )

    # ---- 002 ms_negara ------------------------------------------------------------
    rows = []
    for r in negara["rows"]:
        if r[N["kd_negara"]] is None:
            continue
        rows.append(
            f"({esc(r[N['kd_negara']])}, {esc(r[N['nm_negara']])}, {esc(r[N['kelompok_negara']])})"
        )
    body = (
        "INSERT IGNORE INTO ms_negara (kode_negara, nama_negara, kelompok_negara) VALUES\n"
        + ",\n".join(rows)
        + ";\n"
    )
    write(
        "002_ms_negara.sql",
        [f"ms_negara: {len(rows)} baris dari master_exim_reference (sheet ms_negara)."],
        body,
    )

    # ---- 003 ms_provinsi ------------------------------------------------------------
    rows = []
    for r in provinsi["rows"]:
        if r[P["kd_provinsi"]] is None:
            continue
        rows.append(
            f"({esc(r[P['kd_provinsi']])}, {esc(r[P['nm_provinsi']])}, {esc(r[P['pulau']])})"
        )
    body = (
        "INSERT IGNORE INTO ms_provinsi (kode_provinsi, nama_provinsi, pulau) VALUES\n"
        + ",\n".join(rows)
        + ";\n"
    )
    write(
        "003_ms_provinsi.sql",
        [f"ms_provinsi: {len(rows)} baris dari master_exim_reference (sheet ms_provinsi)."],
        body,
    )

    # ---- 004 ms_pelabuhan -------------------------------------------------------------
    rows = []
    for r in pelabuhan["rows"]:
        if r[PL["kd_pelabuhan"]] is None:
            continue
        rows.append(
            f"ROW({esc(r[PL['kd_pelabuhan']])}, {esc(r[PL['nm_pelabuhan']])}, {esc(r[PL['moda']])}, {esc(r[PL['kd_provinsi']])})"
        )
    body = (
        "INSERT IGNORE INTO ms_pelabuhan (kode_pelabuhan, nama_pelabuhan, moda, id_provinsi)\n"
        "SELECT p.kode_pelabuhan, p.nama_pelabuhan, p.moda, pr.id\n"
        "FROM (\n  SELECT * FROM (VALUES\n"
        + ",\n".join(rows)
        + "\n  ) AS v(kode_pelabuhan, nama_pelabuhan, moda, kd_provinsi)\n"
        ") p\n"
        "JOIN ms_provinsi pr ON pr.kode_provinsi = p.kd_provinsi;\n"
    )
    write(
        "004_ms_pelabuhan.sql",
        [
            f"ms_pelabuhan: {len(rows)} baris (moda DARAT/LAUT/UDARA),"
            " FK id_provinsi via join kode_provinsi.",
        ],
        body,
    )

    # ---- 005 ms_unit --------------------------------------------------------------------
    units = [
        ("KG", "Kilogram", "kg", "Berat/kuantitas"),
        ("TON", "Ton", "ton", "Berat (1e3 kg)"),
        ("USD", "US Dollar", "USD", "Nilai ekspor/impor"),
        ("IDR", "Rupiah", "Rp", "Nilai konversi rupiah"),
        ("USD_KG", "USD per KG", "USD/kg", "Harga unit"),
        ("PCT", "Persen", "%", "Proporsi / pertumbuhan"),
        ("QTY", "Quantity", "unit", "Kuantitas item TradeMap"),
    ]
    rows = [f"({esc(u[0])}, {esc(u[1])}, {esc(u[2])}, {esc(u[3])})" for u in units]
    body = "INSERT IGNORE INTO ms_unit (kode, nama, simbol, deskripsi) VALUES\n" + ",\n".join(rows) + ";\n"
    write("005_ms_unit.sql", [f"ms_unit: {len(rows)} satuan dasar."], body)

    # ---- 006 ms_hscode ------------------------------------------------------------------
    cols = [
        "kode_hs",
        "hs_bab_2digit",
        "hs_pos_4digit",
        "hs_subpos_6digit",
        "uraian_id",
        "uraian_en",
        "uraian_bilingual",
        "kelompok_komoditas",
        "jenis_produk",
        "bentuk_produk_id",
        "bentuk_produk_en",
        "kategori_konsumsi",
        "status_olahan",
        "asal_bahan_baku",
        "kbli_2020",
        "uraian_kbli",
        "rendemen",
        "jenis_pengolahan",
        "kategori_tuna",
        "prioritas_ekspor_utama",
        "prioritas_impor_utama",
        "kode_kelompok",
        "status_transaksi_riil",
        "kode_hs_2017_prev",
    ]
    rows = []
    for r in hs["rows"]:
        vals = []
        for c in cols:
            v = r[H[c]]
            if c == "rendemen":
                vals.append(sql_decimal(v))
            else:
                vals.append(esc(v))
        rows.append("(" + ", ".join(vals) + ")")
    body = (
        "INSERT IGNORE INTO ms_hscode ("
        + ", ".join(cols)
        + ") VALUES\n"
        + ",\n".join(rows)
        + ";\n"
    )
    write(
        "006_ms_hscode.sql",
        [f"ms_hscode: {len(rows)} baris (24 kolom, kanonikal HS 2022)."],
        body,
    )

    # ---- 007 ms_komoditas (dictionary) -------------------------------------------------
    # Nomenklatur versions from master
    master_planes = [
        ("komoditas", "kelompok_komoditas", "kelompok_komoditas", "kelompok_komoditas"),
        ("komoditas", "prioritas_ekspor_utama", "prioritas_ekspor_utama", "prioritas_ekspor_utama"),
        ("komoditas", "prioritas_impor_utama", "prioritas_impor_utama", "prioritas_impor_utama"),
        ("jenis", "jenis_produk", "jenis_produk", "jenis_produk"),
        ("bentuk", "bentuk_produk_id", "bentuk_produk_id", "bentuk_produk_en"),
        ("pengolahan", "jenis_pengolahan", "jenis_pengolahan", "jenis_pengolahan"),
        ("tuna", "kategori_tuna", "kategori_tuna", "kategori_tuna"),
        ("asalbahanbaku", "asal_bahan_baku", "asal_bahan_baku", "asal_bahan_baku"),
    ]

    def distinct(rows, col, extra_en=None):
        d = {}
        for r in rows:
            v = r[col]
            if v is None or str(v).strip() == "":
                continue
            key = str(v).strip()
            en = None
            if extra_en is not None:
                ev = r[extra_en]
                if ev is not None and str(ev).strip() != "":
                    en = str(ev).strip()
            d[key] = en or d.get(key)
        return d

    kom_rows = []  # (nomenklatur, versi, nama, en)
    for r in hs["rows"]:
        for nomen, versi, col, encol in master_planes:
            v = r[H[col]]
            if v is None or str(v).strip() == "":
                continue
            en = None
            if encol and encol != col:
                ev = r[H[encol]]
                if ev is not None and str(ev).strip() != "":
                    en = str(ev).strip()
            kom_rows.append((nomen, versi, str(v).strip(), en))
    # dedup by (nomen, versi, nama)
    seen = set()
    ded = []
    for x in kom_rows:
        key = (x[0], x[1], x[2])
        if key in seen:
            continue
        seen.add(key)
        ded.append(x)

    # RAW-derived planes (dictionary hanya; bridge utk 312 HS via 008)
    raw_planes_ids = [
        ("komoditas", "komoditas_1_2017", 9, 10),
        ("komoditas", "komoditas_4_2024", 11, None),
        ("komoditas", "komoditas_5_2026", 40, None),
        ("bentuk", "bentuk_1", 12, 13),
        ("bentuk", "bentuk_3_2026", 41, 42),
        ("bentuk", "bentuk_5_2026", 45, None),
        ("jenis", "jenis", 14, None),
        ("jenis", "jenis_2_2026", 43, None),
    ]

    if os.path.exists(RAW):
        wbr = load_workbook(RAW, data_only=True, read_only=True)
        raw_rows = list(wbr["Sheet1"].iter_rows(values_only=True))[1:]
        for nomen, versi, cid, cen in raw_planes_ids:
            rd = distinct_raw = []
            for r in raw_rows:
                v = r[cid]
                if v is None or str(v).strip() in ("", "0"):
                    continue
                en = None
                if cen is not None:
                    ev = r[cen]
                    if ev is not None and str(ev).strip() not in ("", "0"):
                        en = str(ev).strip()
                key = (nomen, versi, str(v).strip())
                if key in seen:
                    continue
                seen.add(key)
                ded.append((nomen, versi, str(v).strip(), en))
    else:
        print("  RAW EXIM file tidak ditemukan, taksonomi 2026 dilewati.")

    rows = [
        f"({esc(d[0])}, {esc(d[1])}, {esc(d[2])}, {esc(d[3])}, {esc('master_exim_reference' if d[1] in [p[1] for p in master_planes] else 'raw_exim_ekspor_202606')})"
        for d in ded
    ]
    body = (
        "INSERT IGNORE INTO ms_komoditas (nomenklatur, versi, nama, nama_en, sumber) VALUES\n"
        + ",\n".join(rows)
        + ";\n"
    )
    write(
        "007_ms_komoditas.sql",
        [
            f"ms_komoditas: kamus {len(ded)} nilai klasifikasi",
            "  - master_exim_reference (kelompok_komoditas, prioritas_*, jenis_produk,",
            "    bentuk_produk_id/en, jenis_pengolahan, kategori_tuna, asal_bahan_baku)",
            "  - raw_exim_ekspor_202606 (komoditas_1/2-2017, komoditas_4-2024, komoditas_5-2026,",
            "    bentuk_1/3-2026/5, jenis, jenis_2-2026). Nilai '0' (tidak terklasifikasi) dilewati.",
        ],
        body,
    )

    # ---- 008 ms_komoditas_hscode ---------------------------------------------------------
    # Master-sourced planes
    parts = []

    def bridge_master_plane(colname, versi, col):
        vals = []
        for r in hs["rows"]:
            v = r[H[col]]
            if v is None or str(v).strip() == "":
                continue
            vals.append(f"ROW({esc(r[H['kode_hs']])}, {esc(versi)}, {esc(str(v).strip())}, {esc(colname)})")
        if not vals:
            return None
        return (
            "INSERT IGNORE INTO ms_komoditas_hscode "
            "(ms_hscode_id, ms_komoditas_id, kolom_sumber, sumber)\n"
            "WITH s(kode_hs, versi, nama, kolom_sumber) AS (VALUES\n"
            + ",\n".join(vals)
            + ")\n"
            "SELECT h.id, k.id, s.kolom_sumber, 'master_exim_reference'\n"
            "FROM s\n"
            "JOIN ms_hscode h ON h.kode_hs = s.kode_hs\n"
            "JOIN ms_komoditas k ON k.nomenklatur = 'komoditas' AND k.versi = s.versi AND k.nama = s.nama;\n"
        )

    def bridge_raw_plane(colname, versi, cid, nomen):
        if not os.path.exists(RAW):
            return None
        wbr = load_workbook(RAW, data_only=True, read_only=True)
        below = list(wbr["Sheet1"].iter_rows(values_only=True))[1:]
        vals = []
        for r in below:
            v = r[cid]
            if v is None or str(v).strip() in ("", "0"):
                continue
            vals.append(f"ROW({esc(r[4])}, {esc(versi)}, {esc(str(v).strip())}, {esc(colname)})")
        if not vals:
            return None
        return (
            "INSERT IGNORE INTO ms_komoditas_hscode "
            "(ms_hscode_id, ms_komoditas_id, kolom_sumber, sumber)\n"
            "WITH s(kode_hs, versi, nama, kolom_sumber) AS (VALUES\n"
            + ",\n".join(vals)
            + ")\n"
            "SELECT h.id, k.id, s.kolom_sumber, 'raw_exim_ekspor_202606'\n"
            "FROM s\n"
            "JOIN ms_hscode h ON h.kode_hs = s.kode_hs\n"
            f"JOIN ms_komoditas k ON k.nomenklatur = '{nomen}' AND k.versi = s.versi AND k.nama = s.nama;\n"
        )

    parts.append(bridge_master_plane("kelompok_komoditas", "kelompok_komoditas", "kelompok_komoditas"))
    parts.append(bridge_master_plane("prioritas_ekspor_utama", "prioritas_ekspor_utama", "prioritas_ekspor_utama"))
    parts.append(bridge_master_plane("prioritas_impor_utama", "prioritas_impor_utama", "prioritas_impor_utama"))
    parts.append(bridge_master_plane("jenis_produk", "jenis_produk", "jenis_produk",))
    parts.append(bridge_master_plane("bentuk_produk_id", "bentuk_produk_id", "bentuk_produk_id"))
    parts.append(bridge_master_plane("jenis_pengolahan", "jenis_pengolahan", "jenis_pengolahan"))
    parts.append(bridge_master_plane("kategori_tuna", "kategori_tuna", "kategori_tuna"))
    # RAW planes
    parts.append(bridge_raw_plane("komoditas_1_2017", "komoditas_1_2017", 9, "komoditas"))
    parts.append(bridge_raw_plane("komoditas_4_2024", "komoditas_4_2024", 11, "komoditas"))
    parts.append(bridge_raw_plane("komoditas_5_2026", "komoditas_5_2026", 40, "komoditas"))
    parts.append(bridge_raw_plane("bentuk_1", "bentuk_1", 12, "bentuk"))
    parts.append(bridge_raw_plane("bentuk_3_2026", "bentuk_3_2026", 41, "bentuk"))
    parts.append(bridge_raw_plane("bentuk_5_2026", "bentuk_5_2026", 45, "bentuk"))
    parts.append(bridge_raw_plane("jenis", "jenis", 14, "jenis"))
    parts.append(bridge_raw_plane("jenis_2_2026", "jenis_2_2026", 43, "jenis"))
    body = "\n".join(p for p in parts if p)
    write(
        "008_ms_komoditas_hscode.sql",
        ["ms_komoditas_hscode: mapping HS<->komoditas (kolom_sumber utk traceability)."],
        body,
    )

    # ---- 009 ms_reference -----------------------------------------------------------
    refs = [
        ("pipeline", "upload_status_flow", "uploaded -> validating -> valid -> processed",
         "Alur status upload BPS (spec pipeline).", "PHASE1 design", "validated"),
        ("raw_exim", "setara_segar", "vol_kg / rendemen",
         "Verified 4114/4114 baris Juni 2026 (bukan vol*rendemen).", "audit RAW EXIM", "validated"),
        ("raw_exim", "harga", "nil_usd / vol_kg",
         "Verified 0 mismatch pada file Juni 2026.", "audit RAW EXIM", "validated"),
        ("raw_exim", "kurs_juni_2026", "358482 (KONSTAN, bukan kurs riil)",
         "Temuan audit: nilai mirip 'placeholder', bukan kurs JISDOR (~15800).", "audit RAW EXIM", "needs_validation"),
        ("raw_exim", "nilai_rp", "nil_usd * kurs_usd",
         "Formula mengikuti file; akurasi tergantung sumber kurs.", "audit RAW EXIM", "needs_validation"),
        ("raw_exim", "moda_inkonsisten", "Moda sangat tergantung master_pelabuhan; 10/58 pelabuhan punya 2 moda, 2 sel #N/A",
         "Temuan audit: cek master pelabuhan saat pipeline.", "audit RAW EXIM", "needs_validation"),
        ("raw_exim", "kolom_null_510", "510 baris EXIM & KELOMPOK NEGARA NULL (komoditas non-inti)",
         "Temuan audit: artefak batch terpisah, kode negara tersedia di master.", "audit RAW EXIM", "needs_validation"),
        ("raw_exim", "timor_leste_2026", "EAST TIMOR -> Asean (ms_negara masih 'Lainnya')",
         "TL resmi anggota ASEAN 2025; master belum ter-update.", "audit RAW EXIM", "needs_validation"),
        ("raw_exim", "kode_hs_2012", "KOSONG di seluruh file ekspor 2026-06",
         "Kolom cadangan; tidak dipakai pipeline saat ini.", "audit RAW EXIM", "validated"),
        ("kurs", "sumber", "JISDOR Bank Indonesia",
         "Tabel ms_kurs adalah sumber kurs per periode.", "eksim_system legacy + audit", "validated"),
        ("analytics", "market_share", "NEEDS VALIDATION",
         "Formula share ekspor/global belum resmi dikonfirmasi.", None, "needs_validation"),
        ("analytics", "potensi_ekspor", "NEEDS VALIDATION",
         "Formula potensi ekspor belum resmi dikonfirmasi.", None, "needs_validation"),
        ("analytics", "competitor_analysis", "NEEDS VALIDATION",
         "Formula analisis pesaing belum resmi dikonfirmasi.", None, "needs_validation"),
        ("analytics", "import_market", "NEEDS VALIDATION",
         "Formula analisis pasar impor belum resmi dikonfirmasi.", None, "needs_validation"),
        ("analytics", "indonesia_share", "NEEDS VALIDATION",
         "Formula Indonesia share (global market) belum resmi dikonfirmasi.", None, "needs_validation"),
        ("trademap", "credential_storage", ".env / environment variables",
         "Kredensial TIDAK disimpan di database atau source code.", "security spec", "validated"),
        ("trademap", "login_url", "NEEDS VALIDATION",
         "URL login TradeMap/ITC harus dikonfirmasi.", None, "needs_validation"),
        ("ppt", "template", "Draft_EKSIM_Jan-Juni_2026_06082026 (1).pptx",
         "Template resmi eksisting dari audit; angka PPT verified 100%.", "audit", "validated"),
        ("w21", "definisi", "TIDAK DITEMUKAN",
         "Kode W21 tidak muncul di file/pipeline mana pun.", "audit open item", "needs_validation"),
    ]
    rows = [
        f"({esc(r[0])}, {esc(r[1])}, {esc(r[2])}, {esc(r[3])}, {esc(r[4])}, {esc(r[5])})"
        for r in refs
    ]
    body = (
        "INSERT IGNORE INTO ms_reference (ref_group, ref_key, ref_value, deskripsi, sumber, status) VALUES\n"
        + ",\n".join(rows)
        + ";\n"
    )
    write(
        "009_ms_reference.sql",
        ["ms_reference: konfigurasi & catatan temuan audit;" " status needs_validation untuk nilai belum resmi."],
        body,
    )

    # ---- 010 app_roles & permissions --------------------------------------------------
    roles = [("user", "User", "Pengguna platform: melihat/menggunakan fitur"),
             ("pegawai", "Pegawai", "Pengguna + update BPS, validasi, generate PPT, jalankan proses TradeMap"),
             ("super_admin", "Super Admin", "Seluruh permission + administrasi sistem")]
    rows = [f"({esc(r[0])}, {esc(r[1])}, {esc(r[2])})" for r in roles]
    body = "INSERT IGNORE INTO app_roles (kode, nama, deskripsi) VALUES\n" + ",\n".join(rows) + ";\n\n"

    perms = [
        ("explore.view", "Lihat Overview & Market Intelligence", "EXPLORE"),
        ("explore.commodity", "Lihat analisis komoditas", "EXPLORE"),
        ("explore.country", "Lihat analisis negara", "EXPLORE"),
        ("explore.comparison", "Lihat perbandingan", "EXPLORE"),
        ("explore.opportunity", "Lihat peluang pasar", "EXPLORE"),
        ("explore.competition", "Lihat persaingan", "EXPLORE"),
        ("data.view", "Lihat data BPS/RAW EXIM", "DATA"),
        ("data.update_bps_export", "Update data BPS ekspor", "DATA"),
        ("data.update_bps_import", "Update data BPS impor", "DATA"),
        ("data.validate", "Jalankan validasi data", "DATA"),
        ("exim.view", "Lihat RAW EXIM", "DATA"),
        ("exim.generate", "Generate RAW EXIM", "DATA"),
        ("trademap.view", "Lihat data TradeMap", "TRADEMAP"),
        ("trademap.download", "Jalankan unduhan TradeMap", "TRADEMAP"),
        ("trademap.process", "Proses data TradeMap", "TRADEMAP"),
        ("report.view", "Lihat laporan/PPT", "REPORT"),
        ("report.generate_ppt", "Generate PPT otomatis", "REPORT"),
        ("report.templates", "Kelola template PPT", "REPORT"),
        ("ai.use", "Gunakan AI Assistant", "AI"),
        ("system.profile", "Atur profil sendiri", "SYSTEM"),
        ("system.notifications", "Baca notifikasi", "SYSTEM"),
        ("system.audit", "Lihat audit log", "SYSTEM"),
        ("admin.users", "Kelola pengguna", "ADMIN"),
        ("admin.roles", "Kelola role/permission", "ADMIN"),
        ("admin.config", "Konfigurasi sistem", "ADMIN"),
        ("admin.monitor", "Monitoring seluruh proses", "ADMIN"),
        ("jobs.view", "Lihat status job", "SYSTEM"),
        ("jobs.run", "Menjalankan/membatalkan job", "SYSTEM"),
    ]
    rows = [f"({esc(p[0])}, {esc(p[1])}, {esc(p[2])})" for p in perms]
    body += (
        "INSERT IGNORE INTO app_permissions (kode, nama, grup) VALUES\n" + ",\n".join(rows) + ";\n\n"
    )

    user_p = ["explore.view", "explore.commodity", "explore.country", "explore.comparison",
              "explore.opportunity", "explore.competition", "data.view", "exim.view",
              "trademap.view", "report.view", "ai.use", "system.profile", "system.notifications"]
    pegawai_p = user_p + ["data.update_bps_export", "data.update_bps_import", "data.validate",
                          "exim.generate", "trademap.download", "trademap.process",
                          "report.generate_ppt", "report.templates", "jobs.view", "jobs.run"]
    admin_p = [p[0] for p in perms]

    role_map = [
        ("user", user_p),
        ("pegawai", pegawai_p),
        ("super_admin", admin_p),
    ]
    blocks = []
    for rk, plist in role_map:
        inlist = "(" + ", ".join("'" + p + "'" for p in plist) + ")"
        blocks.append(
            "INSERT IGNORE INTO app_role_permissions (app_role_id, app_permission_id)\n"
            "SELECT r.id, p.id FROM app_roles r\n"
            f"JOIN app_permissions p ON p.kode IN {inlist}\n"
            f"WHERE r.kode = '{rk}';\n"
        )
    body += "-- Role -> permissions\n" + "\n".join(blocks) + "\n"
    write(
        "010_app_roles_permissions.sql",
        [
            "app_roles / app_permissions / app_role_permissions.",
            "Matriks: super_admin = semua; pegawai = user + operasional; user = lihat/explore + AI.",
            "User awal (bootstrap) TIDAK di-seed di sini; dibuat via script dari .env (anti plaintext password).",
        ],
        body,
    )

    print("\nSeeds generated into", SEEDS)


if __name__ == "__main__":
    main()
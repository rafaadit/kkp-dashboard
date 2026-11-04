#!/usr/bin/env python3
"""PHASE 8 — Test parser file BPS: format Data Minimum + file bulanan BPS.

Jalankan: python3 tests/test_bps_parser.py
Tidak butuh database; workbook dibuat sementara di direktori temp.
"""
import os
import sys
import tempfile

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "database", "scripts"))

import etl_bps  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def write_sheet(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    wb.close()


def fake_master():
    return {
        "period": {(2026, 7): 1},
        "hscode": {"01062000": 1},
        "provinsi": {"12": 1, "31": 2},
        "pelabuhan": {"IDCGK": 1},
        "negara": {"VN": 1, "MY": 2, "LI": 3},
        "negara_nama": {"VIET NAM": "VN", "MALAYSIA": "MY", "LIECHTENSTEIN": "LI"},
    }


def main():
    master = fake_master()
    with tempfile.TemporaryDirectory() as tmp:
        # --- file bulanan ekspor: header baris 3 + metadata + Grand Total ---
        ekspor = os.path.join(tmp, "ekspor.xlsx")
        write_sheet(ekspor, [
            ["Ekspor Komoditas Perikanan Juli 2026", None, None, None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None, None, None, None],
            ["Tahun ", "Bulan ", "HS 2022", "Provinsi_Asal", "Provinsi_Muat ",
             "Kode Pel_Muat", "Pelabuhan Muat", "Negara Tujuan", "Volume (Kg) ", "FOB (USD) "],
            [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10],
            ["2026", "07", "01062000", "12", "31", "IDCGK",
             "SOEKARNO-HATTA (U)", "VIETNAM", 815, 12097.952],
            ["2026", "07", "01062000", "12", "12", "IDCGK",
             "SOEKARNO-HATTA (U)", "MALAYSIA", 100, 200],
            ["Grand Total", None, None, None, "#N/A", None, "#N/A", "#N/A", 915, 12297.952],
        ])
        rows = list(etl_bps.iter_canonical_rows(ekspor, "ekspor"))
        check("ekspor header baris 3 terdeteksi", len(rows) == 2, str(len(rows)))
        check("ekspor periode 2026-07", etl_bps.periods_in_file(ekspor, "ekspor") == {(2026, 7)})
        row = etl_bps.canonicalize_row(rows[0], "ekspor", master)
        check("ekspor alias kolom benar",
              row["hscode"] == "01062000" and row["kd_provinsi_asal"] == "12"
              and row["kd_provinsi_muat"] == "31" and row["kd_pelabuhan_muat"] == "IDCGK"
              and row["nm_pelabuhan_muat"] == "SOEKARNO-HATTA (U)")
        check("ekspor nama negara VIETNAM -> VN", row["kd_negara"] == "VN", row["kd_negara"])
        ok, err = etl_bps.validate_row(
            {c: etl_bps._txt(row.get(c)) for c in etl_bps.TEXT_COLS_EXPOR},
            etl_bps.TEXT_COLS_EXPOR, master)
        check("ekspor baris valid", ok, err)

        # --- file bulanan impor: kolom berbeda + metadata + Total Impor ---
        impor = os.path.join(tmp, "impor.xlsx")
        write_sheet(impor, [
            ["Impor Produk Ikan Juli 2026", None, None, None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None, None, None, None],
            ["Tahun ", "Bulan ", "HS", "Deskripsi ", "Negara/Wilayah/Entitas Asal",
             "Provinsi ", "Kode Pelabuhan ", "Pelabuhan Bongkar ", "Berat (Kg) ", "Nilai (USD) "],
            [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10],
            ["2026", "07", "01062000", "Live reptiles", "VIETNAM", "31", "IDCGK",
             "SOEKARNO-HATTA (U)", 88, 6971],
            ["Total Impor", None, None, None, None, None, None, None, 88, 6971],
        ])
        rows = list(etl_bps.iter_canonical_rows(impor, "impor"))
        check("impor header baris 3 terdeteksi", len(rows) == 1, str(len(rows)))
        row = etl_bps.canonicalize_row(rows[0], "impor", master)
        check("impor alias kolom benar",
              row["hscode"] == "01062000" and row["kd_provinsi_bongkar"] == "31"
              and row["kd_pelabuhan_bongkar"] == "IDCGK")
        check("impor nama negara VIETNAM -> VN", row["kd_negara_asal"] == "VN", row["kd_negara_asal"])
        check("impor Liechtenstein -> LI", "LIECHTENSTEIN" in master["negara_nama"] and master["negara_nama"]["LIECHTENSTEIN"] == "LI")
        ok, err = etl_bps.validate_row(
            {c: etl_bps._txt(row.get(c)) for c in etl_bps.TEXT_COLS_IMPOR},
            etl_bps.TEXT_COLS_IMPOR, master)
        check("impor baris valid", ok, err)

        # --- format lama: header baris 1 tetap didukung ---
        lama = os.path.join(tmp, "lama.xlsx")
        write_sheet(lama, [
            etl_bps.TEXT_COLS_EXPOR,
            ["2026", "07", "01062000", "12", "31", "IDCGK", "SOEKARNO-HATTA (U)",
             "VN", "VIET NAM", 10, 20],
        ])
        rows = list(etl_bps.iter_canonical_rows(lama, "ekspor"))
        check("format lama header baris 1", len(rows) == 1, str(len(rows)))
        row = etl_bps.canonicalize_row(rows[0], "ekspor", master)
        check("format lama tidak berubah",
              row["kd_negara"] == "VN" and row["volume_kg"] == "10" and row["nilai_usd"] == "20")

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

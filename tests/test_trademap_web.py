#!/usr/bin/env python3
"""PHASE 9b — Robot TradeMap tanpa API key (webscraper legacy.trademap.org).

Menguji parse grid HTML -> CSV bentuk panjang + umpan ke pipeline
(TradeMapProcessor) tanpa perlu jaringan: fixture HTML diambil dari live
site sekali (tests/fixtures/trademap_web_export.html, Indonesia export ke
dunia, level HS4, nilai 2021-2025, unit US Dollar thousand).
Smoke-test live hanya jalan bila TEST_NETWORK=1.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.trademap import webscraper  # noqa: E402

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


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "trademap_web_export.html")
FIXTURE_TITLE = "Indonesia"


def read_fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return fh.read()


def main():
    html_body = read_fixture()
    print("== parse grid dari fixture HTML ==")
    grid = webscraper.extract_grid(html_body)
    check("flow Export terdeteksi dari header", grid.flow == "Export", str(grid.flow))
    check("indikator value", grid.indicator == "value", str(grid.indicator))
    check("tahun 2021..2025", grid.years == [2021, 2022, 2023, 2024, 2025], str(grid.years))
    check("unit US Dollar thousand", grid.unit == "US Dollar thousand", repr(grid.unit))
    check("level HS4", grid.level == "HS4", repr(grid.level))
    codes = [r[0] for r in grid.rows]
    check("ada baris data", len(grid.rows) >= 10, str(len(grid.rows)))
    check("TOTAL tidak disimpan", "TOTAL" not in codes, [c for c in codes if c == "TOTAL"])
    check("semua kode numerik", all(c.isdigit() for c in codes), [c for c in codes if not c.isdigit()])
    check("ada bab ekspor top-24 (energi/mesin)",
          "27" in codes and "84" in codes, [c for c in codes if c in ("27", "84")])
    check("ada bab perikanan 03 (ekspor Indonesia)",
          "03" in codes, [c for c in codes if c == "03"])
    prow = next(r for r in grid.rows if r[0] == "03")
    check("baris 03 punya 5 nilai tahun", len(prow[2]) == 5, str(len(prow[2])))
    check("nilai bab 03 wajar (ribu USD, miliaran)",
          prow[2][4] and int(prow[2][4].replace(",", "")) > 0, prow[2][4])

    print("== melt grid -> CSV bentuk panjang ==")
    import csv as _csv
    import io as _io

    csv_text = webscraper.grid_to_csv(grid, reporter="ID", partner="WLD", flow="Export")
    rows = list(_csv.reader(_io.StringIO(csv_text)))
    check("header sesuai pipeline",
          rows[0] == ["Reporter", "Partner", "Flow", "Product code", "Product Label",
                      "Year", "Trade Value (US$ Thousand)"], rows[0])
    check("1 baris per tahun-produk", len(rows) == 1 + len(grid.rows) * len(grid.years),
          "%d != %d" % (len(rows), 1 + len(grid.rows) * len(grid.years)))
    check("nilai bernilai angka bersih", all(
        r[-1].replace(",", "").isdigit() for r in rows[1:]), rows[1])
    check("kolom flow Export", all(r[2] == "Export" for r in rows[1:]))
    check("tahun integer", all(len(r) == 7 and r[5].isdigit() for r in rows[1:]))

    print("== build query nvpm ==")
    q_eks = webscraper.build_query("Export")
    q_imp = webscraper.build_query("Import")
    check("path Country_SelProduct", q_eks.startswith("/Country_SelProduct_TS.aspx?nvpm="), q_eks)
    check("vnpm ter-encode", "%7C" in q_eks, q_eks)
    check("export vs import beda flag",
          q_eks != q_imp and "360" in q_eks and "TOTAL" in q_eks, "%s | %s" % (q_eks, q_imp))

    print("== sesi: prefix cookieless ASP.NET ==")
    sess = webscraper.TradeMapWebSession(base="https://x.example", delay=0)
    check("target awal tanpa prefix",
          sess.target("/a.aspx?b=1") == "https://x.example/a.aspx?b=1", sess.target("/a.aspx?b=1"))
    sess._prefix = "/(X(1)S(abc123def456))"
    check("target memakai prefix sesi",
          sess.target("/b.aspx") == "https://x.example/(X(1)S(abc123def456))/b.aspx",
          sess.target("/b.aspx"))
    check("prefix regex cocok",
          webscraper._SESSION_PATH.search("https://legacy.trademap.org/(X(1)S(2i0piu5wj))/Bilateral.aspx")
          is not None)

    print("== pipeline TradeMapProcessor menerima CSV robot ==")
    from backend.trademap.processor import TradeMapProcessor

    with tempfile.TemporaryDirectory() as td:
        csv_path = os.path.join(td, "robot_export.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(csv_text)
        proc = TradeMapProcessor()
        try:
            res = proc.process(csv_path)
        finally:
            proc.close()
        check("process ok", res.ok, res.error or "")
        check("record terbaca", res.stats.total_rows == len(grid.rows) * len(grid.years),
              str(res.stats.total_rows))
        g = res.stats.as_dict()
        check("statistik terisi", isinstance(g.get("total_rows"), int) and g.get("total_rows") > 0,
              str(g))

    print("== smoke-test live (hanya bila TEST_NETWORK=1) ==")
    if os.environ.get("TEST_NETWORK", "0") == "1":
        with tempfile.TemporaryDirectory() as td:
            path, grid_live = webscraper.run(flow="Export", download_dir=td,
                                             session=webscraper.TradeMapWebSession(delay=2))
            check("live: file terunduh", os.path.isfile(path), path)
            check("live: grid export",
                  grid_live.flow == "Export" and grid_live.years[-1] >= 2023, repr(grid_live))
    else:
        print("  SKIP  live (set TEST_NETWORK=1 untuk menguji koneksi nyata)")

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
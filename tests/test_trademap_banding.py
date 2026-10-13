#!/usr/bin/env python3
"""PHASE 12 — Test banding industri BPS vs TradeMap (tingkat bab HS, data nyata).

Mengandalkan data nyata yang sudah termuat: TradeMap bab 03 (Export/Import)
dan raw_exim BPS. Beberapa asersi dibuat toleran terhadap variasi kecil data.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.app import create_app

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


def main():
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()
    tok = c.post("/api/auth/login", json={"email": "admin@kkp.local", "password": "admin123"}).get_json()["token"]
    H = {"Authorization": f"Bearer {tok}"}

    print("== /api/trademap/banding_industri (ekspor, bab 03) ==")
    r = c.get("/api/trademap/banding_industri?flow=ekspor", headers=H)
    check("ekspor 200", r.status_code == 200, r.get_data(as_text=True)[:150])
    d = r.get_json()
    check("ref tahun wajar (>=2024)", d["ref_tahun"] >= 2024, str(d["ref_tahun"]))
    check("hs 03 hasil perikanan", d["hs"] == "03" and d["hs_label"] == "hasil perikanan", str(d["hs"]))
    check("seri tahun banyak (>=5)", len(d["seri_tahun"]) >= 5, str(len(d["seri_tahun"])))
    ref = next((s for s in d["seri_tahun"] if s["tahun"] == d["ref_tahun"]), None)
    check("baris ref punya bps+tm", ref and ref["bps_nilai_usd"] and ref["trademap_nilai_usd"], str(ref))
    check("rasio ref wajar (0.5-1.5)", ref and ref["rasio"] and 0.5 <= ref["rasio"] <= 1.5, str(ref and ref["rasio"]))
    check("ringkasan konsisten ref", d["ringkasan"]["rasio"] and 0.5 <= d["ringkasan"]["rasio"] <= 1.5,
          {k: d["ringkasan"][k] for k in ("tahun", "rasio", "selisih_persen")})
    check("komoditas BPS non-kosong", d["bps"]["per_komoditas"], str(d["bps"]["per_komoditas"][:2]))
    names = [k["komoditas"] for k in d["bps"]["per_komoditas"]]
    check("ada Udang (ekspor)", "Udang" in names, str(names[:4]))
    check("porsi terisi", all(k["porsi_persen"] is not None for k in d["bps"]["per_komoditas"]), str(d["bps"]["per_komoditas"][:1]))
    tm_prod = d["trademap"]["per_produk"]
    check("per_produk TradeMap non-kosong", tm_prod, str(tm_prod[:2]))
    check("per_produk HS4/6 (>2 digit)", tm_prod and all(len(p["product_code"]) > 2 for p in tm_prod), str([p["product_code"] for p in tm_prod[:5]]))
    check("per_produk punya deskripsi", tm_prod and all(p["product_desc"] for p in tm_prod), str(tm_prod[:1]))
    check("per_produk porsi terisi", tm_prod and all(p["porsi_persen"] is not None for p in tm_prod), str(tm_prod[:1]))
    check("per_produk terbesar cakupan (!=0)", tm_prod and float(tm_prod[0]["nilai_usd"]) > 0, str(tm_prod[:1]))
    check("per_produk top konsisten crusiacean (ekspor)", tm_prod[0]["product_code"] == "0306", tm_prod[0]["product_code"])
    nar = d["narasi"]
    check("narasi sebut 2 sumber", "TradeMap" in nar and "BPS" in nar, nar[:200])
    check("narasi angka nyata (4," in nar or "3," in nar or "1," in nar, nar[:200])
    check("narasi sebut produk terbesar", "TradeMap" in nar and "Produk terbesar" in nar, nar[:200])
    check("catatan terpisah", any("terpisah" in k for k in d["catatan"]), str(d["catatan"]))

    print("== filter tahun ==")
    r = c.get("/api/trademap/banding_industri?flow=ekspor&tahun=2024", headers=H)
    check("tahun 2024 -> ref 2024", r.status_code == 200 and r.get_json()["ref_tahun"] == 2024, r.get_data(as_text=True)[:150])

    print("== /api/trademap/banding_industri (impor, bab 03) ==")
    r = c.get("/api/trademap/banding_industri?flow=impor", headers=H)
    check("impor 200", r.status_code == 200, r.get_data(as_text=True)[:150])
    di = r.get_json()
    check("impor ref wajar (>=2024)", di["ref_tahun"] >= 2024, str(di["ref_tahun"]))
    ri = di["ringkasan"]
    check("impor bps+tm terisi", ri["bps_nilai_usd"] and ri["trademap_nilai_usd"], {k: ri[k] for k in ("bps_nilai_usd", "trademap_nilai_usd")})
    check("impor rasio wajar (0.5-1.5)", ri["rasio"] and 0.5 <= ri["rasio"] <= 1.5, str(ri["rasio"]))
    tm_prod_i = di["trademap"]["per_produk"]
    check("impor per_produk non-kosong", tm_prod_i, str(tm_prod_i[:2]))
    check("impor per_produk top beku (0303)", tm_prod_i and tm_prod_i[0]["product_code"] == "0303", tm_prod_i[0]["product_code"] if tm_prod_i else "-")
    print("  INFO  ekspor %s rasio %s | impor %s rasio %s"
          % (d["ref_tahun"], d["ringkasan"]["rasio"], di["ref_tahun"], ri["rasio"]))

    print("== /api/trademap/banding_negara (per negara tujuan ekspor, bab 03) ==")
    r = c.get("/api/trademap/banding_negara?flow=ekspor", headers=H)
    check("banding_negara 200", r.status_code == 200, r.get_data(as_text=True)[:150])
    dn = r.get_json()
    check("ref tahun wajar (>=2024)", dn["ref_tahun"] >= 2024, str(dn["ref_tahun"]))
    t = dn["tabel"]
    check("tabel negara terisi (>=8)", len(t) >= 8, str(len(t)))
    us = next((x for x in t if x["kode"] in ("US", "842")), None)
    check("ada AS di kedua sumber", us and us["bps_nilai_usd"] and us["trademap_nilai_usd"], str(us))
    check("AS rasio wajar (0.9-1.1)", us and us["rasio"] and 0.9 <= us["rasio"] <= 1.1, str(us))
    cn = next((x for x in t if x["kode"] == "CN"), None)
    check("China cocok nyaris penuh (>=0.99)", cn and cn["rasio"] and cn["rasio"] >= 0.99,
          str(cn and cn["rasio"]))
    check("ada negara BPS-only (IT/CA)", any(x["bps_nilai_usd"] and x["trademap_nilai_usd"] is None
          for x in t), str([x["kode"] for x in t[:6]]))
    narn = dn["narasi"]
    check("narasi negara sebut 2 sumber", "TradeMap" in narn and "BPS" in narn, narn[:200])
    check("banding_negara tanpa token 401", c.get("/api/trademap/banding_negara?flow=ekspor").status_code == 401)
    check("banding_negara flow salah 400", c.get("/api/trademap/banding_negara?flow=zz", headers=H).status_code == 400)

    print("== /api/trademap/banding_negara (impor bab 03, per negara asal) ==")
    r = c.get("/api/trademap/banding_negara?flow=impor", headers=H)
    check("impor 200", r.status_code == 200, r.get_data(as_text=True)[:150])
    di_neg = r.get_json()
    check("ref tahun wajar (>=2024)", di_neg["ref_tahun"] >= 2024, str(di_neg["ref_tahun"]))
    t_in = di_neg["tabel"]
    check("tabel negara terisi (>=8)", len(t_in) >= 8, str(len(t_in)))
    cn_in = next((x for x in t_in if x["kode"] == "CN"), None)
    check("impor: China ada di kedua sumber", cn_in and cn_in["bps_nilai_usd"] and cn_in["trademap_nilai_usd"], str(cn_in))
    check("impor: China rasio wajar (1-2)", cn_in and cn_in["rasio"] and 1.0 <= cn_in["rasio"] <= 2.0, str(cn_in and cn_in["rasio"]))
    no_in = next((x for x in t_in if x["kode"] == "NO"), None)
    check("impor: Norwegia ada di kedua sumber", no_in and no_in["bps_nilai_usd"] and no_in["trademap_nilai_usd"], str(no_in))
    check("impor: Norwegia rasio wajar (0.5-1.5)", no_in and no_in["rasio"] and 0.5 <= no_in["rasio"] <= 1.5, str(no_in and no_in["rasio"]))
    check("impor narasi sebut 2 sumber", "TradeMap" in di_neg["narasi"] and "BPS" in di_neg["narasi"], di_neg["narasi"][:200])

    print("== proteksi & validasi ==")
    check("flow salah 400", c.get("/api/trademap/banding_industri?flow=ngawur", headers=H).status_code == 400)
    check("hs salah 400", c.get("/api/trademap/banding_industri?hs=abc", headers=H).status_code == 400)
    check("tanpa token 401", c.get("/api/trademap/banding_industri").status_code == 401)

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
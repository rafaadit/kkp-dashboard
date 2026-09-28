#!/usr/bin/env python3
"""PHASE 4 — Test backend API eksplorasi data (Flask test client, tanpa server berdiri)."""
import sys
import os

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

    print("== health ==")
    r = c.get("/health")
    check("health 200", r.status_code == 200)
    check("health db ok", r.get_json().get("db") == "ok")

    # --- auth: login sekali untuk endpoint terlindungi -----------------------
    r = c.post("/api/auth/login", json={"email": "admin@kkp.local", "password": "admin123"})
    check("login 200", r.status_code == 200, r.get_data(as_text=True)[:200])
    token = r.get_json()["token"]
    H = {"Authorization": f"Bearer {token}"}
    check("token ada", bool(token))
    check("login salah -> 401", c.post("/api/auth/login", json={"email": "admin@kkp.local", "password": "salah"}).status_code == 401)

    r = c.get("/api/auth/me", headers=H)
    check("me 200", r.status_code == 200)
    check("me role super_admin", r.get_json()["user"]["role"] == "super_admin")
    check("me punya explore.view",
          "explore.view" in r.get_json()["user"]["permissions"])

    # tanpa token -> 401, token salah -> 401
    check("tanpa token 401", c.get("/api/explore/overview").status_code == 401)
    check("token salah 401", c.get("/api/explore/overview", headers={"Authorization": "Bearer zzz"}).status_code == 401)

    print("== explore/overview ==")
    r = c.get("/api/explore/overview", headers=H)
    check("overview 200", r.status_code == 200, r.get_data(as_text=True)[:100])
    d = r.get_json()
    check("overview totals baris>0", d["totals"]["baris"] > 0)
    check("overview default exim=ekspor", d["exim"] == "ekspor")

    r = c.get("/api/explore/overview?exim=impor", headers=H)
    d = r.get_json()
    check("overview impor baris>0", d["totals"]["baris"] > 0)

    # Verifikasi angka vs raw_exim (June 2026 ekspor = 4114 baris, sd~669.93 juta USD)
    r = c.get("/api/explore/overview?exim=ekspor&mulai=2026-06&akhir=2026-06", headers=H)
    d = r.get_json()
    check("June 2026 ekspor baris==4114", d["totals"]["baris"] == 4114, str(d["totals"]["baris"]))
    check("June 2026 ekspor hs_unik==312", d["totals"]["hs_unik"] == 312)
    check("June 2026 ekspor negara_unik==125", d["totals"]["negara_unik"] == 125)
    sd = d["totals"]["nilai_usd"]
    check("nilai June>500jt", sd and 5e8 < sd < 8e8, str(sd))
    kel = {k["koding"]: k for k in d["kelompok"]}
    check("kelompok I ada", "I" in kel)
    check("kelompok II ada", "II" in kel)

    print("== explore/komoditas ==")
    r = c.get("/api/explore/komoditas?exim=ekspor&limit=3", headers=H)
    check("komoditas 200", r.status_code == 200)
    d = r.get_json()
    check("komoditas len==3", len(d["komoditas"]) == 3)
    check("komoditas rate desc", d["komoditas"][0]["nilai_usd"] >= d["komoditas"][1]["nilai_usd"])
    check("share in 0..100", 0 <= d["komoditas"][0]["share_nilai_persen"] <= 100)

    print("== explore/komoditas_list (sidebar) ==")
    r = c.get("/api/explore/komoditas_list?exim=ekspor", headers=H)
    check("komoditas_list 200", r.status_code == 200)
    d = r.get_json()
    kl = d["komoditas"]
    check("komoditas_list > 50 item", len(kl) > 50, str(len(kl)))
    check("komoditas_list sorted A-Z",
          all(kl[i]["komoditas"] <= kl[i + 1]["komoditas"] for i in range(len(kl) - 1)))
    check("komoditas_list ada Udang",
          any(k["komoditas"].lower() == "udang" for k in kl))
    check("komoditas_list punya baris>0", all(k["baris"] > 0 for k in kl))

    print("== explore/provinsi ==")
    r = c.get("/api/explore/provinsi?exim=ekspor&limit=5", headers=H)
    check("provinsi 200", r.status_code == 200)
    d = r.get_json()
    check("provinsi len==5", len(d["provinsi"]) == 5)
    check("provinsi rate desc", d["provinsi"][0]["nilai_usd"] >= d["provinsi"][1]["nilai_usd"])
    check("provinsi top==Jawa Timur", d["provinsi"][0]["provinsi"] == "Jawa Timur", str(d["provinsi"][0]))
    check("provinsi total>0", d["total_nilai_usd"] > 0)
    r = c.get("/api/explore/provinsi?exim=ekspor&limit=50", headers=H)
    allp = r.get_json()["provinsi"]
    check("provinsi 37 data", len(allp) == 37, str(len(allp)))
    check("provinsi share sum~100", abs(sum(p["share_nilai_persen"] for p in allp) - 100) < 1)
    r = c.get("/api/explore/provinsi?exim=ekspor&by=pelabuhan", headers=H)
    check("provinsi by=pelabuhan 200", r.status_code == 200 and r.get_json()["by"] == "pelabuhan")
    check("provinsi by=zzz 400", c.get("/api/explore/provinsi?by=zzz", headers=H).status_code == 400)

    print("== explore/country_compare ==")
    r = c.get("/api/explore/negara_list?exim=ekspor", headers=H)
    check("negara_list 200", r.status_code == 200)
    nl = r.get_json()["negara"]
    check("negara_list > 100", len(nl) > 100, str(len(nl)))
    r = c.get("/api/explore/country_compare?exim=ekspor&negara_a=US&negara_b=CN", headers=H)
    check("compare 200", r.status_code == 200)
    d = r.get_json()
    check("compare a==US", d["negara_a"]["kode_negara"] == "US")
    check("compare b==CN", d["negara_b"]["kode_negara"] == "CN")
    check("compare a nilai>0", d["negara_a"]["nilai_usd"] > 0)
    check("compare selisih konsisten",
          d["selisih_nilai_usd"] == round(d["negara_a"]["nilai_usd"] - d["negara_b"]["nilai_usd"], 4))
    check("compare per_bulan hadir", len(d["per_bulan"]) > 0)
    check("compare top komoditas", all(len(g["top_komoditas"]) > 0 for g in (d["negara_a"], d["negara_b"])))
    check("compare sama negara 400", c.get("/api/explore/country_compare?negara_a=US&negara_b=US", headers=H).status_code == 400)
    check("compare kosong 400", c.get("/api/explore/country_compare", headers=H).status_code == 400)
    check("compare negara tak ada 400", c.get("/api/explore/country_compare?negara_a=US&negara_b=ZZ", headers=H).status_code == 400)

    print("== explore/potensi ==")
    r = c.get("/api/explore/potensi?exim=ekspor", headers=H)
    check("potensi 200", r.status_code == 200)
    d = r.get_json()
    check("potensi ref_periode", d["ref_periode"]["mulai"] == "2026-01", str(d["ref_periode"]))
    check("potensi top_market > 0", len(d["top_market"]) > 0)
    check("potensi momentum naik semua > 0",
          all(m["pertumbuhan_persen"] > 0 for m in d["momentum"]))
    check("potensi trademap snapshot (fixture)",
          d["trademap"] is not None and len(d["trademap"]["per_partner"]) > 0)
    check("potensi share ~100",
          abs(sum(p["share_persen"] for p in d["trademap"]["per_partner"]) - 100) < 1)

    print("== kompetitor scaffold ==")
    r = c.get("/api/explore/kompetitor_scope", headers=H)
    check("kompetitor_scope 200", r.status_code == 200)
    d = r.get_json()
    check("kompetitor sumber_kompetitor > 0", len(d["sumber_kompetitor"]) > 0)
    check("kompetitor partner_ekspor_id", len(d["partner_ekspor_id"]) > 0)
    check("kompetitor cakupan hs 030617", any(x["hs"] == "030617" for x in d["cakupan_trademap"]))

    print("== explore/negara ==")
    r = c.get("/api/explore/negara?exim=ekspor&limit=1", headers=H)
    check("negara 200", r.status_code == 200)
    d = r.get_json()
    check("negara top==US", d["negara"][0]["kode_negara"] == "US", str(d["negara"][:1]))
    check("US nilai>50jt", d["negara"][0]["nilai_usd"] > 5e7)

    print("== explore/perbandingan ==")
    r = c.get("/api/explore/perbandingan?exim=ekspor&periode_a_mulai=2026-06&periode_a_akhir=2026-06", headers=H)
    check("perbandingan 200", r.status_code == 200)
    d = r.get_json()
    check("B.back year", d["periode_b"]["mulai"] == "2025-06", str(d["periode_b"]))
    check("delta nilai hadir", d["delta"]["nilai_usd"] == round(d["periode_a"]["nilai_usd"] - d["periode_b"]["nilai_usd"], 4))
    check("pertumbuhan dihitung", d["delta"]["pertumbuhan_nilai_persen"] is not None)

    print("== api/data/raw_exim ==")
    r = c.get("/api/data/raw_exim?exim=ekspor&mulai=2026-06&page=1&limit=2", headers=H)
    check("browse 200", r.status_code == 200)
    d = r.get_json()
    check("browse total==4114", d["total"] == 4114, str(d["total"]))
    check("browse len==2", len(d["rows"]) == 2)
    check("browse pages 2057", d["pages"] == 2057)
    row0 = d["rows"][0]
    check("browse kolom tunggal & terisi (1 per dimensi)", all(
        (row0.get(k) not in (None, "")) for k in
        {"kode_hs", "komoditas", "jenis", "bentuk", "pengolahan",
         "provinsi_asal", "pulau_prov_asal", "kelompok_negara", "koding", "status"}))
    check("browse tak ada kolom tumpukan revisi", all(
        k not in row0 for k in
        {"komoditas_1_2017", "komoditas_2_2017", "komoditas_4_2024", "komoditas_5_2026",
         "bentuk_1", "bentuk_2", "bentuk_3_2026", "bentuk_4_2026", "bentuk_5_2026",
         "jenis_2_2026", "uraian_2", "uraian_id_en_2_2026"}))
    r = c.get("/api/data/raw_exim?exim=impor&mulai=2026-06&limit=1", headers=H)
    check("browse impor total==1624", r.get_json()["total"] == 1624)

    print("== report/exec_summary ==")
    r = c.get("/api/report/exec_summary?tahun=2026&bulan_awal=1&bulan_akhir=6", headers=H)
    check("exec_summary 200", r.status_code == 200)
    d = r.get_json()
    check("exec label", d["periode_label"] == "JANUARI – JUNI 2026", d.get("periode_label"))
    check("exec ekspor>0", d["ekspor"]["nilai_usd"] > 0)
    check("exec neraca==eks-impor", abs(d["neraca"]["nilai_usd"] - (d["ekspor"]["nilai_usd"] - d["impor"]["nilai_usd"])) < 1)
    check("exec yoy hadir", d["ekspor"]["yoy_persen"] is not None)
    check("exec top_negara", len(d["top_negara"]) > 0)
    check("exec top_kom_eks", len(d["top_komoditas_ekspor"]) > 0)
    check("exec perbulan 6", len(d["perbulan"]) == 6, str(len(d.get("perbulan") or [])))
    check("exec invalid bulan 400", c.get("/api/report/exec_summary?tahun=2026&bulan_awal=6&bulan_akhir=1", headers=H).status_code == 400)
    check("exec noauth 401", c.get("/api/report/exec_summary").status_code == 401)

    print("== error handling ==")
    check("bad exim 400", c.get("/api/explore/overview?exim=zzz", headers=H).status_code == 400)
    check("bad limit 400", c.get("/api/explore/komoditas?limit=999", headers=H).status_code == 400)
    check("periode terbalik 400", c.get("/api/explore/overview?mulai=2027-01&akhir=2026-01", headers=H).status_code == 400)
    check("bulan 13 400", c.get("/api/explore/overview?mulai=2026-13", headers=H).status_code == 400)
    check("404 json", c.get("/api/nope").status_code == 404)

    print("== agregat vs raw_exim langsung (sanity) ==")
    # Total baris ekspor seluruh periode harus 189001 (sesuai dokumentasi PHASE 3)
    r = c.get("/api/explore/overview?exim=ekspor", headers=H)
    baris = r.get_json()["totals"]["baris"]
    check("ekspor all baris==189001", baris == 189001, str(baris))

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
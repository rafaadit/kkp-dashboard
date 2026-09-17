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
    check("browse no extra cols", all(
        k in {"id", "exim_type", "tahun", "bulan", "periode", "kode_hs", "komoditas",
              "uraian", "kode_negara", "negara", "kode_pelabuhan_muat",
              "pelabuhan_muat_bongkar", "moda", "vol_kg", "nil_usd",
              "harga_usd_kg", "setara_segar", "koding", "kurs_usd", "nilai_rp",
              "status"} for k in d["rows"][0]))
    r = c.get("/api/data/raw_exim?exim=impor&mulai=2026-06&limit=1", headers=H)
    check("browse impor total==1624", r.get_json()["total"] == 1624)

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
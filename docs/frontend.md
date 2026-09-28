# PHASE 5 — Frontend PHP Native + Auth

## Struktur

```
frontend/
  public/
    index.php            router (login/logout/dashboard/komoditas/negara/perbandingan/data)
    assets/app.css
  src/
    Config.php           config dari frontend/.env.local (API_BASE_URL default :8000)
    ApiClient.php        HTTP client ke backend Flask API (curl, token Bearer)
    Session.php          sesi + token + hak akses (login/logout/me)
    View.php             render layout + view + helper e()/num()
  views/
    layout/header.php, footer.php
    login.php, dashboard.php, komoditas.php, negara.php,
    perbandingan.php, raw_exim.php, 404.php, error.php
  .env.local
```

## Menjalankan

```bash
# 1. Backend API (Flask :8000)
.venv/bin/python backend/api/app.py --port 8000

# 2. Frontend (PHP :8080)
php -S 127.0.0.1:8080 -t frontend/public frontend/public/index.php
```

Buka http://127.0.0.1:8080 → login dengan akun admin.

## User awal

Dibuat via script (bukan seed, anti plaintext password):

```bash
.venv/bin/python database/scripts/create_admin.py \
    --email admin@kkp.local --password 'admin123' --nama 'Admin KKP'
```

Password disimpan sebagai bcrypt (12 rounds) di `app_users.password_hash`.
Role & permission sudah di-seed (`010_app_roles_permissions.sql`):
`user`, `pegawai`, `super_admin`. Login diverifikasi backend; endpoint
`/api/explore/*` & `/api/data/*` **terproteksi permission**
(`require_perm`), token disimpan hashed (SHA-256) di `app_user_tokens`.

## Auth API

| Endpoint | Fungsi |
|---|---|
| `POST /api/auth/login` | `{email, password}` → `{token, user}` |
| `GET /api/auth/me` | user + daftar permissions |
| `POST /api/auth/logout` | revoke token |

Header: `Authorization: Bearer <token>`.

## Halaman

- `/` Dashboard: KPI total (nilai USD, volume, setara segar, baris/HS/negara),
  tabel per-bulan, breakdown kelompok koding I–IV. Filter exim + rentang periode.
  Mendukung deep-link `/dashboard?komoditas=<nama>` (misal dari sidebar).
- `/komoditas` Top komoditas_5_2026 (volume, nilai, harga/kg, share %).
- `/negara` Top negara tujuan/asal + kelompok negara.
- `/provinsi` Top provinsi asal barang (ekspor) / bongkar (impor); bisa
  dialihkan ke `?by=pelabuhan` (provinsi pelabuhan muat/bongkar). Data riil
  BPS dari kolom `provinsi_asal` / `provinsi_pelabuhan` raw_exim.
- `/compare` **Country Compare** — bandingkan kinerja ekspor/impor RI ke
  2 negara: KPI nilai/volume/share/harga, top komoditas per negara, tren
  nilai per periode, dan selisih A − B. Form: exim, negara A/B (dropdown dari
  `/api/explore/negara_list`), rentang periode.
- `/perbandingan` Dua tab: **Periode (BPS)** — pertumbuhan % nilai & volume
  2 periode; **BPS vs TradeMap** — form flow/tahun/komoditas/negara,
  tabel berdampingan (endpoint `/api/trademap/banding`), KPI + catatan cakupan
  (sumber tetap terpisah, tidak digabung).
- `/trademap` Browse TradeMap (KPI, top partner/produk, pagination).
- `/data` Browse RAW EXIM (pagination, filter status/periode/komoditas).
- `/login`, `/logout`.

## Test

- `php tests/test_frontend.php` — smoke test end-to-end (wajib API :8000 running).
- `.venv/bin/python tests/test_auth.py tests/test_api.py` — unit test backend.

Catatan: token sesi disimpan cookie; setiap permintaan ditambahkan
`Authorization` oleh `ApiClient`. Semua angka diformat dengan
`\KKP\View::num()`; semua output HTML di-escape `\KKP\View::e()`.

## Layout (PHASE 5.1 — sidebar navigasi)

- Sidebar (`layout/header.php`) berisi: brand, kotak pencarian komoditas,
  menu halaman, daftar komoditas (urut A-Z, render server-side dari
  `/api/explore/komoditas_list`), user + logout.
- Klik komoditas → `/dashboard?komoditas=<nama>` (dashboard terfilter).
- Pencarian mem-filter daftar komoditas klien-side (tanpa reload).
- Mobile (< 920px): sidebar off-canvas, tombol hamburger di topbar.
- Topbar menampilkan judul halaman + sumber data
  (PDSPKP KKP · BPS · ITC TradeMap).
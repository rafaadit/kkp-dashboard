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
- `/komoditas` Top komoditas_5_2026 (volume, nilai, harga/kg, share %).
- `/negara` Top negara tujuan/asal + kelompok negara.
- `/perbandingan` Perbandingan 2 periode (pertumbuhan % nilai & volume).
- `/data` Browse RAW EXIM (pagination, filter status/periode/komoditas).
- `/login`, `/logout`.

## Test

- `php tests/test_frontend.php` — smoke test end-to-end (wajib API :8000 running).
- `.venv/bin/python tests/test_auth.py tests/test_api.py` — unit test backend.

Catatan: token sesi disimpan cookie; setiap permintaan ditambahkan
`Authorization` oleh `ApiClient`. Semua angka diformat dengan
`\KKP\View::num()`; semua output HTML di-escape `\KKP\View::e()`.
# Deployment di shared hosting / subdirectory

Aplikasi terdiri dari dua proses:

1. **Frontend PHP** — di `frontend/public/`, bisa diakses langsung sebagai
   document root atau subdirectory (contoh: `https://magang.pdspkp.id/tarbhak/frontend/public/`).
2. **Backend Flask** — `backend/api/app.py`, default bind `127.0.0.1:8000`.
   Frontend memanggilnya lewat cURL server-side, jadi **tidak perlu** port 8000
   terbuka ke internet selama Flask berjalan di server yang sama.

## Kenapa halaman sebelumnya 404 / redirect ke `/login`

Router PHP memakai path root (`/login`, `/data`, `/assets/app.css`). Saat aplikasi
diletakkan di `/tarbhak/frontend/public/`, Apache tidak punya aturan rewrite,
sehingga:

- `GET /tarbhak/frontend/public/` → `302 Location: /login` (keluar dari folder aplikasi)
- `GET /login` → 404 Apache
- `POST /tarbhak/frontend/public/login` → 404 Apache (tidak diteruskan ke `index.php`)

Perbaikan yang sudah masuk kode:

- `Config` + `View` mendeteksi otomatis prefix URL dari `SCRIPT_NAME`
  (bisa ditimpa `BASE_URL` di `frontend/.env.local`). Semua redirect dan URL
  di view diberi prefix otomatis.
- `frontend/public/.htaccess` meneruskan request non-file ke `index.php`.
- `frontend/.htaccess` memblokir akses ke `.env.local`.

## Langkah upload (SFTP / Cyberduck)

Upload file-file ini dari repo (relatif terhadap folder `tarbhak/`):

```
frontend/public/index.php
frontend/public/.htaccess                 (BARU — pastikan hidden file ikut ter-upload)
frontend/public/assets/app.css
frontend/src/Config.php
frontend/src/View.php
frontend/.htaccess                         (BARU)
backend/api/app.py
database/scripts/etl_bps.py                (jika belum sesuai commit terbaru)
database/scripts/update_bps.py             (jika belum sesuai commit terbaru)
backend/api/bps.py                         (jika belum sesuai commit terbaru)
```

> Cyberduck: aktifkan **Show Hidden Files** (`View → Show Hidden Files`) agar
> `.htaccess` ikut terkirim. Cek keberadaannya lewat SFTP — lewat HTTP dotfile
> biasanya tetap 403 meski file belum ada, jadi status 403 bukan bukti upload.

Site harus mengizinkan `.htaccess` (`AllowOverride All`). Jika hosting
mengabaikan `.htaccess`, minta admin server menambahkan rewrite:

```apache
<Directory "/path/ke/tarbhak/frontend/public">
    AllowOverride All
    Require all granted
</Directory>
```

## Index database (penting saat data membesar)

Endpoint `/api/explore/*` melakukan agregasi pada `raw_exim`. Tanpa index
covering, satu halaman bisa memakan puluhan detik atau tampak "hang" pada
database hosting yang lambat. Terapkan sekali:

```bash
mysql -u <user> -p <db_name> < database/migrations/0004_raw_exim_perf_index.sql
```

Migration ini idempoten dan sudah diterapkan pada database `magang_tarbhak`.
Untuk instalasi baru, index juga sudah masuk `database/schema.sql`.

Index tambahan untuk `top komoditas/provinsi/pelabuhan`, `country_compare`,
serta browse `raw_exim` sudah termasuk dalam migration yang sama. Pada data
`magang_tarbhak` (±260 ribu baris), waktu tempuh endpoint turun dari
~21–127 detik menjadi ~0,5–4 detik per endpoint. Browse data mentah juga
memakai `STRAIGHT_JOIN` agar optimizer tidak memulai dari `ms_hscode`
(rencana salah yang menyebabkan filesort seluruh tabel).

Jika menambah periode baru dan web kembali berat, jalankan ulang migration
di atas (aman/idempoten), lalu cek `EXPLAIN` pada query yang lambat.

## Konfigurasi

`frontend/.env.local` (di server, **jangan** di-commit):

```ini
API_BASE_URL=http://127.0.0.1:8000
APP_NAME=KKP EXIM Platform
# Opsional — biasanya tidak perlu karena terdeteksi otomatis:
# BASE_URL=/tarbhak/frontend/public
```

- `API_BASE_URL` harus menunjuk ke alamat yang **bisa dijangkau dari server**,
  bukan dari browser. `127.0.0.1:8000` benar jika Flask dijalankan di server yang
  sama. Jika Flask di VPS lain, isi dengan URL/IP tersebut.
- `.env` (DB) tetap di root project (`tarbhak/.env`) dan dibaca `backend/db.py`.
- Pastikan `frontend/.env.local` tidak bisa diunduh:
  `GET /tarbhak/frontend/.env.local` harus **403**.

## Menjalankan backend di server

```bash
cd /path/ke/tarbhak
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
nohup .venv/bin/python backend/api/app.py --port 8000 > data/backend.log 2>&1 &
curl http://127.0.0.1:8000/health
```

Jika perlu diakses dari luar (tidak disarankan tanpa reverse proxy/firewall):

```bash
APP_HOST=0.0.0.0 .venv/bin/python backend/api/app.py --port 8000
```

Untuk produksi, lebih baik reverse proxy `/api/` ke `127.0.0.1:8000` lewat
Apache/Nginx dan simpan `API_BASE_URL` sesuai prefix tersebut.

Batas unggah PHP untuk file BPS (.xlsx besar) perlu dinaikkan di `php.ini`:

```ini
upload_max_filesize = 256M
post_max_size = 260M
max_execution_time = 300
```

## Checklist verifikasi

| Test | Harapan |
|---|---|
| `GET /tarbhak/frontend/public/login` | 200, form login (bukan 404) |
| `POST /tarbhak/frontend/public/login` | 302 ke `/tarbhak/frontend/public/` |
| `GET /tarbhak/frontend/public/assets/app.css` | 200 `text/css` |
| HTML halaman | semua link `/tarbhak/frontend/public/...`, tidak ada `href="/login"` |
| `GET /tarbhak/frontend/.env.local` | 403 |
| `curl http://127.0.0.1:8000/health` di server | `{"status":"ok",...}` |
| Login gagal saat API mati | pesan error tampil di form, bukan halaman 500 |

## Akun awal

User bootstrap dibuat dengan `database/scripts/create_admin.py`; password
disimpan bcrypt. Contoh (ganti password setelah login pertama):

```bash
.venv/bin/python database/scripts/create_admin.py \
    --email admin@kkp.local --password 'admin123' --nama 'Admin KKP'
```

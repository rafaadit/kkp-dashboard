# PHASE 4 — Backend API Eksplorasi Data

REST API Python (Flask) yang menyajikan data ekspor/impor dari `raw_exim`
(satu baris == satu fakt BPS, verified 1:1, tanpa duplikasi — lihat
`docs/raw_exim_generation.md`).

## Menjalankan

```bash
.venv/bin/python backend/api/app.py --port 8000
# health check
curl http://127.0.0.1:8000/health
```

Pengujian: `.venv/bin/python tests/test_api.py` (test client, tanpa server berdiri).

## Endpoint

| Method & Path | Deskripsi |
|---|---|
| `GET /health` | Status server + koneksi DB |
| `GET /api/explore/overview` | Total nilai/volume, breakdown per bulan, breakdown kelompok koding (I–IV) |
| `GET /api/explore/komoditas` | Top komoditas_5_2026 (volume, nilai, harga avg, share) |
| `GET /api/explore/negara` | Top negara tujuan/asal + ringkasan kelompok negara |
| `GET /api/explore/perbandingan` | Perbandingan 2 rentang periode (delta + pertumbuhan %) |
| `GET /api/data/raw_exim` | Browse baris raw_exim (pagination + filter) |
| `GET /api/data/raw_exim.xlsx` | Export Excel (.xlsx) SELURUH baris sesuai filter (tanpa pagination) |
| `POST /api/ai/ask` | Tanya-jawab asisten; bila intent "tampilkan data" mengembalikan field `tabel` |

### Parameter umum (untuk seluruh endpoint explore/data)

| Parameter | Contoh | Keterangan |
|---|---|---|
| `exim` | `ekspor` / `impor` | Wajib, default `ekspor` |
| `periode` | `2026-01` | Satu bulan tertentu (setara mulai=akhir). Prioritas `mulai`/`akhir` bila keduanya diisi |
| `mulai` | `2026-06`, `2026`, `202606` | Periode awal |
| `akhir` | `2026-06`, `2026`, `202606` | Periode akhir |
| `kelompok` | `I`, `I,III,IV` | Filter koding kelompok komoditas |
| `negara` | `US` | Filter kode_negara |
| `komoditas` | `Udang` | Filter LIKE komoditas_5_2026 |
| `limit` | `15` (default; maks per endpoint 50/200) | Jumlah hasil |
| `page` | `1` | Halaman (khusus browse) |
| `status` | `ready` / `needs_validation` | Khusus browse |

`raw_exim.xlsx` memakai filter yang sama (tanpa `page`/`limit`) dan mengembalikan
file `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` dengan
38 kolom (header label Indonesia).

`perbandingan` memakai `periode_a_mulai`, `periode_a_akhir`, `periode_b_mulai`,
`periode_b_akhir`. Jika periode B kosong, dihitung 1 tahun sebelum A.

### Contoh respons

```json
GET /api/explore/overview?exim=ekspor&mulai=2026-06&akhir=2026-06
{
  "exim": "ekspor",
  "totals": {
    "baris": 4114, "volume_kg": 249539640.5356, "nilai_usd": 669929548.4145,
    "setara_segar": 749404983.9981, "hs_unik": 312, "negara_unik": 125
  },
  "perbulan": [{"tahun": 2026, "bulan": 6, "periode": "2026-06", "baris": 4114,
                "volume_kg": 249539640.5356, "nilai_usd": 669929548.4145}],
  "kelompok": [{"koding": "I", "baris": 3585, "volume_kg": 123639317.9341, "nilai_usd": 586006441.513}, ...]
}
```

### Error handling

- Param tidak valid → `400 {"error": "..."}`
- Endpoint tidak ada → `404 {"error": "endpoint tidak ditemukan"}`
- DB/kesalahan lain → `500 {"error": "internal error: ..."}`

Semua query **parameterized** (tidak ada concatenation nilai pengguna), sehingga
aman dari SQL injection. Angka dikembalikan sebagai number (Decimal → `value()`
di `backend/api/helpers.py`).

## Endpoint lanjutan

| Endpoint | Permission | Keterangan |
|---|---|---|
| `POST /api/auth/login` | — | `{email, password}` → `{token, user}` |
| `POST /api/auth/logout` | login | revoke token |
| `GET /api/auth/me` | login | profil + permissions |
| `GET /api/trademap/summary`, `/api/trademap/rows` | `trademap.view` | lihat `docs/trademap.md` |
| `GET /api/report/list` | `report.view` | daftar job laporan PPT |
| `POST /api/report/generate_ppt` | `report.generate_ppt` | generate PPT |
| `GET /api/report/download?job_id=N` | `report.view` | unduh .pptx |
| `POST /api/ai/ask` | `ai.use` | tanya-jawab data EXIM |
| `GET /api/admin/roles` | `admin.users` | daftar role + jumlah permission |
| `GET /api/admin/users` | `admin.users` | daftar akun (`q`, `role`, `active`, `page`, `limit`) |
| `GET /api/admin/users/<id>` | `admin.users` | detail akun + permission efektif |
| `POST /api/admin/users` | `admin.users` | buat akun `{nama,email,password,role}` |
| `PUT /api/admin/users/<id>` | `admin.users` | ubah `nama/email/role/is_active` |
| `POST /api/admin/users/<id>/reset-password` | `admin.users` | reset password + cabut token |
| `GET /api/admin/audit` | `admin.users` | audit log terbaru |
| `GET /api/data/bps/summary` | `data.view`/`exim.view`/update BPS | periode terakhir + jumlah baris |
| `GET /api/data/bps/uploads` | `data.view`/`exim.view`/update BPS | riwayat file BPS |
| `GET /api/data/bps/jobs` | `data.view`/`jobs.view` | riwayat job update BPS |
| `GET /api/data/bps/jobs/<id>` | `data.view`/`jobs.view` | status + log job (polling) |
| `POST /api/data/bps/upload` | `data.update_bps_export` / `data.update_bps_import` | multipart `ekspor`/`impor` `.xlsx`, opsional `force` |
| `POST /api/data/bps/jobs/<id>/cancel` | `jobs.run` | batalkan job `PENDING` |

### Admin akun

- Semua aksi tulis dicatat ke `audit_logs` (action `admin.user.*`).
- Guard: akun tidak bisa menurunkan role/menonaktifkan dirinya sendiri, dan
  sistem menolak bila aksi tersebut menghilangkan super_admin aktif terakhir.
- Menonaktifkan akun / reset password otomatis mencabut seluruh token aktif
  (`app_user_tokens.revoked_at`), sehingga sesi berjalan langsung berakhir.
- Password di-hash bcrypt 12 rounds; respons tidak pernah memuat
  `password_hash`.

### Update BPS (background)

`POST /api/data/bps/upload` menyimpan file ke `data/bps_uploads/`, membuat
`automation_jobs` (`job_type='bps_update'`, status `PENDING`), lalu menjalankan
`database/scripts/update_bps.py` sebagai subprocess. Hanya satu job update BPS
boleh berjalan pada satu waktu (selain itu `409`). Pantau lewat
`GET /api/data/bps/jobs/<id>`.


Header `Authorization: Bearer <token>` (atau query `?token=`). Detail:
`docs/frontend.md` (auth), `docs/report_ppt.md`, `docs/ai.md`.
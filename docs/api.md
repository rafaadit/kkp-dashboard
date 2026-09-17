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

### Parameter umum (untuk seluruh endpoint explore/data)

| Parameter | Contoh | Keterangan |
|---|---|---|
| `exim` | `ekspor` / `impor` | Wajib, default `ekspor` |
| `mulai` | `2026-06`, `2026`, `202606` | Periode awal |
| `akhir` | `2026-06`, `2026`, `202606` | Periode akhir |
| `kelompok` | `I`, `I,III,IV` | Filter koding kelompok komoditas |
| `negara` | `US` | Filter kode_negara |
| `komoditas` | `Udang` | Filter LIKE komoditas_5_2026 |
| `limit` | `15` (default; maks per endpoint 50/200) | Jumlah hasil |
| `page` | `1` | Halaman (khusus browse) |
| `status` | `ready` / `needs_validation` | Khusus browse |

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

Header `Authorization: Bearer <token>` (atau query `?token=`). Detail:
`docs/frontend.md` (auth), `docs/report_ppt.md`, `docs/ai.md`.
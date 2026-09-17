# PHASE 6 — TradeMap (ITC) Integrasi

Schema: `trademap_raw` (file mentah + hash + payload ringkas) dan `trademap_trade`
(reporter, partner, flow, product_code, product_desc, year, qty, qty_unit, value_usd).

## Import pipeline

Sumber: file export dari TradeMap (ITC), mis. hasil query
*International Trade and Market Access Data*. Kolom dipetakan otomatis
(case-insensitive, alias umum):

| Field DB | Contoh header |
|---|---|
| reporter | `Reporter`, `Reporter ISO` |
| partner | `Partner`, `Partner ISO` |
| flow | `Flow`, `Trade Flow` |
| product_code | `Product code`, `HS code`, `Product` |
| product_desc | `Product Label`, `Product description` |
| year | `Year`, `Year(s)` |
| qty / qty_unit | `Quantity`, `Quantity Unit` |
| value_usd | `Trade Value (US$ Thousand)`, `Value`, `Total value` |

```bash
# dry-run (lihat 5 contoh record)
python3 database/scripts/import_trademap.py data/trademap/export.csv

# simpan
python3 database/scripts/import_trademap.py data/trademap/export.csv --source "ITC query Jan 2026" --commit
```

- Format: CSV/TSV (delimiter dideteksi otomatis) atau XLSX (sheet pertama).
- Idempotent: file dengan `sha256` sama tidak diimport ulang.
- Setiap impor tercatat di `automation_jobs` (job_type `trademap_import`) dan
  `automation_job_logs`; baris ganda per (reporter, partner, flow, product_code,
  year) di-skip via `INSERT IGNORE`.
- Catatan: `value_usd` mengikuti satuan file sumber (TradeMap umumnya
  **US$ ribu**) — ditampilkan apa adanya di UI dengan label unit.

## API

| Endpoint | Fungsi |
|---|---|
| `GET /api/trademap/summary` | total + per tahun + top partner + top produk |
| `GET /api/trademap/rows` | browse paginated |

Filter: `reporter`, `partner`, `flow`, `product_code`, `year_min`, `year_max`,
`page`, `limit`. Butuh permission `trademap.view`.

## Frontend

Halaman `/trademap` di PHP Native (menu **TradeMap**): KPI, top partner/produk,
tabel data + pagination. Bila belum ada data, muncul petunjuk perintah import.

## Test

`.venv/bin/python tests/test_trademap.py` — memakai fixture sintetis
`tests/fixtures/trademap_sample.csv` (BUKAN data pasar nyata; hanya untuk
menguji pipeline/API).

## Catatan data nyata

`TRADEMAP_API_KEY` di `.env` masih kosong. Pengambilan otomatis dari situs ITC
memerlukan kredensial/langganan; sementara impor dilakukan dari file export
manual. Script unduh otomatis (jika kredensial tersedia) dapat ditambahkan
sebagai lanjutan PHASE 6.
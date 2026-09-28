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
| `GET /api/trademap/banding` | banding BPS vs TradeMap (side-by-side, tidak digabung) |

Filter: `reporter`, `partner`, `flow`, `product_code`, `year_min`, `year_max`,
`page`, `limit`. Butuh permission `trademap.view`.

`/api/trademap/banding` — params `flow` (ekspor|impor), `tahun`, dan minimal
salah satu `komoditas`/`negara`. Mengembalikan blok terpisah `bps` dan
`trademap`, plus `banding_komoditas` / `banding_negara` (row yang di-join
berdasarkan nama ternormalisasi `_nk()`, hanya untuk tampilan berdampingan;
nilai TIDAK pernah dicampur). Karena cakupan & sumber berbeda, halaman
menampilkan catatan "tidak dibandingkan secara langsung".

## Frontend

Halaman `/trademap` di PHP Native (menu **TradeMap**): KPI, top partner/produk,
tabel data + pagination. Bila belum ada data, muncul petunjuk perintah import.
Halaman `/perbandingan` punya dua tab: **Periode (BPS)** (membandingkan dua
periode raw_exim) dan **BPS vs TradeMap** (form flow/tahun/komoditas/negara →
tabel berdampingan + KPI + catatan cakupan).

## Test

`.venv/bin/python tests/test_trademap.py` — memakai fixture sintetis
`tests/fixtures/trademap_sample.csv` (BUKAN data pasar nyata; hanya untuk
menguji pipeline/API).

## Catatan data nyata

`TRADEMAP_API_KEY` di `.env` masih kosong. Pengambilan otomatis dari situs ITC
memerlukan kredensial/langganan; sementara impor dilakukan dari file export
manual.

## PHASE 9 — pemrosesan & harmonisasi

Pipeline penuh (parser → normalizer → master mapping → HS harmonization →
validation → dedupe → line count) ada di `backend/trademap/*` dengan CLI
`database/scripts/process_trademap.py` (dry-run default, `--commit`).
Detail: `docs/trademap_processing.md`.
`value_usd` tetap = nilai sesuai satuan sumber (kompatibilitas PHASE 6); nilai
USD ter-normalisasi ada di `value_usd_norm`.

## PHASE 9b — robot unduhan + scheduler

`backend/trademap/downloader.py` (`TradeMapDownloader`) mengambil file dari
`TRADEMAP_API_URL` (pakai `--fixture` bila belum ada API key) dan mencatat
lineage di `automation_jobs` (`trademap_download`) + `automation_download_logs`
(PENDING → DOWNLOADED → VALIDATED). Tanpa API key & tanpa fixture → job FAILED
(aman, tidak crash). CLI `database/scripts/download_trademap.py` dan scheduler
cron-friendly `database/scripts/automation_scheduler.py --once` (dispatch job
PENDING jatuh tempo). Detail: `docs/download_trademap.md`.
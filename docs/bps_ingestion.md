# BPS Data Ingestion (PHASE 2)

Pipeline ETL: `UPLOAD → VALIDATE → STAGING → TRANSFORM → PROCESS`

## Jalankan

```bash
# load ekspor + impor
python3 database/scripts/etl_bps.py \
    --ekspor "Data Minimum - Ekspor 2022-2026-Mei.xlsx" \
    --impor  "Data Minimum - Impor 2022-2026-Mei.xlsx"

# reload paksa (abaikan hash existing)
python3 database/scripts/etl_bps.py --ekspor "..." --impor "..." --force
```

Idempotent: file dengan `file_hash` yang sudah ada di `bps_upload` di-skip.

## Hasil (verified)

| Tabel | Baris | Catatan |
|-------|-------|---------|
| `bps_upload` | 2 | 1 ekspor + 1 impor, status `processed` |
| `bps_export_raw` | 189.001 | valid 100% |
| `bps_import_raw` | 53.668 | valid 100% |
| `bps_export` | 189.001 | grain unique 0 duplikat |
| `bps_import` | 53.668 | grain unique 0 duplikat |

### Verifikasi angka vs PPT (Jan–Jun 2026, kelompok I)
- Ekspor **2.995,2 juta USD** ✅ (cocok PPT)
- Impor **379,65 juta USD** ✅ (cocok PPT)

Semua master mapping 100%: 635 HS, 208 negara, 38 provinsi, 199 pelabuhan, 54 periode.

## Pipeline detail

1. **UPLOAD** — hitung `file_hash` sha256; buat baris `bps_upload`
   (`periode_mulai`/`periode_akhir` dari rentang data di file, karena 1 file = multi-periode).
2. **VALIDATE + STAGING** — tulis baris mentah ke `bps_export_raw`/`bps_import_raw`
   (kolom text-fidelity + `row_checksum` sha256 + `is_valid` + `validation_error`).
   Aturan validasi: periode ada di `ms_period`, semua kode master ada, `volume_kg`
   & `nilai_usd` numerik.
3. **TRANSFORM** — `INSERT ... SELECT` join ke master → resolve FK, tulis `bps_export`/`bps_import`
   (grain unique), tanpa duplikat.
4. **PROCESS** — set `bps_upload.status='processed'`.

## Test

```bash
python3 tests/test_etl.py
```

## Catatan / Known Issues

- 1 file BPS konsolidasi 2022-01..2026-06 (54 periode) → `bps_upload.id_ms_period` NULL
  (pakai `periode_mulai`/`periode_akhir`). File bulanan per-periode bisa mengisi `id_ms_period`.
- `ms_reference` formula rendemen/setara segar masih `NEEDS VALIDATION`.
- Verifikasi PPT menyeluruh dilakukan ulang di PHASE 4 (analytics), setelah RAW EXIM.
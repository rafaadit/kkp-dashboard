# PHASE 9 — TradeMap Data Processing & Harmonization

Pipeline yang mengubah file hasil download TradeMap menjadi data terstruktur,
tervalidasi, terharmonisasi dengan master data internal, dan siap untuk
Market Intelligence Analytics.

```
TradeMap Raw File
  → TradeMapParser        (baca CSV/XLSX, deteksi header konfigurabel)
  → TradeMapNormalizer    (type conversion, flow, nilai, unit)
  → TradeMapMapper        (master mapping ms_negara / ms_hscode / ms_komoditas)
  → HS Harmonization      (trademap_hs_mapping, tanpa mengarang equivalence)
  → TradeMapValidator     (VALID / WARNING / INVALID)
  → Duplicate Check       (business key intrafile)
  → trademap_trade        (processed) + trademap_raw (lineage) + validation results
  → Analytics Ready
```

## 1. Struktur file TradeMap (hasil audit)

File yang benar-benar tersedia di project **hanyalah fixture sintetis**
`tests/fixtures/trademap_sample.csv` (dibuat PHASE 6). **Belum ada file download
TradeMap asli** (robot download = PHASE 8, diblokir karena `TRADEMAP_API_KEY`
kosong). Struktur fixture:

| kolom | tipe | keterangan |
|---|---|---|
| `Reporter` | string, kode ISO 2-huruf | negara pelapor (ID) |
| `Partner` | string, kode ISO | mitra dagang |
| `Flow` | string | `Export` / `Import` |
| `Product code` | string, HS 6 digit | `030617` |
| `Product Label` | string | deskripsi produk |
| `Year` | int | periode (tahunan) |
| `Quantity` | numeric | kuantitas (satuan TIDAK disebut) |
| `Trade Value (US$ Thousand)` | numeric | nilai (satuan dinyatakan header) |

Format yang didukung parser: **CSV/TSV/TXT** (sniff delimiter) & **XLSX**
(sheet pertama). Metadata `Reporter:`/`Year:` di atas header diekstrak sebagai
scope metadata. Header dideteksi dengan alias (bukan posisi hardcode)
di `backend/trademap/config.py`.

> Known issue: TradeMap query asli ITC umumnya 6-digit HS dan menyertakan unit
> kuantitas; fixture tidak memuat unit → seluruh record berstatus WARNING
> (QTY_UNIT_UNKNOWN). **NEEDS_VALIDATION** untuk unit riil & struktur file asli.

## 2. Raw storage & lineage

`trademap_raw` menyimpan metadata per file: `file_hash` (sha256), `source`,
`file_name`, `file_format`, `period_label`, `reporter_scope`, `partner_scope`,
`flow_scope`, `id_download_log`, `id_job` (job pemrosesan), statistik processing
(`total/valid/warning/invalid/duplicate/mapped/unmapped_rows`), `processed_at`.
Setiap baris `trademap_trade` menunjuk ke `id_trademap_raw`. Temuan validasi
dicatat di `trademap_validation_results` (field, source_value, reason,
recommended, severity) — tidak ada data yang hilang.

## 3. Master mapping (bukan source of truth TradeMap)

- **Negara** → `ms_negara` (kode ISO2 lalu nama). Tidak ketemu → `COUNTRY_UNMAPPED`.
- **HS** → `ms_hscode` (kanonikal HS 2022). Tidak ketemu → `HS_MAPPING_REQUIRED`.
- **Komoditas** → `ms_komoditas` via bridge `ms_komoditas_hscode`
(kolom `komoditas_5_2026`).

### HS harmonization

Kode 6-digit TradeMap dicocokkan ke `ms_hscode.hs_subpos_6digit` (atau
`kode_hs`/`hs_pos_4digit`/`hs_bab_2digit` untuk kode lain). Hasil:
- 1 kandidat tariff line 8-digit → `MAPPED`
- >1 kandidat → `AMBIGUOUS` (semua kandidat disimpan di `candidates_json`,
  tidak dipilih diam-diam)
- 0 kandidat → `HS_MAPPING_REQUIRED`
- versi sumber ≠ master `HS2022` → `NEEDS_VALIDATION`
- versi tidak diketahui → memakai kandidat `HS2022`, beri catatan

Hasil disimpan ke tabel **`trademap_hs_mapping`** (interface/versioning; unique
`(source_code, source_version)`). **Tidak ada equivalence HS yang dikarang.**

### Trade flow

Kanonikal `EXPORT`/`IMPORT` via `config.FLOW_MAP`; `Re-Export`/`Re-Import`
dinormalisasi dengan tanda WARNING; nilai tak dikenal → record **INVALID**
(`flow` asli tetap disimpan, `flow_norm` menyimpan hasil normalisasi).

### Value & quantity

- `value_usd` (kolom lama) **dipertahankan apa adanya** (nilai sesuai satuan
  sumber, mis. "US$ Thousand") agar kompatibel PHASE 6.
- `value_unit_source` menyimpan label satuan; `value_usd_norm` = nilai
  ter-normalisasi ke USD (faktor skala dari header, bukan business rule).
- Unit kuantitas tidak disebut → WARNING `QTY_UNIT_UNKNOWN`.
- Non-numeric / negatif → INVALID.

## 4. Duplicate & idempotency

- Business key intrafile: `(reporter, partner, flow, product_code, year)`.
  Duplikat dalam file → baris pertama disimpan, sisanya ditandai + dihitung
  `duplicate_rows` dan tidak dimasukkan.
- Idempotensi lintas run: `trademap_raw` di-upsert per `file_hash`;
  `trademap_trade` memakai unique key
  `(reporter, partner, flow, product_code, year, id_trademap_raw)` +
  `INSERT ... ON DUPLICATE KEY UPDATE`. Processing file sama dua kali **tidak**
  menggandakan data (diverifikasi test).

## 5. Perintah

```bash
# dry-run (tidak menulis DB)
.venv/bin/python database/scripts/process_trademap.py tests/fixtures/trademap_sample.csv

# commit (menyimpan + job automation + lineage)
.venv/bin/python database/scripts/process_trademap.py data/trademap/export.csv --commit
# .csv/.tsv/.xlsx ; --source nama_sumber ; --download-log-id N ; --json
```

## 6. Database migration

`database/migrations/0002_trademap_processing.sql` (aditif; tidak mengubah
kolom lama) → 33 tabel. Baru: `trademap_hs_mapping`,
`trademap_validation_results`; kolom baru di `trademap_raw` & `trademap_trade`.

## 7. Test

`.venv/bin/python tests/test_trademap_processing.py` — 58 assertions:
valid / malformed / missing column / invalid HS / unknown country / unknown
commodity / invalid flow / invalid numeric / duplicate / idempotency /
HS version mismatch / empty file / INVALID tidak masuk processed / commit &
lineage. Fixture: `tests/fixtures/trademap/*.csv`.

## 8. Logging per job

Setiap run `trademap_process` menghasilkan job di `automation_jobs` + log di
`automation_job_logs` (start/end, total, valid, warning, invalid, duplicate,
mapped, unmapped, inserted, updated, status, error). Statistik juga disimpan di
`trademap_raw`.
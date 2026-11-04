# BPS Data Ingestion (PHASE 2)

Pipeline ETL: `UPLOAD → VALIDATE → STAGING → TRANSFORM → PROCESS`

## Format file yang didukung

`etl_bps.py` menerima dua bentuk workbook BPS:

| Bentuk | Header | Contoh kolom |
|--------|--------|--------------|
| Data Minimum (kumulatif) | baris 1 | `tahun`, `bulan`, `hscode`, `kd_provinsi_asal`, `kd_negara`, `volume_kg`, `nilai_usd` |
| File bulanan BPS | baris 3 (baris 1 judul, baris 2 kosong) | `Tahun`, `Bulan`, `HS 2022`/`HS`, `Provinsi_Asal`/`Provinsi`, `Kode Pel_Muat`/`Kode Pelabuhan`, `Negara Tujuan`/`Negara/Wilayah/Entitas Asal`, `Volume (Kg)`/`Berat (Kg)`, `FOB (USD)`/`Nilai (USD)` |

Deteksi header otomatis pada 30 baris pertama. Nama kolom dipetakan ke kolom
kanonik tabel staging melalui alias (mis. `HS 2022 → hscode`,
`Berat (Kg) → volume_kg`, `FOB (USD) → nilai_usd`). Baris judul, baris kosong,
baris metadata (`-1, -2, ...`), dan baris `Grand Total`/`Total Impor` dilewati
karena tidak memiliki tahun/bulan valid.

Nama negara pada file bulanan kadang berbeda dengan master `ms_negara`
(mis. `VIETNAM → VIET NAM`). Resolusi memakai kode negara bila sudah valid,
lalu nama negara + alias umum. Nama yang tetap tidak dikenal ditandai
`validation_error` agar terlihat, bukan diam-diam menjadi `NULL`.

## Jalankan

```bash
# load ekspor + impor (format lama maupun bulanan)
python3 database/scripts/etl_bps.py \
    --ekspor "Data Minimum - Ekspor 2022-2026-Mei.xlsx" \
    --impor  "Data Minimum - Impor 2022-2026-Mei.xlsx"

# reload paksa (abaikan hash existing)
python3 database/scripts/etl_bps.py --ekspor "..." --impor "..." --force
```

Idempotent: file dengan `file_hash` yang sudah ada di `bps_upload` di-skip.
File bulanan satu periode juga mengisi `bps_upload.id_ms_period`.

## Hasil (verified)

| Tabel | Baris | Catatan |
|-------|-------|---------|
| `bps_upload` | 4 | 2 file Data Minimum + 1 ekspor & 1 impor bulanan 2026-07 |
| `bps_export_raw` | 193.103 | 189.001 + 4.102, valid 100% |
| `bps_import_raw` | 55.332 | 53.668 + 1.664, valid 100% |
| `bps_export` | 193.103 | grain unique 0 duplikat |
| `bps_import` | 55.332 | grain unique 0 duplikat |
| `raw_exim` | 248.435 | termasuk 5.766 baris periode 2026-07 |

### Verifikasi angka vs PPT (Jan–Jun 2026, kelompok I)
- Ekspor **2.995,2 juta USD** ✅ (cocok PPT)
- Impor **379,65 juta USD** ✅ (cocok PPT)

### Verifikasi file bulanan Juli 2026
- Ekspor: **4.102** baris; volume **361.186.680,8779 kg**; nilai **762.304.444,0546 USD**
- Impor: **1.664** baris; volume **343.302.493,0479 kg**; nilai **290.352.292,0292 USD**
- Semua HS/provinsi/pelabuhan cocok master; 50 baris impor `VIETNAM`
  berhasil dipetakan ke `VIET NAM`.

Semua master mapping 100%: 635 HS, 208 negara, 38 provinsi, 199 pelabuhan, 55 periode.

## Pipeline detail

1. **UPLOAD** — hitung `file_hash` sha256; deteksi header & petakan kolom;
   buat baris `bps_upload` (`periode_mulai`/`periode_akhir` dari rentang data,
   `id_ms_period` terisi bila file hanya berisi satu periode).
2. **VALIDATE + STAGING** — tulis baris mentah ke `bps_export_raw`/`bps_import_raw`
   (kolom text-fidelity + `row_checksum` sha256 + `is_valid` + `validation_error`).
   Aturan validasi: periode ada di `ms_period`, kolom wajib terisi, semua kode
   master ada, `volume_kg` & `nilai_usd` numerik.
3. **TRANSFORM** — `INSERT ... SELECT` join ke master → resolve FK, tulis `bps_export`/`bps_import`
   (grain unique), tanpa duplikat.
4. **PROCESS** — set `bps_upload.status='processed'`.

## Update via dashboard (RBAC)

Pegawai/super_admin dapat mengunggah file BPS periode baru dari halaman
`/data-bps`. Alur background:

```
POST /api/data/bps/upload (multipart ekspor/impor)
  -> data/bps_uploads/<file>.xlsx
  -> automation_jobs (job_type='bps_update')
  -> database/scripts/update_bps.py --job-id N --ekspor ... [--impor ...]
       1. deteksi (tahun, bulan) di file; buat ms_period yang belum ada
       2. etl_bps.ingest_file + transform_fact + reconcile
       3. hapus & generate ulang raw_exim HANYA untuk periode yang
          benar-benar mendapat baris fact baru (file BPS biasanya kumulatif)
       4. catat log ke automation_job_logs + status job
```

Menjalankan wrapper secara manual (mis. untuk debugging):

```bash
python3 database/scripts/update_bps.py --job-id 12 \
    --ekspor data/bps_uploads/file_ekspor.xlsx \
    --impor  data/bps_uploads/file_impor.xlsx
```

Catatan: wrapper berfokus pada **periode baru**. Mengunggah ulang file lama
dengan nilai yang direvisi belum menghapus fact lama; file kumulatif hanya
menambah periode yang belum ada (grain unik `bps_export`/`bps_import` mencegah
duplikasi baris identik).

## Test

```bash
python3 tests/test_bps_parser.py   # parser format lama & bulanan (tanpa DB)
python3 tests/test_etl.py          # verifikasi staging/fact di database
```

## Catatan / Known Issues

- 1 file BPS konsolidasi 2022-01..2026-06 (54 periode) → `bps_upload.id_ms_period` NULL
  (pakai `periode_mulai`/`periode_akhir`). File bulanan per-periode mengisi `id_ms_period`.
- `raw_exim` periode 2026-07 berstatus `needs_validation` sampai `ms_kurs` Juli 2026
  tersedia (kurs JISDOR), karena `kurs_usd`/`nilai_rp` belum bisa dihitung.
- `ms_reference` formula rendemen/setara segar masih `NEEDS VALIDATION`.
- Verifikasi PPT menyeluruh dilakukan ulang di PHASE 4 (analytics), setelah RAW EXIM.

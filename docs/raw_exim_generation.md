# PHASE 3 — RAW EXIM Generation

Pipeline transform `bps_export` / `bps_import` + master/bridge → `raw_exim`
(46 kolom) sesuai format file referensi `Raw_Eksim_Expor .xlsx`.

Script: `database/scripts/generate_raw_exim.py`
Test:   `python3 tests/test_raw_exim.py`

## Alur

```
bps_export / bps_import (fakt BPS PHASE 2)
        │  JOIN ms_period / ms_hscode / ms_provinsi / ms_pelabuhan / ms_negara / ms_kurs
        │  + bridge ms_komoditas_hscode (taxonomi raw: komoditas_1_2017, bentuk_1, jenis, dst)
        ▼
   raw_exim (1 fakt → 1 baris; INSERT IGNORE, idempotent via UNIQUE id_bps_export/id_bps_import)
        │  didaftarkan di automation_jobs (job_type='raw_exim') + automation_job_logs
        ▼
   status: 'ready' utk periode berkurs / 'needs_validation' utk periode tanpa ms_kurs
```

## Pemetaan kolom (ekspor)

| Kolom `raw_exim` | Sumber | Catatan |
|---|---|---|
| exim_type | bps_export → 'ekspor' / bps_import → 'impor' | |
| tahun, bulan | ms_period | |
| kode_hs_2012 | NULL | Selalu kosong di file referensi |
| kode_hs_2022 | ms_hscode.kode_hs | |
| kode_hs_2dg | ms_hscode.hs_bab_2digit | |
| non_konsumsi_konsumsi | kategori_konsumsi → K/N | Konsumsi→K, Non-Konsumsi→N |
| olahan_bukan | status_olahan → O/N | Olahan→O, Non-Olahan→N |
| asalbahanbaku, asalbahanbaku_2_2026 | ms_hscode.asal_bahan_baku | Title-case (2-2026) |
| komoditas_1_2017 / komoditas_2_2017 | bridge `komoditas_1_2017`.nama / .nama_en | |
| komoditas_4_2024 | bridge `komoditas_4_2024`.nama | |
| bentuk_1 / bentuk_2 | bridge `bentuk_1`.nama / .nama_en | |
| jenis | bridge `jenis`.nama | |
| uraian, uraian_id_en_2_2026 | `uraian_id + '/' + lower(uraian_en)` | Format file (tanpa spasi di slash) |
| uraian_2 | ms_hscode.uraian_en | |
| kode_prov_asal / provinsi_asal / pulau_prov_asal | ms_provinsi (dari kode_provinsi_asal) | |
| kode_pelabuhan_muat / pelabuhan_muat_bongkar / moda | ms_pelabuhan | |
| kode_provinsi_pelabuhan / provinsi_pelabuhan / pulau_prov_pelabuhan | ms_provinsi via ms_pelabuhan.id_provinsi | Relasi benar (bukan asal) |
| kode_negara / negara / kelompok_negara | ms_negara | |
| vol_kg, nil_usd | volume_kg, nilai_usd | |
| harga_usd_kg | `nil_usd / vol_kg` | Verified 0 mismatch |
| ttc | kategori_tuna | 'Bukan TTC' → '0' |
| rendemen | ms_hscode.rendemen | 1.0 = placeholder valid (non-perikanan) |
| setara_segar | `vol_kg / rendemen` | Bukan `vol * rendemen` |
| koding | ms_hscode.kode_kelompok | `VARCHAR(3)` (III tidak terpotong) |
| tahun_bulan | `f"{tahun}{bulan:02d}"` | `202606` |
| kurs_usd | ms_kurs.rata_rata_kurs per periode | NULL bila periode belum ada kurs |
| nilai_rp | `round(nil_usd * kurs_usd, 2)` | NULL bila kurs NULL |
| komoditas_5_2026 | ms_hscode.kelompok_komoditas | |
| bentuk_3_2026 / bentuk_4_2026 | bridge `bentuk_3_2026`.nama / .nama_en | |
| jenis_2_2026 | bridge `jenis_2_2026`.nama | |
| bentuk_5_2026 | bridge `bentuk_5_2026`.nama | |

### Impor

Menggunakan kolom bongkar: `kode_provinsi_bongkar`, `kode_pelabuhan_bongkar`,
`kode_negara_asal` dipetakan ke kolom pelabuhan/provinsi/negara yang sama.

## ms_kurs & status

- **Sumber resmi kurs**: JISDOR **website Bank Indonesia** (www.bi.go.id),
  rata-rata **per bulan** — nilai **berbeda tiap bulan** (konfirmasi user).
  Isi per periode: `python3 database/scripts/import_jisdor.py kurs.csv --commit`
  (CSV: `tahun,bulan,kurs`).
- Saat ini `ms_kurs` hanya berisi nilai **referensi verifikasi** dari file RAW
  EXIM (2026-06 = 358482, KONSTAN) — **bukan JISDOR riil**, ditandai
  `needs_validation`. Sumber: seed `011_ms_kurs.sql`.
- Baris dengan kurs tersedia → `status='ready'`; periode tanpa kurs
  (nilai_rp tidak dapat dihitung) → `status='needs_validation'`. Setelah kurs
  JISDOR riil di-import, jalankan ulang `generate_raw_exim.py --force` agar
  `nilai_rp` terisi dengan kurs benar.
- Catatan formula di `ms_reference` (`kurs.sumber` = validated, JISDOR BI):
  `raw_exim.setara_segar`, `raw_exim.harga`, `raw_exim.nilai_rp`,
  `raw_exim.kurs_juni_2026`, `raw_exim.komoditas_...`.

## Verifikasi 1:1 vs file referensi (2026-06 ekspor, 4.114 baris)

Semua 4.114 baris cocok per grain (kode_hs+vol+nil+kode_pelabuhan+kode_negara).
Kolom yang berbeda **bukan bug pipeline** melainkan artefak "master HS v2"
yang dipakai file (NEEDS VALIDATION, lihat ms_reference):

| Kolom | Mismatch | Penyebab |
|---|---|---|
| pelabuhan_muat_bongkar | 2.334 | File pakai nama master v2 (mis. `SOEKARNO-HATTA (U)` vs `CENGKARENG / SOEKARNO-HATTA`) |
| moda | 2.275 | File inkonsisten per pelabuhan (IDCGK: LAUT 506/UDARA 872); kita pakai `ms_pelabuhan.moda` |
| provinsi_pelabuhan | 1.865 | File memakai provinsi asal/inkonsisten; kita pakai relasi benar pelabuhan→provinsi |
| kelompok_negara | 526 | ~510 baris file kosong (komoditas non-inti) |
| pulau_prov_asal | 492 | `Bali-NT` (file) vs `Bali-Nusa Tenggara` (db) |
| bentuk_2 / bentuk_4 | 185 / 132 | Label EN (`Others` vs `Prepared Or Preserved`) |
| uraian_id_en_2_2026 | 103 | Teks deskripsi master v2 |
| asalbahanbaku | 75 | Kasus/`KELAUTAN` vs master |
| uraian | 18 | Teks deskripsi master v2 |
| negara | 1 | `kd ET` → ETHIOPIA (db) vs ESTONIA (file) |

## Cara pakai

```bash
python3 database/scripts/generate_raw_exim.py                 # generate semua periode
python3 database/scripts/generate_raw_exim.py --period 2026-06  # scope satu periode
python3 database/scripts/generate_raw_exim.py --force         # hapus & regenerate
python3 database/scripts/generate_raw_exim.py --ekspor-only   # hanya ekspor
python3 tests/test_raw_exim.py                                # verifikasi
```
# PHASE 7 — Laporan PPT Otomatis

Generator laporan perikanan (neraca perdagangan luar negeri) dari data `raw_exim`
menggunakan **python-pptx**, mengikuti struktur deck referensi
`Draft_EKSIM_Jan-Juni_2026_06082026 (1).pptx` (11 slide).

## Struktur slide

| # | Slide | Isi |
|---|---|---|
| 0 | Cover | Judul + periode |
| 1 | Kinerja Ekspor | Line chart Jan–Jun 2022–tahun (USD miliar) |
| 2 | Ekspor-Impor-Neraca | Bar chart 3 seri (USD miliar) |
| 3 | Negara Tujuan Ekspor | Tabel 10 teratas |
| 4 | Komoditas Utama Ekspor | Tabel 10 teratas |
| 5 | Pasar/Pelabuhan Utama | Tabel 10 teratas |
| 6 | Produk Utama Ekspor | Tabel komoditas_5_2026 |
| 7 | Kinerja Impor | Line chart |
| 8 | Negara Asal Impor | Total + tabel |
| 9 | Komoditas Utama Impor | Tabel |
| 10 | Catatan | Sumber & disclaimer (needs_validation) |

## Menjalankan

```bash
.venv/bin/python backend/report/generate_ppt.py --tahun 2026 --bulan-awal 1 --bulan-akhir 6
# output default: data/reports/Laporan_EKSIM_*-*.pptx
```

Setiap pembuatan dicatat di `automation_jobs` (`job_type='report_ppt'`) dan
`automation_job_logs` (data_json berisi path file).

## API

| Endpoint | Fungsi |
|---|---|
| `GET /api/report/list` | daftar job laporan + status file (downloadable) |
| `POST /api/report/generate_ppt` | `{tahun, bulan_awal, bulan_akhir}` → generate |
| `GET /api/report/download?job_id=N` | unduh file .pptx |

Permission: `report.view` (list/download), `report.generate_ppt` (generate).

## Frontend

Halaman `/laporan` (menu **Laporan PPT**): form periode + tombol Generate,
tabel riwayat job, dan tombol Unduh (proxy melalui `ApiClient::getRaw` agar
token tetap di sisi server).

## Catatan

- Nilai mengambil `raw_exim.nil_usd`; angka `nilai_rp` bergantung kurs JISDOR
  (lihat PHASE 3) sehingga tidak dipakai di deck.
- Semua slide dibuat dari nol dengan tema navy/gold; tidak memerlukan file
  template eksternal (deck referensi hanya acuan struktur).
- Test: `.venv/bin/python tests/test_report.py` (16 assertions).
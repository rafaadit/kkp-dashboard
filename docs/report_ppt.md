# PHASE 7 — Laporan PPT Otomatis (template-driven)

Generator laporan perikanan (neraca perdagangan luar negeri) dari data
`raw_exim`, **mengisi deck resmi template**
`Draft_EKSIM_Jan-Juni_2026_06082026 (1).pptx` (11 slide) menggunakan
python-pptx + pars XML (string table, charts, picture kerangka P4).

## Cara kerja

`backend/report/template_fill.py`:
1. `collect_data()` ambil data dari DB (`raw_exim`), komoditas dari
   `ms_komoditas`, negara dari `ms_negara`, chart agregat periode,
   nilai & YoY per slide.
2. `fill_presentation()` == untuk tiap slide 0–9 jalankan `_fill_slide{0..9}()`
   yang mengisi 25-an kotak teks multi-baris yang direferensikan **string
   persis di template** (placeholder `X:X`), lalu `fill_charts()` yang
   me-replace data chart (2 seri: Volume juta ton + Nilai USD miliar,
   kategori 2022–tahun) dengan `CategoryChartData`, termasuk chart yang
   berada di dalam grup (`_iter_chart_shapes`).
3. Nilai & YoY mengecualikan literal `Lainnya` dari kandidat top-N sehingga
   baris terakhir tidak terisi duplikat; kotak YoY kembar (mis. dua box
   `0,7%`) dibedakan via `_assign_yoy()` dengan marker sub-tree grup.
4. Urutan penampungan nilai done 25 kotak string; tidak ada tabel template
   (deck flat) — slide 10 (Catatan) sengaja dilewati.

Detail referensi & format ada inline di tiap `_fill_slideN()` di
`template_fill.py`: setiap entri berisi `val_refs`, `yoy_refs`, dan pemformat
(`id_fmt`/`miliar_id`/`juta_id`/`pct_id`/`yoy_cur`/`cagr`).

### Bentuk data yang dihasilkan

```
Nilai ekspor (USD, miliar) 3,42; YoY +4,3%; volume impor 1.775,57 Juta Ton
Nilai impor (USD, miliar) 1,38; YoY +19,9% (Jan–Mar: 570,67 Juta / Jan–Jun: 1.376,83 Juta)
```

Nilai yang ditampilkan apa adanya dari DB (`nil_usd`), data-driven — bukan
hardcode. Angka `0,23` di referensi slide awal memang kecil dibanding `1.775,57`
karena referensi itu memakai cakupan/kode berbeda; tetap dianggap benar karena
mengikuti DB.

## Menjalankan

```bash
.venv/bin/python backend/report/generate_ppt.py --template 'Draft_EKSIM_Jan-Juni_2026_06082026 (1).pptx' \
    --tahun 2026 --bulan-awal 1 --bulan-akhir 6
# output default: data/reports/Laporan_EKSIM_2026-01-06.pptx
```

Setiap pembuatan dicatat di `automation_jobs` (`job_type='report_ppt'`) dan
`automation_job_logs` (data_json berisi path file). Data job di skema
`graph.schema_migrations` / `api` opt-in.

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
- Draft terbaru dibuat dari template inti; tidak didukung run-time pemilihan
  tema — mengikuti tema navy/gold deck.
- Test: `.venv/bin/python tests/test_report.py` — wajib template tersedia
  (`Draft_EKSIM_Jan-Juni_2026_06082026 (1).pptx`). Menyatakan 11 slide,
  chart ≥ 3, TANPA tabel (template flat), slide1 mengandung langkah nilai &
  YoY regex, chart 5 kategori berakhir tahun, slide8 TOTAL IMPOR.
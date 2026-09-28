# PHASE 9c — Robot unduhan Kurs JISDOR Bank Indonesia

Ambil kurs harian **JISDOR (USD/IDR)** dari web service resmi Bank Indonesia
`https://www.bi.go.id/biwebservice/wskursbi.asmx`
(fungsi `getSubKursJisdor3`; publik, **tanpa API key**, cukup User-Agent),
lalu:

1. simpan XML mentah ke `BI_JISDOR_DIR` (default `./data/kurs`)
2. tulis lineage: `automation_jobs` (`jisdor_download`) +
   `automation_download_logs` (PENDING → DOWNLOADED → VALIDATED)
3. proses (`--commit`): isi `jisdor_daily` (harian) + **rata-rata bulanan ke
   `ms_kurs`** (sumber `JISDOR Bank Indonesia`) → dasar `raw_exim.kurs_usd` /
   `nilai_rp` yang selama ini masih placeholder `358482`.

## Web service BI

`GET /biwebservice/wskursbi.asmx/getSubKursJisdor3?mts=USD&startDate=…&endDate=…`
→ `DataSet`/`Table` dengan kolom `tgl_subkursasing`, `beli_subkursasing`,
`jual_subkursasing` (JISDOR: beli == jual == kurs acuan). JISDOR diterbitkan
tiap **hari kerja** (libur nasional tidak muncul).

## Komponen

| Komponen | File |
|---|---|
| Downloader + parser XML | `backend/kurs/jisdor.py` (`JisdorDownloader`, `parse_xml`) |
| CLI | `database/scripts/download_jisdor.py` |
| Scheduler | `database/scripts/automation_scheduler.py --once` (`jisdor_download`) |
| Skema | `database/migrations/0003_kurs_jisdor.sql` (`jisdor_daily`) |

Env: `BI_JISDOR_URL`, `BI_JISDOR_DIR` (di `.env`).

## CLI

```bash
# bulan berjalan, dry-run (belum nulis DB)
.venv/bin/python database/scripts/download_jisdor.py

# Juni 2026, simpan ke DB
.venv/bin/python database/scripts/download_jisdor.py --start 2026-06-01 --end 2026-06-30 --commit

# uji tanpa internet: fixture XML
.venv/bin/python database/scripts/download_jisdor.py --fixture tests/fixtures/jisdor_sample.xml --commit --json
```

Opsi: `--mts USD`, `--start/--end YYYY-MM-DD`, `--source`, `--fixture`,
`--no-process`, `--commit` (default dry-run), `--json`. Exit 0 = sukses.

Hasil contoh (Jun 2026 riil): 20 hari kerja, rata-rata **17.924,10** → masuk
`ms_kurs` periode 2026-06.

## Scheduler

```bash
.venv/bin/python database/scripts/automation_scheduler.py --once
# atau cron: 30 16 * * 1-5 ...  (JISDOR terbit ±15.15 WIB)
```

Job `jisdor_download` di `params_json`: `mts`, `start`, `end`, `fixture`,
`process`. Attempts/retry ditangani downloader (resume = attempts+1).

## Setelah kurs riil masuk

`raw_exim.kurs_usd`/`nilai_rp` masih nilai lama hasil generate; hitung ulang
via `database/scripts/generate_raw_exim.py` (dry-run dulu) atau pipeline yang
memakai `ms_kurs` — memvalidasi temuan auditan `needs_validation` kurs.

## Test

`.venv/bin/python tests/test_kurs.py` — fixture lokal + snapshot/restore
(minimal residu DB): unduh+hash+copy, resume/attempts, dry-run tak menyentuh
`ms_kurs`, commit isi `jisdor_daily` + rata2 `ms_kurs`, dispatch scheduler,
CLI `--json`.
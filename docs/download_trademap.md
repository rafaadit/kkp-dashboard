# PHASE 9b — Robot unduhan TradeMap + Scheduler Automation

Mengambil file data TradeMap (ITC) ke `TRADEMAP_DOWNLOAD_DIR` dan mencatat
lineage di `automation_jobs` + `automation_download_logs`:

```
PENDING -> RUNNING -> SUCCESS        (download + hash cocok)
                    -> FAILED        (error; error_message tercatat)
```

## Komponen

| Komponen | File |
|---|---|
| Downloader | `backend/trademap/downloader.py` (`TradeMapDownloader`) |
| CLI | `database/scripts/download_trademap.py` |
| Scheduler | `database/scripts/automation_scheduler.py` |

`TRADEMAP_API_URL`, `TRADEMAP_API_KEY`, `TRADEMAP_DOWNLOAD_DIR` dibaca dari env
(ada di `.env`, default `./data/trademap`). Tanpa `TRADEMAP_API_KEY` dan tanpa
`--fixture`, job diberi status **FAILED** (robot aman, tidak crash) — untuk uji
tanpa kredensial nyata gunakan `--fixture`.

## CLI download

```bash
# unduh Export 2024 (butuh API key nyata)
.venv/bin/python database/scripts/download_trademap.py --flow Export --year 2024 --commit

# uji lokal tanpa API key: pakai file fixture, tanpa pipeline proses
.venv/bin/python database/scripts/download_trademap.py \
    --fixture tests/fixtures/trademap_sample.csv --no-process --json

# unduh + jalankan pipeline pemrosesan (process_trademap), kunci --commit utk menulis
.venv/bin/python database/scripts/download_trademap.py \
    --fixture data/trademap/export.csv --commit
```

Opsi: `--flow Export|Import`, `--year`, `--partner`, `--source`,
`--fixture PATH`, `--no-process`, `--no-commit` (dry-run pipeline),
`--json` (ringkasan). Exit code 0 = sukses.

File disalin ke `data/trademap/<flow>-<year>-<partner>-<ts>.csv` (di
`TRADEMAP_DOWNLOAD_DIR`) dan dicatat `sha256` + `file_size` di
`automation_download_logs`. Status `VALIDATED` tercapai setelah proses
pemrosesan selesai tanpa error.

## Scheduler

```bash
# satu sweep (cocok untuk cron), keluar setelah selesai
.venv/bin/python database/scripts/automation_scheduler.py --once

# loop tiap 300 detik
.venv/bin/python database/scripts/automation_scheduler.py --every 300
```

- Menangkap job `automation_jobs` dengan `status='PENDING'` dan
  `scheduled_at IS NULL` atau sudah lewat, urut paling tua dulu.
- `job_type` yang dikenal: `trademap_download` (dari `params_json`:
  `flow`/`year`/`partner`/`source`/`fixture`/`process`).
- Dispatch memakai `TradeMapDownloader.run(..., job_id=...)` sehingga status &
  `attempts` (retry counter, resume ditambah 1) dikelola downloader.
- `--job-type` membatasi jenis (bisa diulang); jenis tak dikenal → exit 2.

Contoh cron (tiap jam):
```
0 * * * * cd /path/project && .venv/bin/python database/scripts/automation_scheduler.py --once
```

## Test

`.venv/bin/python tests/test_download.py` — fixture lokal, tidak menyentuh
`trademap_trade`: unduhan+copy+hash, resume/attempts, proses dry-run →
`VALIDATED`, gagal aman tanpa API key, dispatch scheduler, CLI `--json`.
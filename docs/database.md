# Database Architecture — `kkp_exim_platform`

MySQL 8.0.33 | InnoDB | utf8mb4_unicode_ci | 31 tabel | Seed + Migration based

---

## Tabel Overview

### Foundation (Master)

| Tabel | Deskripsi | Seed |
|-------|-----------|------|
| `ms_period` | Bulan-tahun data (2022-01 → 2026-06) | 54 baris |
| `ms_negara` | 208 negara, 17 kelompok | master_exim_reference.xlsx |
| `ms_provinsi` | 38 provinsi + pulau | master_exim_reference.xlsx |
| `ms_pelabuhan` | 199 pelabuhan (DARAT/LAUT/UDARA) → ms_provinsi | master_exim_reference.xlsx |
| `ms_unit` | Satuan (kg, ton, USD, Rp, dst) | Seed hardcoded |
| `ms_hscode` | 635 HS 2022 + kelompok_komoditas + bentuk + pengolahan | master_exim_reference.xlsx |
| `ms_komoditas` | 896 taksonomi (kelompok/bentuk/pengolahan/5 versi) | master + RAW EXIM bridge |
| `ms_komoditas_hscode` | 3725 bridge HS↔komoditas | computed |
| `ms_kurs` | Kurs JISDOR per periode | manual |
| `ms_manual_correction` | Koreksi manual (ex. kekerangan) | - |
| `ms_reference` | Formula/metrik + status `needs_validation` | hardcoded |

### BPS Staging → Fact

| Tabel | Deskripsi |
|-------|-----------|
| `bps_upload` | Metadata upload file BPS (per periode per user) |
| `bps_export_raw` | Baris mentah ekspor (belum validated) |
| `bps_import_raw` | Baris mentah impor (belum validated) |
| `bps_export` | Grain ekspor valid (period+HS+prov+pel+negara+vol+nilai) |
| `bps_import` | Grain impor valid |

### Automation

| Tabel | Deskripsi |
|-------|-----------|
| `automation_jobs` | Job ETL / download / validation |
| `automation_job_items` | Sub-item per job |
| `automation_job_logs` | Log per job item |
| `automation_download_logs` | Log download per negara/HS/periode |

### EXIM (Produk Final)

| Tabel | Deskripsi |
|-------|-----------|
| `raw_exim` | 46 kolom, output pipeline → source bps_export/bps_import |

### TradeMap

| Tabel | Deskripsi |
|-------|-----------|
| `trademap_raw` | File mentah ITC TradeMap |
| `trademap_trade` | Data perdagangan terproses (reporter/partner/flow/product/year) |

### Analytics & Audit

| Tabel | Deskripsi |
|-------|-----------|
| `analytics_metric` | Cache metric analytics per grain+periode |
| `audit_logs` | Log perubahan data |

### App / Auth

| Tabel | Deskripsi |
|-------|-----------|
| `app_roles` | 3 role: user, pegawai, super_admin |
| `app_permissions` | 28 izin (explore/data/exim/report/ai/admin/system) |
| `app_role_permissions` | Bridge role→permission |
| `app_users` | User accounts + role FK |
| `app_user_tokens` | JWT / API token |
| `app_notifications` | Notifikasi user |

---

## Key Relationships (FK)

```
ms_period ← bps_upload.uploaded_by → app_users
bps_upload ← bps_export_raw/raw → bps_export/import
bps_export_raw → bps_export (1:1 id)
bps_import_raw → bps_import (1:1 id)
bps_export ← raw_exim (via id_bps_export) [nullable, single source]
bps_import ← raw_exim (via id_bps_import) [nullable, single source]
automation_jobs → raw_exim (via id_generated_by_job)
automation_jobs → automation_job_items → automation_job_logs
automation_job_items → automation_download_logs → trademap_raw
trademap_raw → trademap_trade (1 file : many rows)
ms_hscode ← bps_export/import, raw_exim (via id)
ms_hscode ↔ ms_komoditas via ms_komoditas_hscode (bridge)
ms_negara ← bps_export/import, raw_exim (via kode_negara)
ms_provinsi ← bps_export/import (via kode_provinsi_asal/muat/bongkar)
ms_pelabuhan ← bps_export/import (via kode_pelabuhan_muat/bongkar)
app_roles ← app_users ← app_user_tokens/audit_logs/notifications
app_roles ↔ app_permissions via app_role_permissions
ms_period ← ms_kurs (1:1), ← analytics_metric, ← raw_exim
```

---

## Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| DB baru `kkp_exim_platform` (bukan `eksim_system`) | eksim_system = milik MI KKP lama, dibiarkan utuh |
| 31 tabel (bukan 17 seperti eksim_system) | Lebih granular: bridge `ms_komoditas_hscode`, staging `bps_*_raw`, audit logs, notifications |
| `raw_exim` = 46 kolom | Verified 1:1 dari file Raw_Eksim_Expor.xlsx + exim_type + BPS FK + status |
| `ms_kurs` per periode (bukan per hari) | Kurs JISDOR dikonfirmasi konstan per periode dari eksim_system |
| Grain `bps_export` = 8 kolom | Verified 0 duplikat 189.001 baris ekspor |
| CHECK constraint `single_source` dihapus | MySQL 8.0.33 menolak CHECK yang involves FK+SET NULL; ditegakkan di aplikasi |
| `ms_komoditas` multi-sumber | Konsisten untuk analytics & TradeMap yang butuh taxonomy granular |
| `ms_reference.sumber` = 'NEEDS VALIDATION' | Formula belum dikonfirmasi (sementara) |
| 3 role permission dicek backend | Bukan hanya sembunyi button di frontend |
| `app_users` / `app_user_tokens` | JWT auth via token, password di-hash (tidak di source) |

---

## Seed Files

| File | Isi | Sumber |
|------|-----|--------|
| `001_ms_period.sql` | 54 bulan 2022-01..2026-06 | Generated |
| `002_ms_negara.sql` | 208 negara | master_exim_reference.xlsx |
| `003_ms_provinsi.sql` | 38 provinsi | master_exim_reference.xlsx |
| `004_ms_pelabuhan.sql` | 199 pelabuhan + FK → ms_provinsi | master_exim_reference.xlsx |
| `005_ms_unit.sql` | 7 satuan | Hardcoded |
| `006_ms_hscode.sql` | 635 HS 2022 + metadata | master_exim_reference.xlsx |
| `007_ms_komoditas.sql` | 896 taksonomi | master + RAW EXIM |
| `008_ms_komoditas_hscode.sql` | 3725 bridge | computed |
| `009_ms_reference.sql` | 19 formula/metrik | Hardcoded (NEEDS VALIDATION) |
| `010_app_roles_permissions.sql` | 3 roles + 28 permissions + 64 mappings | Hardcoded |

---

## Known Issues & Assumptions

| Item | Status | Catatan |
|------|--------|---------|
| Formula Setara Segar | Verified 100% | `VOL / Rendemen` (bukan `*`) |
| Kurs JISDOR | Verified konstan per periode | Tabel `ms_kurs` kosong, diisi manual |
| `raw_exim.status` enum | Diperluas dari 'ready' | Sebelumnya hanya 'needs_validation'/'rejected' |
| `bps_export_raw` / `bps_import_raw` | Ready, belum ada data | Data di-load via PHASE 2 |
| `ms_komoditas` bridge coverage | 3725 rows | Multi-sumber: 6 versi kolom |
| `ms_reference` sumber | NEEDS VALIDATION | Beberapa formula belum dikonfirmasi user |
| `app_users` seed | Tidak ada seed default | User registrasi via PHASE 3+ |

---

## Migration

Basis: `migrations/0001_initial.sql` (copy dari `schema.sql`)

Jalankan inisialisasi:
```bash
bash database/scripts/init_db.sh          # build biasa
bash database/scripts/init_db.sh --drop   # rebuild dari nol
```

Tests:
```bash
python3 tests/test_schema.py
```

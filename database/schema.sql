-- ============================================================================
-- PROJECT KKP — Market Intelligence & EXIM Automation Platform
-- DATABASE SCHEMA  (MySQL 8.0)  — source of truth
-- ============================================================================
-- Category separation (konseptual, berdasarkan hasil audit):
--   A. MASTER DATA      (ms_*)            F. AUTOMATION / JOB (automation_*)
--   B. STAGING / RAW    (bps_*_raw, ...)  G. AUDIT / LOG      (audit_logs)
--   C. FACT / PROCESSED (bps_export, bps_import, raw_exim, trademap_trade)
--   D. ANALYTICS        (analytics_metric)
--   E. APPLICATION      (app_*)
--
-- Note: urutan CREATE mengikuti dependensi FOREIGN KEY (parent sebelum child).
--
-- Notes / decisions:
--   * Platform terpisah dari sistem MI KKP lama; database `eksim_system`
--     (legacy, kosong) TIDAK diubah. Database baru: `kkp_exim_platform`.
--   * ms_hscode mengikuti master_exim_reference.xlsx (24 kolom, HS 2022
--     kanonikal + kode_hs_2017_prev untuk versioning lintas versi).
--   * raw_exim mengikuti struktur verified RAW EXIM (46 kolom) + traceability
--     ke baris fact bps_export / bps_import.
--   * ms_kurs = sumber kurs JISDOR Bank Indonesia (menjawab temuan audit
--     tentang kolom Kurs pada RAW EXIM).
--   * ms_komoditas / ms_komoditas_hscode = kamus taksonomi + mapping HS<->komoditas
--     (versi 2017 / 2024 / 2026, serta kelompok/prioritas/komoditas).
--   * ms_reference berisi formula/metrik yang belum resmi dengan status
--     needs_validation (TIDAK ada klaim formula tanpa konfirmasi).
-- ============================================================================

CREATE DATABASE IF NOT EXISTS kkp_exim_platform
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE kkp_exim_platform;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- 1) MASTER DATA (tanpa dependensi eksternal)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ms_negara (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kode_negara   VARCHAR(10)     NOT NULL,
    nama_negara   VARCHAR(150)    NOT NULL,
    kelompok_negara VARCHAR(100)  NOT NULL,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_negara_kode (kode_negara),
    KEY idx_ms_negara_kelompok (kelompok_negara)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master negara tujuan/asal + kelompok negara';

CREATE TABLE IF NOT EXISTS ms_provinsi (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kode_provinsi VARCHAR(10)     NOT NULL,
    nama_provinsi VARCHAR(150)    NOT NULL,
    pulau         VARCHAR(50)     NOT NULL,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_provinsi_kode (kode_provinsi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master provinsi asal/bongkar';

CREATE TABLE IF NOT EXISTS ms_period (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    tahun         SMALLINT UNSIGNED NOT NULL,
    bulan         TINYINT UNSIGNED NOT NULL,
    label         VARCHAR(20)     NOT NULL,
    tanggal_mulai DATE            NULL,
    tanggal_akhir DATE            NULL,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_period (tahun, bulan),
    KEY idx_ms_period_label (label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master referensi periode bulanan EXIM';

CREATE TABLE IF NOT EXISTS ms_pelabuhan (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kode_pelabuhan VARCHAR(10)    NOT NULL,
    nama_pelabuhan VARCHAR(150)   NOT NULL,
    moda          VARCHAR(20)     NOT NULL,
    id_provinsi   BIGINT UNSIGNED NOT NULL,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_pelabuhan_kode (kode_pelabuhan),
    KEY idx_ms_pelabuhan_provinsi (id_provinsi),
    CONSTRAINT fk_ms_pelabuhan_provinsi FOREIGN KEY (id_provinsi)
        REFERENCES ms_provinsi (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master pelabuhan muat/bongkar beserta moda transportasi';

CREATE TABLE IF NOT EXISTS ms_unit (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kode        VARCHAR(20)     NOT NULL,
    nama        VARCHAR(100)    NOT NULL,
    simbol      VARCHAR(20)     NULL,
    deskripsi   VARCHAR(255)    NULL,
    is_active   TINYINT(1)      NOT NULL DEFAULT 1,
    created_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_unit_kode (kode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master satuan/unit';

CREATE TABLE IF NOT EXISTS ms_reference (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ref_group     VARCHAR(100)    NOT NULL,
    ref_key       VARCHAR(100)    NOT NULL,
    ref_value     VARCHAR(1000)   NOT NULL,
    deskripsi     VARCHAR(1000)   NULL,
    sumber        VARCHAR(255)    NULL,
    status        ENUM('validated','needs_validation') NOT NULL DEFAULT 'needs_validation',
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_reference (ref_group, ref_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Konfigurasi/referensi generik; formula belum resmi ditandai needs_validation';

CREATE TABLE IF NOT EXISTS ms_hscode (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kode_hs           VARCHAR(10)     NOT NULL,
    hs_bab_2digit     VARCHAR(2)      NULL,
    hs_pos_4digit     VARCHAR(4)      NULL,
    hs_subpos_6digit  VARCHAR(6)      NULL,
    uraian_id         VARCHAR(1000)   NULL,
    uraian_en         VARCHAR(1000)   NULL,
    uraian_bilingual  VARCHAR(2000)   NULL,
    kelompok_komoditas VARCHAR(150)   NULL,
    jenis_produk      VARCHAR(150)    NULL,
    bentuk_produk_id  VARCHAR(150)    NULL,
    bentuk_produk_en  VARCHAR(150)    NULL,
    kategori_konsumsi VARCHAR(20)     NULL,
    status_olahan     VARCHAR(20)     NULL,
    asal_bahan_baku   VARCHAR(50)     NULL,
    kbli_2020         VARCHAR(20)     NULL,
    uraian_kbli       VARCHAR(255)    NULL,
    rendemen          DECIMAL(12,6)   NULL,
    jenis_pengolahan  VARCHAR(100)    NULL,
    kategori_tuna     VARCHAR(30)     NULL,
    prioritas_ekspor_utama VARCHAR(150) NULL,
    prioritas_impor_utama VARCHAR(150) NULL,
    kode_kelompok     VARCHAR(3)      NULL,
    status_transaksi_riil VARCHAR(40)  NULL,
    kode_hs_2017_prev VARCHAR(10)     NULL,
    is_active         TINYINT(1)      NOT NULL DEFAULT 1,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_hscode_kode (kode_hs),
    KEY idx_ms_hscode_kelompok (kode_kelompok),
    KEY idx_ms_hscode_prio_ekspor (prioritas_ekspor_utama),
    KEY idx_ms_hscode_prio_impor (prioritas_impor_utama)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master HS Code (kanonikal HS 2022) + atribut tetap';

CREATE TABLE IF NOT EXISTS ms_komoditas (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nomenklatur   VARCHAR(30)     NOT NULL,
    versi         VARCHAR(50)     NOT NULL,
    kode          VARCHAR(50)     NULL,
    nama          VARCHAR(150)    NOT NULL,
    nama_en       VARCHAR(150)    NULL,
    urutan        INT             NULL,
    sumber        VARCHAR(50)     NULL,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_komoditas (nomenklatur, versi, nama),
    KEY idx_ms_komoditas_versi (versi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Kamus klasifikasi: komoditas/bentuk/jenis/tuna/pengolahan per versi taksonomi';

CREATE TABLE IF NOT EXISTS ms_komoditas_hscode (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ms_hscode_id    BIGINT UNSIGNED NOT NULL,
    ms_komoditas_id BIGINT UNSIGNED NOT NULL,
    kolom_sumber    VARCHAR(60)     NOT NULL,
    sumber          VARCHAR(50)     NULL,
    is_primary      TINYINT(1)      NOT NULL DEFAULT 0,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_komoditas_hscode (ms_hscode_id, ms_komoditas_id, kolom_sumber),
    KEY idx_ms_komoditas_hscode_k (ms_komoditas_id),
    CONSTRAINT fk_kh_hscode FOREIGN KEY (ms_hscode_id)
        REFERENCES ms_hscode (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_kh_komoditas FOREIGN KEY (ms_komoditas_id)
        REFERENCES ms_komoditas (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Mapping HS Code <-> komoditas (banyak versi taksonomi)';

-- ============================================================================
-- 2) APPLICATION FOUNDATION (parent: roles & permissions, users)
-- ============================================================================

CREATE TABLE IF NOT EXISTS app_roles (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kode       VARCHAR(30)     NOT NULL,
    nama       VARCHAR(100)    NOT NULL,
    deskripsi  VARCHAR(255)    NULL,
    is_active  TINYINT(1)      NOT NULL DEFAULT 1,
    created_at TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_app_roles_kode (kode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Role: user / pegawai / super_admin';

CREATE TABLE IF NOT EXISTS app_permissions (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kode       VARCHAR(100)    NOT NULL,
    nama       VARCHAR(150)    NOT NULL,
    grup       VARCHAR(50)     NULL,
    is_active  TINYINT(1)      NOT NULL DEFAULT 1,
    created_at TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_app_permissions_kode (kode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Katalog permission (dicek di backend)';

CREATE TABLE IF NOT EXISTS app_role_permissions (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    app_role_id      BIGINT UNSIGNED NOT NULL,
    app_permission_id BIGINT UNSIGNED NOT NULL,
    created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_app_role_permissions (app_role_id, app_permission_id),
    KEY idx_app_rp_perm (app_permission_id),
    CONSTRAINT fk_app_rp_role FOREIGN KEY (app_role_id)
        REFERENCES app_roles (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_app_rp_perm FOREIGN KEY (app_permission_id)
        REFERENCES app_permissions (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Mapping role <-> permission';

CREATE TABLE IF NOT EXISTS app_users (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nama          VARCHAR(150)    NOT NULL,
    email         VARCHAR(150)    NOT NULL,
    password_hash VARCHAR(255)    NOT NULL,
    app_role_id   BIGINT UNSIGNED NOT NULL,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    last_login_at TIMESTAMP       NULL,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_app_users_email (email),
    KEY idx_app_users_role (app_role_id),
    CONSTRAINT fk_app_users_role FOREIGN KEY (app_role_id)
        REFERENCES app_roles (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Akun pengguna platform';

CREATE TABLE IF NOT EXISTS app_user_tokens (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    app_user_id BIGINT UNSIGNED NOT NULL,
    token_hash  CHAR(64)        NOT NULL,
    token_type  ENUM('session','api','refresh') NOT NULL DEFAULT 'api',
    expires_at  TIMESTAMP       NULL,
    revoked_at  TIMESTAMP       NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_app_user_tokens_hash (token_hash),
    KEY idx_app_user_tokens (app_user_id),
    CONSTRAINT fk_app_tokens_user FOREIGN KEY (app_user_id)
        REFERENCES app_users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Token sesi/API (hash, bukan plaintext)';

CREATE TABLE IF NOT EXISTS app_notifications (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    app_user_id BIGINT UNSIGNED NOT NULL,
    judul       VARCHAR(200)    NOT NULL,
    isi         TEXT            NULL,
    is_read     TINYINT(1)      NOT NULL DEFAULT 0,
    created_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_app_notifications_user (app_user_id, is_read),
    CONSTRAINT fk_app_notif_user FOREIGN KEY (app_user_id)
        REFERENCES app_users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Notifikasi dalam aplikasi';

-- ============================================================================
-- 3) MASTER data dengan dependensi app/job
-- ============================================================================

CREATE TABLE IF NOT EXISTS ms_kurs (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_ms_period BIGINT UNSIGNED NOT NULL,
    rata_rata_kurs DECIMAL(18,4) NOT NULL,
    sumber       VARCHAR(100)    NOT NULL DEFAULT 'JISDOR Bank Indonesia',
    keterangan   VARCHAR(255)    NULL,
    input_by     BIGINT UNSIGNED NULL,
    input_at     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_kurs_period (id_ms_period),
    KEY idx_ms_kurs_user (input_by),
    CONSTRAINT fk_ms_kurs_period FOREIGN KEY (id_ms_period)
        REFERENCES ms_period (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ms_kurs_user FOREIGN KEY (input_by)
        REFERENCES app_users (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Kurs per periode (sumber JISDOR Bank Indonesia)';

CREATE TABLE IF NOT EXISTS ms_manual_correction (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kolom_sumber  VARCHAR(60)     NOT NULL,
    nilai_sumber  VARCHAR(150)    NOT NULL,
    nilai_koreksi VARCHAR(150)    NOT NULL,
    deskripsi     VARCHAR(255)    NULL,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    created_by    BIGINT UNSIGNED NULL,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ms_correction (kolom_sumber, nilai_sumber),
    KEY idx_ms_correction_by (created_by),
    CONSTRAINT fk_ms_correction_user FOREIGN KEY (created_by)
        REFERENCES app_users (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Koreksi master manual (mis. kekerangan)';

-- ============================================================================
-- 4) STAGING / RAW (BPS)
-- ============================================================================

CREATE TABLE IF NOT EXISTS bps_upload (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    exim_type     ENUM('ekspor','impor') NOT NULL,
    id_ms_period  BIGINT UNSIGNED NULL,
    periode_mulai BIGINT UNSIGNED NULL,
    periode_akhir BIGINT UNSIGNED NULL,
    nama_file     VARCHAR(255)    NOT NULL,
    file_path     VARCHAR(1000)   NULL,
    file_hash     CHAR(64)        NOT NULL,
    row_count     INT UNSIGNED    NULL,
    status        ENUM('uploaded','validating','valid','invalid_partial','processed','failed') NOT NULL DEFAULT 'uploaded',
    error_summary TEXT            NULL,
    uploaded_by   BIGINT UNSIGNED NULL,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_bps_upload_hash (file_hash),
    KEY idx_bps_upload_period_type (id_ms_period, exim_type),
    KEY idx_bps_upload_user (uploaded_by),
    CONSTRAINT fk_bps_upload_period FOREIGN KEY (id_ms_period)
        REFERENCES ms_period (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_upload_periode_mulai FOREIGN KEY (periode_mulai)
        REFERENCES ms_period (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_upload_periode_akhir FOREIGN KEY (periode_akhir)
        REFERENCES ms_period (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_upload_user FOREIGN KEY (uploaded_by)
        REFERENCES app_users (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tracking upload file BPS (anti-duplikat via file hash)';

CREATE TABLE IF NOT EXISTS bps_export_raw (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_bps_upload    BIGINT UNSIGNED NOT NULL,
    line_no          INT UNSIGNED    NOT NULL,
    tahun            VARCHAR(4)      NULL,
    bulan            VARCHAR(2)      NULL,
    hscode           VARCHAR(10)     NULL,
    kd_provinsi_asal VARCHAR(10)     NULL,
    kd_provinsi_muat VARCHAR(10)     NULL,
    kd_pelabuhan_muat VARCHAR(10)    NULL,
    nm_pelabuhan_muat VARCHAR(150)   NULL,
    kd_negara        VARCHAR(10)     NULL,
    nm_negara_tujuan VARCHAR(150)    NULL,
    volume_kg        VARCHAR(30)     NULL,
    nilai_usd        VARCHAR(30)     NULL,
    row_checksum     CHAR(64)        NULL,
    is_valid         TINYINT(1)      NOT NULL DEFAULT 0,
    validation_error TEXT            NULL,
    created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_bps_export_raw_upload_line (id_bps_upload, line_no),
    KEY idx_bps_export_raw_period (tahun, bulan),
    CONSTRAINT fk_bps_export_raw_upload FOREIGN KEY (id_bps_upload)
        REFERENCES bps_upload (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Staging baris mentah BPS ekspor (fidelity penuh, text)';

CREATE TABLE IF NOT EXISTS bps_import_raw (
    id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_bps_upload      BIGINT UNSIGNED NOT NULL,
    line_no            INT UNSIGNED    NOT NULL,
    tahun              VARCHAR(4)      NULL,
    bulan              VARCHAR(2)      NULL,
    hscode             VARCHAR(10)     NULL,
    kd_provinsi_bongkar VARCHAR(10)    NULL,
    kd_pelabuhan_bongkar VARCHAR(10)   NULL,
    nm_pelabuhan_bongkar VARCHAR(150)  NULL,
    kd_negara_asal     VARCHAR(10)     NULL,
    nm_negara_asal     VARCHAR(150)    NULL,
    volume_kg          VARCHAR(30)     NULL,
    nilai_usd          VARCHAR(30)     NULL,
    row_checksum       CHAR(64)        NULL,
    is_valid           TINYINT(1)      NOT NULL DEFAULT 0,
    validation_error   TEXT            NULL,
    created_at         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_bps_import_raw_upload_line (id_bps_upload, line_no),
    KEY idx_bps_import_raw_period (tahun, bulan),
    CONSTRAINT fk_bps_import_raw_upload FOREIGN KEY (id_bps_upload)
        REFERENCES bps_upload (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Staging baris mentah BPS impor (fidelity penuh, text)';

-- ============================================================================
-- 5) FACT / PROCESSED (BPS)
-- ============================================================================

CREATE TABLE IF NOT EXISTS bps_export (
    id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_ms_period       BIGINT UNSIGNED NOT NULL,
    id_ms_hscode       BIGINT UNSIGNED NOT NULL,
    kode_hs            VARCHAR(10)     NOT NULL,
    kode_provinsi_asal BIGINT UNSIGNED NOT NULL,
    kode_provinsi_muat BIGINT UNSIGNED NOT NULL,
    kode_pelabuhan_muat BIGINT UNSIGNED NOT NULL,
    kode_negara        BIGINT UNSIGNED NOT NULL,
    volume_kg          DECIMAL(20,4)   NOT NULL,
    nilai_usd          DECIMAL(20,4)   NOT NULL,
    id_bps_export_raw  BIGINT UNSIGNED NULL,
    created_at         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_bps_export_grain
        (id_ms_period, id_ms_hscode, kode_provinsi_asal, kode_provinsi_muat,
         kode_pelabuhan_muat, kode_negara, volume_kg, nilai_usd),
    KEY idx_bps_export_negara (kode_negara),
    KEY idx_bps_export_provinsi (kode_provinsi_asal),
    KEY idx_bps_export_hscode (id_ms_hscode),
    CONSTRAINT fk_bps_export_period FOREIGN KEY (id_ms_period)
        REFERENCES ms_period (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_export_hscode FOREIGN KEY (id_ms_hscode)
        REFERENCES ms_hscode (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_export_prov_asal FOREIGN KEY (kode_provinsi_asal)
        REFERENCES ms_provinsi (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_export_prov_muat FOREIGN KEY (kode_provinsi_muat)
        REFERENCES ms_provinsi (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_export_pel FOREIGN KEY (kode_pelabuhan_muat)
        REFERENCES ms_pelabuhan (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_export_negara FOREIGN KEY (kode_negara)
        REFERENCES ms_negara (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_export_raw FOREIGN KEY (id_bps_export_raw)
        REFERENCES bps_export_raw (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Fakt ekspor BPS terproses (grain = periode+HS+prov+pel+negara+vol+nilai)';

CREATE TABLE IF NOT EXISTS bps_import (
    id                       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_ms_period             BIGINT UNSIGNED NOT NULL,
    id_ms_hscode             BIGINT UNSIGNED NOT NULL,
    kode_hs                  VARCHAR(10)     NOT NULL,
    kode_provinsi_bongkar    BIGINT UNSIGNED NOT NULL,
    kode_pelabuhan_bongkar   BIGINT UNSIGNED NOT NULL,
    kode_negara_asal         BIGINT UNSIGNED NOT NULL,
    volume_kg                DECIMAL(20,4)   NOT NULL,
    nilai_usd                DECIMAL(20,4)   NOT NULL,
    id_bps_import_raw        BIGINT UNSIGNED NULL,
    created_at               TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_bps_import_grain
        (id_ms_period, id_ms_hscode, kode_provinsi_bongkar,
         kode_pelabuhan_bongkar, kode_negara_asal, volume_kg, nilai_usd),
    KEY idx_bps_import_negara (kode_negara_asal),
    KEY idx_bps_import_provinsi (kode_provinsi_bongkar),
    KEY idx_bps_import_hscode (id_ms_hscode),
    CONSTRAINT fk_bps_import_period FOREIGN KEY (id_ms_period)
        REFERENCES ms_period (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_import_hscode FOREIGN KEY (id_ms_hscode)
        REFERENCES ms_hscode (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_import_prov FOREIGN KEY (kode_provinsi_bongkar)
        REFERENCES ms_provinsi (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_import_pel FOREIGN KEY (kode_pelabuhan_bongkar)
        REFERENCES ms_pelabuhan (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_import_negara FOREIGN KEY (kode_negara_asal)
        REFERENCES ms_negara (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_bps_import_raw FOREIGN KEY (id_bps_import_raw)
        REFERENCES bps_import_raw (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Fakt impor BPS terproses';

-- ============================================================================
-- 6) AUTOMATION / JOB
-- ============================================================================

CREATE TABLE IF NOT EXISTS automation_jobs (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    job_type       VARCHAR(50)     NOT NULL,
    id_ms_period   BIGINT UNSIGNED NULL,
    status         ENUM('PENDING','RUNNING','SUCCESS','FAILED','RETRYING','CANCELLED') NOT NULL DEFAULT 'PENDING',
    params_json    JSON            NULL,
    error_message  TEXT            NULL,
    attempts       INT UNSIGNED    NOT NULL DEFAULT 0,
    max_retry      INT UNSIGNED    NOT NULL DEFAULT 3,
    correlation_id VARCHAR(64)     NOT NULL,
    scheduled_at   TIMESTAMP       NULL,
    started_at     TIMESTAMP       NULL,
    finished_at    TIMESTAMP       NULL,
    created_by     BIGINT UNSIGNED NULL,
    created_at     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_automation_jobs_corr (correlation_id),
    KEY idx_automation_jobs_status (status, scheduled_at),
    KEY idx_automation_jobs_type (job_type, status),
    CONSTRAINT fk_automation_jobs_period FOREIGN KEY (id_ms_period)
        REFERENCES ms_period (id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_automation_jobs_user FOREIGN KEY (created_by)
        REFERENCES app_users (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Job antrian automation (BPS, RAW EXIM, TradeMap, PPT)';

CREATE TABLE IF NOT EXISTS automation_job_items (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_job        BIGINT UNSIGNED NOT NULL,
    item_key      VARCHAR(255)    NOT NULL,
    params_json   JSON            NULL,
    status        ENUM('PENDING','RUNNING','SUCCESS','FAILED','RETRYING','CANCELLED') NOT NULL DEFAULT 'PENDING',
    attempts      INT UNSIGNED    NOT NULL DEFAULT 0,
    error_message TEXT            NULL,
    sequence_no   INT UNSIGNED    NULL,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_automation_job_items (id_job, item_key),
    KEY idx_automation_job_items_status (id_job, status),
    CONSTRAINT fk_auto_items_job FOREIGN KEY (id_job)
        REFERENCES automation_jobs (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Item per-job (mis. per negara/komoditas TradeMap)';

CREATE TABLE IF NOT EXISTS automation_job_logs (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_job     BIGINT UNSIGNED NOT NULL,
    id_item    BIGINT UNSIGNED NULL,
    level      ENUM('debug','info','warn','error') NOT NULL DEFAULT 'info',
    message    TEXT            NOT NULL,
    data_json  JSON            NULL,
    created_at TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_auto_logs_job (id_job, created_at),
    KEY idx_auto_logs_item (id_item),
    CONSTRAINT fk_auto_logs_job FOREIGN KEY (id_job)
        REFERENCES automation_jobs (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_auto_logs_item FOREIGN KEY (id_item)
        REFERENCES automation_job_items (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Log proses per job/item (correlation via automation_jobs)';

CREATE TABLE IF NOT EXISTS automation_download_logs (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_job       BIGINT UNSIGNED NULL,
    id_item      BIGINT UNSIGNED NULL,
    sumber       VARCHAR(255)    NOT NULL,
    url          VARCHAR(1000)   NULL,
    file_path    VARCHAR(1000)   NULL,
    file_name    VARCHAR(255)    NULL,
    file_size    BIGINT UNSIGNED NULL,
    file_hash    CHAR(64)        NULL,
    status       ENUM('PENDING','DOWNLOADED','VALIDATED','INVALID','FAILED') NOT NULL DEFAULT 'PENDING',
    error_message TEXT           NULL,
    downloaded_at TIMESTAMP      NULL,
    created_at   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_dl_logs_job (id_job),
    CONSTRAINT fk_dl_logs_job FOREIGN KEY (id_job)
        REFERENCES automation_jobs (id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_dl_logs_item FOREIGN KEY (id_item)
        REFERENCES automation_job_items (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Log unduhan (TradeMap dsb.)';

-- ============================================================================
-- 7) RAW EXIM + TRADEMAP
-- ============================================================================

CREATE TABLE IF NOT EXISTS raw_exim (
    id                        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    exim_type                 ENUM('ekspor','impor') NOT NULL,
    id_ms_period              BIGINT UNSIGNED NOT NULL,
    id_bps_export             BIGINT UNSIGNED NULL,
    id_bps_import             BIGINT UNSIGNED NULL,
    tahun                     SMALLINT UNSIGNED NOT NULL,
    bulan                     TINYINT UNSIGNED NOT NULL,
    kode_hs_2012              VARCHAR(10)     NULL,
    kode_hs_2022              VARCHAR(10)     NOT NULL,
    kode_hs_2dg               VARCHAR(2)      NULL,
    non_konsumsi_konsumsi     VARCHAR(5)      NULL,
    olahan_bukan              VARCHAR(5)      NULL,
    asalbahanbaku             VARCHAR(50)     NULL,
    komoditas_1_2017          VARCHAR(150)    NULL,
    komoditas_2_2017          VARCHAR(150)    NULL,
    komoditas_4_2024          VARCHAR(150)    NULL,
    bentuk_1                  VARCHAR(150)    NULL,
    bentuk_2                  VARCHAR(150)    NULL,
    jenis                     VARCHAR(150)    NULL,
    uraian                    VARCHAR(2000)   NULL,
    uraian_2                  VARCHAR(2000)   NULL,
    kode_prov_asal            VARCHAR(10)     NULL,
    provinsi_asal             VARCHAR(150)    NULL,
    pulau_prov_asal           VARCHAR(50)     NULL,
    kode_pelabuhan_muat       VARCHAR(10)     NULL,
    pelabuhan_muat_bongkar    VARCHAR(150)    NULL,
    kode_provinsi_pelabuhan   VARCHAR(10)     NULL,
    provinsi_pelabuhan        VARCHAR(150)    NULL,
    pulau_prov_pelabuhan      VARCHAR(50)     NULL,
    kode_negara               VARCHAR(10)     NULL,
    negara                    VARCHAR(150)    NULL,
    kelompok_negara           VARCHAR(100)    NULL,
    vol_kg                    DECIMAL(20,4)   NOT NULL,
    nil_usd                   DECIMAL(20,4)   NOT NULL,
    harga_usd_kg              DECIMAL(20,6)   NULL,
    ttc                       VARCHAR(30)     NULL,
    rendemen                  DECIMAL(12,6)   NULL,
    setara_segar              DECIMAL(20,4)   NULL,
    moda                      VARCHAR(20)     NULL,
    koding                    VARCHAR(3)      NULL,
    tahun_bulan               VARCHAR(10)     NULL,
    kurs_usd                  DECIMAL(18,4)   NULL,
    nilai_rp                  DECIMAL(24,2)   NULL,
    asalbahanbaku_2_2026      VARCHAR(50)     NULL,
    komoditas_5_2026          VARCHAR(150)    NULL,
    bentuk_3_2026             VARCHAR(150)    NULL,
    bentuk_4_2026             VARCHAR(150)    NULL,
    jenis_2_2026              VARCHAR(150)    NULL,
    uraian_id_en_2_2026       VARCHAR(2000)   NULL,
    bentuk_5_2026             VARCHAR(150)    NULL,
    status                    ENUM('ready','needs_validation','rejected') NOT NULL DEFAULT 'ready',
    id_generated_by_job       BIGINT UNSIGNED NULL,
    created_at                TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_raw_exim_ekspor_src (id_bps_export),
    UNIQUE KEY uq_raw_exim_impor_src (id_bps_import),
    KEY idx_raw_exim_period_type (id_ms_period, exim_type),
    KEY idx_raw_exim_koding (koding),
    KEY idx_raw_exim_negara (kode_negara),
    KEY idx_raw_exim_komoditas (komoditas_5_2026),
    KEY idx_raw_exim_hs (kode_hs_2022),
    KEY idx_raw_exim_job (id_generated_by_job),
    CONSTRAINT fk_raw_exim_period FOREIGN KEY (id_ms_period)
        REFERENCES ms_period (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_raw_exim_bps_export FOREIGN KEY (id_bps_export)
        REFERENCES bps_export (id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_raw_exim_bps_import FOREIGN KEY (id_bps_import)
        REFERENCES bps_import (id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_raw_exim_job FOREIGN KEY (id_generated_by_job)
        REFERENCES automation_jobs (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAW EXIM (46 kolom, struktur verified)';

CREATE TABLE IF NOT EXISTS trademap_raw (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_download_log  BIGINT UNSIGNED NULL,
    file_path        VARCHAR(1000)   NULL,
    file_hash        CHAR(64)        NULL,
    row_count        INT UNSIGNED    NULL,
    payload_json     JSON            NULL,
    status           ENUM('raw','validated','processed','failed') NOT NULL DEFAULT 'raw',
    validation_error TEXT            NULL,
    created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_trademap_raw_hash (file_hash),
    KEY idx_trademap_raw_dl (id_download_log),
    CONSTRAINT fk_trademap_raw_dl FOREIGN KEY (id_download_log)
        REFERENCES automation_download_logs (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Data mentah TradeMap per file';

CREATE TABLE IF NOT EXISTS trademap_trade (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    reporter        VARCHAR(10)     NOT NULL,
    partner         VARCHAR(10)     NULL,
    flow            VARCHAR(20)     NOT NULL,
    product_code    VARCHAR(20)     NOT NULL,
    product_desc    VARCHAR(500)    NULL,
    year            SMALLINT UNSIGNED NOT NULL,
    qty             DECIMAL(24,4)   NULL,
    qty_unit        VARCHAR(20)     NULL,
    value_usd       DECIMAL(24,4)   NULL,
    id_trademap_raw BIGINT UNSIGNED NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_trademap_trade (reporter, partner, flow, product_code, year, id_trademap_raw),
    KEY idx_trademap_product (product_code, year),
    KEY idx_trademap_partner (partner, year),
    CONSTRAINT fk_trademap_trade_raw FOREIGN KEY (id_trademap_raw)
        REFERENCES trademap_raw (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Data perdagangan TradeMap (ITC) terproses';

-- ============================================================================
-- 8) ANALYTICS + AUDIT
-- ============================================================================

CREATE TABLE IF NOT EXISTS analytics_metric (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    metric_code     VARCHAR(100)    NOT NULL,
    id_ms_period    BIGINT UNSIGNED NULL,
    grain           VARCHAR(30)     NOT NULL,
    dim1_type       VARCHAR(30)     NULL,
    dim1_id         BIGINT UNSIGNED NULL,
    dim1_value      VARCHAR(150)    NULL,
    dim2_type       VARCHAR(30)     NULL,
    dim2_id         BIGINT UNSIGNED NULL,
    dim2_value      VARCHAR(150)    NULL,
    value_usd       DECIMAL(24,4)   NULL,
    value_vol       DECIMAL(24,4)   NULL,
    yoy_value_pct   DECIMAL(9,4)    NULL,
    yoy_vol_pct     DECIMAL(9,4)    NULL,
    contribution_pct DECIMAL(9,4)   NULL,
    id_job          BIGINT UNSIGNED NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_metric_lookup (metric_code, id_ms_period, grain),
    KEY idx_metric_job (id_job),
    CONSTRAINT fk_analytic_period FOREIGN KEY (id_ms_period)
        REFERENCES ms_period (id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_analytic_job FOREIGN KEY (id_job)
        REFERENCES automation_jobs (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Cache snapshot metric analytics (traceable ke job + konfigurasi)';

CREATE TABLE IF NOT EXISTS audit_logs (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    app_user_id    BIGINT UNSIGNED NULL,
    action         VARCHAR(100)    NOT NULL,
    entity         VARCHAR(100)    NOT NULL,
    entity_id      VARCHAR(100)    NULL,
    before_data    JSON            NULL,
    after_data     JSON            NULL,
    ip_address     VARCHAR(45)     NULL,
    user_agent     VARCHAR(255)    NULL,
    correlation_id VARCHAR(64)     NULL,
    created_at     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_audit_entity (entity, entity_id),
    KEY idx_audit_user (app_user_id, created_at),
    CONSTRAINT fk_audit_user FOREIGN KEY (app_user_id)
        REFERENCES app_users (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Audit trail seluruh proses penting';

SET FOREIGN_KEY_CHECKS = 1;
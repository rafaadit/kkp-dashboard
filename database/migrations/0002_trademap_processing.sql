-- ============================================================================
-- PROJECT KKP — MIGRATION 0002
-- PHASE 9 — TRADEMAP DATA PROCESSING & HARMONIZATION
-- ============================================================================
-- Perubahan bersifat ADITIF (tidak menghapus/mengubah kolom lama) agar
-- pipeline PHASE 6 (import_trademap.py) dan data existing tetap kompatibel.
--
--   1. trademap_raw   : metadata sumber + statistik processing + lineage job
--   2. trademap_trade : hasil master mapping, harmonisasi HS, validasi,
--                       normalisasi nilai (nilai asli tetap di `value_usd`)
--   3. trademap_hs_mapping          : interface/versioning mapping HS
--   4. trademap_validation_results  : temuan validasi (source value + reason)
--
-- Catatan: `value_usd` DIPERTAHANKAN apa adanya (nilai sesuai satuan sumber,
-- mis. "US$ Thousand"). Nilai USD ter-normalisasi disimpan di `value_usd_norm`.
-- ============================================================================

-- 1) trademap_raw -----------------------------------------------------------
ALTER TABLE trademap_raw
    ADD COLUMN source           VARCHAR(255)  NULL AFTER id_download_log,
    ADD COLUMN file_name        VARCHAR(255)  NULL AFTER file_path,
    ADD COLUMN file_format      VARCHAR(20)   NULL AFTER file_name,
    ADD COLUMN period_label     VARCHAR(50)   NULL AFTER row_count,
    ADD COLUMN reporter_scope   VARCHAR(50)   NULL AFTER period_label,
    ADD COLUMN partner_scope    VARCHAR(50)   NULL AFTER reporter_scope,
    ADD COLUMN commodity_scope  VARCHAR(150)  NULL AFTER partner_scope,
    ADD COLUMN flow_scope       VARCHAR(20)   NULL AFTER commodity_scope,
    ADD COLUMN id_job           BIGINT UNSIGNED NULL AFTER id_download_log,
    ADD COLUMN total_rows       INT UNSIGNED  NULL,
    ADD COLUMN valid_rows       INT UNSIGNED  NULL,
    ADD COLUMN warning_rows     INT UNSIGNED  NULL,
    ADD COLUMN invalid_rows     INT UNSIGNED  NULL,
    ADD COLUMN duplicate_rows   INT UNSIGNED  NULL,
    ADD COLUMN mapped_rows      INT UNSIGNED  NULL,
    ADD COLUMN unmapped_rows    INT UNSIGNED  NULL,
    ADD COLUMN processed_at     TIMESTAMP     NULL,
    ADD KEY idx_trademap_raw_job (id_job),
    ADD CONSTRAINT fk_trademap_raw_job FOREIGN KEY (id_job)
        REFERENCES automation_jobs (id) ON DELETE SET NULL ON UPDATE CASCADE;

-- 2) trademap_trade ---------------------------------------------------------
ALTER TABLE trademap_trade
    ADD COLUMN id_ms_negara_reporter BIGINT UNSIGNED NULL AFTER partner,
    ADD COLUMN id_ms_negara          BIGINT UNSIGNED NULL AFTER id_ms_negara_reporter,
    ADD COLUMN flow_norm             VARCHAR(20)   NULL AFTER flow,
    ADD COLUMN id_ms_hscode          BIGINT UNSIGNED NULL AFTER product_desc,
    ADD COLUMN id_ms_komoditas       BIGINT UNSIGNED NULL AFTER id_ms_hscode,
    ADD COLUMN hs_version            VARCHAR(20)   NULL AFTER id_ms_komoditas,
    ADD COLUMN hs_mapping_status     ENUM('MAPPED','AMBIGUOUS','HS_MAPPING_REQUIRED','NOT_FOUND','NEEDS_VALIDATION')
                                     NOT NULL DEFAULT 'HS_MAPPING_REQUIRED' AFTER hs_version,
    ADD COLUMN value_unit_source     VARCHAR(50)   NULL AFTER value_usd,
    ADD COLUMN value_usd_norm        DECIMAL(24,4) NULL AFTER value_unit_source,
    ADD COLUMN validation_status     ENUM('VALID','WARNING','INVALID') NOT NULL DEFAULT 'WARNING' AFTER value_usd_norm,
    ADD COLUMN validation_notes      VARCHAR(500)  NULL AFTER validation_status,
    ADD COLUMN row_ref               VARCHAR(100)  NULL AFTER validation_notes,
    ADD KEY idx_trademap_hscode (id_ms_hscode),
    ADD KEY idx_trademap_negara (id_ms_negara),
    ADD KEY idx_trademap_valid (validation_status),
    ADD CONSTRAINT fk_trademap_trade_reporter FOREIGN KEY (id_ms_negara_reporter)
        REFERENCES ms_negara (id) ON DELETE SET NULL ON UPDATE CASCADE,
    ADD CONSTRAINT fk_trademap_trade_negara FOREIGN KEY (id_ms_negara)
        REFERENCES ms_negara (id) ON DELETE SET NULL ON UPDATE CASCADE,
    ADD CONSTRAINT fk_trademap_trade_hscode FOREIGN KEY (id_ms_hscode)
        REFERENCES ms_hscode (id) ON DELETE SET NULL ON UPDATE CASCADE,
    ADD CONSTRAINT fk_trademap_trade_komoditas FOREIGN KEY (id_ms_komoditas)
        REFERENCES ms_komoditas (id) ON DELETE SET NULL ON UPDATE CASCADE;

-- 3) trademap_hs_mapping ----------------------------------------------------
CREATE TABLE IF NOT EXISTS trademap_hs_mapping (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_code      VARCHAR(20)     NOT NULL COMMENT 'HS code dari TradeMap (mis. 6 digit)',
    source_version   VARCHAR(20)     NOT NULL DEFAULT '' COMMENT 'versi HS sumber; "" = belum diketahui',
    ms_hscode_id     BIGINT UNSIGNED NULL COMMENT 'hasil resolusi kanonikal (NULL bila ambigu/belum ada)',
    ms_komoditas_id  BIGINT UNSIGNED NULL COMMENT 'komoditas_5_2026 hasil resolusi',
    mapping_status   ENUM('MAPPED','AMBIGUOUS','HS_MAPPING_REQUIRED','NOT_FOUND','NEEDS_VALIDATION')
                     NOT NULL DEFAULT 'HS_MAPPING_REQUIRED',
    candidate_count  INT UNSIGNED    NOT NULL DEFAULT 0,
    candidates_json  JSON            NULL COMMENT 'daftar kandidat ms_hscode [{id,kode_hs,uraian_en}]',
    notes            VARCHAR(500)    NULL,
    sumber           VARCHAR(100)    NULL,
    created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_trademap_hs_mapping (source_code, source_version),
    KEY idx_trademap_hs_map_status (mapping_status),
    CONSTRAINT fk_thm_hscode FOREIGN KEY (ms_hscode_id)
        REFERENCES ms_hscode (id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_thm_komoditas FOREIGN KEY (ms_komoditas_id)
        REFERENCES ms_komoditas (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Interface harmonisasi/versioning HS TradeMap -> ms_hscode (tanpa mengarang equivalence)';

-- 4) trademap_validation_results -------------------------------------------
CREATE TABLE IF NOT EXISTS trademap_validation_results (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_job         BIGINT UNSIGNED NULL,
    id_trademap_raw BIGINT UNSIGNED NULL,
    row_ref        VARCHAR(100)    NULL COMMENT 'penanda baris sumber (mis. #3 atau reporter|partner|hs)',
    field          VARCHAR(50)     NOT NULL,
    kode           VARCHAR(50)     NULL COMMENT 'kode temuan (mis. COUNTRY_UNMAPPED)',
    source_value   VARCHAR(255)    NULL,
    severity       ENUM('WARNING','INVALID') NOT NULL DEFAULT 'WARNING',
    reason         VARCHAR(500)    NULL,
    recommended    VARCHAR(500)    NULL,
    created_at     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_tvr_job (id_job),
    KEY idx_tvr_raw (id_trademap_raw),
    KEY idx_tvr_sev (severity),
    CONSTRAINT fk_tvr_job FOREIGN KEY (id_job)
        REFERENCES automation_jobs (id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_tvr_raw FOREIGN KEY (id_trademap_raw)
        REFERENCES trademap_raw (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Hasil validasi TradeMap per field (lineage: source value + reason + rekomendasi)';

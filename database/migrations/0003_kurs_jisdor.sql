-- ============================================================================
-- PROJECT KKP — MIGRATION 0003
-- PHASE 9c — KURS JISDOR BANK INDONESIA (AUTOMATION)
-- ============================================================================
-- Menampung data HARIAN JISDOR (USD/IDR) yang diambil otomatis dari web
-- service resmi BI (wskursbi.asmx, getSubKursJisdor3). Rata-rata bulanan
-- diagregasi ke ms_kurs (rata_rata_kurs, sumber 'JISDOR Bank Indonesia')
-- untuk perhitungan raw_exim.kurs_usd / nilai_rp.
--
-- Aditif; tidak mengubah kolom lama.
-- ============================================================================

CREATE TABLE IF NOT EXISTS jisdor_daily (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    tanggal         DATE            NOT NULL,
    mata_uang       VARCHAR(8)      NOT NULL DEFAULT 'USD',
    kurs            DECIMAL(18,4)   NOT NULL,
    sumber          VARCHAR(100)    NOT NULL,
    id_download_log BIGINT UNSIGNED NULL,
    downloaded_at   TIMESTAMP       NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_jisdor_daily (tanggal, mata_uang),
    KEY idx_jisdor_tanggal (tanggal),
    CONSTRAINT fk_jisdor_download FOREIGN KEY (id_download_log)
        REFERENCES automation_download_logs (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Kurs harian JISDOR USD/IDR dari web service Bank Indonesia (getSubKursJisdor3)';
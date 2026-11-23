-- Percepat filter & agregasi endpoint /api/explore/* pada raw_exim.
-- Filter selalu memakai exim_type, sering memakai rentang (tahun, bulan),
-- dan halaman potensi mengelompokkan per negara/komoditas.
-- Index covering menghindari full table scan 200+ ribu baris.
-- Aman dijalankan berulang (idempoten) pada database yang sudah berisi data.

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
               AND INDEX_NAME = 'idx_raw_exim_exim_tahun_bulan');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_exim_tahun_bulan (exim_type, tahun, bulan)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
               AND INDEX_NAME = 'idx_raw_exim_overview_cover');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_overview_cover (exim_type, tahun, bulan, vol_kg, nil_usd, setara_segar, kode_hs_2022, kode_negara)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
               AND INDEX_NAME = 'idx_raw_exim_eksim_komoditas');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_eksim_komoditas (exim_type, komoditas_5_2026, nil_usd, vol_kg)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
               AND INDEX_NAME = 'idx_raw_exim_eksim_negara');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_eksim_negara (exim_type, kode_negara, negara, kelompok_negara, nil_usd, vol_kg)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
               AND INDEX_NAME = 'idx_raw_exim_eksim_koding');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_eksim_koding (exim_type, koding, nil_usd, vol_kg)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
               AND INDEX_NAME = 'idx_raw_exim_eksim_hs');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_eksim_hs (exim_type, kode_hs_2022, nil_usd, vol_kg)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
               AND INDEX_NAME = 'idx_raw_exim_potensi_negara');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_potensi_negara (exim_type, tahun, bulan, kode_negara, negara, nil_usd)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
               AND INDEX_NAME = 'idx_raw_exim_eksim_negara_komoditas');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_eksim_negara_komoditas (exim_type, kode_negara, komoditas_5_2026, tahun, bulan, nil_usd)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Agregasi top komoditas / provinsi / pelabuhan butuh Group By + SUM langsung
-- dari index (covering), supaya tidak menyentuh 200+ ribu baris tabel.

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
                AND INDEX_NAME = 'idx_raw_exim_top_komoditas');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_top_komoditas (exim_type, komoditas_5_2026, komoditas_2_2017, kode_hs_2022, vol_kg, nil_usd)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
                AND INDEX_NAME = 'idx_raw_exim_top_provinsi');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_top_provinsi (exim_type, provinsi_asal, kode_hs_2022, vol_kg, nil_usd, setara_segar)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
                AND INDEX_NAME = 'idx_raw_exim_top_pelabuhan');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_top_pelabuhan (exim_type, provinsi_pelabuhan, kode_hs_2022, vol_kg, nil_usd, setara_segar)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
                AND INDEX_NAME = 'idx_raw_exim_compare_cover');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_compare_cover (exim_type, kode_negara, tahun, bulan, negara, kelompok_negara, kode_hs_2022, vol_kg, nil_usd, setara_segar)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- country_compare: COUNT(DISTINCT kode_hs_2022) per grup butuh kode_hs
-- berurutan setelah kode_negara/negara/kelompok, dan top komoditas butuh
-- vol_kg + nil_usd di dalam index yang sama.

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
                AND INDEX_NAME = 'idx_raw_exim_compare_hs');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_compare_hs (exim_type, kode_negara, negara, kelompok_negara, kode_hs_2022, vol_kg, nil_usd, setara_segar)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'raw_exim'
                AND INDEX_NAME = 'idx_raw_exim_compare_komoditas');
SET @sql := IF(@idx = 0, 'ALTER TABLE raw_exim ADD INDEX idx_raw_exim_compare_komoditas (exim_type, kode_negara, komoditas_5_2026, vol_kg, nil_usd)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

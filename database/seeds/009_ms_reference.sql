-- ==================================================================
-- ms_reference: konfigurasi & catatan temuan audit; status needs_validation untuk nilai belum resmi.
-- Idempotent (INSERT IGNORE).
-- ==================================================================
USE kkp_exim_platform;

INSERT IGNORE INTO ms_reference (ref_group, ref_key, ref_value, deskripsi, sumber, status) VALUES
('pipeline', 'upload_status_flow', 'uploaded -> validating -> valid -> processed', 'Alur status upload BPS (spec pipeline).', 'PHASE1 design', 'validated'),
('raw_exim', 'setara_segar', 'vol_kg / rendemen', 'Verified 4114/4114 baris Juni 2026 (bukan vol*rendemen).', 'audit RAW EXIM', 'validated'),
('raw_exim', 'harga', 'nil_usd / vol_kg', 'Verified 0 mismatch pada file Juni 2026.', 'audit RAW EXIM', 'validated'),
('raw_exim', 'kurs_juni_2026', '358482 (KONSTAN, bukan kurs riil)', 'Temuan audit: nilai mirip ''placeholder'', bukan kurs JISDOR (~15800).', 'audit RAW EXIM', 'needs_validation'),
('raw_exim', 'nilai_rp', 'nil_usd * kurs_usd', 'Formula mengikuti file; akurasi tergantung sumber kurs.', 'audit RAW EXIM', 'needs_validation'),
('raw_exim', 'moda_inkonsisten', 'Moda sangat tergantung master_pelabuhan; 10/58 pelabuhan punya 2 moda, 2 sel #N/A', 'Temuan audit: cek master pelabuhan saat pipeline.', 'audit RAW EXIM', 'needs_validation'),
('raw_exim', 'kolom_null_510', '510 baris EXIM & KELOMPOK NEGARA NULL (komoditas non-inti)', 'Temuan audit: artefak batch terpisah, kode negara tersedia di master.', 'audit RAW EXIM', 'needs_validation'),
('raw_exim', 'timor_leste_2026', 'EAST TIMOR -> Asean (ms_negara masih ''Lainnya'')', 'TL resmi anggota ASEAN 2025; master belum ter-update.', 'audit RAW EXIM', 'needs_validation'),
('raw_exim', 'kode_hs_2012', 'KOSONG di seluruh file ekspor 2026-06', 'Kolom cadangan; tidak dipakai pipeline saat ini.', 'audit RAW EXIM', 'validated'),
('kurs', 'sumber', 'JISDOR Bank Indonesia', 'Tabel ms_kurs adalah sumber kurs per periode.', 'eksim_system legacy + audit', 'validated'),
('analytics', 'market_share', 'NEEDS VALIDATION', 'Formula share ekspor/global belum resmi dikonfirmasi.', NULL, 'needs_validation'),
('analytics', 'potensi_ekspor', 'NEEDS VALIDATION', 'Formula potensi ekspor belum resmi dikonfirmasi.', NULL, 'needs_validation'),
('analytics', 'competitor_analysis', 'NEEDS VALIDATION', 'Formula analisis pesaing belum resmi dikonfirmasi.', NULL, 'needs_validation'),
('analytics', 'import_market', 'NEEDS VALIDATION', 'Formula analisis pasar impor belum resmi dikonfirmasi.', NULL, 'needs_validation'),
('analytics', 'indonesia_share', 'NEEDS VALIDATION', 'Formula Indonesia share (global market) belum resmi dikonfirmasi.', NULL, 'needs_validation'),
('trademap', 'credential_storage', '.env / environment variables', 'Kredensial TIDAK disimpan di database atau source code.', 'security spec', 'validated'),
('trademap', 'login_url', 'NEEDS VALIDATION', 'URL login TradeMap/ITC harus dikonfirmasi.', NULL, 'needs_validation'),
('ppt', 'template', 'Draft_EKSIM_Jan-Juni_2026_06082026 (1).pptx', 'Template resmi eksisting dari audit; angka PPT verified 100%.', 'audit', 'validated'),
('w21', 'definisi', 'TIDAK DITEMUKAN', 'Kode W21 tidak muncul di file/pipeline mana pun.', 'audit open item', 'needs_validation');

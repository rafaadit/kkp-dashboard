-- ==================================================================
-- app_roles / app_permissions / app_role_permissions.
-- Matriks: super_admin = semua; pegawai = user + operasional; user = lihat/explore + AI.
-- User awal (bootstrap) TIDAK di-seed di sini; dibuat via script dari .env (anti plaintext password).
-- Idempotent (INSERT IGNORE).
-- ==================================================================
USE kkp_exim_platform;

INSERT IGNORE INTO app_roles (kode, nama, deskripsi) VALUES
('user', 'User', 'Pengguna platform: melihat/menggunakan fitur'),
('pegawai', 'Pegawai', 'Pengguna + update BPS, validasi, generate PPT, jalankan proses TradeMap'),
('super_admin', 'Super Admin', 'Seluruh permission + administrasi sistem');

INSERT IGNORE INTO app_permissions (kode, nama, grup) VALUES
('explore.view', 'Lihat Overview & Market Intelligence', 'EXPLORE'),
('explore.commodity', 'Lihat analisis komoditas', 'EXPLORE'),
('explore.country', 'Lihat analisis negara', 'EXPLORE'),
('explore.comparison', 'Lihat perbandingan', 'EXPLORE'),
('explore.opportunity', 'Lihat peluang pasar', 'EXPLORE'),
('explore.competition', 'Lihat persaingan', 'EXPLORE'),
('data.view', 'Lihat data BPS/RAW EXIM', 'DATA'),
('data.update_bps_export', 'Update data BPS ekspor', 'DATA'),
('data.update_bps_import', 'Update data BPS impor', 'DATA'),
('data.validate', 'Jalankan validasi data', 'DATA'),
('exim.view', 'Lihat RAW EXIM', 'DATA'),
('exim.generate', 'Generate RAW EXIM', 'DATA'),
('trademap.view', 'Lihat data TradeMap', 'TRADEMAP'),
('trademap.download', 'Jalankan unduhan TradeMap', 'TRADEMAP'),
('trademap.process', 'Proses data TradeMap', 'TRADEMAP'),
('report.view', 'Lihat laporan/PPT', 'REPORT'),
('report.generate_ppt', 'Generate PPT otomatis', 'REPORT'),
('report.templates', 'Kelola template PPT', 'REPORT'),
('ai.use', 'Gunakan AI Assistant', 'AI'),
('system.profile', 'Atur profil sendiri', 'SYSTEM'),
('system.notifications', 'Baca notifikasi', 'SYSTEM'),
('system.audit', 'Lihat audit log', 'SYSTEM'),
('admin.users', 'Kelola pengguna', 'ADMIN'),
('admin.roles', 'Kelola role/permission', 'ADMIN'),
('admin.config', 'Konfigurasi sistem', 'ADMIN'),
('admin.monitor', 'Monitoring seluruh proses', 'ADMIN'),
('jobs.view', 'Lihat status job', 'SYSTEM'),
('jobs.run', 'Menjalankan/membatalkan job', 'SYSTEM');

-- Role -> permissions
INSERT IGNORE INTO app_role_permissions (app_role_id, app_permission_id)
SELECT r.id, p.id FROM app_roles r
JOIN app_permissions p ON p.kode IN ('explore.view', 'explore.commodity', 'explore.country', 'explore.comparison', 'explore.opportunity', 'explore.competition', 'data.view', 'exim.view', 'trademap.view', 'report.view', 'ai.use', 'system.profile', 'system.notifications')
WHERE r.kode = 'user';

INSERT IGNORE INTO app_role_permissions (app_role_id, app_permission_id)
SELECT r.id, p.id FROM app_roles r
JOIN app_permissions p ON p.kode IN ('explore.view', 'explore.commodity', 'explore.country', 'explore.comparison', 'explore.opportunity', 'explore.competition', 'data.view', 'exim.view', 'trademap.view', 'report.view', 'ai.use', 'system.profile', 'system.notifications', 'data.update_bps_export', 'data.update_bps_import', 'data.validate', 'exim.generate', 'trademap.download', 'trademap.process', 'report.generate_ppt', 'report.templates', 'jobs.view', 'jobs.run')
WHERE r.kode = 'pegawai';

INSERT IGNORE INTO app_role_permissions (app_role_id, app_permission_id)
SELECT r.id, p.id FROM app_roles r
JOIN app_permissions p ON p.kode IN ('explore.view', 'explore.commodity', 'explore.country', 'explore.comparison', 'explore.opportunity', 'explore.competition', 'data.view', 'data.update_bps_export', 'data.update_bps_import', 'data.validate', 'exim.view', 'exim.generate', 'trademap.view', 'trademap.download', 'trademap.process', 'report.view', 'report.generate_ppt', 'report.templates', 'ai.use', 'system.profile', 'system.notifications', 'system.audit', 'admin.users', 'admin.roles', 'admin.config', 'admin.monitor', 'jobs.view', 'jobs.run')
WHERE r.kode = 'super_admin';


-- ==================================================================
-- ms_unit: 7 satuan dasar.
-- Idempotent (INSERT IGNORE).
-- ==================================================================
USE kkp_exim_platform;

INSERT IGNORE INTO ms_unit (kode, nama, simbol, deskripsi) VALUES
('KG', 'Kilogram', 'kg', 'Berat/kuantitas'),
('TON', 'Ton', 'ton', 'Berat (1e3 kg)'),
('USD', 'US Dollar', 'USD', 'Nilai ekspor/impor'),
('IDR', 'Rupiah', 'Rp', 'Nilai konversi rupiah'),
('USD_KG', 'USD per KG', 'USD/kg', 'Harga unit'),
('PCT', 'Persen', '%', 'Proporsi / pertumbuhan'),
('QTY', 'Quantity', 'unit', 'Kuantitas item TradeMap');

-- ==================================================================
-- ms_kurs: kurs per periode dari file RAW EXIM (referensi verifikasi).
-- Nilai KONSTAN 358482 = placeholder, bukan JISDOR; status needs_validation.
-- Idempotent (INSERT IGNORE).
-- ==================================================================
USE kkp_exim_platform;

INSERT IGNORE INTO ms_kurs (id_ms_period, rata_rata_kurs, sumber, keterangan)
SELECT p.id, s.kurs, 'referensi file RAW EXIM (placeholder)',
       'KONSTAN dari file referensi; BUKAN kurs JISDOR riil; NEEDS VALIDATION'
FROM (
  SELECT * FROM (VALUES
ROW(2026, 6, 358482)
  ) AS v(tahun, bulan, kurs)
) s
JOIN ms_period p ON p.tahun = s.tahun AND p.bulan = s.bulan;

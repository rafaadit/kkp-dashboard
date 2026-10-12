-- ==================================================================
-- ms_kurs: rata-rata bulanan kurs USD/IDR (JISDOR Bank Indonesia).
-- Sumber: web service resmi BI (wskursbi.asmx, getSubKursJisdor3).
-- Nilai riil hasil robot database/scripts/download_jisdor.py (2022-01 .. 2026-06).
-- Idempotent (INSERT IGNORE); sesudah ini raw_exim.kurs_usd/nilai_rp terisi.
-- ==================================================================
USE kkp_exim_platform;

INSERT IGNORE INTO ms_kurs (id_ms_period, rata_rata_kurs, sumber, keterangan)
SELECT p.id, s.kurs, 'JISDOR Bank Indonesia',
       'Rata-rata bulanan JISDOR harian (ws BI otomatis)'
FROM (
  SELECT * FROM (VALUES
ROW(2022, 1, 14340.6667),
ROW(2022, 2, 14349.7778),
ROW(2022, 3, 14348.0909),
ROW(2022, 4, 14375.2105),
ROW(2022, 5, 14615.4667),
ROW(2022, 6, 14702.381),
ROW(2022, 7, 14983.3333),
ROW(2022, 8, 14850.3182),
ROW(2022, 9, 14989),
ROW(2022, 10, 15434.8095),
ROW(2022, 11, 15665.3636),
ROW(2022, 12, 15608.1818),
ROW(2023, 1, 15266.6667),
ROW(2023, 2, 15138.4),
ROW(2023, 3, 15288.1905),
ROW(2023, 4, 14844.1429),
ROW(2023, 5, 14827.1429),
ROW(2023, 6, 14931.8235),
ROW(2023, 7, 15044.35),
ROW(2023, 8, 15251.7273),
ROW(2023, 9, 15366.7),
ROW(2023, 10, 15759.8636),
ROW(2023, 11, 15598.6364),
ROW(2023, 12, 15511),
ROW(2024, 1, 15627.3636),
ROW(2024, 2, 15660.4444),
ROW(2024, 3, 15711.3889),
ROW(2024, 4, 16125.1875),
ROW(2024, 5, 16082.5556),
ROW(2024, 6, 16337.3333),
ROW(2024, 7, 16257.3043),
ROW(2024, 8, 15755.8636),
ROW(2024, 9, 15324.8),
ROW(2024, 10, 15565.7391),
ROW(2024, 11, 15819.9),
ROW(2024, 12, 16038.55),
ROW(2025, 1, 16270.1579),
ROW(2025, 2, 16351.05),
ROW(2025, 3, 16455.6842),
ROW(2025, 4, 16827.0625),
ROW(2025, 5, 16418.4118),
ROW(2025, 6, 16306.7222),
ROW(2025, 7, 16286.3478),
ROW(2025, 8, 16308.9),
ROW(2025, 9, 16523.1905),
ROW(2025, 10, 16604.4348),
ROW(2025, 11, 16704.85),
ROW(2025, 12, 16702.0476),
ROW(2026, 1, 16836.4444),
ROW(2026, 2, 16824.7222),
ROW(2026, 3, 16914.9333),
ROW(2026, 4, 17138.5789),
ROW(2026, 5, 17556.8),
ROW(2026, 6, 17929.2778)
  ) AS v(tahun, bulan, kurs)
) s
JOIN ms_period p ON p.tahun = s.tahun AND p.bulan = s.bulan;

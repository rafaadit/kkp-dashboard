<?php

declare(strict_types=1);

namespace KKP;

/** Renderer view sederhana (layout + partial). */
final class View
{
    private static string $viewDir = BASE_PATH . '/views';

    public static function render(string $name, array $vars): void
    {
        $file = self::$viewDir . "/{$name}.php";
        if (!is_file($file)) {
            http_response_code(500);
            echo "View tidak ditemukan: {$name}";
            return;
        }
        $vars['__name__'] = $name;
        extract($vars, EXTR_SKIP);
        require self::$viewDir . '/layout/header.php';
        require $file;
        require self::$viewDir . '/layout/footer.php';
    }

    public static function renderPartial(string $name, array $vars): void
    {
        $file = self::$viewDir . "/{$name}.php";
        if (!is_file($file)) {
            return;
        }
        extract($vars, EXTR_SKIP);
        require $file;
    }

    public static function e(mixed $v): string
    {
        return htmlspecialchars((string) ($v ?? ''), ENT_QUOTES, 'UTF-8');
    }

    public static function num(mixed $v, int $dec = 0): string
    {
        return is_numeric($v) ? number_format((float) $v, $dec) : (string) ($v ?? '');
    }

    /** Format ringkas angka besar (K/M/B/T) untuk KPI hero. */
    public static function compact(mixed $v, int $dec = 2): string
    {
        if (!is_numeric($v)) {
            return (string) ($v ?? '');
        }
        $n = (float) $v;
        $abs = abs($n);
        if ($abs >= 1e12) { return number_format($n / 1e12, $dec) . ' T'; }
        if ($abs >= 1e9) { return number_format($n / 1e9, $dec) . ' B'; }
        if ($abs >= 1e6) { return number_format($n / 1e6, $dec) . ' M'; }
        if ($abs >= 1e3) { return number_format($n / 1e3, 1) . ' K'; }
        return number_format($n, 0);
    }

    /** Nama bulan Indonesia (1-12). */
    public static function bulan(int $m): string
    {
        $nama = [1 => 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
        return $nama[$m] ?? (string) $m;
    }
}
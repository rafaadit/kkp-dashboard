<?php

declare(strict_types=1);

namespace KKP;

/** Renderer view sederhana (layout + partial). */
final class View
{
    private static string $viewDir = BASE_PATH . '/views';

    /** Prefix URL aplikasi; diisi bootstrap dari Config::$baseUrl. */
    private static string $baseUrl = '';

    public static function setBaseUrl(string $base): void
    {
        self::$baseUrl = rtrim($base, '/');
    }

    /** URL internal aplikasi (sudah termasuk prefix base). */
    public static function url(string $path = '/'): string
    {
        if ($path === '' || $path === '/') {
            return self::$baseUrl === '' ? '/' : self::$baseUrl . '/';
        }
        return self::$baseUrl . '/' . ltrim($path, '/');
    }

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

        ob_start();
        try {
            require self::$viewDir . '/layout/header.php';
            require $file;
            require self::$viewDir . '/layout/footer.php';
        } catch (\Throwable $e) {
            ob_end_clean();
            throw $e;
        }
        echo self::prefixUrls((string) ob_get_clean());
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

    /**
     * Beri prefix base pada URL internal yang ditulis absolut (href/src/action
     * dan string fetch/location di JS). Dengan begitu seluruh view tetap memakai
     * path root ('/login', '/assets/app.css', ...) baik saat di-deploy di root
     * maupun di subdirectory seperti /tarbhak/frontend/public/.
     */
    private static function prefixUrls(string $html): string
    {
        if (self::$baseUrl === '' || $html === '') {
            return $html;
        }
        $base = self::$baseUrl;

        $html = preg_replace_callback(
            '/\b(href|src|action|poster)\s*=\s*"(\/[^"]*)"/i',
            static fn(array $m): string => $m[1] . '="' . $base . $m[2] . '"',
            $html
        ) ?? $html;

        $html = preg_replace_callback(
            '/(\bfetch\s*\(\s*|\.href\s*=\s*|\.location\s*=\s*|window\.open\s*\(\s*)([\'"])(\/[^\'"]*)\2/i',
            static fn(array $m): string => $m[1] . $m[2] . $base . $m[3] . $m[2],
            $html
        ) ?? $html;

        return $html;
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

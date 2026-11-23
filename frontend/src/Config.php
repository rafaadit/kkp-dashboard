<?php

declare(strict_types=1);

namespace KKP;

/** Konfigurasi frontend: dibaca dari .env.local (→ env variabel / default). */
final class Config
{
    public string $apiBaseUrl;
    public string $appName;

    /** Prefix URL aplikasi, tanpa trailing slash. '' bila dipasang di root domain. */
    public string $baseUrl;

    private function __construct(string $apiBaseUrl, string $appName, string $baseUrl)
    {
        $this->apiBaseUrl = rtrim($apiBaseUrl, '/');
        $this->appName = $appName;
        $this->baseUrl = $baseUrl;
    }

    public static function load(string $envPath = '', ?string $fallbackBaseUrl = null): self
    {
        $map = [];
        if ($envPath && is_file($envPath)) {
            foreach (file($envPath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
                $line = trim($line);
                if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) {
                    continue;
                }
                [$k, $v] = explode('=', $line, 2);
                $map[trim($k)] = trim($v, " \t\"'");
            }
        }
        $api = $map['API_BASE_URL'] ?? getenv('API_BASE_URL');

        // BASE_URL di .env.local menang; bila kosong pakai deteksi otomatis
        // dari lokasi folder public (mis. /tarbhak/frontend/public).
        $base = $map['BASE_URL'] ?? getenv('BASE_URL');
        if ($base === false || trim((string) $base) === '') {
            $base = $fallbackBaseUrl;
        }

        return new self(
            $api ?: 'http://127.0.0.1:8000',
            $map['APP_NAME'] ?? 'KKP EXIM Platform',
            self::normalizeBaseUrl((string) $base)
        );
    }

    private static function normalizeBaseUrl(string $base): string
    {
        $base = trim($base);
        if ($base === '' || $base === '/') {
            return '';
        }
        // Izinkan juga BASE_URL ditulis sebagai URL penuh; yang dipakai hanya path-nya.
        if (preg_match('#^https?://#i', $base)) {
            $base = (string) (parse_url($base, PHP_URL_PATH) ?: '');
        }
        if ($base === '' || $base === '/') {
            return '';
        }
        if (!str_starts_with($base, '/')) {
            $base = '/' . $base;
        }
        return rtrim($base, '/');
    }

    /** URL internal aplikasi (sudah termasuk prefix base). */
    public function url(string $path = '/'): string
    {
        if ($path === '' || $path === '/') {
            return $this->baseUrl === '' ? '/' : $this->baseUrl . '/';
        }
        return $this->baseUrl . '/' . ltrim($path, '/');
    }
}

<?php

declare(strict_types=1);

namespace KKP;

/** Konfigurasi frontend: dibaca dari .env.local (→ env variabel / default). */
final class Config
{
    public string $apiBaseUrl;
    public string $appName;

    private function __construct(string $apiBaseUrl, string $appName)
    {
        $this->apiBaseUrl = rtrim($apiBaseUrl, '/');
        $this->appName = $appName;
    }

    public static function load(string $envPath = ''): self
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
        return new self(
            $api ?: 'http://127.0.0.1:8000',
            $map['APP_NAME'] ?? 'KKP EXIM Platform'
        );
    }
}
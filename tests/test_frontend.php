#!/usr/bin/env php
<?php
/**
 * PHASE 5 — Smoke test frontend PHP Native (wajib API :8000 jalan + user admin ada).
 * Usage: php tests/test_frontend.php
 */
declare(strict_types=1);

$base = 'http://127.0.0.1:8080';
$ok = 0;
$fail = 0;

function check(string $name, bool $cond, string $detail = ''): void
{
    global $ok, $fail;
    if ($cond) {
        $ok++;
        echo "  PASS  $name\n";
    } else {
        $fail++;
        echo "  FAIL  $name  $detail\n";
    }
}

function http(string $method, string $url, ?string $body = null, string $cookieFile = '/tmp/kkp_t.csv'): array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_COOKIEFILE => $cookieFile,
        CURLOPT_COOKIEJAR => $cookieFile,
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_TIMEOUT => 20,
    ]);
    if ($body !== null) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
    }
    $resp = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    $redirect = (string) curl_getinfo($ch, CURLINFO_REDIRECT_URL);
    return [$code, (string) $resp, $redirect];
}

$cookie = sys_get_temp_dir() . '/kkp_fe_test_' . getmypid() . '.txt';
@unlink($cookie);
$cookiefn = $cookie;

echo "== auth ==";
[$c, , $r] = http('GET', "$base/dashboard", null, $cookiefn);
check('dashboard tanpa login -> 302 ke /login', $c === 302 && str_contains($r, '/login'), "$c $r");

[$c, $body] = http('POST', "$base/login", 'email=admin@kkp.local&password=admin123', $cookiefn);
check('login benar -> 302 ke /', $c === 302 && str_contains($body, '/login') === false, "$c");

[$c, $body] = http('POST', "$base/login", 'email=admin@kkp.local&password=wrong', '/tmp/kkp_bad_' . getmypid() . '.txt');
check('login salah -> 401', $c === 401, "$c");

echo "== pages ==";
foreach ([
    '/' => '<h1>Dashboard Ekspor/Impor</h1>',
    '/komoditas' => '<h1>Analisis Komoditas</h1>',
    '/negara' => '<h1>Analisis Negara</h1>',
    '/trademap' => '<h1>TradeMap (ITC)</h1>',
    '/laporan' => '<h1>Laporan PPT</h1>',
    '/asisten' => '<h1>Asisten AI</h1>',
    '/perbandingan' => '<h1>Perbandingan Periode</h1>',
    '/data?limit=5' => '<h1>Data RAW EXIM</h1>',
    '/data?exim=impor&limit=2&status=needs_validation' => 'needs_validation',
] as $path => $needle) {
    [$c, $body] = http('GET', "$base$path", null, $cookiefn);
    check("GET $path -> 200 & konten", $c === 200 && str_contains($body, $needle), "$c " . (str_contains($body, $needle) ? '' : 'konten tak ada'));
}
[$c, $body] = http('GET', "$base/data?limit=5", null, $cookiefn);
check('data menampilkan total baris', str_contains($body, 'Total') && str_contains($body, 'baris'), 'no total');

echo "== logout ==";
[$c, , $r] = http('GET', "$base/logout", null, $cookiefn);
check('logout -> 302 /login', $c === 302 && str_contains($r, '/login'), "$c $r");
[$c] = http('GET', "$base/dashboard", null, $cookiefn);
check('dashboard setelah logout -> redirect', $c === 302, "$c");

@unlink($cookie);
echo "\nRESULT: $ok passed, $fail failed\n";
exit($fail ? 1 : 0);
#!/usr/bin/env php
<?php
/**
 * Regression test: aplikasi jalan baik di root maupun di subdirectory.
 * Usage: php tests/test_base_url.php
 */
declare(strict_types=1);

define('BASE_PATH', dirname(__DIR__) . '/frontend');
require_once BASE_PATH . '/src/Config.php';
require_once BASE_PATH . '/src/View.php';

use KKP\Config;
use KKP\View;

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

$root = Config::load('', '');
check('root base kosong', $root->baseUrl === '', $root->baseUrl);
check('root url /login', $root->url('/login') === '/login', $root->url('/login'));

$sub = Config::load('', '/tarbhak/frontend/public/');
check('subdirectory base normal', $sub->baseUrl === '/tarbhak/frontend/public', $sub->baseUrl);
check('subdirectory url /', $sub->url('/') === '/tarbhak/frontend/public/', $sub->url('/'));
check('subdirectory url /login', $sub->url('/login') === '/tarbhak/frontend/public/login', $sub->url('/login'));

// Deploy live: folder versi baru milik atasan di /tarbhak/v2.
$v2 = Config::load('', '/tarbhak/v2');
check('v2 base normal', $v2->baseUrl === '/tarbhak/v2', $v2->baseUrl);
check('v2 url /', $v2->url('/') === '/tarbhak/v2/', $v2->url('/'));
check('v2 url /login', $v2->url('/login') === '/tarbhak/v2/login', $v2->url('/login'));

View::setBaseUrl($sub->baseUrl);
$method = new ReflectionMethod(View::class, 'prefixUrls');
if (PHP_VERSION_ID < 80100) {
    $method->setAccessible(true);
}
$html = <<<'HTML'
<a href="/login" class="btn">Masuk</a>
<img src="/assets/logo-kkp.png?v=1">
<form action="/data-bps/delete" method="post"></form>
<a href="https://kkp.go.id/">Eksternal</a>
<a href="?page=2">Next</a>
<script>fetch('/data-bps/status?job=1'); window.location.href = '/data-bps?job=1';</script>
HTML;
$out = (string) $method->invoke(null, $html);

check('href diberi prefix', str_contains($out, 'href="/tarbhak/frontend/public/login"'), $out);
check('src diberi prefix', str_contains($out, 'src="/tarbhak/frontend/public/assets/logo-kkp.png?v=1"'), $out);
check('action diberi prefix', str_contains($out, 'action="/tarbhak/frontend/public/data-bps/delete"'), $out);
check('fetch diberi prefix', str_contains($out, "fetch('/tarbhak/frontend/public/data-bps/status?job=1')"), $out);
check('location.href diberi prefix', str_contains($out, "window.location.href = '/tarbhak/frontend/public/data-bps?job=1'"), $out);
check('url eksternal tidak diubah', str_contains($out, 'href="https://kkp.go.id/"'), $out);
check('url relatif tidak diubah', str_contains($out, 'href="?page=2"'), $out);

echo "\nRESULT: $ok passed, $fail failed\n";
exit($fail ? 1 : 0);

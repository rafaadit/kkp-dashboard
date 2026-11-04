<?php
/**
 * KKP EXIM Platform — Frontend PHP Native.
 * Bootstrap minimal: config + autoload + session + router.
 */

declare(strict_types=1);

define('BASE_PATH', dirname(__DIR__));
define('PUBLIC_PATH', __DIR__);

require_once BASE_PATH . '/src/Config.php';
require_once BASE_PATH . '/src/ApiClient.php';
require_once BASE_PATH . '/src/Session.php';
require_once BASE_PATH . '/src/View.php';

use KKP\Config;
use KKP\Session;

$config = Config::load(BASE_PATH . '/.env.local');
$session = new Session($config);

$uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
$uri = rtrim($uri, '/');
if ($uri === '') {
    $uri = '/';
}

// Passthrough aset statis bila server tanpa docroot (php -S ... index.php).
$static = PUBLIC_PATH . $uri;
if ($uri !== '/' && is_file($static)) {
    $mime = [
        'css' => 'text/css',
        'js' => 'application/javascript',
        'png' => 'image/png',
        'jpg' => 'image/jpeg',
        'jpeg' => 'image/jpeg',
        'svg' => 'image/svg+xml',
        'gif' => 'image/gif',
        'ico' => 'image/x-icon',
        'woff' => 'font/woff',
        'woff2' => 'font/woff2',
        'ttf' => 'font/ttf',
    ];
    $ext = strtolower(pathinfo($static, PATHINFO_EXTENSION));
    header('Content-Type: ' . ($mime[$ext] ?? 'application/octet-stream'));
    header('Content-Length: ' . filesize($static));
    readfile($static);
    exit;
}

try {
    if ($uri === '/login') {
        if ($session->isLoggedIn() && $session->validate()) {
            redirect('/');
        }
        $error = null;
        $notice = isset($_GET['expired']) ? 'Sesi Anda berakhir. Silakan masuk kembali.' : null;
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            $error = $session->login($_POST['email'] ?? '', $_POST['password'] ?? '');
            if ($error === null) {
                redirect('/');
            }
        }
        http_response_code($error ? 401 : 200);
        render_view('login', ['config' => $config, 'error' => $error, 'notice' => $notice,
                              'email' => $_POST['email'] ?? '']);
        exit;
    }

    if ($uri === '/logout') {
        $session->logout();
        redirect('/login');
        exit;
    }

    // Semua halaman lain wajib login + token masih valid di backend.
    if (!$session->isLoggedIn()) {
        redirect('/login');
        exit;
    }
    if (!$session->validate()) {
        $session->logout();
        redirect('/login?expired=1');
        exit;
    }
    $user = $session->user();
    $view = null;
    $vars = ['config' => $config, 'session' => $session, 'user' => $user, 'active' => $uri];

    switch ($uri) {
        case '/':
        case '/dashboard':
            guard($session, ['explore.view'], $vars);
            $view = 'dashboard';
            break;
        case '/data':
            guard($session, ['data.view', 'exim.view'], $vars);
            $view = 'raw_exim';
            break;
        case '/data/export':
            guard($session, ['data.view', 'exim.view'], $vars);
            @set_time_limit(600);
            $api = $session->api();
            $qs = (string) ($_SERVER['QUERY_STRING'] ?? '');
            [$st, $errbody, $cerr] = $api->stream('/api/data/raw_exim.xlsx' . ($qs !== '' ? '?' . $qs : ''));
            if ($st !== 200) {
                http_response_code($st ?: 502);
                echo 'Gagal mengekspor data.' . ($cerr !== '' ? ' (' . $cerr . ')' : '');
            }
            exit;
        case '/komoditas':
            guard($session, ['explore.commodity'], $vars);
            $view = 'komoditas';
            break;
        case '/negara':
            guard($session, ['explore.country'], $vars);
            $view = 'negara';
            break;
        case '/provinsi':
            guard($session, ['explore.country'], $vars);
            $view = 'provinsi';
            break;
        case '/compare':
        case '/perbandingan':
            guard($session, ['explore.comparison'], $vars);
            $view = $uri === '/compare' ? 'compare' : 'perbandingan';
            break;
        case '/potensi':
            guard($session, ['explore.opportunity'], $vars);
            $view = 'potensi';
            break;
        case '/kompetitor':
            guard($session, ['explore.competition'], $vars);
            $view = 'kompetitor';
            break;
        case '/trademap':
            guard($session, ['trademap.view'], $vars);
            $view = 'trademap';
            break;
        case '/asisten':
            guard($session, ['ai.use'], $vars);
            $view = 'asisten';
            break;
        case '/laporan':
            guard($session, ['report.view'], $vars);
            if ($_SERVER['REQUEST_METHOD'] === 'POST') {
                guard($session, ['report.generate_ppt'], $vars);
                try {
                    $api = $session->api();
                    [$st, $body] = $api->post('/api/report/generate_ppt', [
                        'tahun' => (int) ($_POST['tahun'] ?? 2026),
                        'bulan_awal' => (int) ($_POST['bulan_awal'] ?? 1),
                        'bulan_akhir' => (int) ($_POST['bulan_akhir'] ?? 6),
                    ]);
                    if ($st !== 200) {
                        $msg = is_array($body) ? ($body['error'] ?? 'gagal membuat PPT') : 'gagal membuat PPT';
                        redirect('/laporan?err=' . urlencode((string) $msg));
                    }
                    $job = is_array($body) ? (string) ($body['job_id'] ?? '') : '';
                    redirect('/laporan?ok=1&job=' . urlencode($job)
                        . '&tahun=' . urlencode((string) ($_POST['tahun'] ?? 2026))
                        . '&bulan_awal=' . urlencode((string) ($_POST['bulan_awal'] ?? 1))
                        . '&bulan_akhir=' . urlencode((string) ($_POST['bulan_akhir'] ?? 6)));
                } catch (Throwable $e) {
                    // pesan error ditampilkan di view via query
                    redirect('/laporan?err=' . urlencode($e->getMessage()));
                }
            }
            $view = 'laporan';
            break;
        case '/laporan/download':
            guard($session, ['report.view'], $vars);
            $api = $session->api();
            [$st, $blob, $ctype] = $api->getRaw('/api/report/download?job_id=' . urlencode((string) ($_GET['job_id'] ?? '')));
            if ($st !== 200 || $blob === '') {
                http_response_code($st ?: 502);
                echo 'Gagal mengunduh laporan.';
                exit;
            }
            $fname = 'Laporan_EKSIM_' . ($_GET['job_id'] ?? 'report') . '.pptx';
            header('Content-Type: ' . ($ctype ?: 'application/vnd.openxmlformats-officedocument.presentationml.presentation'));
            header('Content-Disposition: attachment; filename="' . $fname . '"');
            header('Content-Length: ' . strlen($blob));
            echo $blob;
            exit;
        case '/data-bps':
            guard($session, ['data.update_bps_export', 'data.update_bps_import'], $vars);
            if ($_SERVER['REQUEST_METHOD'] === 'POST') {
                @set_time_limit(300);
                $files = [];
                foreach (['ekspor', 'impor'] as $key) {
                    if (!empty($_FILES[$key]['tmp_name']) && is_uploaded_file($_FILES[$key]['tmp_name'])) {
                        $files[$key] = $_FILES[$key];
                    }
                }
                if (!$files) {
                    redirect('/data-bps?err=' . urlencode('Pilih minimal satu file BPS (.xlsx).'));
                }
                try {
                    [$st, $body] = $session->api()->postMultipart(
                        '/api/data/bps/upload',
                        ['force' => isset($_POST['force']) ? '1' : ''],
                        $files,
                        180
                    );
                    if ($st !== 200 && $st !== 202) {
                        $msg = is_array($body) ? ($body['error'] ?? 'gagal memulai update BPS') : 'gagal memulai update BPS';
                        redirect('/data-bps?err=' . urlencode((string) $msg));
                    }
                    $job = is_array($body) ? (string) ($body['job_id'] ?? '') : '';
                    redirect('/data-bps?ok=1&job=' . urlencode($job));
                } catch (Throwable $e) {
                    redirect('/data-bps?err=' . urlencode($e->getMessage()));
                }
            }
            $view = 'data_bps';
            break;
        case '/data-bps/status':
            guard($session, ['data.update_bps_export', 'data.update_bps_import'], $vars);
            header('Content-Type: application/json; charset=utf-8');
            $jid = (int) ($_GET['job'] ?? 0);
            if ($jid < 1) {
                http_response_code(400);
                echo json_encode(['error' => 'job tidak valid']);
                exit;
            }
            try {
                [$st, $body] = $session->api()->get('/api/data/bps/jobs/' . $jid);
                http_response_code($st ?: 502);
                echo json_encode($body);
            } catch (Throwable $e) {
                http_response_code(502);
                echo json_encode(['error' => $e->getMessage()]);
            }
            exit;
        case '/akun':
            guard($session, ['admin.users'], $vars);
            if ($_SERVER['REQUEST_METHOD'] === 'POST') {
                $action = (string) ($_POST['action'] ?? '');
                $api = $session->api();
                try {
                    if ($action === 'create') {
                        [$st, $body] = $api->post('/api/admin/users', [
                            'nama' => (string) ($_POST['nama'] ?? ''),
                            'email' => (string) ($_POST['email'] ?? ''),
                            'password' => (string) ($_POST['password'] ?? ''),
                            'role' => (string) ($_POST['role'] ?? ''),
                        ]);
                    } elseif ($action === 'update') {
                        $uid = (int) ($_POST['id'] ?? 0);
                        [$st, $body] = $api->request('PUT', '/api/admin/users/' . $uid, [
                            'nama' => (string) ($_POST['nama'] ?? ''),
                            'email' => (string) ($_POST['email'] ?? ''),
                            'role' => (string) ($_POST['role'] ?? ''),
                        ]);
                    } elseif ($action === 'reset_password') {
                        $uid = (int) ($_POST['id'] ?? 0);
                        [$st, $body] = $api->post('/api/admin/users/' . $uid . '/reset-password', [
                            'password' => (string) ($_POST['password'] ?? ''),
                        ]);
                    } elseif ($action === 'toggle') {
                        $uid = (int) ($_POST['id'] ?? 0);
                        $active = (string) ($_POST['is_active'] ?? '0') === '1';
                        [$st, $body] = $api->request('PUT', '/api/admin/users/' . $uid, [
                            'is_active' => $active,
                        ]);
                    } else {
                        $st = 400;
                        $body = ['error' => 'aksi tidak dikenal'];
                    }
                    if ($st !== 200 && $st !== 201) {
                        $msg = is_array($body) ? ($body['error'] ?? 'gagal memproses akun') : 'gagal memproses akun';
                        redirect('/akun?err=' . urlencode((string) $msg));
                    }
                    redirect('/akun?ok=' . urlencode($action === 'create' ? 'Akun berhasil dibuat.' : 'Perubahan berhasil disimpan.'));
                } catch (Throwable $e) {
                    redirect('/akun?err=' . urlencode($e->getMessage()));
                }
            }
            $view = 'akun';
            break;
        default:
            http_response_code(404);
            render_view('404', $vars);
            exit;
    }
    render_view($view, $vars);
} catch (Throwable $e) {
    http_response_code(500);
    render_view('error', ['config' => $config, 'message' => $e->getMessage()]);
}

/** Tolak akses bila tidak punya salah satu permission; render halaman 403. */
function guard(Session $session, array $permissions, array $vars): void
{
    if (!$session->hasAnyPermission($permissions)) {
        http_response_code(403);
        render_view('403', $vars);
        exit;
    }
}

function render_view(string $name, array $vars): void
{
    \KKP\View::render($name, $vars);
}

function redirect(string $to): void
{
    header('Location: ' . $to);
    exit;
}
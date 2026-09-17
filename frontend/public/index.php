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

try {
    if ($uri === '/login') {
        if ($session->isLoggedIn()) {
            redirect('/');
        }
        $error = null;
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            $error = $session->login($_POST['email'] ?? '', $_POST['password'] ?? '');
            if ($error === null) {
                redirect('/');
            }
        }
        http_response_code($error ? 401 : 200);
        render_view('login', ['config' => $config, 'error' => $error, 'email' => $_POST['email'] ?? '']);
        exit;
    }

    if ($uri === '/logout') {
        $session->logout();
        redirect('/login');
        exit;
    }

    // Semua halaman lain wajib login.
    if (!$session->isLoggedIn()) {
        redirect('/login');
        exit;
    }
    $user = $session->user();
    $view = null;
    $vars = ['config' => $config, 'session' => $session, 'user' => $user, 'active' => $uri];

    switch ($uri) {
        case '/':
        case '/dashboard':
            $view = 'dashboard';
            break;
        case '/data':
            $view = 'raw_exim';
            break;
        case '/komoditas':
            $view = 'komoditas';
            break;
        case '/negara':
            $view = 'negara';
            break;
        case '/trademap':
            $view = 'trademap';
            break;
        case '/asisten':
            $view = 'asisten';
            break;
        case '/laporan':
            if ($_SERVER['REQUEST_METHOD'] === 'POST') {
                try {
                    $api = $session->api();
                    $api->post('/api/report/generate_ppt', [
                        'tahun' => (int) ($_POST['tahun'] ?? 2026),
                        'bulan_awal' => (int) ($_POST['bulan_awal'] ?? 1),
                        'bulan_akhir' => (int) ($_POST['bulan_akhir'] ?? 6),
                    ]);
                } catch (Throwable $e) {
                    // pesan error ditampilkan di view via query
                    redirect('/laporan?err=' . urlencode($e->getMessage()));
                }
                redirect('/laporan?ok=1');
            }
            $view = 'laporan';
            break;
        case '/laporan/download':
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
        case '/perbandingan':
            $view = 'perbandingan';
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

function render_view(string $name, array $vars): void
{
    \KKP\View::render($name, $vars);
}

function redirect(string $to): void
{
    header('Location: ' . $to);
    exit;
}
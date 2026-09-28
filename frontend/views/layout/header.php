<?php /** layout header */ [$name, $active, $user, $config, $session] = [$__name__ ?? '', $active ?? '', $user ?? [], $config ?? null, $session ?? null];

$side_list = [];
$side_err = null;
if ($session !== null && $session->isLoggedIn()) {
    try {
        $side_api = $session->api();
        [$side_st, $side_json] = $side_api->get('/api/explore/komoditas_list?exim=' . urlencode($_GET['exim'] ?? 'ekspor'));
        if ($side_st === 200 && is_array($side_json) && isset($side_json['komoditas'])) {
            foreach ($side_json['komoditas'] as $k) {
                $side_list[] = ['n' => (string) ($k['komoditas'] ?? ''), 'r' => (int) ($k['baris'] ?? 0)];
            }
        } else {
            $side_err = is_array($side_json) ? ($side_json['error'] ?? 'gagal') : 'gagal';
        }
    } catch (\Throwable $e) {
        $side_err = $e->getMessage();
    }
}
?>
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= KKP\View::e($config?->appName ?? 'KKP EXIM Platform'); ?> — <?= KKP\View::e($active); ?></title>
<link rel="stylesheet" href="/assets/app.css">
</head>
<body>
<?php if ($session !== null && $session->isLoggedIn()): ?>
<div class="layout" id="layout">
<aside class="sidebar" id="sidebar">
    <div class="sidebar-brand">
        <span class="brand-badge">MI</span>
        <div>
            <div class="brand-title"><?= KKP\View::e($config?->appName ?? 'KKP EXIM'); ?></div>
            <div class="brand-sub">Market Intelligence</div>
        </div>
    </div>
    <div class="side-search">
        <input id="sideSearch" type="search" placeholder="Cari komoditas… (mis. Udang)" autocomplete="off">
    </div>
    <nav class="side-nav">
        <a href="/" class="<?= $active === '/' ? 'on' : ''; ?>">Ringkasan</a>
        <a href="/komoditas" class="<?= $active === '/komoditas' ? 'on' : ''; ?>">Komoditas</a>
        <a href="/negara" class="<?= $active === '/negara' ? 'on' : ''; ?>">Negara</a>
        <a href="/perbandingan" class="<?= $active === '/perbandingan' ? 'on' : ''; ?>">Perbandingan</a>
        <a href="/trademap" class="<?= $active === '/trademap' ? 'on' : ''; ?>">TradeMap</a>
        <a href="/laporan" class="<?= $active === '/laporan' ? 'on' : ''; ?>">Laporan PPT</a>
        <a href="/asisten" class="<?= $active === '/asisten' ? 'on' : ''; ?>">Asisten AI</a>
        <a href="/data" class="<?= $active === '/data' ? 'on' : ''; ?>">Raw EXIM</a>
    </nav>
    <div class="side-comms">
        <div class="side-comms-head"><span>Komoditas</span><span class="count" id="sideCount"><?= count($side_list); ?></span></div>
        <div class="side-comms-list" id="sideList">
        <?php if ($side_err !== null): ?>
            <span class="muted">Komoditas tak termuat.</span>
        <?php else: foreach ($side_list as $s): ?>
            <a href="/dashboard?komoditas=<?= urlencode($s['n']); ?>" title="<?= KKP\View::e($s['n']); ?> — <?= KKP\View::num($s['r']); ?> baris"><?= KKP\View::e($s['n']); ?></a>
        <?php endforeach; endif; ?>
        </div>
    </div>
    <div class="side-user">
        <div class="side-user-name">
            <?= KKP\View::e($user['nama'] ?? $user['email'] ?? ''); ?>
            <small>[<?= KKP\View::e($user['role'] ?? ''); ?>]</small>
        </div>
        <a class="btn" href="/logout">Logout</a>
    </div>
</aside>
<div class="main">
    <header class="topbar">
        <button id="sideToggle" class="icon-btn" aria-label="Buka/tutup menu">&#9776;</button>
        <span class="topbar-title"><?= KKP\View::e($active === '/' ? 'Ringkasan' : trim($active, '/')); ?></span>
        <span class="topbar-spacer"></span>
        <span class="topbar-meta">Sumber: PDSPKP KKP &middot; BPS &middot; ITC TradeMap</span>
    </header>
    <main class="container">
<?php else: ?>
<main class="container">
<?php endif; ?>
<?php if (isset($error) && $error): ?><div class="alert alert-danger"><?= KKP\View::e($error); ?></div><?php endif; ?>
<?php if (isset($api_error)): ?><div class="alert alert-danger"><?= KKP\View::e($api_error); ?></div><?php endif; ?>
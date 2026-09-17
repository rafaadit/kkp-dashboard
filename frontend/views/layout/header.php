<?php /** layout header */ [$name, $active, $user, $config, $session] = [$__name__ ?? '', $active ?? '', $user ?? [], $config ?? null, $session ?? null]; ?>
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
<header class="topbar">
    <div class="brand"><?= KKP\View::e($config?->appName ?? 'KKP EXIM Platform'); ?></div>
    <nav>
        <a href="/" class="<?= $active === '/' ? 'on' : ''; ?>">Dashboard</a>
        <a href="/komoditas" class="<?= $active === '/komoditas' ? 'on' : ''; ?>">Komoditas</a>
        <a href="/negara" class="<?= $active === '/negara' ? 'on' : ''; ?>">Negara</a>
        <a href="/trademap" class="<?= $active === '/trademap' ? 'on' : ''; ?>">TradeMap</a>
        <a href="/laporan" class="<?= $active === '/laporan' ? 'on' : ''; ?>">Laporan PPT</a>
        <a href="/asisten" class="<?= $active === '/asisten' ? 'on' : ''; ?>">Asisten AI</a>
        <a href="/data" class="<?= $active === '/data' ? 'on' : ''; ?>">Data RAW EXIM</a>
        <a href="/perbandingan" class="<?= $active === '/perbandingan' ? 'on' : ''; ?>">Perbandingan</a>
    </nav>
    <div class="user">
        <span>Halo, <?= KKP\View::e($user['nama'] ?? $user['email'] ?? ''); ?><br>
            <small>[<?= KKP\View::e($user['role'] ?? ''); ?>]</small></span>
        <a class="btn" href="/logout">Logout</a>
    </div>
</header>
<?php endif; ?>
<main class="container">
<?php if (isset($error) && $error): ?><div class="alert alert-danger"><?= KKP\View::e($error); ?></div><?php endif; ?>
<?php if (isset($api_error)): ?><div class="alert alert-danger"><?= KKP\View::e($api_error); ?></div><?php endif; ?>
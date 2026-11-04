<?php /** layout header — top navigation (home-user style) */ [$name, $active, $user, $config, $session] = [$__name__ ?? '', $active ?? '', $user ?? [], $config ?? null, $session ?? null];
$isLogged = $session !== null && $session->isLoggedIn();
$appName = $config?->appName ?? 'KKP EXIM Platform';
$logo_ver = @filemtime(__DIR__ . '/../../public/assets/logo-kkp.png') ?: time();

$komoditas_list = [];
$list_err = null;
$ticker = [];
$exim_side = (($_GET['exim'] ?? 'ekspor') === 'impor') ? 'impor' : 'ekspor';
if ($isLogged) {
    try {
        $side_api = $session->api();
        $side_res = $side_api->getMany([
            'list' => '/api/explore/komoditas_list?exim=' . urlencode($exim_side),
            'ticker' => '/api/explore/komoditas?exim=' . urlencode($exim_side) . '&limit=3',
        ]);
        [$st, $json] = $side_res['list'] ?? [0, null];
        if ($st === 200 && is_array($json) && isset($json['komoditas'])) {
            foreach ($json['komoditas'] as $k) {
                $komoditas_list[] = ['n' => (string) ($k['komoditas'] ?? ''), 'r' => (int) ($k['baris'] ?? 0)];
            }
        } else {
            $list_err = is_array($json) ? ($json['error'] ?? 'gagal') : 'gagal';
        }
        [$tst, $tjson] = $side_res['ticker'] ?? [0, null];
        if ($tst === 200 && is_array($tjson) && isset($tjson['komoditas'])) {
            $ticker = $tjson['komoditas'];
        }
    } catch (\Throwable $e) {
        $list_err = $e->getMessage();
    }
}

$nav = [
    ['href' => '/', 'label' => 'Beranda', 'on' => in_array($active, ['/', '/dashboard'], true)],
];
$analisis = ['/komoditas', '/negara', '/provinsi', '/potensi', '/kompetitor', '/trademap'];
$laporan = ['/laporan', '/data', '/asisten', '/data-bps'];
$initial = mb_strtoupper(mb_substr(trim((string) ($user['nama'] ?? $user['email'] ?? 'U')), 0, 1));
$exim_label = $exim_side === 'impor' ? 'Indeks Impor' : 'Indeks Ekspor';
$canUpdateBps = $session !== null && $session->hasAnyPermission(['data.update_bps_export', 'data.update_bps_import']);
$isAdmin = $session !== null && $session->isAdmin();
$roleLabel = $session !== null ? $session->roleLabel() : '';
$roleClass = $session !== null ? $session->roleClass() : 'role-guest';
?>
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= KKP\View::e($appName); ?> — <?= KKP\View::e($active === '/' ? 'Beranda' : trim($active, '/')); ?></title>
<link rel="stylesheet" href="/assets/app.css?v=<?= @filemtime(__DIR__ . '/../../public/assets/app.css') ?: time(); ?>">
</head>
<body class="has-waves">
<canvas id="waveCanvas" aria-hidden="true"></canvas>

<?php if ($isLogged): ?>
<header class="topnav" id="topnav">
  <div class="topnav-inner">
    <a class="nav-brand" href="/">
      <img class="brand-logo" src="/assets/logo-kkp.png?v=<?= $logo_ver; ?>" alt="Logo Kementerian Kelautan dan Perikanan" width="46" height="46">
      <span class="brand-text">
        <span class="brand-title"><?= KKP\View::e($appName); ?></span>
        <span class="brand-sub">Market Intelligence</span>
      </span>
    </a>

    <nav class="nav-links" id="navLinks" aria-label="Navigasi utama">
      <a class="nav-link <?= $nav[0]['on'] ? 'on' : ''; ?>" href="/">Beranda</a>

      <div class="nav-drop">
        <button class="nav-link <?= array_intersect($analisis, [$active]) ? 'on' : ''; ?>" type="button">
          Analisis <span class="caret">&#9662;</span>
        </button>
        <div class="nav-drop-menu">
          <a href="/komoditas"><div class="mi-title">Analisis Komoditas</div><div class="mi-sub">Udang, tuna, &amp; kepiting utama</div></a>
          <a href="/negara"><div class="mi-title">Analisis Negara</div><div class="mi-sub">Destinasi ekspor &amp; asal impor</div></a>
          <a href="/provinsi"><div class="mi-title">Provinsi Asal</div><div class="mi-sub">Sentra produksi &amp; pelabuhan</div></a>
          <a href="/potensi"><div class="mi-title">Potensi &amp; Pangsa</div><div class="mi-sub">Momentum pasar &amp; peluang</div></a>
          <a href="/kompetitor"><div class="mi-title">Profil Kompetitor</div><div class="mi-sub">Lanskap persaingan</div></a>
          <a href="/trademap"><div class="mi-title">TradeMap (ITC)</div><div class="mi-sub">Data mitra dagang global</div></a>
        </div>
      </div>

      <a class="nav-link <?= $active === '/compare' ? 'on' : ''; ?>" href="/compare">Banding Negara</a>
      <a class="nav-link <?= $active === '/perbandingan' ? 'on' : ''; ?>" href="/perbandingan">Perbandingan</a>

      <div class="nav-drop">
        <button class="nav-link <?= array_intersect($laporan, [$active]) ? 'on' : ''; ?>" type="button">
          Laporan <span class="caret">&#9662;</span>
        </button>
        <div class="nav-drop-menu">
          <a href="/laporan"><div class="mi-title">Laporan PPT</div><div class="mi-sub">Infografis eksekutif bulanan</div></a>
          <a href="/data"><div class="mi-title">Data RAW EXIM</div><div class="mi-sub">Data mentah BPS &amp; Bea Cukai</div></a>
          <?php if ($canUpdateBps): ?>
          <a href="/data-bps"><div class="mi-title">Update Data BPS</div><div class="mi-sub">Unggah periode BPS terbaru</div></a>
          <?php endif; ?>
          <a href="/asisten"><div class="mi-title">Asisten AI</div><div class="mi-sub">Tanya jawab data EXIM</div></a>
        </div>
      </div>
    </nav>

    <div class="nav-actions">
      <?php if ($isAdmin): ?>
      <a class="btn nav-admin <?= $active === '/akun' ? 'on' : ''; ?>" href="/akun" title="Kelola Akun" aria-label="Kelola Akun">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        <span class="nav-admin-text">Kelola Akun</span>
      </a>
      <?php endif; ?>
      <div class="nav-search">
        <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input id="komSearch" type="search" placeholder="Cari komoditas…" autocomplete="off" aria-label="Cari komoditas">
        <div class="search-menu" id="komMenu">
          <?php if ($list_err !== null): ?>
            <div class="empty">Komoditas tak termuat.</div>
          <?php else: foreach ($komoditas_list as $k): ?>
            <a href="/dashboard?komoditas=<?= urlencode($k['n']); ?>"><span><?= KKP\View::e($k['n']); ?></span><span class="cnt"><?= KKP\View::num($k['r']); ?></span></a>
          <?php endforeach; endif; ?>
        </div>
      </div>
      <div class="nav-user">
        <span class="avatar" aria-hidden="true"><?= KKP\View::e($initial); ?></span>
        <span class="nav-user-meta">
          <span class="nav-user-name"><?= KKP\View::e($user['nama'] ?? $user['email'] ?? ''); ?></span>
          <span class="nav-user-role role-badge <?= KKP\View::e($roleClass); ?>"><?= KKP\View::e($roleLabel); ?></span>
        </span>
        <a class="btn nav-logout" href="/logout">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>
          Keluar
        </a>
      </div>
      <button class="nav-toggle" id="navToggle" type="button" aria-label="Buka menu" aria-expanded="false">&#9776;</button>
    </div>
  </div>
</header>

<div class="ticker" aria-label="Ringkasan komoditas">
  <div class="ticker-inner">
    <span class="ticker-label"><span class="dot"></span><?= KKP\View::e($exim_label); ?>:</span>
    <div class="ticker-items">
      <?php if ($ticker): foreach ($ticker as $t): ?>
        <span class="ticker-item">
          <span class="name"><?= KKP\View::e($t['komoditas'] ?? '-'); ?></span>
          <span class="val">USD <?= KKP\View::num($t['harga_usd_kg'] ?? 0, 2); ?>/kg</span>
          <span class="chg up">share <?= KKP\View::num($t['share_nilai_persen'] ?? 0, 1); ?>%</span>
        </span>
      <?php endforeach; else: ?>
        <span class="ticker-item"><span class="name">Data komoditas belum tersedia</span></span>
      <?php endif; ?>
    </div>
    <span class="ticker-sync">Sumber: BPS &middot; KKP &middot; ITC TradeMap</span>
  </div>
</div>

<main class="container">
<?php else: ?>
<header class="topnav">
  <div class="topnav-inner">
    <a class="nav-brand" href="/login">
      <img class="brand-logo" src="/assets/logo-kkp.png?v=<?= $logo_ver; ?>" alt="Logo Kementerian Kelautan dan Perikanan" width="46" height="46">
      <span class="brand-text">
        <span class="brand-title"><?= KKP\View::e($appName); ?></span>
        <span class="brand-sub">Market Intelligence</span>
      </span>
    </a>
    <div class="nav-actions"><span class="nav-link nav-tagline">Sistem Intelijen Pasar Perikanan</span></div>
  </div>
</header>
<main>
<?php endif; ?>
<?php if (isset($error) && $error): ?><div class="alert alert-danger"><?= KKP\View::e($error); ?></div><?php endif; ?>
<?php if (isset($api_error)): ?><div class="alert alert-danger"><?= KKP\View::e($api_error); ?></div><?php endif; ?>

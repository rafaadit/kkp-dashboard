<?php
$kode = strtoupper(trim($_GET['negara'] ?? ''));
$negara = [];
try {
    $api = $session->api();
    [$st, $nl] = $api->get('/api/explore/negara_list?exim=ekspor');
    if ($st === 200 && is_array($nl) && isset($nl['negara'])) {
        $negara = $nl['negara'];
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
}

$d = null;
if ($kode !== '') {
    try {
        [$st, $d] = $api->get('/api/explore/dossier?negara=' . urlencode($kode));
        if ($st !== 200) {
            $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
            $d = null;
        }
    } catch (\Throwable $e) {
        $api_error = $e->getMessage();
        $d = null;
    }
}
?>
<h1>Dossier Pasar 360°</h1>
<form class="filters" method="get">
    <select name="negara" required>
        <option value="">— Pilih Pasar (Negara) —</option>
        <?php foreach ($negara as $n): ?>
            <option value="<?= \KKP\View::e($n['kode_negara']); ?>" <?= $kode === $n['kode_negara'] ? 'selected' : ''; ?>><?= KKP\View::e($n['negara']); ?> (<?= \KKP\View::e($n['kode_negara']); ?>)</option>
        <?php endforeach; ?>
    </select>
    <button class="btn btn-primary" type="submit">Lihat Dossier</button>
</form>

<?php if ($d): $p = $d['profil']; $ex = $d['ekspor']; $im = $d['impor']; ?>
<div class="card">
    <h2><?= \KKP\View::e($p['negara']); ?><span class="muted"> (<?= \KKP\View::e($p['kode_negara']); ?>)</span></h2>
    <p class="muted">Kelompok regional: <?= \KKP\View::e($p['kelompok_negara'] ?? '-'); ?></p>
</div>
<section class="kpi-grid">
    <div class="card kpi"><div class="k">Ekspor RI (total)</div><div class="v"><?= \KKP\View::num($ex['total_usd'], 2); ?></div><div class="muted">YoY <?= $ex['yoy'] !== null ? \KKP\View::num($ex['yoy'], 2) . '%' : '-'; ?> · Share RI <?= $ex['share_ri'] !== null ? \KKP\View::num($ex['share_ri'], 2) . '%' : '-'; ?></div></div>
    <div class="card kpi"><div class="k">Impor RI (total)</div><div class="v"><?= \KKP\View::num($im['total_usd'], 2); ?></div><div class="muted">dari <?= \KKP\View::e($p['negara']); ?></div></div>
    <?php $nlast = end($d['neraca']); ?>
    <div class="card kpi <?= ($nlast['neraca'] ?? 0) >= 0 ? 'pos' : 'neg'; ?>"><div class="k">Neraca (<?= \KKP\View::e((string)($nlast['tahun'] ?? '-')); ?>)</div><div class="v"><?= $nlast['neraca'] !== null ? \KKP\View::num($nlast['neraca'], 2) : '-'; ?></div><div class="muted"><?= ($nlast['neraca'] ?? 0) >= 0 ? 'Surplus' : 'Defisit'; ?></div></div>
</section>

<section class="grid-2">
    <div class="card">
        <h2>Tren Ekspor RI ke <?= \KKP\View::e($p['negara']); ?></h2>
        <table class="tbl">
            <thead><tr><th>Tahun</th><th>Baris</th><th>Volume (kg)</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($ex['per_tahun'] as $t): ?>
                <tr><td><?= \KKP\View::num($t['tahun']); ?></td><td><?= \KKP\View::num($t['baris']); ?></td><td><?= \KKP\View::num($t['volume_kg'], 0); ?></td><td><?= \KKP\View::num($t['nilai_usd'], 2); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <div class="card">
        <h2>Neraca per Tahun</h2>
        <table class="tbl">
            <thead><tr><th>Tahun</th><th>Ekspor</th><th>Impor</th><th>Neraca</th></tr></thead>
            <tbody>
            <?php foreach ($d['neraca'] as $r): ?>
                <tr>
                    <td><?= \KKP\View::num($r['tahun']); ?></td>
                    <td><?= $r['ekspor'] !== null ? \KKP\View::num($r['ekspor'], 2) : '-'; ?></td>
                    <td><?= $r['impor'] !== null ? \KKP\View::num($r['impor'], 2) : '-'; ?></td>
                    <td class="<?= ($r['neraca'] ?? 0) >= 0 ? 'pos' : 'neg'; ?>"><?= $r['neraca'] !== null ? \KKP\View::num($r['neraca'], 2) : '-'; ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>

<section class="grid-2">
    <div class="card">
        <h2>Top Komoditas Ekspor</h2>
        <table class="tbl">
            <thead><tr><th>Komoditas</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($ex['top_komoditas'] as $k): ?>
                <tr><td><?= \KKP\View::e($k['komoditas']); ?></td><td><?= \KKP\View::num($k['nilai_usd'], 2); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <div class="card">
        <h2>Top Komoditas Impor</h2>
        <table class="tbl">
            <thead><tr><th>Komoditas</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($im['top_komoditas'] as $k): ?>
                <tr><td><?= \KKP\View::e($k['komoditas']); ?></td><td><?= \KKP\View::num($k['nilai_usd'], 2); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>
<?php endif; ?>
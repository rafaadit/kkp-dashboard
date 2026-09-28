<?php
$kode = strtoupper(trim($_GET['negara'] ?? ''));
$mulai = $_GET['mulai'] ?? '';
$akhir = $_GET['akhir'] ?? '';
$komoditas = trim($_GET['komoditas'] ?? '');

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
    $query = ['negara' => $kode];
    if ($mulai) { $query['mulai'] = $mulai; }
    if ($akhir) { $query['akhir'] = $akhir; }
    if ($komoditas !== '') { $query['komoditas'] = $komoditas; }
    try {
        [$st, $d] = $api->get('/api/explore/bilateral?' . http_build_query($query));
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
<h1>Intelijen Bilateral</h1>
<form class="filters" method="get">
    <select name="negara" required>
        <option value="">— Pilih Negara Mitra —</option>
        <?php foreach ($negara as $n): ?>
            <option value="<?= \KKP\View::e($n['kode_negara']); ?>" <?= $kode === $n['kode_negara'] ? 'selected' : ''; ?>><?= KKP\View::e($n['negara']); ?> (<?= \KKP\View::e($n['kode_negara']); ?>)</option>
        <?php endforeach; ?>
    </select>
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>">
    <input type="text" name="komoditas" placeholder="Komoditas (opsional)" value="<?= \KKP\View::e($komoditas); ?>">
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>

<?php if ($d): $ng = $d['negara']; $eks = $d['ekspor']['rincian']; $imp = $d['impor']['rincian']; $neraca = $d['neraca_nilai_usd']; ?>
<section class="kpi-grid">
    <div class="card kpi"><div class="k"><?= \KKP\View::e($ng['negara']); ?> — Ekspor RI</div><div class="v"><?= \KKP\View::num($eks['nilai_usd'], 2); ?></div><div class="muted"><?= \KKP\View::num($eks['baris']); ?> baris · <?= \KKP\View::num($eks['hs_unik']); ?> HS</div></div>
    <div class="card kpi"><div class="k"><?= \KKP\View::e($ng['negara']); ?> — Impor RI</div><div class="v"><?= \KKP\View::num($imp['nilai_usd'], 2); ?></div><div class="muted"><?= \KKP\View::num($imp['baris']); ?> baris · <?= \KKP\View::num($imp['hs_unik']); ?> HS</div></div>
    <div class="card kpi <?= $neraca >= 0 ? 'pos' : 'neg'; ?>"><div class="k">Neraca RI — <?= \KKP\View::e($ng['negara']); ?></div><div class="v"><?= \KKP\View::num(abs($neraca), 2); ?></div><div class="muted"><?= $neraca >= 0 ? 'Surplus' : 'Defisit'; ?> (USD)</div></div>
</section>
<section class="grid-2">
    <div class="card">
        <h2>Top Komoditas Ekspor — RI → <?= \KKP\View::e($ng['negara']); ?></h2>
        <table class="tbl">
            <thead><tr><th>Komoditas</th><th>Volume (kg)</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($d['ekspor']['top_komoditas'] as $k): ?>
                <tr><td><?= \KKP\View::e($k['komoditas']); ?></td><td><?= \KKP\View::num($k['volume_kg'], 0); ?></td><td><?= \KKP\View::num($k['nilai_usd'], 2); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <div class="card">
        <h2>Top Komoditas Impor — RI ← <?= \KKP\View::e($ng['negara']); ?></h2>
        <table class="tbl">
            <thead><tr><th>Komoditas</th><th>Volume (kg)</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($d['impor']['top_komoditas'] as $k): ?>
                <tr><td><?= \KKP\View::e($k['komoditas']); ?></td><td><?= \KKP\View::num($k['volume_kg'], 0); ?></td><td><?= \KKP\View::num($k['nilai_usd'], 2); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>
<div class="card">
    <h2>Neraca per Periode</h2>
    <div class="tbl-scroll">
    <table class="tbl">
        <thead><tr><th>Periode</th><th>Ekspor (USD)</th><th>Impor (USD)</th><th>Neraca</th></tr></thead>
        <tbody>
        <?php foreach ($d['per_periode'] as $r): ?>
            <tr>
                <td><?= \KKP\View::e($r['periode']); ?></td>
                <td><?= $r['ekspor'] !== null ? \KKP\View::num($r['ekspor'], 2) : '-'; ?></td>
                <td><?= $r['impor'] !== null ? \KKP\View::num($r['impor'], 2) : '-'; ?></td>
                <td class="<?= ($r['neraca'] ?? 0) >= 0 ? 'pos' : 'neg'; ?>"><?= $r['neraca'] !== null ? \KKP\View::num($r['neraca'], 2) : '-'; ?></td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
    </div>
</div>
<?php endif; ?>
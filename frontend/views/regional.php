<?php
$exim = $_GET['exim'] ?? 'ekspor';
$mulai = $_GET['mulai'] ?? '';
$akhir = $_GET['akhir'] ?? '';
$region = trim($_GET['region'] ?? '');

$base = ['exim' => $exim];
if ($mulai) { $base['mulai'] = $mulai; }
if ($akhir) { $base['akhir'] = $akhir; }

$query = $base;
if ($region !== '') { $query['region'] = $region; }

$d = null;
$region_options = [];
try {
    $api = $session->api();
    [$st, $regs] = $api->get('/api/explore/regional?' . http_build_query($base));
    if ($st === 200 && is_array($regs) && isset($regs['regional'])) {
        $region_options = array_map(fn($r) => $r['region'], $regs['regional']);
    }
    [$st, $d] = $api->get('/api/explore/regional?' . http_build_query($query));
    if ($st !== 200) {
        $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
        $d = null;
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Analisis Regional</h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <select name="region">
        <option value="">Semua Regional</option>
        <?php foreach ($region_options as $r): ?>
            <option value="<?= \KKP\View::e($r); ?>" <?= $region === $r ? 'selected' : ''; ?>><?= \KKP\View::e($r); ?></option>
        <?php endforeach; ?>
    </select>
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>">
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>

<?php if ($d && isset($d['regional'])): ?>
<section class="kpi-grid">
    <div class="card kpi"><div class="k">Total Nilai (USD)</div><div class="v"><?= \KKP\View::num($d['total_nilai_usd'], 2); ?></div></div>
    <div class="card kpi"><div class="k">Kelompok Regional</div><div class="v"><?= \KKP\View::num(count($d['regional'])); ?></div></div>
</section>
<div class="card">
    <h2>Ringkasan Kelompok Regional (<?= \KKP\View::e($exim); ?>)</h2>
    <div class="tbl-scroll">
    <table class="tbl">
        <thead><tr><th>Regional</th><th>Negara</th><th>Baris</th><th>Volume (kg)</th><th>Nilai (USD)</th><th>Harga (USD/kg)</th><th>Share</th></tr></thead>
        <tbody>
        <?php foreach ($d['regional'] as $r): ?>
            <tr>
                <td><a href="?exim=<?= \KKP\View::e($exim); ?>&region=<?= urlencode($r['region']); ?>"><?= \KKP\View::e($r['region']); ?></a></td>
                <td><?= \KKP\View::num($r['jumlah_negara']); ?></td>
                <td><?= \KKP\View::num($r['baris']); ?></td>
                <td><?= \KKP\View::num($r['volume_kg'], 0); ?></td>
                <td><?= \KKP\View::num($r['nilai_usd'], 2); ?></td>
                <td><?= $r['harga_usd_kg'] !== null ? \KKP\View::num($r['harga_usd_kg'], 4) : '-'; ?></td>
                <td><?= $r['share_nilai_persen'] !== null ? \KKP\View::num($r['share_nilai_persen'], 2) . '%' : '-'; ?></td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
    </div>
</div>
<?php elseif ($d && isset($d['detail'])): ?>
<?php $det = $d['detail']; ?>
<section class="kpi-grid">
    <div class="card kpi"><div class="k"><?= \KKP\View::e($d['region']); ?> — Nilai</div><div class="v"><?= \KKP\View::num($det['nilai_usd'] ?? 0, 2); ?></div></div>
    <div class="card kpi"><div class="k">Volume (kg)</div><div class="v"><?= \KKP\View::num($det['volume_kg'] ?? 0, 0); ?></div></div>
    <div class="card kpi"><div class="k">Setara Segar</div><div class="v"><?= \KKP\View::num($det['setara_segar'] ?? 0, 0); ?></div></div>
    <div class="card kpi"><div class="k">Baris / HS / Negara</div><div class="v"><?= \KKP\View::num($det['baris'] ?? 0); ?> / <?= \KKP\View::num($det['hs_unik'] ?? 0); ?> / <?= \KKP\View::num($det['jumlah_negara'] ?? 0); ?></div></div>
</section>
<div class="card">
    <h2>Breakdown Negara — <?= \KKP\View::e($d['region']); ?></h2>
    <div class="tbl-scroll">
    <table class="tbl">
        <thead><tr><th>#</th><th>Negara</th><th>Baris</th><th>Volume (kg)</th><th>Nilai (USD)</th><th>Share Regional</th></tr></thead>
        <tbody>
        <?php foreach ($d['negara'] as $i => $n): ?>
            <tr>
                <td><?= $i + 1; ?></td>
                <td><?= \KKP\View::e($n['negara']); ?> (<?= \KKP\View::e($n['kode_negara']); ?>)</td>
                <td><?= \KKP\View::num($n['baris']); ?></td>
                <td><?= \KKP\View::num($n['volume_kg'], 0); ?></td>
                <td><?= \KKP\View::num($n['nilai_usd'], 2); ?></td>
                <td><?= $n['share_region_persen'] !== null ? \KKP\View::num($n['share_region_persen'], 2) . '%' : '-'; ?></td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
    </div>
</div>
<?php endif; ?>
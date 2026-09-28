<?php
$exim = $_GET['exim'] ?? 'ekspor';
$mulai = $_GET['mulai'] ?? '';
$akhir = $_GET['akhir'] ?? '';
$by = $_GET['by'] ?? 'asal';
if (!in_array($by, ['asal', 'pelabuhan'], true)) { $by = 'asal'; }
$limit = (int) ($_GET['limit'] ?? 15);
if ($limit < 1 || $limit > 50) { $limit = 15; }
$query = ['exim' => $exim, 'by' => $by, 'limit' => $limit];
if ($mulai) { $query['mulai'] = $mulai; }
if ($akhir) { $query['akhir'] = $akhir; }
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/explore/provinsi?' . http_build_query($query));
    if ($st !== 200) { throw new \RuntimeException(is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal'); }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
$judul = $by === 'asal'
    ? 'Ekspor Provinsi Asal' . ($exim === 'impor' ? ' (Asal Impor)' : '')
    : 'Ekspor Provinsi Pelabuhan Muat/Bongkar';
?>
<h1><?= \KKP\View::e($judul); ?></h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <select name="by">
        <option value="asal" <?= $by === 'asal' ? 'selected' : ''; ?>>Provinsi Asal</option>
        <option value="pelabuhan" <?= $by === 'pelabuhan' ? 'selected' : ''; ?>>Provinsi Pelabuhan</option>
    </select>
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>">
    <input type="number" name="limit" min="1" max="50" value="<?= $limit; ?>">
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>
<?php if ($d): ?>
<section class="kpi-grid">
    <div class="card kpi"><div class="k">Total Nilai (USD)</div><div class="v"><?= \KKP\View::num($d['total_nilai_usd'], 2); ?></div></div>
    <div class="card kpi"><div class="k">Provinsi Terdata</div><div class="v"><?= \KKP\View::num(count($d['provinsi'])); ?></div></div>
</section>
<div class="card">
    <h2>Top Provinsi (<?= \KKP\View::e($by === 'asal' ? 'asal barang' : 'pelabuhan muat/bongkar'); ?>)</h2>
    <table class="tbl">
        <thead><tr><th>#</th><th>Provinsi</th><th>Baris</th><th>HS</th><th>Volume (kg)</th><th>Nilai (USD)</th><th>Harga (USD/kg)</th><th>Share</th></tr></thead>
        <tbody>
        <?php foreach ($d['provinsi'] as $i => $p): ?>
            <tr>
                <td><?= $i + 1; ?></td>
                <td><?= \KKP\View::e($p['provinsi']); ?></td>
                <td><?= \KKP\View::num($p['baris']); ?></td>
                <td><?= \KKP\View::num($p['hs_unik']); ?></td>
                <td><?= \KKP\View::num($p['volume_kg'], 0); ?></td>
                <td><?= \KKP\View::num($p['nilai_usd'], 2); ?></td>
                <td><?= $p['harga_usd_kg'] !== null ? \KKP\View::num($p['harga_usd_kg'], 4) : '-'; ?></td>
                <td><?= $p['share_nilai_persen'] !== null ? \KKP\View::num($p['share_nilai_persen'], 2) . '%' : '-'; ?></td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
</div>
<?php endif; ?>
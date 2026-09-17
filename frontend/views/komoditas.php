<?php
$exim = $_GET['exim'] ?? 'ekspor';
$mulai = $_GET['mulai'] ?? '';
$akhir = $_GET['akhir'] ?? '';
$limit = (int) ($_GET['limit'] ?? 15);
if ($limit < 1 || $limit > 50) { $limit = 15; }
$query = ['exim' => $exim, 'limit' => $limit];
if ($mulai) { $query['mulai'] = $mulai; }
if ($akhir) { $query['akhir'] = $akhir; }
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/explore/komoditas?' . http_build_query($query));
    if ($st !== 200) { throw new \RuntimeException(is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal'); }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Analisis Komoditas</h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>">
    <input type="number" name="limit" min="1" max="50" value="<?= $limit; ?>" title="Limit">
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>
<?php if ($d): ?>
<p class="muted">Total nilai: <strong>USD <?= \KKP\View::num($d['total_nilai_usd'], 2); ?></strong> (<?= $d['limit']; ?> teratas)</p>
<table class="tbl">
    <thead><tr>
        <th>Komoditas</th><th>HS unik</th><th>Baris</th>
        <th>Volume (kg)</th><th>Nilai (USD)</th><th>Harga (USD/kg)</th><th>Share</th>
    </tr></thead>
    <tbody>
    <?php foreach ($d['komoditas'] as $k): ?>
        <tr>
            <td><?= \KKP\View::e($k['komoditas']); ?></td>
            <td><?= \KKP\View::num($k['hs_unik']); ?></td>
            <td><?= \KKP\View::num($k['baris']); ?></td>
            <td><?= \KKP\View::num($k['volume_kg'], 0); ?></td>
            <td><?= \KKP\View::num($k['nilai_usd'], 2); ?></td>
            <td><?= \KKP\View::num($k['harga_usd_kg'], 4); ?></td>
            <td><?= \KKP\View::num($k['share_nilai_persen'], 2); ?>%</td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
<?php endif; ?>
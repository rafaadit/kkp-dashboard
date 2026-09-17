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
    [$st, $d] = $api->get('/api/explore/negara?' . http_build_query($query));
    if ($st !== 200) { throw new \RuntimeException(is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal'); }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Analisis Negara</h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>">
    <input type="number" name="limit" min="1" max="50" value="<?= $limit; ?>">
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>
<?php if ($d): ?>
<section class="grid-2">
    <div class="card">
        <h2>Top Negara (<?= $exim; ?>)</h2>
        <table class="tbl">
            <thead><tr><th>Kode</th><th>Negara</th><th>Volume (kg)</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($d['negara'] as $n): ?>
                <tr>
                    <td><?= \KKP\View::e($n['kode_negara']); ?></td>
                    <td><?= \KKP\View::e($n['negara']); ?></td>
                    <td><?= \KKP\View::num($n['volume_kg'], 0); ?></td>
                    <td><?= \KKP\View::num($n['nilai_usd'], 2); ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <div class="card">
        <h2>Kelompok Negara</h2>
        <table class="tbl">
            <thead><tr><th>Kelompok</th><th>Baris</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($d['kelompok_negara'] as $n): ?>
                <tr>
                    <td><?= \KKP\View::e($n['kelompok_negara'] ?? '(kosong)'); ?></td>
                    <td><?= \KKP\View::num($n['baris']); ?></td>
                    <td><?= \KKP\View::num($n['nilai_usd'], 2); ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>
<?php endif; ?>
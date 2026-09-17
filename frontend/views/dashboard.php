<?php
$exim = $_GET['exim'] ?? 'ekspor';
$mulai = $_GET['mulai'] ?? '';
$akhir = $_GET['akhir'] ?? '';
$query = ['exim' => $exim];
if ($mulai) { $query['mulai'] = $mulai; }
if ($akhir) { $query['akhir'] = $akhir; }
try {
    $api = $session->api();
    [$st, $ov] = $api->get('/api/explore/overview?' . http_build_query($query));
    if ($st !== 200) { throw new \RuntimeException(is_array($ov) ? ($ov['error'] ?? 'gagal') : 'gagal'); }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $ov = null;
}
?>
<h1>Dashboard Ekspor/Impor</h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>" title="Periode awal">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>" title="Periode akhir">
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>

<?php if ($ov): $t = $ov['totals']; ?>
<section class="kpi-grid">
    <div class="card kpi"><div class="k">Nilai (USD)</div><div class="v"><?= \KKP\View::num($t['nilai_usd'], 2); ?></div></div>
    <div class="card kpi"><div class="k">Volume (kg)</div><div class="v"><?= \KKP\View::num($t['volume_kg'], 0); ?></div></div>
    <div class="card kpi"><div class="k">Setara Segar</div><div class="v"><?= \KKP\View::num($t['setara_segar'], 0); ?></div></div>
    <div class="card kpi"><div class="k">Baris / HS / Negara</div><div class="v"><?= \KKP\View::num($t['baris']); ?> / <?= \KKP\View::num($t['hs_unik']); ?> / <?= \KKP\View::num($t['negara_unik']); ?></div></div>
</section>

<section class="grid-2">
    <div class="card">
        <h2>Periode <?= \KKP\View::e(ucfirst($exim)); ?></h2>
        <table class="tbl">
            <thead><tr><th>Periode</th><th>Baris</th><th>Volume (kg)</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($ov['perbulan'] as $p): ?>
                <tr>
                    <td><?= \KKP\View::e($p['periode']); ?></td>
                    <td><?= \KKP\View::num($p['baris']); ?></td>
                    <td><?= \KKP\View::num($p['volume_kg']); ?></td>
                    <td><?= \KKP\View::num($p['nilai_usd'], 2); ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <div class="card">
        <h2>Kelompok Komoditas (Koding)</h2>
        <table class="tbl">
            <thead><tr><th>Kelompok</th><th>Baris</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($ov['kelompok'] as $k): ?>
                <tr>
                    <td><?= \KKP\View::e($k['koding']); ?></td>
                    <td><?= \KKP\View::num($k['baris']); ?></td>
                    <td><?= \KKP\View::num($k['nilai_usd'], 2); ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>
<?php else: ?>
<p class="muted">Tidak ada data / API tidak terjangkau.</p>
<?php endif; ?>
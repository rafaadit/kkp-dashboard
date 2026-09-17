<?php
$exim = $_GET['exim'] ?? 'ekspor';
$a_mulai = $_GET['a_mulai'] ?? '2026-06';
$a_akhir = $_GET['a_akhir'] ?? '2026-06';
$query = ['exim' => $exim, 'periode_a_mulai' => $a_mulai, 'periode_a_akhir' => $a_akhir];
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/explore/perbandingan?' . http_build_query($query));
    if ($st !== 200) { throw new \RuntimeException(is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal'); }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Perbandingan Periode</h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <input type="month" name="a_mulai" value="<?= \KKP\View::e($a_mulai); ?>">
    <input type="month" name="a_akhir" value="<?= \KKP\View::e($a_akhir); ?>">
    <button class="btn btn-primary" type="submit">Bandingkan (B = setahun sebelumnya)</button>
</form>
<?php if ($d): ?>
<section class="grid-3">
    <div class="card kpi">
        <div class="k">Periode A</div>
        <div class="v">USD <?= \KKP\View::num($d['periode_a']['nilai_usd'], 2); ?></div>
        <div class="muted">vol <?= \KKP\View::num($d['periode_a']['volume_kg'], 0); ?> kg</div>
    </div>
    <div class="card kpi">
        <div class="k">Periode B</div>
        <div class="v">USD <?= \KKP\View::num($d['periode_b']['nilai_usd'], 2); ?></div>
        <div class="muted">vol <?= \KKP\View::num($d['periode_b']['volume_kg'], 0); ?> kg</div>
    </div>
    <div class="card kpi <?= ($d['delta']['pertumbuhan_nilai_persen'] ?? 0) >= 0 ? 'pos' : 'neg'; ?>">
        <div class="k">Pertumbuhan Nilai</div>
        <div class="v"><?= \KKP\View::num($d['delta']['pertumbuhan_nilai_persen'] ?? 0, 2); ?>%</div>
        <div class="v">Volume <?= \KKP\View::num($d['delta']['pertumbuhan_volume_persen'] ?? 0, 2); ?>%</div>
    </div>
</section>
<table class="tbl">
    <thead><tr><th></th><th>Periode A</th><th>Periode B</th><th>Delta</th></tr></thead>
    <tbody>
    <?php foreach (['baris', 'nilai_usd', 'volume_kg'] as $m): ?>
        <tr>
            <td><?= $m; ?></td>
            <td><?= \KKP\View::num($d['periode_a'][$m] ?? null, $m === 'baris' ? 0 : 2); ?></td>
            <td><?= \KKP\View::num($d['periode_b'][$m] ?? null, $m === 'baris' ? 0 : 2); ?></td>
            <td><?= \KKP\View::num($d['delta'][$m] ?? null, $m === 'baris' ? 0 : 2); ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
<p class="muted">A: <?= \KKP\View::e($d['periode_a']['mulai']); ?> → <?= \KKP\View::e($d['periode_a']['akhir']); ?><br>B: <?= \KKP\View::e($d['periode_b']['mulai']); ?> → <?= \KKP\View::e($d['periode_b']['akhir']); ?></p>
<?php endif; ?>
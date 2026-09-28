<?php
$mode = $_GET['mode'] ?? 'periode';
$exim = $_GET['exim'] ?? 'ekspor';
$a_mulai = $_GET['a_mulai'] ?? '2026-06';
$a_akhir = $_GET['a_akhir'] ?? '2026-06';
$d = null;
$api_error = null;

if ($mode === 'banding') {
    $b_flow = $_GET['b_flow'] ?? 'ekspor';
    $b_tahun = $_GET['b_tahun'] ?? '2023';
    $b_komoditas = $_GET['b_komoditas'] ?? '';
    $b_negara = $_GET['b_negara'] ?? '';
    $query = ['flow' => $b_flow, 'tahun' => $b_tahun];
    if ($b_komoditas !== '') { $query['komoditas'] = $b_komoditas; }
    if ($b_negara !== '') { $query['negara'] = $b_negara; }
    try {
        [$st, $d] = $session->api()->get('/api/trademap/banding?' . http_build_query($query));
        if ($st !== 200) { throw new \RuntimeException(is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal'); }
    } catch (\Throwable $e) {
        $api_error = $e->getMessage();
        $d = null;
    }
} else {
    $query = ['exim' => $exim, 'periode_a_mulai' => $a_mulai, 'periode_a_akhir' => $a_akhir];
    try {
        [$st, $d] = $session->api()->get('/api/explore/perbandingan?' . http_build_query($query));
        if ($st !== 200) { throw new \RuntimeException(is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal'); }
    } catch (\Throwable $e) {
        $api_error = $e->getMessage();
        $d = null;
    }
}
?>
<h1>Perbandingan Periode</h1>
<nav class="tabs">
    <a class="<?= $mode !== 'banding' ? 'on' : ''; ?>" href="/perbandingan?mode=periode">Periode (BPS)</a>
    <a class="<?= $mode === 'banding' ? 'on' : ''; ?>" href="/perbandingan?mode=banding">BPS vs TradeMap</a>
</nav>

<?php if ($mode === 'banding'): ?>
<h2>BPS vs TradeMap (sisi-ber-sisi)</h2>
<form class="filters" method="get">
    <input type="hidden" name="mode" value="banding">
    <select name="b_flow">
        <option value="ekspor" <?= $b_flow === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $b_flow === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <input type="number" name="b_tahun" min="2020" max="2030" value="<?= \KKP\View::e($b_tahun); ?>">
    <input type="text" name="b_komoditas" placeholder="komoditas mis. Udang" value="<?= \KKP\View::e($b_komoditas); ?>">
    <input type="text" name="b_negara" placeholder="negara (opsional)" value="<?= \KKP\View::e($b_negara); ?>">
    <button class="btn btn-primary" type="submit">Bandingkan</button>
</form>
<?php if ($d): ?>
<ul>
    <?php foreach ($d['catatan'] as $keterangan): ?>
        <li class="muted"><small><?= \KKP\View::e($keterangan); ?></small></li>
    <?php endforeach; ?>
</ul>
<section class="grid-3">
    <div class="card kpi">
        <div class="k">BPS/Bea Cukai — <?= \KKP\View::e($d['flow']); ?></div>
        <div class="v">USD <?= \KKP\View::num($d['bps']['nilai_usd'], 2); ?></div>
        <div class="muted">vol <?= \KKP\View::num($d['bps']['volume_kg'], 0); ?> kg (<?= \KKP\View::num($d['bps']['baris'], 0); ?> baris)</div>
    </div>
    <div class="card kpi">
        <div class="k">TradeMap (ITC) — <?= \KKP\View::e($d['flow']); ?></div>
        <div class="v">USD <?= \KKP\View::num($d['trademap']['nilai_usd'], 2); ?></div>
        <div class="muted"><?= \KKP\View::num($d['trademap']['baris'], 0); ?> baris (nilai ternormalisasi)</div>
    </div>
    <div class="card kpi">
        <div class="k">Cakupan berbeda</div>
        <div class="v muted">lihat tabel banding</div>
    </div>
</section>

<?php if ($d['banding_komoditas']): ?>
<table class="tbl">
    <thead><tr><th>Komoditas</th><th>BPS (USD)</th><th>BPS (kg)</th><th>TradeMap (USD)</th><th>Rasio TM/BPS</th></tr></thead>
    <tbody>
    <?php foreach ($d['banding_komoditas'] as $r): ?>
        <tr>
            <td><?= \KKP\View::e($r['komoditas']); ?></td>
            <td><?= \KKP\View::num($r['bps_nilai_usd'], 2); ?></td>
            <td><?= \KKP\View::num($r['bps_volume_kg'], 0); ?></td>
            <td><?= \KKP\View::num($r['trademap_nilai_usd'], 2); ?></td>
            <td><?= $r['rasio_trademap_bps'] !== null ? \KKP\View::num($r['rasio_trademap_bps'], 2) . 'x' : '-'; ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
<?php else: ?>
<p class="muted">Tidak ada pasangan komoditas yang namanya cocok antara BPS dan TradeMap untuk filter ini.</p>
<?php endif; ?>

<section class="grid-2">
    <div>
        <h3>Komoditas — BPS</h3>
        <table class="tbl">
            <thead><tr><th>Komoditas</th><th>Nilai (USD)</th><th>Volume (kg)</th></tr></thead>
            <tbody>
            <?php foreach ($d['bps']['per_komoditas'] as $r): ?>
                <tr><td><?= \KKP\View::e($r['komoditas']); ?></td>
                    <td><?= \KKP\View::num($r['nilai_usd'], 2); ?></td>
                    <td><?= \KKP\View::num($r['volume_kg'], 0); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <div>
        <h3>Komoditas — TradeMap</h3>
        <table class="tbl">
            <thead><tr><th>Komoditas</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($d['trademap']['per_komoditas'] as $r): ?>
                <tr><td><?= \KKP\View::e($r['komoditas']); ?></td>
                    <td><?= \KKP\View::num($r['nilai_usd'], 2); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>

<?php if ($d['banding_negara']): ?>
<h3>Negara tujuan/asal (pasangan nama cocok)</h3>
<table class="tbl">
    <thead><tr><th>Negara</th><th>BPS (USD)</th><th>BPS (kg)</th><th>TradeMap (USD)</th><th>Rasio TM/BPS</th></tr></thead>
    <tbody>
    <?php foreach ($d['banding_negara'] as $r): ?>
        <tr>
            <td><?= \KKP\View::e($r['negara']); ?></td>
            <td><?= \KKP\View::num($r['bps_nilai_usd'], 2); ?></td>
            <td><?= \KKP\View::num($r['bps_volume_kg'], 0); ?></td>
            <td><?= \KKP\View::num($r['trademap_nilai_usd'], 2); ?></td>
            <td><?= $r['rasio_trademap_bps'] !== null ? \KKP\View::num($r['rasio_trademap_bps'], 2) . 'x' : '-'; ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
<?php endif; ?>
<?php endif; ?>
<?php endif; ?>

<?php if ($mode !== 'banding'): ?>
<form class="filters" method="get">
    <input type="hidden" name="mode" value="periode">
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
<?php endif; ?>
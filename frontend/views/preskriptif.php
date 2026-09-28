<?php
$exim = $_GET['exim'] ?? 'ekspor';
$d = null;
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/explore/preskriptif?exim=' . urlencode($exim));
    if ($st !== 200) {
        $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
        $d = null;
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}

$badge = [
    'pertahankan' => 'badge-blue',
    'ekspansi' => 'badge-green',
    'diversifikasi' => 'badge-amber',
    'evaluasi' => 'badge-red',
];
?>
<h1>Analisis Preskriptif</h1>
<form class="filters" method="get">
    <select name="exim">
        <?php foreach (['ekspor', 'impor'] as $e): ?>
            <option value="<?= $e; ?>" <?= $exim === $e ? 'selected' : ''; ?>><?= ucfirst($e); ?></option>
        <?php endforeach; ?>
    </select>
    <button class="btn btn-primary" type="submit">Hasilkan Rekomendasi</button>
</form>

<?php if ($d): ?>
<?php $m = $d['metrik']; ?>
<section class="kpi-grid">
    <div class="card kpi"><div class="k">CR3 Pasar</div><div class="v"><?= \KKP\View::num($m['cr3_persen'], 1); ?>%</div><div class="muted">konsentrasi 3 pasar teratas</div></div>
    <div class="card kpi <?= $m['hhi_komoditas'] >= 2500 ? 'neg' : ''; ?>"><div class="k">HHI Komoditas</div><div class="v"><?= \KKP\View::num($m['hhi_komoditas'], 0); ?></div><div class="muted"><?= $m['hhi_komoditas'] >= 2500 ? 'terkonsentrasi tinggi' : 'terdiversifikasi'; ?></div></div>
    <div class="card kpi <?= $m['cr5_komoditas_persen'] >= 80 ? 'neg' : ''; ?>"><div class="k">CR5 Komoditas</div><div class="v"><?= \KKP\View::num($m['cr5_komoditas_persen'], 1); ?>%</div><div class="muted">share 5 komoditas teratas</div></div>
</section>

<h2>Rekomendasi</h2>
<?php foreach ($d['rekomendasi'] as $i => $r): ?>
<div class="card reco">
    <span class="badge <?= $badge[$r['kategori']] ?? 'badge-blue'; ?>"><?= \KKP\View::e($r['kategori']); ?></span>
    <strong><?= \KKP\View::e($r['tindakan']); ?></strong> — <span class="target"><?= \KKP\View::e($r['target']); ?></span>
    <div class="muted"><?= \KKP\View::e($r['alasan']); ?></div>
</div>
<?php endforeach; ?>

<section class="grid-2">
    <div class="card">
        <h2>Pasar Momentum (tumbuh)</h2>
        <table class="tbl">
            <thead><tr><th>Pasar</th><th>Nilai (USD)</th><th>Pertumbuhan</th></tr></thead>
            <tbody>
            <?php foreach ($m['momentum'] as $x): ?>
                <tr><td><?= \KKP\View::e($x['negara']); ?></td><td><?= \KKP\View::num($x['nilai_usd'], 2); ?></td><td class="pos">+<?= \KKP\View::num($x['pertumbuhan_persen'], 2); ?>%</td></tr>
            <?php endforeach; ?>
            <?php if (!$m['momentum']): ?><tr><td colspan="3" class="muted">Tidak ada pasar tumbuh signifikan.</td></tr><?php endif; ?>
            </tbody>
        </table>
    </div>
    <div class="card">
        <h2>Pasar Menurun</h2>
        <table class="tbl">
            <thead><tr><th>Pasar</th><th>Nilai (USD)</th><th>Pertumbuhan</th></tr></thead>
            <tbody>
            <?php foreach ($m['penurun'] as $x): ?>
                <tr><td><?= \KKP\View::e($x['negara']); ?></td><td><?= \KKP\View::num($x['nilai_usd'], 2); ?></td><td class="neg"><?= \KKP\View::num($x['pertumbuhan_persen'], 2); ?>%</td></tr>
            <?php endforeach; ?>
            <?php if (!$m['penurun']): ?><tr><td colspan="3" class="muted">Tidak ada pasar menurun.</td></tr><?php endif; ?>
            </tbody>
        </table>
    </div>
</section>

<section class="card">
    <h2>Top 5 Pasar (periode <?= \KKP\View::e($d['ref_periode']['mulai']); ?> – <?= \KKP\View::e($d['ref_periode']['akhir']); ?>)</h2>
    <table class="tbl">
        <thead><tr><th>#</th><th>Pasar</th><th>Nilai (USD)</th><th>Sebelumnya</th><th>Pertumbuhan</th></tr></thead>
        <tbody>
        <?php foreach ($m['top_market'] as $i => $x): ?>
            <tr><td><?= $i + 1; ?></td><td><?= \KKP\View::e($x['negara']); ?></td><td><?= \KKP\View::num($x['nilai_usd'], 2); ?></td>
                <td><?= $x['prev_nilai_usd'] !== null ? \KKP\View::num($x['prev_nilai_usd'], 2) : '-'; ?></td>
                <td class="<?= ($x['pertumbuhan_persen'] ?? 0) >= 0 ? 'pos' : 'neg'; ?>"><?= $x['pertumbuhan_persen'] !== null ? \KKP\View::num($x['pertumbuhan_persen'], 2) . '%' : '-'; ?></td></tr>
        <?php endforeach; ?>
        </tbody>
    </table>
</section>
<?php endif; ?>
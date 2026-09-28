<?php
$exim = $_GET['exim'] ?? 'ekspor';
$mulai = $_GET['mulai'] ?? '';
$akhir = $_GET['akhir'] ?? '';
$komoditas = trim($_GET['komoditas'] ?? '');
$negara = strtoupper(trim($_GET['negara'] ?? ''));
$horizon = (int) ($_GET['horizon'] ?? 6);
if ($horizon < 1) { $horizon = 1; }
if ($horizon > 12) { $horizon = 12; }

$query = ['exim' => $exim, 'horizon' => $horizon];
if ($mulai) { $query['mulai'] = $mulai; }
if ($akhir) { $query['akhir'] = $akhir; }
if ($komoditas !== '') { $query['komoditas'] = $komoditas; }
if ($negara !== '') { $query['negara'] = $negara; }

$d = null;
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/explore/prediktif?' . http_build_query($query));
    if ($st !== 200) {
        $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
        $d = null;
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Analisis Prediktif (Proyeksi Tren)</h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <input type="text" name="komoditas" placeholder="Komoditas (opsional)" value="<?= \KKP\View::e($komoditas); ?>">
    <input type="text" name="negara" placeholder="Negara (opsional)" value="<?= \KKP\View::e($negara); ?>">
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>">
    <select name="horizon">
        <?php for ($h = 1; $h <= 12; $h++): ?>
            <option value="<?= $h; ?>" <?= $horizon === $h ? 'selected' : ''; ?>><?= $h; ?> bulan</option>
        <?php endfor; ?>
    </select>
    <button class="btn btn-primary" type="submit">Proyeksikan</button>
</form>

<?php if ($d && $d['metrik'] !== null): $m = $d['metrik']; ?>
<section class="kpi-grid">
    <div class="card kpi"><div class="k">Tren</div><div class="v <?= $m['label_tren'] === 'naik' ? 'pos' : ($m['label_tren'] === 'turun' ? 'neg' : ''); ?>"><?= \KKP\View::e(ucfirst($m['label_tren'])); ?></div><div class="muted">slope <?= \KKP\View::num($m['slope_per_bulan_usd'], 2); ?> USD/bulan</div></div>
    <div class="card kpi"><div class="k">Fit (R²)</div><div class="v"><?= \KKP\View::num($m['r2'], 4); ?></div><div class="muted">kualitas garis tren (0–1)</div></div>
    <div class="card kpi"><div class="k">Rata-rata 3 Bulan</div><div class="v"><?= \KKP\View::num($m['rata_rata_3_bulan'], 2); ?></div><div class="muted">basis proyeksi MA</div></div>
    <div class="card kpi"><div class="k">Proyeksi akhir vs terakhir</div><div class="v"><?= $m['atas_nilai_terakhir'] !== null ? \KKP\View::num($m['atas_nilai_terakhir'], 2) . '%' : '-'; ?></div><div class="muted">linear vs nilai bulan terakhir</div></div>
</section>

<section class="grid-2">
    <div class="card">
        <h2>Seri Aktual (<?= \KKP\View::e($exim); ?>)</h2>
        <div class="tbl-scroll">
        <table class="tbl">
            <thead><tr><th>Periode</th><th>Baris</th><th>Volume (kg)</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($d['series'] as $r): ?>
                <tr><td><?= \KKP\View::e($r['periode']); ?></td><td><?= \KKP\View::num($r['baris']); ?></td><td><?= \KKP\View::num($r['volume_kg'], 0); ?></td><td><?= \KKP\View::num($r['nilai_usd'], 2); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
        </div>
    </div>
    <div class="card">
        <h2>Proyeksi <?= $horizon; ?> Bulan ke Depan</h2>
        <div class="tbl-scroll">
        <table class="tbl">
            <thead><tr><th>Periode</th><th>Linear</th><th>Naive</th><th>MA-3</th></tr></thead>
            <tbody>
            <?php foreach ($d['forecast'] as $f): ?>
                <tr>
                    <td><strong><?= \KKP\View::e($f['periode']); ?></strong></td>
                    <td><?= \KKP\View::num($f['linear'], 2); ?></td>
                    <td><?= \KKP\View::num($f['naive'], 2); ?></td>
                    <td><?= $f['ma3'] !== null ? \KKP\View::num($f['ma3'], 2) : '-'; ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
        </div>
    </div>
</section>
<p class="muted">Catatan: proyeksi dari tren linear least-squares, naive (nilai terakhir), dan rata-rata 3 bulan. Estimasi indikatif, bukan pengganti analisis resmi.</p>
<?php elseif ($d): ?>
<p class="muted">Data terlalu sedikit (< 2 periode) untuk proyeksi.</p>
<?php endif; ?>
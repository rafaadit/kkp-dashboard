<?php
$exim = $_GET['exim'] ?? 'ekspor';
$a = strtoupper(trim($_GET['negara_a'] ?? ''));
$b = strtoupper(trim($_GET['negara_b'] ?? ''));
$mulai = $_GET['mulai'] ?? '';
$akhir = $_GET['akhir'] ?? '';

$negara = [];
try {
    $api = $session->api();
    [$st, $nl] = $api->get('/api/explore/negara_list?exim=' . $exim);
    if ($st === 200 && is_array($nl) && isset($nl['negara'])) {
        $negara = $nl['negara'];
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
}

$d = null;
if ($a !== '' && $b !== '') {
    $query = ['exim' => $exim, 'negara_a' => $a, 'negara_b' => $b];
    if ($mulai) { $query['mulai'] = $mulai; }
    if ($akhir) { $query['akhir'] = $akhir; }
    try {
        [$st, $d] = $api->get('/api/explore/country_compare?' . http_build_query($query));
        if ($st !== 200) {
            $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
            $d = null;
        }
    } catch (\Throwable $e) {
        $api_error = $e->getMessage();
        $d = null;
    }
}
$judul = $exim === 'ekspor' ? 'Country Compare — Ekspor RI ke 2 Negara' : 'Country Compare — Impor RI dari 2 Negara';
?>
<h1><?= \KKP\View::e($judul); ?></h1>
<form class="filters" method="get">
    <select name="exim" onchange="this.form.submit()">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <select name="negara_a" required>
        <option value="">— Negara A —</option>
        <?php foreach ($negara as $n): ?>
            <option value="<?= \KKP\View::e($n['kode_negara']); ?>" <?= $a === $n['kode_negara'] ? 'selected' : ''; ?>><?= KKP\View::e($n['negara']); ?> (<?= \KKP\View::e($n['kode_negara']); ?>)</option>
        <?php endforeach; ?>
    </select>
    <select name="negara_b" required>
        <option value="">— Negara B —</option>
        <?php foreach ($negara as $n): ?>
            <option value="<?= \KKP\View::e($n['kode_negara']); ?>" <?= $b === $n['kode_negara'] ? 'selected' : ''; ?>><?= KKP\View::e($n['negara']); ?> (<?= \KKP\View::e($n['kode_negara']); ?>)</option>
        <?php endforeach; ?>
    </select>
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>">
    <button class="btn btn-primary" type="submit">Bandingkan</button>
</form>

<?php if ($d): $xa = $d['negara_a']; $xb = $d['negara_b']; ?>
<section class="grid-2">
    <div class="card kpi">
        <div class="k"><?= \KKP\View::e($xa['negara']); ?> — Nilai</div>
        <div class="v"><?= \KKP\View::num($xa['nilai_usd'], 2); ?></div>
        <div class="muted">Share <?= $xa['share_nilai_persen'] !== null ? \KKP\View::num($xa['share_nilai_persen'], 2) . '%' : '-'; ?> · <?= \KKP\View::num($xa['baris']); ?> baris · <?= \KKP\View::num($xa['hs_unik']); ?> HS · Volume <?= \KKP\View::num($xa['volume_kg'], 0); ?> kg</div>
    </div>
    <div class="card kpi">
        <div class="k"><?= \KKP\View::e($xb['negara']); ?> — Nilai</div>
        <div class="v"><?= \KKP\View::num($xb['nilai_usd'], 2); ?></div>
        <div class="muted">Share <?= $xb['share_nilai_persen'] !== null ? \KKP\View::num($xb['share_nilai_persen'], 2) . '%' : '-'; ?> · <?= \KKP\View::num($xb['baris']); ?> baris · <?= \KKP\View::num($xb['hs_unik']); ?> HS · Volume <?= \KKP\View::num($xb['volume_kg'], 0); ?> kg</div>
    </div>
</section>
<div class="card">
    <h2>Selisih Nilai A − B</h2>
    <p class="<?= $d['selisih_nilai_usd'] >= 0 ? '' : 'muted'; ?>">
        <strong class="<?= $d['selisih_nilai_usd'] >= 0 ? 'pos' : 'neg'; ?>"><?= \KKP\View::num(abs($d['selisih_nilai_usd']), 2); ?> USD</strong>
        <?= $d['selisih_nilai_usd'] >= 0 ? '(negara A unggul)' : '(negara B unggul)'; ?>
    </p>
</div>
<section class="grid-2">
    <div class="card">
        <h2>Top Komoditas — <?= \KKP\View::e($xa['negara']); ?></h2>
        <table class="tbl">
            <thead><tr><th>Komoditas</th><th>Volume (kg)</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($xa['top_komoditas'] as $k): ?>
                <tr><td><?= \KKP\View::e($k['komoditas']); ?></td><td><?= \KKP\View::num($k['volume_kg'], 0); ?></td><td><?= \KKP\View::num($k['nilai_usd'], 2); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <div class="card">
        <h2>Top Komoditas — <?= \KKP\View::e($xb['negara']); ?></h2>
        <table class="tbl">
            <thead><tr><th>Komoditas</th><th>Volume (kg)</th><th>Nilai (USD)</th></tr></thead>
            <tbody>
            <?php foreach ($xb['top_komoditas'] as $k): ?>
                <tr><td><?= \KKP\View::e($k['komoditas']); ?></td><td><?= \KKP\View::num($k['volume_kg'], 0); ?></td><td><?= \KKP\View::num($k['nilai_usd'], 2); ?></td></tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>
<div class="card">
    <h2>Tren Nilai per Periode</h2>
    <div class="tbl-scroll">
    <table class="tbl">
        <thead><tr><th>Periode</th><th><?= \KKP\View::e($xa['negara']); ?> (USD)</th><th><?= \KKP\View::e($xb['negara']); ?> (USD)</th></tr></thead>
        <tbody>
        <?php foreach ($d['per_bulan'] as $r): ?>
            <tr>
                <td><?= \KKP\View::e($r['periode']); ?></td>
                <td><?= $r['a'] ? \KKP\View::num($r['a']['nilai_usd'], 2) : '-'; ?></td>
                <td><?= $r['b'] ? \KKP\View::num($r['b']['nilai_usd'], 2) : '-'; ?></td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
    </div>
</div>
<?php endif; ?>
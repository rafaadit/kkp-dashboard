<?php
$exim = $_GET['exim'] ?? 'ekspor';
$d = null;
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/explore/potensi?exim=' . urlencode($exim));
    if ($st !== 200) {
        $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
        $d = null;
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Potensi Ekspor &amp; Pangsa Pasar</h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>

<?php if ($d): ?>
<p class="muted">Jendela analisis: <strong><?= \KKP\View::e($d['ref_periode']['mulai'] ?? '-'); ?></strong> s.d. <strong><?= \KKP\View::e($d['ref_periode']['akhir'] ?? '-'); ?></strong>, dibandingkan jendela sebelumnya (<strong><?= \KKP\View::e($d['prev_periode'] ?? '-'); ?></strong>).</p>

<?php if ($d['momentum']): ?>
<div class="card">
    <h2>Momentum Pasar (Potensi) — <?= \KKP\View::e($exim); ?></h2>
    <div class="tbl-scroll">
    <table class="tbl">
        <thead><tr><th>#</th><th>Negara</th><th>Nilai (USD)</th><th>Sebelumnya</th><th>Pertumbuhan</th><th>Komoditas Momentum</th></tr></thead>
        <tbody>
        <?php foreach ($d['momentum'] as $i => $m): ?>
            <tr>
                <td><?= $i + 1; ?></td>
                <td><?= \KKP\View::e($m['negara']); ?> (<?= \KKP\View::e($m['kode_negara']); ?>)</td>
                <td><?= \KKP\View::num($m['nilai_usd'], 2); ?></td>
                <td><?= \KKP\View::num($m['prev_nilai_usd'], 2); ?></td>
                <td class="pos">+<?= \KKP\View::num($m['pertumbuhan_persen'], 2); ?>%</td>
                <td>
                    <?php foreach ($m['komoditas_momentum'] ?? [] as $k): ?>
                        <span class="badge ok" title="+<?= \KKP\View::num($k['pertumbuhan_persen'], 2); ?>%"><?= \KKP\View::e($k['komoditas']); ?></span>
                    <?php endforeach; ?>
                </td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
    </div>
</div>
<?php endif; ?>

<div class="card">
    <h2>Top Pasar (<?= \KKP\View::e($d['ref_periode']['mulai'] ?? '-'); ?> s.d. <?= \KKP\View::e($d['ref_periode']['akhir'] ?? '-'); ?>)</h2>
    <div class="tbl-scroll">
    <table class="tbl">
        <thead><tr><th>#</th><th>Negara</th><th>Nilai (USD)</th><th>Sebelumnya</th><th>Pertumbuhan</th></tr></thead>
        <tbody>
        <?php foreach ($d['top_market'] as $i => $m): ?>
            <tr>
                <td><?= $i + 1; ?></td>
                <td><?= \KKP\View::e($m['negara']); ?> (<?= \KKP\View::e($m['kode_negara']); ?>)</td>
                <td><?= \KKP\View::num($m['nilai_usd'], 2); ?></td>
                <td><?= $m['prev_nilai_usd'] !== null ? \KKP\View::num($m['prev_nilai_usd'], 2) : '-'; ?></td>
                <td class="<?= ($m['pertumbuhan_persen'] ?? 0) >= 0 ? 'pos' : 'neg'; ?>"><?= $m['pertumbuhan_persen'] !== null ? \KKP\View::num($m['pertumbuhan_persen'], 2) . '%' : '-'; ?></td>
            </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
    </div>
</div>

<div class="card">
    <h2>Pangsa Pasar — Snapshot TradeMap (data tersedia)</h2>
    <?php if ($d['trademap']): ?>
    <section class="grid-2">
        <div>
            <h3 class="muted" style="text-transform:uppercase;font-size:12px;">Nilai per Tahun</h3>
            <table class="tbl">
                <thead><tr><th>Tahun</th><th>Baris</th><th>Nilai (USD)</th></tr></thead>
                <tbody>
                <?php foreach ($d['trademap']['per_tahun'] as $t): ?>
                    <tr><td><?= \KKP\View::num($t['tahun']); ?></td><td><?= \KKP\View::num($t['baris']); ?></td><td><?= \KKP\View::num($t['nilai_usd'], 2); ?></td></tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
        <div>
            <h3 class="muted" style="text-transform:uppercase;font-size:12px;">Mitra (share dalam cakupan data)</h3>
            <table class="tbl">
                <thead><tr><th>Mitra</th><th>Nilai (USD)</th><th>Share</th></tr></thead>
                <tbody>
                <?php foreach ($d['trademap']['per_partner'] as $p): ?>
                    <tr><td><?= \KKP\View::e($p['nama_partner']); ?></td><td><?= \KKP\View::num($p['nilai_usd'], 2); ?></td><td><?= $p['share_persen'] !== null ? \KKP\View::num($p['share_persen'], 2) . '%' : '-'; ?></td></tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    </section>
    <p class="muted">Total tersedia: <?= \KKP\View::num($d['trademap']['total_usd'], 2); ?> USD.</p>
    <?php else: ?>
    <p class="muted">Belum ada data TradeMap dunia. Isi <code>TRADEMAP_API_KEY</code> di <code>.env</code> lalu jalankan robot unduhan TradeMap untuk pangsa pasar global riil.</p>
    <?php endif; ?>
</div>
<p class="muted">Catatan: momentum & potensi bersifat indikatif (tren 6 bulan terakhir data riil BPS); pangsa pasar dari cakupan data TradeMap yang tersedia saat ini.</p>
<?php endif; ?>
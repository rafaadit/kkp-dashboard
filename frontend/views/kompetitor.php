<?php
$d = null;
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/explore/kompetitor_scope');
    if ($st !== 200) {
        $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
        $d = null;
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Profil Kompetitor &amp; Lanskap Persaingan</h1>

<section class="card note-warn">
    <h2>Data yang masih dibutuhkan</h2>
    <ul>
        <?php foreach ($d['sumber_kompetitor'] ?? [] as $s): ?>
            <li><?= \KKP\View::e($s); ?></li>
        <?php endforeach; ?>
    </ul>
    <p class="muted">Fitur ini aktif penuh bila `TRADEMAP_API_KEY` terisi dan robot unduhan berhasil
        menarik impor dunia per negara-penjual. Di bawah adalah cakupan data yang ada sekarang.</p>
</section>

<?php if ($d): ?>
<section class="card">
    <h2>Mitra Ekspor RI (TradeMap, data tersedia)</h2>
    <table class="tbl">
        <thead><tr><th>Mitra</th><th>Nilai (USD)</th></tr></thead>
        <tbody>
        <?php foreach (($d['partner_ekspor_id'] ?? []) as $p): ?>
            <tr><td><?= \KKP\View::e($p['nama_partner']); ?></td><td><?= \KKP\View::num($p['nilai_usd'], 2); ?></td></tr>
        <?php endforeach; ?>
        <?php if (empty($d['partner_ekspor_id'])): ?><tr><td colspan="2" class="muted">Belum ada baris TradeMap ekspor RI.</td></tr><?php endif; ?>
        </tbody>
    </table>
</section>

<section class="card">
    <h2>Cakupan Tabel TradeMap</h2>
    <table class="tbl">
        <thead><tr><th>Reporter</th><th>Flow</th><th>HS</th><th>Tahun</th><th>Baris</th><th>Nilai (USD)</th></tr></thead>
        <tbody>
        <?php foreach (($d['cakupan_trademap'] ?? []) as $c): ?>
            <tr><td><?= \KKP\View::e($c['reporter']); ?></td><td><?= \KKP\View::e($c['flow']); ?></td><td><?= \KKP\View::e($c['hs']); ?></td>
                <td><?= \KKP\View::num($c['tahun']); ?></td><td><?= \KKP\View::num($c['baris']); ?></td><td><?= \KKP\View::num($c['nilai_usd'], 2); ?></td></tr>
        <?php endforeach; ?>
        <?php if (empty($d['cakupan_trademap'])): ?><tr><td colspan="6" class="muted">Belum ada data TradeMap.</td></tr><?php endif; ?>
        </tbody>
    </table>
</section>
<?php endif; ?>
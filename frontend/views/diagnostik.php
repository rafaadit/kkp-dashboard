<?php
$exim = $_GET['exim'] ?? 'ekspor';
$mulai = $_GET['mulai'] ?? '';
$akhir = $_GET['akhir'] ?? '';
$query = ['exim' => $exim];
if ($mulai) { $query['mulai'] = $mulai; }
if ($akhir) { $query['akhir'] = $akhir; }
$d = null;
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/explore/diagnostik?' . http_build_query($query));
    if ($st !== 200) {
        $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
        $d = null;
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Analisis Diagnostik</h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>">
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>

<?php if ($d): $t = $d['totals']; $m = $d['metrik']; ?>
<section class="kpi-grid">
    <div class="card kpi"><div class="k">Nilai (USD)</div><div class="v"><?= \KKP\View::num($t['nilai_usd'], 2); ?></div><div class="muted"><?= $t['baris']; ?> baris · <?= $t['hs_unik']; ?> HS · <?= $t['komoditas_unik']; ?> komoditas · <?= $t['negara_unik']; ?> negara</div></div>
    <div class="card kpi"><div class="k">HHI Komoditas</div><div class="v"><?= \KKP\View::num($m['hhi_komoditas']); ?></div><div class="muted"><?= \KKP\View::e($m['label_hhi']); ?></div></div>
    <div class="card kpi"><div class="k">CR5 Komoditas</div><div class="v"><?= $m['konsentrasi_komoditas_cr5'] !== null ? \KKP\View::num($m['konsentrasi_komoditas_cr5'], 2) . '%' : '-'; ?></div><div class="muted">share 5 komoditas teratas</div></div>
    <div class="card kpi"><div class="k">CR3 Negara</div><div class="v"><?= $m['ketergantungan_negara_cr3'] !== null ? \KKP\View::num($m['ketergantungan_negara_cr3'], 2) . '%' : '-'; ?></div><div class="muted">ketergantungan 3 pasar teratas</div></div>
    <div class="card kpi"><div class="k">Pareto 80%</div><div class="v"><?= \KKP\View::num($m['komoditas_80_persen']); ?> komoditas</div><div class="muted">menyumbang 80% nilai</div></div>
</section>

<section class="grid-2">
    <div class="card">
        <h2>Konsentrasi Komoditas (<?= \KKP\View::e($exim); ?>)</h2>
        <table class="tbl">
            <thead><tr><th>Komoditas</th><th>Nilai (USD)</th><th>Share</th><th>Kumulatif</th></tr></thead>
            <tbody>
            <?php foreach ($d['top_komoditas'] as $k): ?>
                <tr>
                    <td><?= \KKP\View::e($k['komoditas']); ?></td>
                    <td><?= \KKP\View::num($k['nilai_usd'], 2); ?></td>
                    <td><?= $k['share_nilai_persen'] !== null ? \KKP\View::num($k['share_nilai_persen'], 2) . '%' : '-'; ?></td>
                    <td><?= $k['kumulatif_persen'] !== null ? \KKP\View::num($k['kumulatif_persen'], 2) . '%' : '-'; ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <div class="card">
        <h2>Ketergantungan Negara</h2>
        <table class="tbl">
            <thead><tr><th>Negara</th><th>Nilai (USD)</th><th>Share</th></tr></thead>
            <tbody>
            <?php foreach ($d['top_negara'] as $n): ?>
                <tr>
                    <td><?= \KKP\View::e($n['negara']); ?> (<?= \KKP\View::e($n['kode_negara']); ?>)</td>
                    <td><?= \KKP\View::num($n['nilai_usd'], 2); ?></td>
                    <td><?= $n['share_nilai_persen'] !== null ? \KKP\View::num($n['share_nilai_persen'], 2) . '%' : '-'; ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>
<p class="muted">Catatan: HHI = Herfindahl–Hirschman Index (0–10000). Diagnostik dihitung dari data riil BPS (raw_exim).</p>
<?php endif; ?>
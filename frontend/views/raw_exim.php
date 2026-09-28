<?php
$exim = $_GET['exim'] ?? 'ekspor';
$mulai = $_GET['mulai'] ?? '';
$akhir = $_GET['akhir'] ?? '';
$status = $_GET['status'] ?? '';
$q = $_GET['q'] ?? '';
$page = max(1, (int) ($_GET['page'] ?? 1));
$limit = (int) ($_GET['limit'] ?? 25);
if ($limit < 1 || $limit > 200) { $limit = 25; }

$query = ['exim' => $exim, 'page' => $page, 'limit' => $limit];
if ($mulai) { $query['mulai'] = $mulai; }
if ($akhir) { $query['akhir'] = $akhir; }
if ($status) { $query['status'] = $status; }
if ($q) { $query['komoditas'] = $q; }
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/data/raw_exim?' . http_build_query($query));
    if ($st !== 200) { throw new \RuntimeException(is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal'); }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Data RAW EXIM</h1>
<form class="filters" method="get">
    <select name="exim">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
    </select>
    <input type="month" name="mulai" value="<?= \KKP\View::e($mulai); ?>">
    <input type="month" name="akhir" value="<?= \KKP\View::e($akhir); ?>">
    <input type="text" name="q" value="<?= \KKP\View::e($q); ?>" placeholder="cari komoditas">
    <select name="status">
        <option value="">Semua status</option>
        <option value="ready" <?= $status === 'ready' ? 'selected' : ''; ?>>ready</option>
        <option value="needs_validation" <?= $status === 'needs_validation' ? 'selected' : ''; ?>>needs_validation</option>
    </select>
    <button class="btn btn-primary" type="submit">Cari</button>
</form>
<?php if ($d): $total = (int) $d['total']; $pages = (int) $d['pages']; ?>
<p class="muted">Total <?= \KKP\View::num($total); ?> baris · halaman <?= $page; ?>/<?= \KKP\View::num($pages); ?></p>
<div class="tbl-scroll">
<table class="tbl tbl-wide">
    <thead><tr>
        <th>ID</th><th>Status</th><th>Exim</th><th>Periode</th>
        <th>HS</th><th>HS 2dg</th>
        <th>Komoditas</th><th>Jenis</th><th>Bentuk</th><th>Bentuk (EN)</th><th>Pengolahan</th>
        <th>Uraian</th>
        <th>Konsumsi/K</th><th>Olahan</th><th>Asal Bahan Baku</th>
        <th>Kode Prov Asal</th><th>Provinsi Asal</th><th>Pulau Prov Asal</th>
        <th>Kode Pelabuhan</th><th>Pelabuhan Muat/Bongkar</th><th>Moda</th>
        <th>Kode Prov Pelabuhan</th><th>Provinsi Pelabuhan</th><th>Pulau Prov Pelabuhan</th>
        <th>Kode Negara</th><th>Negara</th><th>Kelompok Negara</th>
        <th>Vol (kg)</th><th>Nilai USD</th><th>Harga USD/kg</th>
        <th>TTC</th><th>Rendemen</th><th>Setara Segar</th><th>Koding</th>
        <th>Kurs USD</th><th>Nilai Rp</th>
    </tr></thead>
    <tbody>
    <?php foreach ($d['rows'] as $r): ?>
        <tr>
            <td><?= \KKP\View::num($r['id']); ?></td>
            <td><span class="badge <?= ($r['status'] ?? '') === 'ready' ? 'ok' : 'warn'; ?>"><?= \KKP\View::e($r['status'] ?? '-'); ?></span></td>
            <td><?= \KKP\View::e($r['exim_type']); ?></td>
            <td><?= \KKP\View::e($r['periode']); ?></td>
            <td><?= \KKP\View::e($r['kode_hs']); ?></td>
            <td><?= \KKP\View::e($r['kode_hs_2dg']); ?></td>
            <td><?= \KKP\View::e($r['komoditas']); ?></td>
            <td><?= \KKP\View::e($r['jenis']); ?></td>
            <td><?= \KKP\View::e($r['bentuk']); ?></td>
            <td><?= \KKP\View::e($r['bentuk_en']); ?></td>
            <td><?= \KKP\View::e($r['pengolahan']); ?></td>
            <td><?= \KKP\View::e($r['uraian']); ?></td>
            <td><?= \KKP\View::e($r['non_konsumsi_konsumsi']); ?></td>
            <td><?= \KKP\View::e($r['olahan_bukan']); ?></td>
            <td><?= \KKP\View::e($r['asalbahanbaku']); ?></td>
            <td><?= \KKP\View::e($r['kode_prov_asal']); ?></td>
            <td><?= \KKP\View::e($r['provinsi_asal']); ?></td>
            <td><?= \KKP\View::e($r['pulau_prov_asal']); ?></td>
            <td><?= \KKP\View::e($r['kode_pelabuhan_muat']); ?></td>
            <td><?= \KKP\View::e($r['pelabuhan_muat_bongkar']); ?></td>
            <td><?= \KKP\View::e($r['moda']); ?></td>
            <td><?= \KKP\View::e($r['kode_provinsi_pelabuhan']); ?></td>
            <td><?= \KKP\View::e($r['provinsi_pelabuhan']); ?></td>
            <td><?= \KKP\View::e($r['pulau_prov_pelabuhan']); ?></td>
            <td><?= \KKP\View::e($r['kode_negara']); ?></td>
            <td><?= \KKP\View::e($r['negara']); ?></td>
            <td><?= \KKP\View::e($r['kelompok_negara']); ?></td>
            <td class="num"><?= \KKP\View::num($r['vol_kg'], 2); ?></td>
            <td class="num"><?= \KKP\View::num($r['nil_usd'], 2); ?></td>
            <td class="num"><?= $r['harga_usd_kg'] !== null ? \KKP\View::num($r['harga_usd_kg'], 4) : '-'; ?></td>
            <td><?= \KKP\View::e($r['ttc']); ?></td>
            <td><?= $r['rendemen'] !== null ? \KKP\View::e((string) $r['rendemen']) : '-'; ?></td>
            <td class="num"><?= $r['setara_segar'] !== null ? \KKP\View::num($r['setara_segar'], 2) : '-'; ?></td>
            <td><?= \KKP\View::e($r['koding']); ?></td>
            <td class="num"><?= $r['kurs_usd'] !== null ? \KKP\View::num($r['kurs_usd'], 4) : '-'; ?></td>
            <td class="num"><?= $r['nilai_rp'] !== null ? \KKP\View::num($r['nilai_rp'], 2) : '-'; ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
</div>
<?php if ($pages > 1): ?>
<div class="pager">
    <?php if ($page > 1): ?><a class="btn" href="?<?= http_build_query(array_merge($query, ['page' => $page - 1])); ?>">&laquo; Prev</a><?php endif; ?>
    <span>Hal <?= $page; ?> / <?= $pages; ?></span>
    <?php if ($page < $pages): ?><a class="btn" href="?<?= http_build_query(array_merge($query, ['page' => $page + 1])); ?>">Next &raquo;</a><?php endif; ?>
</div>
<?php endif; ?>
<?php endif; ?>
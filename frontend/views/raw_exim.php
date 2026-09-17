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
<table class="tbl">
    <thead><tr>
        <th>ID</th><th>Periode</th><th>HS</th><th>Komoditas</th>
        <th>Negara</th><th>Pelabuhan</th><th>Vol (kg)</th><th>Nilai USD</th>
        <th>Koding</th><th>Status</th>
    </tr></thead>
    <tbody>
    <?php foreach ($d['rows'] as $r): ?>
        <tr>
            <td><?= \KKP\View::num($r['id']); ?></td>
            <td><?= \KKP\View::e($r['periode']); ?></td>
            <td><?= \KKP\View::e($r['kode_hs']); ?></td>
            <td><?= \KKP\View::e($r['komoditas']); ?></td>
            <td><?= \KKP\View::e($r['kode_negara']); ?></td>
            <td><?= \KKP\View::e($r['pelabuhan_muat_bongkar']); ?></td>
            <td><?= \KKP\View::num($r['vol_kg'], 2); ?></td>
            <td><?= \KKP\View::num($r['nil_usd'], 2); ?></td>
            <td><?= \KKP\View::e($r['koding']); ?></td>
            <td><span class="badge <?= $r['status'] === 'ready' ? 'ok' : 'warn'; ?>"><?= \KKP\View::e($r['status']); ?></span></td>
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
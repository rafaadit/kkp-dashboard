<?php
$product = $_GET['product_code'] ?? '';
$partner = $_GET['partner'] ?? '';
$year_min = $_GET['year_min'] ?? '';
$year_max = $_GET['year_max'] ?? '';
$page = max(1, (int) ($_GET['page'] ?? 1));
$limit = (int) ($_GET['limit'] ?? 25);
if ($limit < 1 || $limit > 200) { $limit = 25; }

$query = ['page' => $page, 'limit' => $limit];
foreach (['product_code' => $product, 'partner' => $partner, 'year_min' => $year_min, 'year_max' => $year_max] as $k => $v) {
    if ($v !== '') { $query[$k] = $v; }
}
try {
    $api = $session->api();
    [$s1, $sum] = $api->get('/api/trademap/summary?' . http_build_query($query));
    [$s2, $rows] = $api->get('/api/trademap/rows?' . http_build_query($query));
    if ($s1 !== 200 || $s2 !== 200) {
        throw new \RuntimeException(is_array($sum) ? ($sum['error'] ?? 'gagal') : 'gagal');
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $sum = $rows = null;
}
?>
<h1>TradeMap (ITC)</h1>
<?php if ($sum && ($sum['totals']['baris'] ?? 0) == 0): ?>
<div class="alert alert-danger">Belum ada data TradeMap. Import file export ITC via
<code>python3 database/scripts/import_trademap.py &lt;file.csv|xlsx&gt; --commit</code>.</div>
<?php endif; ?>
<form class="filters" method="get">
    <input type="text" name="product_code" value="<?= \KKP\View::e($product); ?>" placeholder="kode produk (HS)">
    <input type="text" name="partner" value="<?= \KKP\View::e($partner); ?>" placeholder="partner (ISO)">
    <input type="number" name="year_min" value="<?= \KKP\View::e($year_min); ?>" placeholder="tahun dari" style="width:110px">
    <input type="number" name="year_max" value="<?= \KKP\View::e($year_max); ?>" placeholder="tahun s/d" style="width:110px">
    <button class="btn btn-primary" type="submit">Filter</button>
</form>

<?php if ($sum): $t = $sum['totals']; ?>
<section class="kpi-grid">
    <div class="card kpi"><div class="k">Total Nilai (USD ribu)</div><div class="v"><?= \KKP\View::num($t['nilai_usd'], 0); ?></div></div>
    <div class="card kpi"><div class="k">Total Qty</div><div class="v"><?= \KKP\View::num($t['qty'], 0); ?></div></div>
    <div class="card kpi"><div class="k">Baris</div><div class="v"><?= \KKP\View::num($t['baris']); ?></div></div>
    <div class="card kpi"><div class="k">Partner / Produk</div><div class="v"><?= \KKP\View::num($t['partner_unik']); ?> / <?= \KKP\View::num($t['produk_unik']); ?></div></div>
</section>
<section class="grid-2">
    <div class="card">
        <h2>Top Partner</h2>
        <table class="tbl">
            <thead><tr><th>Partner</th><th>Nilai (USD ribu)</th><th>Qty</th></tr></thead>
            <tbody><?php foreach ($sum['top_partner'] as $p): ?>
                <tr><td><?= \KKP\View::e($p['partner']); ?></td><td><?= \KKP\View::num($p['nilai_usd'], 0); ?></td><td><?= \KKP\View::num($p['qty'], 0); ?></td></tr>
            <?php endforeach; ?></tbody>
        </table>
    </div>
    <div class="card">
        <h2>Top Produk</h2>
        <table class="tbl">
            <thead><tr><th>HS</th><th>Deskripsi</th><th>Nilai (USD ribu)</th></tr></thead>
            <tbody><?php foreach ($sum['top_produk'] as $p): ?>
                <tr><td><?= \KKP\View::e($p['product_code']); ?></td><td><?= \KKP\View::e($p['product_desc']); ?></td><td><?= \KKP\View::num($p['nilai_usd'], 0); ?></td></tr>
            <?php endforeach; ?></tbody>
        </table>
    </div>
</section>
<?php endif; ?>

<?php if ($rows && ($rows['total'] ?? 0) > 0): $total = (int) $rows['total']; $pages = (int) $rows['pages']; ?>
<h2>Data</h2>
<p class="muted">Total <?= \KKP\View::num($total); ?> baris · halaman <?= $page; ?>/<?= \KKP\View::num($pages); ?></p>
<div class="tbl-scroll">
<table class="tbl">
    <thead><tr><th>Reporter</th><th>Partner</th><th>Flow</th><th>HS</th><th>Tahun</th><th>Qty</th><th>Nilai (USD ribu)</th></tr></thead>
    <tbody><?php foreach ($rows['rows'] as $r): ?>
        <tr>
            <td><?= \KKP\View::e($r['reporter']); ?></td>
            <td><?= \KKP\View::e($r['partner']); ?></td>
            <td><?= \KKP\View::e($r['flow']); ?></td>
            <td><?= \KKP\View::e($r['product_code']); ?></td>
            <td><?= \KKP\View::e($r['year']); ?></td>
            <td><?= \KKP\View::num($r['qty'], 0); ?></td>
            <td><?= \KKP\View::num($r['value_usd'], 0); ?></td>
        </tr>
    <?php endforeach; ?></tbody>
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
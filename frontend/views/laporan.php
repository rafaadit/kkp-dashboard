<?php
$tahun = (int) ($_GET['tahun'] ?? $_POST['tahun'] ?? 2026);
$b1 = (int) ($_GET['bulan_awal'] ?? $_POST['bulan_awal'] ?? 1);
$b2 = (int) ($_GET['bulan_akhir'] ?? $_POST['bulan_akhir'] ?? 6);
if ($tahun < 2000 || $tahun > 2100) { $tahun = 2026; }
if ($b1 < 1 || $b1 > 12) { $b1 = 1; }
if ($b2 < 1 || $b2 > 12) { $b2 = 6; }
$periode_ok = $b1 <= $b2;

$sm = null;
$api_error = null;
try {
    $api = $session->api();
    if ($periode_ok) {
        [$st, $sm] = $api->get('/api/report/exec_summary?tahun=' . $tahun . '&bulan_awal=' . $b1 . '&bulan_akhir=' . $b2);
        if ($st !== 200) { $api_error = is_array($sm) ? ($sm['error'] ?? 'gagal') : 'gagal'; $sm = null; }
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $sm = null;
}

$canGenerate = $session->hasPermission('report.generate_ppt');
$canDownload = $session->hasPermission('report.view');
$job = !empty($_GET['ok']) ? (string) ($_GET['job'] ?? '') : '';

function laporan_badge(?float $p): string
{
    if ($p === null) { return '<span class="badge warn">-</span>'; }
    $up = $p >= 0;
    $cls = $up ? 'ok' : 'warn';
    $lbl = ($up ? 'Naik ' : 'Turun ') . \KKP\View::num(abs($p), 1) . '%';
    return '<span class="badge ' . $cls . '">' . $lbl . '</span>';
}
?>
<h1>Laporan Eksekutif</h1>
<p class="muted">Ringkasan ekspor/impor hasil perikanan untuk periode terpilih, lalu generate Laporan PPT sesuai periode tersebut.</p>

<?php if (!empty($_GET['err'])): ?>
    <div class="alert alert-danger">Gagal: <?= \KKP\View::e($_GET['err']); ?></div>
<?php endif; ?>
<?php if ($job !== ''): ?>
    <div class="alert" style="background:#e7f6ec;color:#15803d;border:1px solid #bfe3c9">
        Laporan PPT periode <?= \KKP\View::e($tahun); ?> berhasil dibuat.
        <?php if ($canDownload): ?>
            <a class="btn btn-primary" href="/laporan/download?job_id=<?= \KKP\View::e($job); ?>">Unduh PPT</a>
        <?php endif; ?>
    </div>
<?php endif; ?>

<form class="filters" method="get">
    <label style="align-self:center">Periode</label>
    <select name="tahun">
        <?php for ($t = 2022; $t <= 2100; $t++): ?>
            <option value="<?= $t; ?>" <?= $t === $tahun ? 'selected' : ''; ?>><?= $t; ?></option>
        <?php endfor; ?>
    </select>
    <select name="bulan_awal">
        <?php for ($m = 1; $m <= 12; $m++): ?>
            <option value="<?= $m; ?>" <?= $m === $b1 ? 'selected' : ''; ?>><?= \KKP\View::e(date('F', mktime(0, 0, 0, $m, 1))); ?></option>
        <?php endfor; ?>
    </select>
    <span style="align-self:center">s/d</span>
    <select name="bulan_akhir">
        <?php for ($m = 1; $m <= 12; $m++): ?>
            <option value="<?= $m; ?>" <?= $m === $b2 ? 'selected' : ''; ?>><?= \KKP\View::e(date('F', mktime(0, 0, 0, $m, 1))); ?></option>
        <?php endfor; ?>
    </select>
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>

<?php if (!$periode_ok): ?>
    <p class="muted">Bulan awal tidak boleh melebihi bulan akhir.</p>
<?php elseif ($api_error): ?>
    <p class="muted">Tidak ada data / API tidak terjangkau: <?= \KKP\View::e($api_error); ?></p>
<?php elseif ($sm && !empty($sm['empty'])): ?>
    <p class="muted">Tidak ada data raw_exim untuk periode <?= \KKP\View::e($tahun); ?> bulan <?= \KKP\View::e($b1); ?>–<?= \KKP\View::e($b2); ?>.</p>
<?php elseif ($sm): $eks = $sm['ekspor']; $imp = $sm['impor']; $ner = $sm['neraca']; ?>
    <section class="kpi-grid">
        <div class="card kpi">
            <div class="k">Ekspor (USD)</div>
            <div class="v"><?= \KKP\View::num($eks['nilai_usd'], 2); ?></div>
            <div class="sub">vs tahun lalu <?= laporan_badge($eks['yoy_persen']); ?></div>
        </div>
        <div class="card kpi">
            <div class="k">Impor (USD)</div>
            <div class="v"><?= \KKP\View::num($imp['nilai_usd'], 2); ?></div>
            <div class="sub">vs tahun lalu <?= laporan_badge($imp['yoy_persen']); ?></div>
        </div>
        <div class="card kpi <?= $ner['nilai_usd'] >= 0 ? 'pos' : 'neg'; ?>">
            <div class="k">Neraca (USD)</div>
            <div class="v"><?= \KKP\View::num($ner['nilai_usd'], 2); ?></div>
            <div class="sub">vs tahun lalu <?= laporan_badge($ner['yoy_persen']); ?></div>
        </div>
        <div class="card kpi">
            <div class="k">Volume Ekspor</div>
            <div class="v"><?= \KKP\View::num(($eks['volume_kg'] ?? 0) / 1e9, 2); ?> <span style="font-size:12px;color:var(--muted)">juta ton</span></div>
            <div class="sub"><?= \KKP\View::num($eks['hs'] ?? 0, 0); ?> komoditas / <?= \KKP\View::num($eks['negara'] ?? 0, 0); ?> negara</div>
        </div>
        <div class="card kpi">
            <div class="k">Volume Impor</div>
            <div class="v"><?= \KKP\View::num(($imp['volume_kg'] ?? 0) / 1e9, 2); ?> <span style="font-size:12px;color:var(--muted)">juta ton</span></div>
            <div class="sub"><?= \KKP\View::num($imp['hs'] ?? 0, 0); ?> komoditas / <?= \KKP\View::num($imp['negara'] ?? 0, 0); ?> negara</div>
        </div>
    </section>

    <section class="grid-2">
        <div class="card">
            <h2>Top Negara Tujuan (Ekspor)</h2>
            <table class="tbl">
                <thead><tr><th>#</th><th>Negara</th><th>Nilai (USD)</th><th>Share</th></tr></thead>
                <tbody>
                <?php foreach ($sm['top_negara'] as $i => $r): ?>
                    <tr>
                        <td><?= $i + 1; ?></td>
                        <td><?= \KKP\View::e($r['name']); ?></td>
                        <td class="num"><?= \KKP\View::num($r['nilai_usd'], 2); ?></td>
                        <td><?= $r['share'] !== null ? \KKP\View::num($r['share'], 1) . '%' : '-'; ?></td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
        <div class="card">
            <h2>Top Komoditas Ekspor</h2>
            <table class="tbl">
                <thead><tr><th>#</th><th>Komoditas</th><th>Nilai (USD)</th><th>Share</th></tr></thead>
                <tbody>
                <?php foreach ($sm['top_komoditas_ekspor'] as $i => $r): ?>
                    <tr>
                        <td><?= $i + 1; ?></td>
                        <td><?= \KKP\View::e($r['name']); ?></td>
                        <td class="num"><?= \KKP\View::num($r['nilai_usd'], 2); ?></td>
                        <td><?= $r['share'] !== null ? \KKP\View::num($r['share'], 1) . '%' : '-'; ?></td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    </section>

    <section class="grid-2">
        <div class="card">
            <h2>Top Komoditas Impor</h2>
            <table class="tbl">
                <thead><tr><th>#</th><th>Komoditas</th><th>Nilai (USD)</th><th>Share</th></tr></thead>
                <tbody>
                <?php foreach ($sm['top_komoditas_impor'] as $i => $r): ?>
                    <tr>
                        <td><?= $i + 1; ?></td>
                        <td><?= \KKP\View::e($r['name']); ?></td>
                        <td class="num"><?= \KKP\View::num($r['nilai_usd'], 2); ?></td>
                        <td><?= $r['share'] !== null ? \KKP\View::num($r['share'], 1) . '%' : '-'; ?></td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
        <div class="card">
            <h2>Per Bulan (USD)</h2>
            <table class="tbl">
                <thead><tr><th>Periode</th><th>Ekspor</th><th>Impor</th><th>Neraca</th></tr></thead>
                <tbody>
                <?php foreach ($sm['perbulan'] as $p): ?>
                    <tr>
                        <td><?= \KKP\View::e($p['periode']); ?></td>
                        <td class="num"><?= \KKP\View::num($p['ekspor_usd'], 2); ?></td>
                        <td class="num"><?= \KKP\View::num($p['impor_usd'], 2); ?></td>
                        <td class="num"><?= \KKP\View::num($p['neraca_usd'], 2); ?></td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    </section>
<?php endif; ?>

<?php if ($canGenerate): ?>
<section class="card">
    <h2>Buat Laporan PPT</h2>
    <p class="muted">Laporan PPT eksekutif akan dibuat untuk periode yang dipilih:
        <strong><?= \KKP\View::e($tahun); ?> bulan <?= \KKP\View::e($b1); ?>–<?= \KKP\View::e($b2); ?></strong>.</p>
    <form method="post" action="/laporan">
        <input type="hidden" name="tahun" value="<?= $tahun; ?>">
        <input type="hidden" name="bulan_awal" value="<?= $b1; ?>">
        <input type="hidden" name="bulan_akhir" value="<?= $b2; ?>">
        <button class="btn btn-primary" type="submit" <?= !$periode_ok ? 'disabled' : ''; ?>>Generate PPT</button>
    </form>
</section>
<?php else: ?>
<p class="muted">Anda tidak memiliki permission <code>report.generate_ppt</code>.</p>
<?php endif; ?>
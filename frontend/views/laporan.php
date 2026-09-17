<?php
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/report/list');
    if ($st !== 200) { throw new \RuntimeException(is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal'); }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
$canGenerate = $session->hasPermission('report.generate_ppt');
?>
<h1>Laporan PPT</h1>
<?php if (!empty($_GET['ok'])): ?><div class="alert" style="background:#e7f6ec;color:#15803d;border:1px solid #bfe3c9">Laporan berhasil dibuat.</div><?php endif; ?>
<?php if (!empty($_GET['err'])): ?><div class="alert alert-danger">Gagal: <?= \KKP\View::e($_GET['err']); ?></div><?php endif; ?>

<?php if ($canGenerate): ?>
<form class="filters" method="post" action="/laporan">
    <label style="align-self:center">Periode</label>
    <input type="number" name="tahun" value="2026" min="2000" max="2100" style="width:100px">
    <input type="number" name="bulan_awal" value="1" min="1" max="12" style="width:80px">
    <span style="align-self:center">s/d</span>
    <input type="number" name="bulan_akhir" value="6" min="1" max="12" style="width:80px">
    <button class="btn btn-primary" type="submit">Generate PPT</button>
</form>
<?php else: ?>
<p class="muted">Anda tidak memiliki permission <code>report.generate_ppt</code>.</p>
<?php endif; ?>

<?php if ($d): ?>
<table class="tbl">
    <thead><tr><th>Job</th><th>Status</th><th>Periode</th><th>Mulai</th><th>Selesai</th><th>Aksi</th></tr></thead>
    <tbody>
    <?php foreach ($d['reports'] as $r): $p = json_decode((string) $r['params'], true) ?: []; ?>
        <tr>
            <td>#<?= \KKP\View::e($r['id']); ?></td>
            <td><span class="badge <?= $r['status'] === 'SUCCESS' ? 'ok' : 'warn'; ?>"><?= \KKP\View::e($r['status']); ?></span></td>
            <td><?= \KKP\View::e(($p['bulan_awal'] ?? '?') . '-' . ($p['bulan_akhir'] ?? '?') . ' / ' . ($p['tahun'] ?? '?')); ?></td>
            <td><?= \KKP\View::e($r['started_at']); ?></td>
            <td><?= \KKP\View::e($r['finished_at']); ?></td>
            <td>
                <?php if ($r['downloadable']): ?>
                    <a class="btn" href="/laporan/download?job_id=<?= \KKP\View::e($r['id']); ?>">Unduh</a>
                <?php else: ?>
                    <span class="muted">-</span>
                <?php endif; ?>
            </td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
<?php if (empty($d['reports'])): ?><p class="muted">Belum ada laporan.</p><?php endif; ?>
<?php endif; ?>
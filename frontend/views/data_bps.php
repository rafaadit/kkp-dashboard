<?php
$api = $session->api();
$summary = null;
$uploads = [];
$jobs = [];
$periods = [];
$api_error = null;
try {
    $res = $api->getMany([
        'summary' => '/api/data/bps/summary',
        'uploads' => '/api/data/bps/uploads?limit=10',
        'jobs' => '/api/data/bps/jobs?limit=10',
        'periods' => '/api/data/bps/periods',
    ]);
    foreach ($res as $key => $pair) {
        [$st, $body] = $pair;
        if ($st !== 200 || !is_array($body)) {
            $api_error = is_array($body) ? ($body['error'] ?? 'gagal memuat data BPS') : 'gagal memuat data BPS';
            continue;
        }
        if ($key === 'summary') { $summary = $body; }
        if ($key === 'uploads') { $uploads = $body['uploads'] ?? []; }
        if ($key === 'jobs') { $jobs = $body['jobs'] ?? []; }
        if ($key === 'periods') { $periods = $body['periods'] ?? []; }
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
}

$ok = isset($_GET['ok']) ? (string) $_GET['ok'] : null;
if ($ok === '1' && isset($_GET['job'])) {
    $ok = 'Permintaan update BPS berhasil dikirim.';
}
$err = isset($_GET['err']) ? (string) $_GET['err'] : null;

$status_class = static function (string $s): string {
    return match ($s) {
        'SUCCESS', 'processed', 'valid' => 'ok',
        'FAILED', 'invalid_partial', 'failed' => 'danger',
        'RUNNING', 'PENDING', 'RETRYING', 'validating', 'uploaded' => 'warn',
        default => '',
    };
};
$status_label = static function (string $s): string {
    return match ($s) {
        'SUCCESS' => 'Selesai',
        'FAILED' => 'Gagal',
        'RUNNING' => 'Berjalan',
        'PENDING' => 'Menunggu',
        'CANCELLED' => 'Dibatalkan',
        'RETRYING' => 'Mencoba ulang',
        'processed' => 'Diproses',
        'valid' => 'Valid',
        'invalid_partial' => 'Sebagian invalid',
        'uploaded' => 'Terunggah',
        'validating' => 'Validasi',
        default => $s,
    };
};

$active = null;
foreach ($jobs as $j) {
    if (in_array($j['status'] ?? '', ['PENDING', 'RUNNING'], true)) { $active = $j; break; }
}
$selected_job = null;
if (!empty($_GET['job'])) {
    $jid = (int) $_GET['job'];
    if ($jid > 0) {
        try {
            [$st, $body] = $api->get('/api/data/bps/jobs/' . $jid);
            if ($st === 200 && is_array($body) && isset($body['job'])) {
                $selected_job = $body;
                $active = $body['job'];
            }
        } catch (\Throwable $e) {
            // abaikan; riwayat tetap tampil
        }
    }
}

$ini_bytes = static function (string $v): int {
    $v = trim($v);
    if ($v === '' || $v === '-1') { return PHP_INT_MAX; }
    $unit = strtolower(substr($v, -1));
    $n = (float) $v;
    return (int) match ($unit) {
        'g' => $n * 1024 ** 3,
        'm' => $n * 1024 ** 2,
        'k' => $n * 1024,
        default => $n,
    };
};
$upload_max = (string) ini_get('upload_max_filesize');
$post_max = (string) ini_get('post_max_size');
$limits_ok = $ini_bytes($upload_max) >= 64 * 1024 ** 2 && $ini_bytes($post_max) >= 64 * 1024 ** 2;
$latest = $summary['latest_period'] ?? null;
$counts = $summary['counts'] ?? [];
?>
<h1>Update Data BPS</h1>
<p class="muted">Unggah file BPS periode baru (.xlsx). Sistem memvalidasi, memuat ke tabel fakta, lalu membuat ulang RAW EXIM hanya untuk periode yang berubah.</p>

<?php if ($ok): ?><div class="alert" style="background:#e7f8f0;color:#087f5b;border-color:#b7ebd7"><?= \KKP\View::e($ok); ?></div><?php endif; ?>
<?php if ($err): ?><div class="alert alert-danger"><?= \KKP\View::e($err); ?></div><?php endif; ?>
<?php if ($api_error): ?><div class="alert alert-danger"><?= \KKP\View::e($api_error); ?></div><?php endif; ?>

<div class="kpi-grid">
  <div class="card kpi">
    <div class="k">Periode terakhir</div>
    <div class="v"><?= \KKP\View::e($latest['label'] ?? '-'); ?></div>
    <div class="sub">Batas data saat ini di ms_period</div>
  </div>
  <div class="card kpi">
    <div class="k">Baris fakt ekspor</div>
    <div class="v"><?= \KKP\View::num($counts['bps_export'] ?? 0); ?></div>
    <div class="sub">Tabel bps_export</div>
  </div>
  <div class="card kpi">
    <div class="k">Baris fakt impor</div>
    <div class="v"><?= \KKP\View::num($counts['bps_import'] ?? 0); ?></div>
    <div class="sub">Tabel bps_import</div>
  </div>
  <div class="card kpi">
    <div class="k">Baris RAW EXIM</div>
    <div class="v"><?= \KKP\View::num($counts['raw_exim'] ?? 0); ?></div>
    <div class="sub">Hasil generate ulang</div>
  </div>
</div>

<div class="card">
  <h2>Unggah File BPS</h2>
  <?php if (!$limits_ok): ?>
  <div class="alert alert-warning">
    Batas unggah PHP saat ini <strong>upload_max_filesize=<?= \KKP\View::e($upload_max); ?></strong>,
    <strong>post_max_size=<?= \KKP\View::e($post_max); ?></strong>. File BPS bisa puluhan MB.
    Jalankan frontend dengan: <code>php -d upload_max_filesize=256M -d post_max_size=260M -S 127.0.0.1:8080 -t frontend/public frontend/public/index.php</code>
  </div>
  <?php endif; ?>
  <form method="post" action="/data-bps" enctype="multipart/form-data" class="upload-form">
    <div class="grid-2">
      <label class="file-field">
        <span>File BPS Ekspor (.xlsx)</span>
        <input type="file" name="ekspor" accept=".xlsx,.xlsm">
        <small>Kosongkan jika hanya memperbarui impor.</small>
      </label>
      <label class="file-field">
        <span>File BPS Impor (.xlsx)</span>
        <input type="file" name="impor" accept=".xlsx,.xlsm">
        <small>Kosongkan jika hanya memperbarui ekspor.</small>
      </label>
    </div>
    <label class="check-field">
      <input type="checkbox" name="force" value="1">
      Paksa baca ulang walau isi file sama (opsional)
    </label>
    <div class="upload-actions">
      <button class="btn btn-primary" type="submit" <?= $active ? 'disabled' : ''; ?>>Mulai Update BPS</button>
      <?php if ($active): ?><span class="muted">Ada job yang masih berjalan. Tunggu sampai selesai.</span><?php endif; ?>
    </div>
  </form>
</div>

<div class="card bps-delete-card">
  <h2>Hapus Data BPS per Periode</h2>
  <p class="muted">Pilih periode dan jenis data yang ingin dihapus. Perubahan akan menghapus RAW EXIM serta tabel fakt dan staging terkait.</p>
  <form method="post" action="/data-bps/delete" class="grid-3" onsubmit="return confirm('Hapus data pada periode yang dipilih? Tindakan ini tidak dapat dibatalkan.');">
    <label class="file-field">
      <span>Periode</span>
      <select name="period_id" required>
        <option value="">Pilih periode</option>
        <?php foreach ($periods as $period): ?>
        <option value="<?= (int) $period['id']; ?>"><?= \KKP\View::e($period['label']); ?> — Ekspor <?= \KKP\View::num($period['ekspor_rows']); ?>, Impor <?= \KKP\View::num($period['impor_rows']); ?></option>
        <?php endforeach; ?>
      </select>
    </label>
    <label class="file-field">
      <span>Jenis Data</span>
      <select name="exim" required>
        <option value="both">Ekspor dan Impor</option>
        <option value="ekspor">Ekspor saja</option>
        <option value="impor">Impor saja</option>
      </select>
    </label>
    <div class="upload-actions" style="align-self:end">
      <button class="btn btn-danger" type="submit">Hapus Periode</button>
    </div>
  </form>
</div>

<?php if ($active): ?>
<div class="card job-live" id="bpsJob" data-job-id="<?= (int) ($active['id'] ?? 0); ?>" data-status="<?= \KKP\View::e($active['status'] ?? ''); ?>">
  <h2>Progres Job #<?= (int) ($active['id'] ?? 0); ?>
    <span class="badge <?= $status_class((string) ($active['status'] ?? '')); ?>" id="bpsJobStatus"><?= \KKP\View::e($status_label((string) ($active['status'] ?? ''))); ?></span>
  </h2>
  <div class="job-meta">
    <span>Diminta oleh: <strong><?= \KKP\View::e($active['created_by'] ?? '-'); ?></strong></span>
    <span>Mulai: <strong><?= \KKP\View::e($active['started_at'] ?? $active['created_at'] ?? '-'); ?></strong></span>
    <?php if (!empty($active['finished_at'])): ?><span>Selesai: <strong><?= \KKP\View::e($active['finished_at']); ?></strong></span><?php endif; ?>
  </div>
  <?php if (!empty($active['error'])): ?><div class="alert alert-danger"><?= \KKP\View::e($active['error']); ?></div><?php endif; ?>
  <pre class="job-log" id="bpsLogs"><?php
    if ($selected_job && !empty($selected_job['logs'])) {
        foreach ($selected_job['logs'] as $lg) {
            echo '[' . \KKP\View::e($lg['level'] ?? 'info') . '] ' . \KKP\View::e($lg['message'] ?? '') . "\n";
        }
    } else {
        echo 'Menunggu log…';
    }
  ?></pre>
</div>
<script>
(function () {
    var box = document.getElementById('bpsJob');
    if (!box) return;
    var id = box.getAttribute('data-job-id');
    var status = box.getAttribute('data-status');
    if (!id || ['SUCCESS', 'FAILED', 'CANCELLED'].indexOf(status) !== -1) return;
    var logs = document.getElementById('bpsLogs');
    var badge = document.getElementById('bpsJobStatus');
    var labels = {SUCCESS: 'Selesai', FAILED: 'Gagal', RUNNING: 'Berjalan', PENDING: 'Menunggu', CANCELLED: 'Dibatalkan', RETRYING: 'Mencoba ulang'};
    function poll() {
        fetch('/data-bps/status?job=' + encodeURIComponent(id), {headers: {'Accept': 'application/json'}})
            .then(function (r) { return r.json(); })
            .then(function (d) {
                if (!d || !d.job) throw new Error('no job');
                var s = d.job.status || '';
                if (badge) {
                    badge.textContent = labels[s] || s;
                    badge.className = 'badge ' + (s === 'SUCCESS' ? 'ok' : (s === 'FAILED' ? 'danger' : 'warn'));
                }
                if (logs) {
                    logs.textContent = (d.logs || []).map(function (l) {
                        return '[' + (l.level || 'info') + '] ' + (l.message || '');
                    }).join('\n');
                    logs.scrollTop = logs.scrollHeight;
                }
                if (s === 'SUCCESS' || s === 'FAILED' || s === 'CANCELLED') {
                    setTimeout(function () { window.location.href = '/data-bps?job=' + encodeURIComponent(id); }, 1200);
                    return;
                }
                setTimeout(poll, 3000);
            })
            .catch(function () { setTimeout(poll, 5000); });
    }
    setTimeout(poll, 2000);
})();
</script>
<?php endif; ?>

<div class="card">
  <h2>Riwayat Update BPS</h2>
  <?php if (!$jobs): ?>
    <p class="muted">Belum ada job update BPS.</p>
  <?php else: ?>
  <div class="tbl-scroll">
    <table class="tbl">
      <thead><tr><th>Job</th><th>Status</th><th>File</th><th>Diminta</th><th>Mulai</th><th>Selesai</th><th>Pesan</th><th></th></tr></thead>
      <tbody>
      <?php foreach ($jobs as $j): ?>
        <tr>
          <td>#<?= (int) ($j['id'] ?? 0); ?></td>
          <td><span class="badge <?= $status_class((string) ($j['status'] ?? '')); ?>"><?= \KKP\View::e($status_label((string) ($j['status'] ?? ''))); ?></span></td>
          <td>
            <?php foreach (($j['params']['files'] ?? []) as $ft => $f): ?>
              <div><strong><?= \KKP\View::e($ft); ?></strong>: <?= \KKP\View::e($f['original_name'] ?? '-'); ?></div>
            <?php endforeach; ?>
          </td>
          <td><?= \KKP\View::e($j['created_by'] ?? '-'); ?></td>
          <td><?= \KKP\View::e($j['started_at'] ?? '-'); ?></td>
          <td><?= \KKP\View::e($j['finished_at'] ?? '-'); ?></td>
          <td class="wrap"><?= \KKP\View::e($j['error'] ?? ''); ?></td>
          <td><a class="btn" href="/data-bps?job=<?= (int) ($j['id'] ?? 0); ?>">Detail</a></td>
        </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
  </div>
  <?php endif; ?>
</div>

<div class="card">
  <h2>File BPS Terakhir</h2>
  <?php if (!$uploads): ?>
    <p class="muted">Belum ada file BPS yang diunggah.</p>
  <?php else: ?>
  <div class="tbl-scroll">
    <table class="tbl">
      <thead><tr><th>ID</th><th>Jenis</th><th>File</th><th>Periode</th><th>Baris</th><th>Status</th><th>Diunggah oleh</th><th>Waktu</th></tr></thead>
      <tbody>
      <?php foreach ($uploads as $u): ?>
        <tr>
          <td><?= (int) ($u['id'] ?? 0); ?></td>
          <td><?= \KKP\View::e($u['exim_type'] ?? '-'); ?></td>
          <td class="wrap"><?= \KKP\View::e($u['nama_file'] ?? '-'); ?></td>
          <td><?= \KKP\View::e(trim(($u['periode_mulai'] ?? '') . ' – ' . ($u['periode_akhir'] ?? ''), ' –')); ?></td>
          <td class="num"><?= \KKP\View::num($u['row_count'] ?? 0); ?></td>
          <td><span class="badge <?= $status_class((string) ($u['status'] ?? '')); ?>"><?= \KKP\View::e($status_label((string) ($u['status'] ?? ''))); ?></span></td>
          <td><?= \KKP\View::e($u['uploaded_by'] ?? '-'); ?></td>
          <td><?= \KKP\View::e($u['created_at'] ?? '-'); ?></td>
        </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
  </div>
  <?php endif; ?>
</div>

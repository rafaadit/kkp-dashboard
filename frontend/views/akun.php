<?php
$api = $session->api();
$error = null;
$users = [];
$roles = [];
$total = 0;
$q = trim((string) ($_GET['q'] ?? ''));
$role_filter = trim((string) ($_GET['role'] ?? ''));
$edit = null;

$params = ['limit' => 200];
if ($q !== '') { $params['q'] = $q; }
if ($role_filter !== '') { $params['role'] = $role_filter; }

try {
    $res = $api->getMany([
        'users' => '/api/admin/users?' . http_build_query($params),
        'roles' => '/api/admin/roles',
    ]);
    [$st, $body] = $res['users'] ?? [0, null];
    if ($st === 200 && is_array($body)) {
        $users = $body['users'] ?? [];
        $total = (int) ($body['total'] ?? count($users));
    } else {
        $error = is_array($body) ? ($body['error'] ?? 'gagal memuat akun') : 'gagal memuat akun';
    }
    [$st, $body] = $res['roles'] ?? [0, null];
    if ($st === 200 && is_array($body)) {
        $roles = $body['roles'] ?? [];
    }
} catch (\Throwable $e) {
    $error = $e->getMessage();
}

if (!empty($_GET['edit'])) {
    $uid = (int) $_GET['edit'];
    foreach ($users as $u) {
        if ((int) ($u['id'] ?? 0) === $uid) { $edit = $u; break; }
    }
    if (!$edit && $uid > 0) {
        try {
            [$st, $body] = $api->get('/api/admin/users/' . $uid);
            if ($st === 200 && is_array($body)) { $edit = $body['user'] ?? null; }
        } catch (\Throwable $e) {
            // abaikan
        }
    }
}

$ok = isset($_GET['ok']) ? (string) $_GET['ok'] : null;
$err = isset($_GET['err']) ? (string) $_GET['err'] : null;
$me = $user['id'] ?? ($user['user_id'] ?? 0);
$role_meta = [];
foreach ($roles as $r) { $role_meta[(string) $r['kode']] = $r; }
$role_class = static function (string $kode): string {
    return match ($kode) {
        'super_admin' => 'role-admin',
        'pegawai' => 'role-pegawai',
        'user' => 'role-user',
        default => 'role-guest',
    };
};
?>
<h1>Kelola Akun</h1>
<p class="muted">Atur akun dan peran akses. <strong>User</strong> hanya melihat/mengunduh data, <strong>Pegawai</strong> dapat memperbarui data BPS periode baru, <strong>Super Admin</strong> mengelola seluruh fitur dan akun.</p>

<?php if ($ok): ?><div class="alert" style="background:#e7f8f0;color:#087f5b;border-color:#b7ebd7"><?= \KKP\View::e($ok); ?></div><?php endif; ?>
<?php if ($err): ?><div class="alert alert-danger"><?= \KKP\View::e($err); ?></div><?php endif; ?>
<?php if ($error): ?><div class="alert alert-danger"><?= \KKP\View::e($error); ?></div><?php endif; ?>

<?php if ($edit): ?>
<div class="card" id="edit">
  <h2>Edit Akun #<?= (int) ($edit['id'] ?? 0); ?> <span class="role-badge <?= $role_class((string) ($edit['role'] ?? '')); ?>"><?= \KKP\View::e($edit['role_nama'] ?? $edit['role'] ?? ''); ?></span></h2>
  <?php if (!($edit['is_active'] ?? true)): ?><div class="alert alert-warning">Akun ini sedang nonaktif. Semua token/sesi aktif sudah dicabut.</div><?php endif; ?>
  <div class="grid-2">
    <form method="post" action="/akun" class="stack-form">
      <input type="hidden" name="action" value="update">
      <input type="hidden" name="id" value="<?= (int) ($edit['id'] ?? 0); ?>">
      <label>Nama
        <input type="text" name="nama" value="<?= \KKP\View::e($edit['nama'] ?? ''); ?>" required minlength="2" maxlength="150">
      </label>
      <label>Email
        <input type="email" name="email" value="<?= \KKP\View::e($edit['email'] ?? ''); ?>" required maxlength="150">
      </label>
      <label>Role
        <select name="role" required>
          <?php foreach ($roles as $r): ?>
            <option value="<?= \KKP\View::e($r['kode']); ?>" <?= ($edit['role'] ?? '') === $r['kode'] ? 'selected' : ''; ?>><?= \KKP\View::e($r['nama']); ?> (<?= (int) ($r['jumlah_permission'] ?? 0); ?> izin)</option>
          <?php endforeach; ?>
        </select>
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit">Simpan Perubahan</button>
        <a class="btn" href="/akun">Batal</a>
      </div>
    </form>

    <form method="post" action="/akun" class="stack-form">
      <input type="hidden" name="action" value="reset_password">
      <input type="hidden" name="id" value="<?= (int) ($edit['id'] ?? 0); ?>">
      <label>Password Baru
        <input type="password" name="password" minlength="6" required autocomplete="new-password" placeholder="minimal 6 karakter">
      </label>
      <p class="muted" style="font-size:12px">Reset password akan mencabut semua sesi akun ini sehingga wajib login ulang.</p>
      <div class="form-actions">
        <button class="btn btn-dark" type="submit">Reset Password</button>
      </div>
    </form>
  </div>
</div>
<?php endif; ?>

<div class="card">
  <h2>Buat Akun Baru</h2>
  <form method="post" action="/akun" class="stack-form create-user-form">
    <input type="hidden" name="action" value="create">
    <div class="grid-3">
      <label>Nama
        <input type="text" name="nama" required minlength="2" maxlength="150" placeholder="Nama lengkap">
      </label>
      <label>Email
        <input type="email" name="email" required maxlength="150" placeholder="nama@kkp.go.id">
      </label>
      <label>Password
        <input type="password" name="password" required minlength="6" autocomplete="new-password" placeholder="minimal 6 karakter">
      </label>
      <label>Role
        <select name="role" required>
          <?php foreach ($roles as $r): ?>
            <option value="<?= \KKP\View::e($r['kode']); ?>"><?= \KKP\View::e($r['nama']); ?> — <?= \KKP\View::e($r['deskripsi'] ?? ''); ?></option>
          <?php endforeach; ?>
        </select>
      </label>
      <div class="form-actions align-end">
        <button class="btn btn-primary" type="submit">Buat Akun</button>
      </div>
    </div>
  </form>
</div>

<div class="card">
  <h2>Daftar Akun <span class="muted" style="font-weight:400;font-size:12px">(<?= \KKP\View::num($total); ?> akun)</span></h2>
  <form class="filters" method="get" action="/akun">
    <input type="text" name="q" value="<?= \KKP\View::e($q); ?>" placeholder="Cari nama / email">
    <select name="role">
      <option value="">Semua role</option>
      <?php foreach ($roles as $r): ?>
        <option value="<?= \KKP\View::e($r['kode']); ?>" <?= $role_filter === $r['kode'] ? 'selected' : ''; ?>><?= \KKP\View::e($r['nama']); ?></option>
      <?php endforeach; ?>
    </select>
    <button class="btn btn-primary" type="submit">Cari</button>
    <?php if ($q !== '' || $role_filter !== ''): ?><a class="btn" href="/akun">Reset</a><?php endif; ?>
  </form>

  <?php if (!$users): ?>
    <p class="muted">Tidak ada akun yang cocok.</p>
  <?php else: ?>
  <div class="tbl-scroll">
    <table class="tbl">
      <thead><tr><th>Nama</th><th>Email</th><th>Role</th><th>Status</th><th>Login terakhir</th><th>Dibuat</th><th>Aksi</th></tr></thead>
      <tbody>
      <?php foreach ($users as $u): $uid = (int) ($u['id'] ?? 0); $self = $uid === (int) $me; ?>
        <tr>
          <td><strong><?= \KKP\View::e($u['nama'] ?? '-'); ?></strong><?= $self ? ' <span class="badge ok">Anda</span>' : ''; ?></td>
          <td><?= \KKP\View::e($u['email'] ?? '-'); ?></td>
          <td><span class="role-badge <?= $role_class((string) ($u['role'] ?? '')); ?>"><?= \KKP\View::e($u['role_nama'] ?? $u['role'] ?? '-'); ?></span></td>
          <td><span class="badge <?= !empty($u['is_active']) ? 'ok' : 'danger'; ?>"><?= !empty($u['is_active']) ? 'Aktif' : 'Nonaktif'; ?></span></td>
          <td><?= \KKP\View::e($u['last_login_at'] ?? '-'); ?></td>
          <td><?= \KKP\View::e($u['created_at'] ?? '-'); ?></td>
          <td class="row-actions">
            <a class="btn" href="/akun?edit=<?= $uid; ?>">Edit</a>
            <form method="post" action="/akun" class="inline-form">
              <input type="hidden" name="action" value="toggle">
              <input type="hidden" name="id" value="<?= $uid; ?>">
              <input type="hidden" name="is_active" value="<?= !empty($u['is_active']) ? '0' : '1'; ?>">
              <button class="btn <?= !empty($u['is_active']) ? '' : 'btn-primary'; ?>" type="submit" <?= $self ? 'disabled title="Tidak bisa menonaktifkan akun sendiri"' : ''; ?>><?= !empty($u['is_active']) ? 'Nonaktifkan' : 'Aktifkan'; ?></button>
            </form>
          </td>
        </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
  </div>
  <?php endif; ?>
</div>

<div class="card">
  <h2>Matriks Role</h2>
  <div class="grid-3">
    <?php foreach ($roles as $r): ?>
      <div class="role-card <?= $role_class((string) $r['kode']); ?>">
        <div class="role-card-head">
          <span class="role-badge <?= $role_class((string) $r['kode']); ?>"><?= \KKP\View::e($r['nama']); ?></span>
          <span class="muted"><?= (int) ($r['jumlah_permission'] ?? 0); ?> izin</span>
        </div>
        <p class="muted"><?= \KKP\View::e($r['deskripsi'] ?? ''); ?></p>
      </div>
    <?php endforeach; ?>
  </div>
</div>

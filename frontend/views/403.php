<section class="forbidden">
  <div class="forbidden-icon" aria-hidden="true">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/><circle cx="12" cy="16" r="1.5"/></svg>
  </div>
  <h1>Akses Dibatasi</h1>
  <p class="muted">Peran akun Anda (<?= \KKP\View::e($session?->roleLabel() ?? 'Tamu'); ?>) tidak memiliki izin untuk membuka halaman ini.</p>
  <div class="forbidden-actions">
    <a class="btn btn-primary" href="/">Kembali ke Beranda</a>
    <a class="btn" href="/data">Lihat Data</a>
  </div>
</section>

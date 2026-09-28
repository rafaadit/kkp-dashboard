<?php
$d = null;
try {
    $api = $session->api();
    [$st, $d] = $api->get('/api/explore/ntm');
    if ($st !== 200) {
        $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
        $d = null;
    }
} catch (\Throwable $e) {
    $api_error = $e->getMessage();
    $d = null;
}
?>
<h1>Hambatan Non-Tarif (NTM / SPS)</h1>

<section class="card note-warn">
    <h2>Sumber data</h2>
    <p class="muted"><?= \KKP\View::e($d['sumber'] ?? '-'); ?></p>
    <p>Belum ada koneksi sumber. Struktur kategorisasi NTM sudah siap &amp; transparan;
        setiap baris berstatus "belum ada data" sampai sumber (FAO SPS / UNCTAD TRAINS) tersambung.</p>
</section>

<?php if ($d): ?>
<section class="card">
    <h2>Kategorisasi Hambatan Non-Tarif</h2>
    <table class="tbl">
        <thead><tr><th>Kode</th><th>Kategori</th><th>Format penerapan</th><th>Status</th></tr></thead>
        <tbody>
        <?php foreach (($d['kategori'] ?? []) as $k): ?>
            <tr><td><?= \KKP\View::e($k['kode']); ?></td><td><?= \KKP\View::e($k['nama']); ?></td>
                <td><?= \KKP\View::e($k['format']); ?></td><td class="muted"><?= \KKP\View::e($k['status']); ?></td></tr>
        <?php endforeach; ?>
        </tbody>
    </table>
</section>
<?php endif; ?>
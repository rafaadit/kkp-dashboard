<?php
/** Beranda — home-user dashboard (data riil dari API). */
use KKP\View;

$exim = (($_GET['exim'] ?? 'ekspor') === 'impor') ? 'impor' : 'ekspor';
$periode = trim((string) ($_GET['periode'] ?? ''));
if (!preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $periode)) { $periode = ''; }
$komoditas = trim((string) ($_GET['komoditas'] ?? ''));

$api = $session->api();
$get = function (string $path, array $params) use ($api): ?array {
    try {
        [$st, $d] = $api->get($path . '?' . http_build_query($params));
        return ($st === 200 && is_array($d)) ? $d : null;
    } catch (\Throwable $e) {
        return null;
    }
};

$common = [];
if ($komoditas !== '') { $common['komoditas'] = $komoditas; }

$resolve_periode = function (array $d): string {
    if (empty($d['perbulan'])) { return ''; }
    $last = end($d['perbulan']);
    return sprintf('%04d-%02d', (int) $last['tahun'], (int) $last['bulan']);
};

if ($periode === '') {
    $probe = $get('/api/explore/overview', ['exim' => $exim] + $common);
    if ($probe) { $periode = $resolve_periode($probe); }
}

$ref_y = $periode !== '' ? (int) substr($periode, 0, 4) : null;
$ref_m = $periode !== '' ? (int) substr($periode, 5, 2) : null;
$prev_periode = $yoy_periode = '';
if ($ref_y !== null) {
    $pm = $ref_m - 1; $py = $ref_y;
    if ($pm < 1) { $pm = 12; $py--; }
    $prev_periode = sprintf('%04d-%02d', $py, $pm);
    $yoy_periode = sprintf('%04d-%02d', $ref_y - 1, $ref_m);
}

$other_exim = $exim === 'ekspor' ? 'impor' : 'ekspor';
$ytd_start = $ref_y !== null ? sprintf('%04d-01', $ref_y) : '';
$ytd_end = $ref_y !== null ? sprintf('%04d-12', $ref_y) : '';

$paths = [];
if ($periode !== '') {
    $periode_q = ['periode' => $periode] + $common;
    $paths = [
        'cur' => '/api/explore/overview?' . http_build_query(['exim' => $exim] + $periode_q),
        'other' => '/api/explore/overview?' . http_build_query(['exim' => $other_exim] + $periode_q),
        'kom' => '/api/explore/komoditas?' . http_build_query(['exim' => $exim, 'limit' => 10] + $periode_q),
        'kom_prev' => '/api/explore/komoditas?' . http_build_query(['exim' => $exim, 'periode' => $prev_periode, 'limit' => 10] + $common),
        'kom_yoy' => '/api/explore/komoditas?' . http_build_query(['exim' => $exim, 'periode' => $yoy_periode, 'limit' => 10] + $common),
        'negara' => '/api/explore/negara?' . http_build_query(['exim' => $exim, 'limit' => 4] + $periode_q),
        'provinsi' => '/api/explore/provinsi?' . http_build_query(['exim' => $exim, 'limit' => 6, 'by' => 'asal'] + $periode_q),
        'ytd' => '/api/explore/overview?' . http_build_query(['exim' => $exim, 'mulai' => $ytd_start, 'akhir' => $ytd_end] + $common),
        'ytd_other' => '/api/explore/overview?' . http_build_query(['exim' => $other_exim, 'mulai' => $ytd_start, 'akhir' => $ytd_end] + $common),
    ];
}
$res = $api->getMany($paths);
$pick = function (string $key) use ($res): ?array {
    return (($res[$key][0] ?? 0) === 200 && is_array($res[$key][1] ?? null)) ? $res[$key][1] : null;
};
$cur = $pick('cur');
$cur_other = $pick('other');
$kom = $pick('kom');
$kom_prev = $pick('kom_prev');
$kom_yoy = $pick('kom_yoy');
$negara = $pick('negara');
$provinsi = $pick('provinsi');
$ytd_cur = $pick('ytd');
$ytd_other = $pick('ytd_other');

$map_by_name = function (?array $d): array {
    $m = [];
    foreach (($d['komoditas'] ?? []) as $k) { $m[(string) $k['komoditas']] = $k; }
    return $m;
};
$prev_map = $map_by_name($kom_prev);
$yoy_map = $map_by_name($kom_yoy);
$trend = function ($now, $then, bool $as_pct = true) {
    if ($now === null || $then === null || (float) $then <= 0) { return null; }
    return ((float) $now - (float) $then) / (float) $then * 100;
};

$tot_cur = $cur['totals'] ?? null;
$tot_other = $cur_other['totals'] ?? null;
$surplus = ($tot_cur && $tot_other) ? ((float) $tot_cur['nilai_usd'] - (float) $tot_other['nilai_usd']) : null;
$surplus_ytd = ($ytd_cur && $ytd_other)
    ? ((float) ($ytd_cur['totals']['nilai_usd'] ?? 0) - (float) ($ytd_other['totals']['nilai_usd'] ?? 0))
    : null;
$periode_label = $ref_m !== null ? View::bulan($ref_m) . ' ' . $ref_y : 'Semua periode';
$exim_label = ucfirst($exim);
$kom_list = $komoditas_list ?? [];
?>
<?php if ($komoditas !== ''): ?>
<p class="muted">Fokus komoditas: <strong><?= View::e($komoditas); ?></strong>
  <a href="?exim=<?= View::e($exim); ?>">hapus filter</a></p>
<?php endif; ?>

<section class="hero">
  <div class="hero-content">
    <span class="hero-badge"><span class="dot"></span> WPPNRI &middot; Intelijen Perdagangan Bahari</span>
    <h1>Pusat Intelijen Pasar Perikanan Indonesia</h1>
    <p class="lead">
      Pantau arus komparatif komoditas laut unggulan nasional ke
      <strong><?= View::num($tot_cur['negara_unik'] ?? 0); ?></strong> negara mitra dagang
      &middot; data kepabeanan BPS/KKP terverifikasi &middot; periode <strong><?= View::e($periode_label); ?></strong>.
    </p>
    <div class="hero-stats">
      <div class="hero-stat">
        <span class="k">Nilai <?= View::e($exim_label); ?></span>
        <span class="v">US$ <?= View::compact($tot_cur['nilai_usd'] ?? 0); ?></span>
        <span class="s"><?= View::num($tot_cur['baris'] ?? 0); ?> baris &middot; <?= View::e($periode_label); ?></span>
      </div>
      <div class="hero-stat">
        <span class="k">Volume Kargo</span>
        <span class="v"><?= View::num(($tot_cur['volume_kg'] ?? 0) / 1000); ?> <small>Ton</small></span>
        <span class="s"><?= View::num($tot_cur['hs_unik'] ?? 0); ?> kode HS unik</span>
      </div>
      <?php if ($surplus !== null): $ratio = ((float) $tot_other['nilai_usd'] > 0) ? (float) $tot_cur['nilai_usd'] / (float) $tot_other['nilai_usd'] : null; ?>
      <div class="hero-stat">
        <span class="k">Surplus Neraca</span>
        <span class="v <?= $surplus >= 0 ? 'pos' : 'neg'; ?>"><?= $surplus >= 0 ? '+' : '-'; ?>US$ <?= View::compact(abs($surplus)); ?></span>
        <span class="s <?= $surplus >= 0 ? 'up' : 'down'; ?>"><?= $ratio !== null ? 'Rasio ' . View::num($ratio, 2) . 'x' : 'ekspor vs impor'; ?></span>
      </div>
      <?php else: ?>
      <div class="hero-stat">
        <span class="k">Periode Data</span>
        <span class="v"><?= View::e($periode_label); ?></span>
        <span class="s">Sumber BPS &amp; KKP</span>
      </div>
      <?php endif; ?>
    </div>
  </div>
  <div class="hero-filter">
    <form method="get" action="/">
      <span class="flabel">Filter Cepat:</span>
      <select name="exim" aria-label="Jenis">
        <option value="ekspor" <?= $exim === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
        <option value="impor" <?= $exim === 'impor' ? 'selected' : ''; ?>>Impor</option>
      </select>
      <input type="month" name="periode" value="<?= View::e($periode); ?>" aria-label="Periode">
      <input type="text" name="komoditas" value="<?= View::e($komoditas); ?>" list="komList"
             placeholder="Semua komoditas" aria-label="Komoditas">
      <datalist id="komList">
        <?php foreach ($kom_list as $k): ?><option value="<?= View::e($k['n']); ?>"></option><?php endforeach; ?>
      </datalist>
      <button class="btn-apply" type="submit">Terapkan</button>
      <?php if ($komoditas !== '' || $exim === 'impor'): ?>
      <a class="btn" style="background:rgba(255,255,255,.12);border-color:rgba(255,255,255,.25);color:#e2e8f0" href="/">Reset</a>
      <?php endif; ?>
    </form>
  </div>
</section>

<?php if ($kom && !empty($kom['komoditas'])): $cards = array_slice($kom['komoditas'], 0, 3); ?>
<section class="section">
  <div class="section-head">
    <div>
      <div class="eyebrow">Portofolio Bahari Utama</div>
      <h2>Komoditas Unggulan <?= View::e($exim_label); ?></h2>
    </div>
    <a class="section-link" href="/komoditas?exim=<?= View::e($exim); ?><?= $periode ? '&mulai=' . View::e($periode) . '&akhir=' . View::e($periode) : ''; ?>">
      Lihat komoditas lengkap <span aria-hidden="true">&rarr;</span>
    </a>
  </div>
  <div class="prod-grid">
    <?php foreach ($cards as $k): $mom = $trend($k['nilai_usd'] ?? null, $prev_map[(string) $k['komoditas']]['nilai_usd'] ?? null); ?>
    <article class="prod-card">
      <div class="prod-thumb">
        <svg class="wave-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M2 7c2.5 0 2.5 2 5 2s2.5-2 5-2 2.5 2 5 2 2.5-2 5-2"/><path d="M2 12c2.5 0 2.5 2 5 2s2.5-2 5-2 2.5 2 5 2 2.5-2 5-2"/><path d="M2 17c2.5 0 2.5 2 5 2s2.5-2 5-2 2.5 2 5 2 2.5-2 5-2"/></svg>
        <span class="prod-chip">HS unik <?= View::num($k['hs_unik'] ?? 0); ?></span>
        <?php if ($mom !== null): ?>
        <span class="prod-delta <?= $mom < 0 ? 'down' : ''; ?>"><?= $mom >= 0 ? '+' : ''; ?><?= View::num($mom, 1); ?>% MoM</span>
        <?php endif; ?>
      </div>
      <div class="prod-body">
        <div class="prod-title-row">
          <h3 class="prod-title"><?= View::e($k['komoditas']); ?></h3>
          <span class="prod-price">US$ <?= View::num($k['harga_usd_kg'] ?? 0, 2); ?><small>/kg</small></span>
        </div>
        <p class="prod-desc">
          Menyumbang <?= View::num($k['share_nilai_persen'] ?? 0, 1); ?>% dari total nilai <?= View::e($exim); ?>
          periode <?= View::e($periode_label); ?> &middot; <?= View::num($k['baris'] ?? 0); ?> baris transaksi.
        </p>
        <div class="prod-meta">
          <span>Volume:</span><strong><?= View::num(($k['volume_kg'] ?? 0) / 1000, 1); ?> Ton</strong>
          <span>&middot;</span><span>Nilai:</span><strong>US$ <?= View::compact($k['nilai_usd'] ?? 0); ?></strong>
        </div>
      </div>
      <div class="prod-cta">
        <a href="/dashboard?komoditas=<?= urlencode((string) $k['komoditas']); ?>&exim=<?= View::e($exim); ?><?= $periode ? '&periode=' . View::e($periode) : ''; ?>">Analisis komoditas &rsaquo;</a>
      </div>
    </article>
    <?php endforeach; ?>
  </div>
</section>
<?php endif; ?>

<?php if ($cur && !empty($cur['perbulan'])): ?>
<section class="section">
  <div class="home-grid">
    <div class="home-card">
      <div class="home-card-head">
        <div>
          <div class="eyebrow">Tren Bulanan</div>
          <h3>Nilai <?= View::e($exim_label); ?> per Periode</h3>
        </div>
        <span class="live-pill"><span class="dot"></span> BPS/KKP</span>
      </div>
      <?php
        $bulan_rows = array_slice($cur['perbulan'], -12);
        $max_val = 0.0;
        foreach ($bulan_rows as $p) { $max_val = max($max_val, (float) $p['nilai_usd']); }
      ?>
      <div class="chart">
        <?php foreach ($bulan_rows as $p): $h = $max_val > 0 ? max(3, (float) $p['nilai_usd'] / $max_val * 100) : 3; ?>
        <div class="col" title="<?= View::e($p['periode']); ?> — US$ <?= View::num($p['nilai_usd'], 2); ?>">
          <div class="bar" style="height:<?= View::num($h, 1); ?>%"></div>
          <span class="lbl"><?= View::e(substr((string) $p['periode'], 2)); ?></span>
        </div>
        <?php endforeach; ?>
      </div>
      <div class="chart-foot">
        <span><?= count($bulan_rows); ?> periode terakhir &middot; puncak US$ <?= View::compact($max_val); ?></span>
        <a class="section-link" href="/perbandingan">Bandingkan periode &rarr;</a>
      </div>
    </div>

    <div class="home-col">
      <?php if ($negara && !empty($negara['negara'])): $nt = (float) ($tot_cur['nilai_usd'] ?? 0); ?>
      <div class="home-card">
        <div class="home-card-head">
          <div>
            <div class="eyebrow">Pangsa Pasar</div>
            <h3><?= $exim === 'ekspor' ? 'Negara Tujuan Utama' : 'Negara Asal Utama'; ?></h3>
          </div>
          <span class="hint"><?= View::e($periode_label); ?></span>
        </div>
        <div class="bars">
          <?php foreach ($negara['negara'] as $i => $n): $share = $nt > 0 ? (float) $n['nilai_usd'] / $nt * 100 : 0; ?>
          <div class="bar-row">
            <div class="bar-top">
              <span class="bar-name"><?= View::e($n['negara'] ?: $n['kode_negara']); ?></span>
              <span class="bar-val">US$ <?= View::compact($n['nilai_usd']); ?> <span>(<?= View::num($share, 1); ?>%)</span></span>
            </div>
            <div class="bar-track"><div class="bar-fill <?= ['', 'secondary', 'sky', 'slate'][$i] ?? 'slate'; ?>" style="width:<?= View::num(min(100, $share), 1); ?>%"></div></div>
          </div>
          <?php endforeach; ?>
        </div>
      </div>
      <?php endif; ?>

      <?php if ($cur && !empty($cur['kelompok'])): $kt = (float) ($tot_cur['nilai_usd'] ?? 0); ?>
      <div class="home-card">
        <div class="home-card-head">
          <div>
            <div class="eyebrow">Klaster Komoditas</div>
            <h3>Kelompok Koding (I&ndash;IV)</h3>
          </div>
        </div>
        <div class="bars">
          <?php foreach ($cur['kelompok'] as $i => $g): $share = $kt > 0 ? (float) $g['nilai_usd'] / $kt * 100 : 0; ?>
          <div class="bar-row">
            <div class="bar-top">
              <span class="bar-name">Kelompok <?= View::e($g['koding'] ?? '-'); ?></span>
              <span class="bar-val">US$ <?= View::compact($g['nilai_usd']); ?> <span>(<?= View::num($share, 1); ?>%)</span></span>
            </div>
            <div class="bar-track"><div class="bar-fill <?= ['teal', 'secondary', 'sky', 'slate'][$i] ?? 'slate'; ?>" style="width:<?= View::num(min(100, $share), 1); ?>%"></div></div>
          </div>
          <?php endforeach; ?>
        </div>
      </div>
      <?php endif; ?>
    </div>
  </div>
</section>
<?php endif; ?>

<?php if ($provinsi && !empty($provinsi['provinsi'])): ?>
<section class="section">
  <div class="section-head">
    <div>
      <div class="eyebrow">Sentra Produksi</div>
      <h2><?= $exim === 'ekspor' ? 'Provinsi Asal Utama' : 'Provinsi Asal Bahan Utama'; ?></h2>
    </div>
    <a class="section-link" href="/provinsi?exim=<?= View::e($exim); ?>">Lihat semua provinsi <span aria-hidden="true">&rarr;</span></a>
  </div>
  <div class="prov-grid">
    <?php foreach ($provinsi['provinsi'] as $p): $share = (float) ($p['share_nilai_persen'] ?? 0); ?>
    <article class="prov-card">
      <div class="prov-head">
        <span class="ph-name">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.5 2.6 3.9 5.7 3.9 9s-1.4 6.4-3.9 9c-2.5-2.6-3.9-5.7-3.9-9S9.5 5.6 12 3z"/></svg>
          <?= View::e($p['provinsi']); ?>
        </span>
        <span class="ph-share"><?= View::num($share, 1); ?>%</span>
      </div>
      <div class="prov-body">
        <div class="prov-mini-bars"><div class="prov-mini"><span style="width:<?= View::num(min(100, $share), 1); ?>%"></span></div></div>
        <div class="prov-row"><span class="pr-name">Nilai</span><span class="pr-val">US$ <?= View::compact($p['nilai_usd'] ?? 0); ?></span></div>
        <div class="prov-row"><span class="pr-name">Volume</span><span class="pr-val"><?= View::num(($p['volume_kg'] ?? 0) / 1000, 1); ?> Ton</span></div>
        <div class="prov-row"><span class="pr-name">Harga rata-rata</span><span class="pr-val">US$ <?= View::num($p['harga_usd_kg'] ?? 0, 2); ?>/kg</span></div>
      </div>
      <div class="prov-foot"><span><?= View::num($p['baris'] ?? 0); ?> baris</span><span><?= View::num($p['hs_unik'] ?? 0); ?> HS</span></div>
    </article>
    <?php endforeach; ?>
  </div>
</section>
<?php endif; ?>

<?php if ($kom && !empty($kom['komoditas'])):
    $total_cur = (float) ($tot_cur['nilai_usd'] ?? 0);
    $total_prev = $kom_prev ? (float) ($kom_prev['total_nilai_usd'] ?? 0) : null;
    $total_yoy = $kom_yoy ? (float) ($kom_yoy['total_nilai_usd'] ?? 0) : null;
    $sum_top = 0.0;
    foreach ($kom['komoditas'] as $k) { $sum_top += (float) $k['nilai_usd']; }
    $lainnya = max(0.0, $total_cur - $sum_top);
    $mom_total = $trend($total_cur, $total_prev);
    $yoy_total = $trend($total_cur, $total_yoy);
    $prev_label = $prev_periode !== '' ? View::bulan((int) substr($prev_periode, 5, 2)) . ' ' . substr($prev_periode, 0, 4) : '-';
    $yoy_label = $yoy_periode !== '' ? View::bulan((int) substr($yoy_periode, 5, 2)) . ' ' . substr($yoy_periode, 0, 4) : '-';
?>
<section class="section">
  <div class="section-head">
    <div>
      <h2>Data &amp; Informasi</h2>
      <p class="page-lead" style="margin:-6px 0 0">Ekspor dan Impor Produk Perikanan</p>
    </div>
    <div class="pill-tabs">
      <a class="pill-tab <?= $exim === 'ekspor' ? 'on' : ''; ?>" href="/?exim=ekspor<?= $periode ? '&periode=' . View::e($periode) : ''; ?><?= $komoditas !== '' ? '&komoditas=' . urlencode($komoditas) : ''; ?>">Ekspor</a>
      <a class="pill-tab <?= $exim === 'impor' ? 'on' : ''; ?>" href="/?exim=impor<?= $periode ? '&periode=' . View::e($periode) : ''; ?><?= $komoditas !== '' ? '&komoditas=' . urlencode($komoditas) : ''; ?>">Impor</a>
    </div>
  </div>
  <div class="data-table-wrap">
    <div class="tbl-scroll">
      <table class="tbl tbl-teal">
        <thead>
          <tr>
            <th rowspan="2" style="width:52px;text-align:center">No.</th>
            <th rowspan="2" style="min-width:220px">Uraian Komoditas</th>
            <th colspan="2" style="text-align:center"><?= View::e($periode_label); ?> (*)</th>
            <th colspan="2" style="text-align:center"><?= View::e($yoy_label); ?> (*)</th>
          </tr>
          <tr>
            <th class="num" style="width:150px">Juta (US$)</th>
            <th style="width:110px;text-align:center">MoM (%)</th>
            <th class="num" style="width:150px">Juta (US$)</th>
            <th style="width:110px;text-align:center">YoY (%)</th>
          </tr>
        </thead>
        <tbody>
          <tr class="total-row">
            <td style="text-align:center">—</td>
            <td>Total <?= View::e($exim_label); ?></td>
            <td class="num"><?= View::num($total_cur / 1e6, 2); ?></td>
            <td style="text-align:center">
              <?php if ($mom_total !== null): ?>
                <span class="trend <?= $mom_total >= 0 ? 'up' : 'down'; ?>"><?= View::num($mom_total, 2); ?> <?= $mom_total >= 0 ? '&uarr;' : '&darr;'; ?></span>
              <?php else: ?><span class="muted">—</span><?php endif; ?>
            </td>
            <td class="num"><?= $total_yoy !== null ? View::num($total_yoy / 1e6, 2) : '—'; ?></td>
            <td style="text-align:center">
              <?php if ($yoy_total !== null): ?>
                <span class="trend <?= $yoy_total >= 0 ? 'up' : 'down'; ?>"><?= View::num($yoy_total, 2); ?> <?= $yoy_total >= 0 ? '&uarr;' : '&darr;'; ?></span>
              <?php else: ?><span class="muted">—</span><?php endif; ?>
            </td>
          </tr>
          <?php foreach ($kom['komoditas'] as $i => $k):
              $nama = (string) $k['komoditas'];
              $p = $prev_map[$nama]['nilai_usd'] ?? null;
              $y = $yoy_map[$nama]['nilai_usd'] ?? null;
              $mom = $trend($k['nilai_usd'] ?? null, $p);
              $yy = $trend($k['nilai_usd'] ?? null, $y);
          ?>
          <tr>
            <td style="text-align:center" class="muted"><?= $i + 1; ?></td>
            <td style="font-weight:700"><?= View::e($nama); ?></td>
            <td class="num"><?= View::num(($k['nilai_usd'] ?? 0) / 1e6, 2); ?></td>
            <td style="text-align:center">
              <?php if ($mom !== null): ?>
                <span class="trend <?= $mom >= 0 ? 'up' : 'down'; ?>"><?= View::num($mom, 2); ?> <?= $mom >= 0 ? '&uarr;' : '&darr;'; ?></span>
              <?php else: ?><span class="muted">—</span><?php endif; ?>
            </td>
            <td class="num"><?= $y !== null ? View::num((float) $y / 1e6, 2) : '—'; ?></td>
            <td style="text-align:center">
              <?php if ($yy !== null): ?>
                <span class="trend <?= $yy >= 0 ? 'up' : 'down'; ?>"><?= View::num($yy, 2); ?> <?= $yy >= 0 ? '&uarr;' : '&darr;'; ?></span>
              <?php else: ?><span class="muted">—</span><?php endif; ?>
            </td>
          </tr>
          <?php endforeach; ?>
          <tr class="sub-row">
            <td style="text-align:center">—</td>
            <td style="font-weight:600">Lainnya</td>
            <td class="num"><?= View::num($lainnya / 1e6, 2); ?></td>
            <td style="text-align:center">—</td>
            <td class="num">—</td>
            <td style="text-align:center">—</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="tbl-foot">
      <div>
        <p><strong>Sumber :</strong> BPS diolah oleh Ditjen PDSPKP &middot; Basis data KKP EXIM Platform</p>
        <p><strong>Keterangan :</strong> (*) Angka sementara &middot; MoM vs <?= View::e($prev_label); ?> &middot; YoY vs <?= View::e($yoy_label); ?></p>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <?php if ($surplus !== null): ?>
        <span class="surplus soft"><span class="dot" style="width:8px;height:8px;border-radius:99px;background:#10b981"></span><?= View::e($periode_label); ?>: <span class="mono">Surplus US$ <?= View::num($surplus / 1e6, 2); ?> Juta</span></span>
        <?php endif; ?>
        <?php if ($surplus_ytd !== null): ?>
        <span class="surplus strong">Jan&ndash;<?= View::e(View::bulan((int) ($ref_m ?? 12))); ?> <?= View::e((string) ($ref_y ?? '')); ?>: <span class="mono">Surplus US$ <?= View::num($surplus_ytd / 1e6, 2); ?> Juta</span></span>
        <?php endif; ?>
      </div>
    </div>
  </div>
</section>
<?php endif; ?>

<?php if (!$cur && !$kom): ?>
<div class="card"><p class="muted">Data belum tersedia / API tidak terjangkau.</p></div>
<?php endif; ?>

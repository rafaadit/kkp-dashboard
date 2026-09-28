<?php
/* --- periode dari query --- */
$tahun = (int) ($_GET['tahun'] ?? $_POST['tahun'] ?? 2026);
$b1 = (int) ($_GET['bulan_awal'] ?? $_POST['bulan_awal'] ?? 1);
$b2 = (int) ($_GET['bulan_akhir'] ?? $_POST['bulan_akhir'] ?? 6);
if ($tahun < 2000 || $tahun > 2100) { $tahun = 2026; }
if ($b1 < 1 || $b1 > 12) { $b1 = 1; }
if ($b2 < 1 || $b2 > 12) { $b2 = 6; }
$periode_ok = $b1 <= $b2;

$d = null;
$api_error = null;
if ($periode_ok) {
    try {
        $api = $session->api();
        [$st, $d] = $api->get('/api/report/preview?tahun=' . $tahun . '&bulan_awal=' . $b1 . '&bulan_akhir=' . $b2);
        if ($st !== 200) { $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal'; $d = null; }
    } catch (\Throwable $e) {
        $api_error = $e->getMessage();
        $d = null;
    }
}

$canGenerate = $session->hasPermission('report.generate_ppt');
$canDownload = $session->hasPermission('report.view');
$job = !empty($_GET['ok']) ? (string) ($_GET['job'] ?? '') : '';

$BULAN = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
$PARTNER = [
    'United States' => 'Amerika Serikat', 'China' => 'Tiongkok', 'Japan' => 'Jepang',
    'Asean' => 'ASEAN', 'Uni Eropa' => 'Uni Eropa', 'Korea Selatan' => 'Korea Selatan',
    'Taiwan' => 'Taiwan', 'Timur Tengah' => 'Timur Tengah', 'Hong Kong' => 'Hong Kong',
    'United Kingdom' => 'United Kingdom', 'Australia And New Zealand' => 'Australia & NZ',
    'Canada' => 'Kanada', 'Rusia' => 'Rusia', 'EFTA' => 'EFTA', 'Eurasia' => 'Eurasia',
];
$KOM_SHORT = [
    'Udang' => 'UDANG', 'Tuna-Cakalang-Tongkol' => 'TCT', 'Cumi-Sotong-Gurita' => 'CSG',
    'Rajungan-Kepiting' => 'RK', 'Rumput Laut' => 'RUMPUT LAUT', 'Ikan Lainnya' => 'IKAN LAINNYA',
];

function pk_name3(string $n, array $map): string
{
    return $map[$n] ?? (strlen($n) > 28 ? substr($n, 0, 26) . '…' : $n);
}
function pk_m(float $v, int $dec = 2): string { return number_format($v / 1e9, $dec, ',', '.'); }
function pk_jt(float $v): string { return number_format($v / 1e6, 2, ',', '.'); }
function pk_pct(?float $v, int $dec = 1): string { return $v === null ? '-' : number_format((float) $v, $dec, ',', '.') . '%'; }
function pk_ton(float $kg): string { return number_format($kg / 1e9, 2, ',', '.') . ' Juta Ton'; }
function pk_yoy(?string $s): string { return ($s ?? '-') . ' (YoY)'; }
function pk_yoy_label(?float $p): string
{
    if ($p === null) { return '-'; }
    return (($p >= 0 ? 'Naik ' : 'Turun ') . number_format(abs($p), 1, ',', '.') . '%%');
}
function pk_tab_pct(float $v, float $tot): string { return $tot ? number_format($v / $tot * 100, 1, ',', '.') . '%' : '-'; }
?>
<h1>Laporan Eksekutif Infografis Perikanan</h1>
<p class="muted">Standar 11 Slide Ditjen PDSPKP · 100% data dinamis. Semua angka, pangsa, dan YoY dihitung dari database sesuai periode terpilih.</p>

<?php if (!empty($_GET['err'])): ?>
    <div class="alert alert-danger">Gagal: <?= \KKP\View::e($_GET['err']); ?></div>
<?php endif; ?>
<?php if ($job !== ''): ?>
    <div class="alert" style="background:#e7f6ec;color:#15803d;border:1px solid #bfe3c9">
        Laporan PPT periode <?= \KKP\View::e($BULAN[$b1]); ?>–<?= \KKP\View::e($BULAN[$b2]); ?> <?= \KKP\View::e($tahun); ?> berhasil dibuat.
        <?php if ($canDownload): ?>
            <a class="btn btn-primary" href="/laporan/download?job_id=<?= \KKP\View::e($job); ?>">Unduh PPT</a>
        <?php endif; ?>
    </div>
<?php endif; ?>

<form class="filters" method="get">
    <label style="align-self:center">Tahun</label>
    <select name="tahun">
        <?php for ($t = 2022; $t <= 2026; $t++): ?>
            <option value="<?= $t; ?>" <?= $t === $tahun ? 'selected' : ''; ?>><?= $t; ?></option>
        <?php endfor; ?>
    </select>
    <label style="align-self:center">Dari</label>
    <select name="bulan_awal">
        <?php for ($m = 1; $m <= 12; $m++): ?>
            <option value="<?= $m; ?>" <?= $m === $b1 ? 'selected' : ''; ?>><?= $BULAN[$m]; ?></option>
        <?php endfor; ?>
    </select>
    <label style="align-self:center">Sampai</label>
    <select name="bulan_akhir">
        <?php for ($m = 1; $m <= 12; $m++): ?>
            <option value="<?= $m; ?>" <?= $m === $b2 ? 'selected' : ''; ?>><?= $BULAN[$m]; ?></option>
        <?php endfor; ?>
    </select>
    <button class="btn btn-primary" type="submit">Tampilkan</button>
</form>

<div class="filters">
    <span class="muted" style="align-self:center">Preset:</span>
    <?php
    $presets = [
        'Jan-' . \KKP\View::e(substr($BULAN[min($b2, 6)], 0, 3)) => ['bulan_awal' => 1, 'bulan_akhir' => min($b2, 6)],
        'Semester I (Jan-Jun)' => ['bulan_awal' => 1, 'bulan_akhir' => 6],
        'Triwulan I (Jan-Mar)' => ['bulan_awal' => 1, 'bulan_akhir' => 3],
        'Triwulan II (Apr-Jun)' => ['bulan_awal' => 4, 'bulan_akhir' => 6],
    ];
    foreach ($presets as $label => $p): ?>
        <a class="btn <?= ($b1 === $p['bulan_awal'] && $b2 === $p['bulan_akhir']) ? 'btn-primary' : ''; ?>"
           href="/laporan?tahun=<?= $tahun; ?>&bulan_awal=<?= $p['bulan_awal']; ?>&bulan_akhir=<?= $p['bulan_akhir']; ?>"><?= \KKP\View::e($label); ?></a>
    <?php endforeach; ?>
</div>

<?php if (!$periode_ok): ?>
    <p class="muted">Bulan awal tidak boleh melebihi bulan akhir.</p>
<?php elseif ($api_error): ?>
    <p class="muted">Tidak ada data / API tidak terjangkau: <?= \KKP\View::e($api_error); ?></p>
<?php elseif (!$d || empty($d['ok'])): ?>
    <p class="muted">Tidak ada data raw_exim untuk periode <?= \KKP\View::e($tahun); ?> bulan <?= \KKP\View::e($b1); ?>–<?= \KKP\View::e($b2); ?>.</p>
<?php else:
    $x = $d['data'];
    $tot = $x['tot']; $yoy = $x['yoy']; $cagr = $x['cagr'];
    $n1 = $d['data']['tahun']; $bl1 = $d['data']['b1']; $bl2 = $d['data']['b2'];
?>

<!-- 1. COVER -->
<section class="card">
    <h2>Cover</h2>
    <p class="muted"><strong><?= \KKP\View::e($x['period_cover']); ?> · KINERJA EKSPOR HASIL PERIKANAN</strong></p>
    <p>Laporan Eksekutif Infografis <strong><?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> <?= \KKP\View::e($n1); ?></strong>
        — Data Kinerja Ekspor–Impor Produk Perikanan. Sumber: Bea Cukai divalidasi BPS, Diolah Ditjen PDSPKP.</p>
</section>

<!-- 2. KINERJA EKSPOR -->
<section class="card">
    <h2>Kinerja Ekspor</h2>
    <p class="muted">Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> <?= \KKP\View::e($n1); ?> (histori <?= \KKP\View::e($n1 - 4); ?>-<?= \KKP\View::e($n1); ?>)</p>
    <div class="kpi-grid">
        <div class="card kpi">
            <div class="k">Total Nilai Ekspor (USD)</div>
            <div class="v"><?= pk_m($tot['eks']); ?> Miliar</div>
            <div class="sub">Nilai: <?= \KKP\View::e($yoy['eks']); ?> (YoY)</div>
        </div>
        <div class="card kpi">
            <div class="k">Total Volume Ekspor</div>
            <div class="v"><?= pk_ton($tot['eks_kg']); ?></div>
            <div class="sub">CAGR Vol/thn <?= \KKP\View::e($cagr['eks_kg']); ?></div>
        </div>
        <div class="card kpi">
            <div class="k">CAGR Nilai Ekspor</div>
            <div class="v"><?= \KKP\View::e($cagr['eks_usd']); ?></div>
            <div class="sub">pertumbuhan rata-rata/thn (<?= \KKP\View::e($n1 - 4); ?>–<?= \KKP\View::e($n1); ?>)</div>
        </div>
    </div>
    <div class="grid-2">
        <div>
            <h3>5 TOP NEGARA TUJUAN</h3>
            <table class="tbl">
                <tbody>
                <?php foreach (array_slice($x['eks_partner'], 0, 5) as $r): ?>
                    <tr><td><?= \KKP\View::e(pk_name3($r['name'], $PARTNER)); ?></td>
                        <td class="num"><?= pk_jt($r['v']); ?> Jt</td>
                        <td><?= \KKP\View::e($r['yoy'] ?? '-'); ?></td></tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
        <div>
            <h3>5 TOP KOMODITAS EKSPOR</h3>
            <table class="tbl">
                <tbody>
                <?php foreach (array_slice($x['eks_komoditas'], 0, 5) as $r): ?>
                    <tr><td><?= \KKP\View::e(pk_name3($r['name'], $KOM_SHORT)); ?></td>
                        <td class="num"><?= pk_jt($r['v']); ?> Jt</td>
                        <td><?= \KKP\View::e($r['yoy'] ?? '-'); ?></td></tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    </div>
</section>

<!-- 3. EKSPOR - IMPOR - NERACA -->
<section class="card">
    <h2>Ekspor – Impor – Neraca</h2>
    <div class="kpi-grid">
        <div class="card kpi pos">
            <div class="k">Ekspor (USD)</div>
            <div class="v"><?= pk_m($tot['eks']); ?> Miliar</div>
            <div class="sub"><?= \KKP\View::e($yoy['eks']); ?> (YoY)</div>
        </div>
        <div class="card kpi <?= $tot['imp'] ? 'neg' : ''; ?>">
            <div class="k">Impor (USD)</div>
            <div class="v"><?= pk_m($tot['imp']); ?> Miliar</div>
            <div class="sub"><?= \KKP\View::e($yoy['imp']); ?> (YoY)</div>
        </div>
        <div class="card kpi pos">
            <div class="k">Neraca Perdagangan</div>
            <div class="v"><?= pk_m($tot['eks'] - $tot['imp']); ?> Miliar</div>
            <div class="sub">Surplus · <?= \KKP\View::e($yoy['ner']); ?> (YoY)</div>
        </div>
    </div>
</section>

<!-- 4. NEGARA EKSPOR -->
<section class="card">
    <h2>Negara Tujuan Ekspor</h2>
    <p class="muted">Struktur Pangsa Pasar Ekspor · Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> Tahun <?= \KKP\View::e($n1); ?></p>
    <div class="grid-2">
        <?php foreach ($x['eks_partner'] as $r): ?>
            <div class="card">
                <div class="grid-2" style="gap:4px">
                    <div><strong><?= \KKP\View::e(pk_name3($r['name'], $PARTNER)); ?></strong></div>
                    <div class="num"><?= pk_pct($r['share']); ?></div>
                    <div class="num">USD <?= pk_jt($r['v']); ?> Jt</div>
                    <div class="num"><?= \KKP\View::e($r['yoy'] ?? '-'); ?> (YoY)</div>
                </div>
            </div>
        <?php endforeach; ?>
    </div>
    <?php if (count($x['eks_partner']) >= 2): ?>
        <p class="muted">Konsentrasi pasar: US + Tiongkok = <?= pk_pct($x['eks_partner'][0]['share'] + $x['eks_partner'][1]['share']); ?>
            dari total ekspor nasional.</p>
    <?php endif; ?>
</section>

<!-- 5. KOMODITAS EKSPOR -->
<section class="card">
    <h2>Komoditas Utama Ekspor</h2>
    <p class="muted">Kontribusi terhadap total nilai ekspor · Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> Tahun <?= \KKP\View::e($n1); ?></p>
    <div class="grid-2">
        <?php foreach ($x['eks_komoditas'] as $r): ?>
            <div class="card">
                <div class="grid-2" style="gap:4px">
                    <div><strong><?= \KKP\View::e(pk_name3($r['name'], $KOM_SHORT)); ?></strong></div>
                    <div class="num"><?= pk_pct($r['share']); ?></div>
                    <div class="num">USD <?= pk_jt($r['v']); ?> Jt</div>
                    <div class="num"><?= \KKP\View::e(pk_yoy_label($r['yoy_p'])); ?> (YoY)</div>
                </div>
            </div>
        <?php endforeach; ?>
    </div>
</section>

<!-- 6. PASAR 5 KOMODITAS -->
<section class="card">
    <h2>Pasar 5 Komoditas</h2>
    <p class="muted">Top negara tujuan per komoditas utama · Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> Tahun <?= \KKP\View::e($n1); ?></p>
    <div class="grid-2">
        <?php foreach ($x['per_komoditas_partner'] as $kom => $rows): ?>
            <div class="card">
                <h3><?= \KKP\View::e(pk_name3($kom, $KOM_SHORT)); ?></h3>
                <table class="tbl">
                    <tbody>
                    <?php foreach (array_slice($rows, 0, 5) as $r): ?>
                        <tr><td><?= \KKP\View::e(pk_name3($r['name'], $PARTNER)); ?></td>
                            <td class="num">USD <?= pk_jt($r['v']); ?> Jt (<?= pk_pct($r['share']); ?>)</td></tr>
                    <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
        <?php endforeach; ?>
    </div>
</section>

<!-- 7. PRODUK PER NEGARA -->
<section class="card">
    <h2>Produk per Negara</h2>
    <p class="muted">Top komoditas ke setiap tujuan utama · Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> Tahun <?= \KKP\View::e($n1); ?></p>
    <div class="grid-2">
        <?php foreach ($x['per_partner_komoditas'] as $partner => $rows): ?>
            <div class="card">
                <h3><?= \KKP\View::e(pk_name3($partner, $PARTNER)); ?></h3>
                <table class="tbl">
                    <tbody>
                    <?php foreach (array_slice($rows, 0, 5) as $r): ?>
                        <tr><td><?= \KKP\View::e(pk_name3($r['name'], $KOM_SHORT)); ?></td>
                            <td class="num">USD <?= pk_jt($r['v']); ?> Jt (<?= pk_pct($r['share']); ?>)</td></tr>
                    <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
        <?php endforeach; ?>
    </div>
</section>

<!-- 8. KINERJA IMPOR -->
<section class="card">
    <h2>Kinerja Impor</h2>
    <p class="muted">Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> <?= \KKP\View::e($n1); ?> (histori <?= \KKP\View::e($n1 - 4); ?>-<?= \KKP\View::e($n1); ?>)</p>
    <div class="kpi-grid">
        <div class="card kpi <?= $tot['imp'] ? 'neg' : ''; ?>">
            <div class="k">Nilai Impor (USD)</div>
            <div class="v"><?= pk_m($tot['imp']); ?> Miliar</div>
            <div class="sub"><?= \KKP\View::e($yoy['imp']); ?> (YoY)</div>
        </div>
        <div class="card kpi">
            <div class="k">Volume Impor</div>
            <div class="v"><?= pk_ton($tot['imp_kg']); ?></div>
            <div class="sub">CAGR Vol/thn <?= \KKP\View::e($cagr['imp_kg']); ?></div>
        </div>
        <div class="card kpi">
            <div class="k">CAGR Nilai Impor</div>
            <div class="v"><?= \KKP\View::e($cagr['imp_usd']); ?></div>
            <div class="sub">pertumbuhan rata-rata/thn (<?= \KKP\View::e($n1 - 4); ?>–<?= \KKP\View::e($n1); ?>)</div>
        </div>
    </div>
    <p class="muted">Mayoritas impor untuk pemenuhan bahan baku industri UPI (re-ekspor) dan pakan perikanan budidaya.</p>
</section>

<!-- 9. ASAL IMPOR -->
<section class="card">
    <h2>Asal Impor</h2>
    <p class="muted">Struktur pangsa asal impor · Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> Tahun <?= \KKP\View::e($n1); ?></p>
    <div class="grid-2">
        <?php foreach ($x['imp_negara'] as $r): ?>
            <div class="card">
                <div class="grid-2" style="gap:4px">
                    <div><strong><?= \KKP\View::e($r['name'] === 'Lainnya' ? 'Negara Lainnya' : pk_name3($r['name'], $PARTNER)); ?></strong></div>
                    <div class="num"><?= pk_pct($r['share']); ?></div>
                    <div class="num">USD <?= pk_jt($r['v']); ?> Jt</div>
                    <div class="num"><?= \KKP\View::e($r['yoy'] ?? '-'); ?> (YoY)</div>
                </div>
            </div>
        <?php endforeach; ?>
    </div>
</section>

<!-- 10. KOMODITAS IMPOR -->
<section class="card">
    <h2>Komoditas Impor</h2>
    <p class="muted">Struktur pangsa komoditas impor · Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> Tahun <?= \KKP\View::e($n1); ?></p>
    <div class="grid-2">
        <?php foreach ($x['imp_komoditas'] as $r): ?>
            <div class="card">
                <div class="grid-2" style="gap:4px">
                    <div><strong><?= \KKP\View::e(pk_name3($r['name'], $KOM_SHORT)); ?></strong></div>
                    <div class="num"><?= pk_pct($r['share']); ?></div>
                    <div class="num">USD <?= pk_jt($r['v']); ?> Jt</div>
                    <div class="num"><?= \KKP\View::e($r['yoy'] ?? '-'); ?> (YoY)</div>
                </div>
            </div>
        <?php endforeach; ?>
    </div>
</section>

<!-- 11. PENUTUP -->
<section class="card">
    <h2>Penutup</h2>
    <p>Terima kasih. Laporan Eksekutif Infografis Produk Perikanan Indonesia.
        Sumber Data: Bea Cukai (divalidasi BPS) diolah Ditjen PDSPKP.</p>
</section>

<?php endif; ?>

<?php if ($canGenerate): ?>
<section class="card">
    <h2>Buat Laporan PPT</h2>
    <p class="muted">Hasilkan berkas PPTX sesuai slide infografis di atas untuk periode
        <strong><?= \KKP\View::e($BULAN[$b1]); ?> – <?= \KKP\View::e($BULAN[$b2]); ?> <?= \KKP\View::e($tahun); ?></strong>.</p>
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
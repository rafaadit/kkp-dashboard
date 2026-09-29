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

$CHART = [
    'eks' => ['#1c3f63', '#3a7faf', '#5aa0c8'],
    'imp' => ['#c98a2d', '#d8a44f'],
    'donut' => ['#1c3f63', '#2f6fa3', '#2d9c8f', '#ddb03a', '#c25b4e', '#7fa3c2', '#9fc0dd', '#b8c6d3'],
    'neg' => '#b91c1c',
    'pos' => '#15803d',
];

function pk_chart_pal(string $k): array
{
    return [
        'eks' => ['#1c3f63', '#3a7faf', '#5aa0c8'],
        'donut' => ['#1c3f63', '#2f6fa3', '#2d9c8f', '#ddb03a', '#c25b4e', '#7fa3c2', '#9fc0dd', '#b8c6d3'],
    ][$k];
}

function pk_nice_ceil($v): float
{
    if ($v <= 0) { return 1; }
    $mag = pow(10, floor(log10($v)));
    $raw = $v / $mag;
    foreach ([1, 2, 2.5, 5, 10] as $n) { if ($raw <= $n) { return $n * $mag; } }
    return 10 * $mag;
}

function pk_svg_bars(array $cats, array $series, array $o = []): string
{
    $w = $o['w'] ?? 560; $h = $o['h'] ?? 230;
    $padL = 46; $padR = 10; $padT = 30; $padB = 30;
    $plotW = $w - $padL - $padR; $plotH = $h - $padT - $padB;
    $fmt = $o['fmt'] ?? null;
    $ymax = 0;
    foreach ($series as $s) { foreach ($s['values'] as $v) { $ymax = max($ymax, (float) $v); } }
    $ymax = pk_nice_ceil($ymax) ?: 1;
    $ticks = 4;
    $out = '<svg viewBox="0 0 ' . $w . ' ' . $h . '" role="img" xmlns="http://www.w3.org/2000/svg" class="chart" style="width:100%;height:auto">';
    $out .= '<rect x="0" y="0" width="' . $w . '" height="' . $h . '" fill="#f7fafc" rx="8"/>';
    for ($i = 0; $i <= $ticks; $i++) {
        $frac = 1 - $i / $ticks;
        $y = $padT + $plotH * $frac;
        $out .= '<line x1="' . $padL . '" y1="' . $y . '" x2="' . ($w - $padR) . '" y2="' . $y . '" stroke="#e3e9f0" stroke-width="1"/>';
        $val = $ymax * $i / $ticks;
        $txt = $fmt ? $fmt($val) : number_format($val, 0, ',', '.');
        $out .= '<text x="' . ($padL - 8) . '" y="' . ($y + 4) . '" text-anchor="end" font-size="10" fill="#8aa0b5">' . $txt . '</text>';
    }
    $n = count($cats); $gW = $plotW / max(1, $n);
    $nS = count($series); $barW = min($gW * 0.62 / max(1, $nS), 46);
    foreach ($cats as $i => $cat) {
        $gx = $padL + $gW * $i;
        $sp = ($gW - $barW * $nS) / 2;
        foreach ($series as $j => $s) {
            $v = (float) ($s['values'][$i] ?? 0);
            $bh = $v > 0 ? max(1, $plotH * ($v / $ymax)) : 0;
            $x = $gx + $sp + $j * $barW;
            $y = $padT + $plotH - $bh;
            $col = ($o['colors'] ?? [])[$j] ?? $s['color'] ?? pk_chart_pal('eks')[$j % 3];
            $out .= '<rect x="' . $x . '" y="' . $y . '" width="' . $barW . '" height="' . $bh . '" rx="2" fill="' . $col . '">'
                . '<title>' . htmlspecialchars($cat . ': ' . ($fmt ? $fmt($v) : $v)) . '</title></rect>';
            if ($bh > 8) {
                $t = $fmt ? $fmt($v) : number_format($v, 1, ',', '.');
                $out .= '<text x="' . ($x + $barW / 2) . '" y="' . ($y - 5) . '" text-anchor="middle" font-size="9" fill="#33414e">' . $t . '</text>';
            }
        }
        $out .= '<text x="' . ($gx + $gW / 2) . '" y="' . ($padT + $plotH + 16) . '" text-anchor="middle" font-size="10" fill="#4a5a6a">' . htmlspecialchars($cat) . '</text>';
    }
    if (count($series) > 1) {
        $lx = $padL; $ly = $h - 8;
        foreach ($series as $j => $s) {
            $col = $s['color'] ?? $CHART['eks'][$j % 3];
            $out .= '<rect x="' . $lx . '" y="' . ($ly - 8) . '" width="10" height="10" rx="2" fill="' . $col . '"/>';
            $out .= '<text x="' . ($lx + 14) . '" y="' . $ly . '" font-size="10" fill="#33414e">' . htmlspecialchars($s['name']) . '</text>';
            $lx += 22 + strlen($s['name']) * 5.5;
        }
    }
    $out .= '</svg>';
    return $out;
}

function pk_svg_hbars(array $items, array $o = []): string
{
    $w = $o['w'] ?? 560; $rowH = $o['rowH'] ?? 34; $padL = $o['padL'] ?? 168; $h = count($items) * $rowH + 14;
    $maxv = 0.0001;
    foreach ($items as $it) { $maxv = max($maxv, (float) $it[1]); }
    $out = '<svg viewBox="0 0 ' . $w . ' ' . $h . '" role="img" xmlns="http://www.w3.org/2000/svg" class="chart" style="width:100%;height:auto">';
    $i = 0;
    foreach ($items as $it) {
        $y = 12 + $i * $rowH;
        $frac = (float) $it[1] / $maxv;
        $col = $it[3] ?? '#1c3f63';
        $out .= '<text x="' . ($padL - 10) . '" y="' . ($y + 12) . '" text-anchor="end" font-size="11" fill="#33414e">' . htmlspecialchars($it[0]) . '</text>';
        $out .= '<rect x="' . $padL . '" y="' . ($y + 4) . '" width="' . ($w - $padL - 92) . '" height="14" rx="7" fill="#eef3f8"/>';
        $out .= '<rect x="' . $padL . '" y="' . ($y + 4) . '" width="' . max(3, ($w - $padL - 92) * $frac) . '" height="14" rx="7" fill="' . $col . '"/>';
        $out .= '<text x="' . ($w - 88) . '" y="' . ($y + 16) . '" font-size="11" font-weight="600" fill="#1c3f63">' . htmlspecialchars($it[2]) . '</text>';
        $i++;
    }
    $out .= '</svg>';
    return $out;
}

function pk_svg_donut(array $items, array $o = []): string
{
    $w = $o['w'] ?? 240; $h = $o['h'] ?? 240;
    $R = $o['R'] ?? 92; $r = $o['r'] ?? 60;
    $cx = $w / 2; $cy = $h / 2;
    $tot = 0;
    foreach ($items as $it) { $tot += (float) $it[1]; }
    $tot = $tot ?: 1;
    $gap = 0.012; $a = -90.0;
    $out = '<svg viewBox="0 0 ' . $w . ' ' . $h . '" role="img" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">';
    foreach ($items as $k => $it) {
        $frac = (float) $it[1] / $tot;
        $a1 = $a; $a2 = $a + 360 * $frac;
        $col = $it[2] ?? pk_chart_pal('donut')[$k % 8];
        $a = $a2 + 360 * $gap;
        $x1 = $cx + $R * cos(deg2rad($a1)); $y1 = $cy + $R * sin(deg2rad($a1));
        $x2 = $cx + $R * cos(deg2rad($a2)); $y2 = $cy + $R * sin(deg2rad($a2));
        $x3 = $cx + $r * cos(deg2rad($a2)); $y3 = $cy + $r * sin(deg2rad($a2));
        $x4 = $cx + $r * cos(deg2rad($a1)); $y4 = $cy + $r * sin(deg2rad($a1));
        $lf = (($a2 - $a1) > 180) ? 1 : 0;
        $d = 'M ' . $x1 . ' ' . $y1 . ' A ' . $R . ' ' . $R . ' 0 ' . $lf . ' 1 ' . $x2 . ' ' . $y2
            . ' L ' . $x3 . ' ' . $y3 . ' A ' . $r . ' ' . $r . ' 0 ' . $lf . ' 0 ' . $x4 . ' ' . $y4 . ' Z';
        $out .= '<path d="' . $d . '" fill="' . $col . '"/>';
    }
    if (!empty($o['center'])) {
        $lc = explode('|', $o['center']);
        $out .= '<text x="' . $cx . '" y="' . ($cy - 6) . '" text-anchor="middle" font-size="13" font-weight="700" fill="#1c3f63">' . htmlspecialchars($lc[0]) . '</text>';
        if (isset($lc[1])) { $out .= '<text x="' . $cx . '" y="' . ($cy + 14) . '" text-anchor="middle" font-size="10" fill="#8aa0b5">' . htmlspecialchars($lc[1]) . '</text>'; }
    }
    $out .= '</svg>';
    return $out;
}

function pk_svg_banner(string $title, string $sub): string
{
    return '<svg viewBox="0 0 900 130" role="img" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;border-radius:10px">
        <defs><linearGradient id="g1" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#1c3f63"/><stop offset="100%" stop-color="#2d9c8f"/></linearGradient></defs>
        <rect width="900" height="130" rx="12" fill="url(#g1)"/>
        <path d="M0 78 Q 80 44 160 74 T 320 74 T 480 74 T 640 74 T 800 74 T 920 74 L 920 130 L 0 130 Z" fill="#ffffff" opacity="0.12"/>
        <path d="M0 96 Q 90 66 180 94 T 380 94 T 580 94 T 780 94 T 920 94 L 920 130 L 0 130 Z" fill="#ffffff" opacity="0.16"/>
        <circle cx="836" cy="34" r="26" fill="#ffffff" opacity="0.14"/>
        <circle cx="806" cy="20" r="8" fill="#ffffff" opacity="0.18"/>
        <text x="44" y="52" font-size="30" font-weight="700" fill="#ffffff">' . htmlspecialchars($title) . '</text>
        <text x="46" y="84" font-size="15" fill="#d6e9ff">' . htmlspecialchars($sub) . '</text>
        <text x="44" y="112" font-size="11" fill="#aecdff">Sumber: Bea Cukai (divalidasi BPS) · Diolah Ditjen PDSPKP</text>
    </svg>';
}
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
    <?= pk_svg_banner(
        'LAPORAN EKSEKUTIF INFOGRAFIS · ' . \KKP\View::e($x['period_cover']),
        'Kinerja Ekspor Hasil Perikanan · Periode ' . \KKP\View::e($BULAN[$bl1]) . ' – ' . \KKP\View::e($BULAN[$bl2]) . ' ' . \KKP\View::e($n1)
    ); ?>
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
        <div class="card">
            <h3>Nilai Ekspor <?= \KKP\View::e($BULAN[$bl1]); ?>–<?= \KKP\View::e($BULAN[$bl2]); ?> (USD Miliar / tahun)</h3>
            <?php $cats = array_map(fn($r) => (string) $r['tahun'], $x['series']);
            $valsEks = array_map(fn($r) => (float) $r['eks_usd'], $x['series']);
            echo pk_svg_bars($cats, [['name' => 'Ekspor', 'values' => $valsEks]], [
                'fmt' => fn($v) => number_format($v / 1e9, 2, ',', '.'),
            ]); ?>
        </div>
        <div class="card">
            <h3>Volume Ekspor <?= \KKP\View::e($BULAN[$bl1]); ?>–<?= \KKP\View::e($BULAN[$bl2]); ?> (Juta Ton / tahun)</h3>
            <?php $valsEksKg = array_map(fn($r) => (float) $r['eks_kg'], $x['series']);
            echo pk_svg_bars($cats, [['name' => 'Volume', 'color' => '#2d9c8f', 'values' => $valsEksKg]], [
                'fmt' => fn($v) => number_format($v / 1e9, 2, ',', '.'),
            ]); ?>
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
    <div class="card">
        <h3>Ekspor vs Impor <?= \KKP\View::e($BULAN[$bl1]); ?>–<?= \KKP\View::e($BULAN[$bl2]); ?> per Tahun (USD Miliar)</h3>
        <?php $valsImp = array_map(fn($r) => (float) $r['imp_usd'], $x['series']);
        echo pk_svg_bars($cats, [
            ['name' => 'Ekspor', 'color' => '#1c3f63', 'values' => $valsEks],
            ['name' => 'Impor', 'color' => '#c98a2d', 'values' => $valsImp],
        ], [
            'fmt' => fn($v) => number_format($v / 1e9, 2, ',', '.'),
        ]); ?>
    </div>
</section>

<!-- 4. NEGARA EKSPOR -->
<section class="card">
    <h2>Negara Tujuan Ekspor</h2>
    <p class="muted">Struktur Pangsa Pasar Ekspor · Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> Tahun <?= \KKP\View::e($n1); ?></p>
    <div style="display:flex;flex-wrap:wrap;gap:20px;align-items:center;justify-content:center">
        <div style="width:280px">
            <?php $dq = [];
            foreach ($x['eks_partner'] as $k => $r) { $dq[] = [$r['name'], (float) $r['v'], $CHART['donut'][$k % 8]]; }
            echo pk_svg_donut($dq, ['center' => 'USD ' . pk_jt($tot['eks']) . ' Jt|Total Ekspor', 'w' => 280, 'h' => 280]); ?>
        </div>
        <div class="grid-2" style="flex:1;min-width:320px">
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
    <?php $hb = [];
    foreach ($x['eks_komoditas'] as $k => $r) {
        $hb[] = [pk_name3($r['name'], $KOM_SHORT), (float) $r['share'], $k === 0 ? 'paling besar' : pk_pct($r['share']), $CHART['donut'][$k % 8]];
    }
    echo pk_svg_hbars($hb); ?>
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
                <?php $hb = [];
                $rows5 = array_slice($rows, 0, 5);
                foreach ($rows5 as $k => $r) {
                    $hb[] = [pk_name3($r['name'], $PARTNER), (float) $r['share'], pk_pct($r['share']), $CHART['donut'][$k % 8]];
                }
                echo pk_svg_hbars($hb, ['padL' => 140]); ?>
                <table class="tbl">
                    <tbody>
                    <?php foreach ($rows5 as $r): ?>
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
                <?php $hb = [];
                $rows5 = array_slice($rows, 0, 5);
                foreach ($rows5 as $k => $r) {
                    $hb[] = [pk_name3($r['name'], $KOM_SHORT), (float) $r['share'], pk_pct($r['share']), $CHART['donut'][$k % 8]];
                }
                echo pk_svg_hbars($hb, ['padL' => 150]); ?>
                <table class="tbl">
                    <tbody>
                    <?php foreach ($rows5 as $r): ?>
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
    <div class="card">
        <h3>Nilai Impor <?= \KKP\View::e($BULAN[$bl1]); ?>–<?= \KKP\View::e($BULAN[$bl2]); ?> (USD Miliar / tahun)</h3>
        <?php $valsImpKg = array_map(fn($r) => (float) $r['imp_kg'], $x['series']);
        echo pk_svg_bars($cats, [
            ['name' => 'Nilai Impor', 'color' => '#c98a2d', 'values' => $valsImp],
        ], [
            'fmt' => fn($v) => number_format($v / 1e9, 2, ',', '.'),
        ]); ?>
    </div>
    <p class="muted">Mayoritas impor untuk pemenuhan bahan baku industri UPI (re-ekspor) dan pakan perikanan budidaya.</p>
</section>

<!-- 9. ASAL IMPOR -->
<section class="card">
    <h2>Asal Impor</h2>
    <p class="muted">Struktur pangsa asal impor · Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> Tahun <?= \KKP\View::e($n1); ?></p>
    <div style="display:flex;flex-wrap:wrap;gap:20px;align-items:center;justify-content:center">
        <div style="width:280px">
            <?php $dq = [];
            foreach ($x['imp_negara'] as $k => $r) { $dq[] = [$r['name'], (float) $r['v'], $CHART['donut'][$k % 8]]; }
            echo pk_svg_donut($dq, ['center' => 'USD ' . pk_jt($tot['imp']) . ' Jt|Total Impor', 'w' => 280, 'h' => 280]); ?>
        </div>
        <div class="grid-2" style="flex:1;min-width:320px">
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
    </div>
</section>

<!-- 10. KOMODITAS IMPOR -->
<section class="card">
    <h2>Komoditas Impor</h2>
    <p class="muted">Struktur pangsa komoditas impor · Periode <?= \KKP\View::e($BULAN[$bl1]); ?> – <?= \KKP\View::e($BULAN[$bl2]); ?> Tahun <?= \KKP\View::e($n1); ?></p>
    <?php $hb = [];
    foreach ($x['imp_komoditas'] as $k => $r) {
        $hb[] = [pk_name3($r['name'], $KOM_SHORT), (float) $r['share'], pk_pct($r['share']), $CHART['donut'][$k % 8]];
    }
    echo pk_svg_hbars($hb); ?>
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
    <?= pk_svg_banner('TERIMA KASIH', 'Laporan Eksekutif Infografis Produk Perikanan Indonesia'); ?>
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
<?php
/* Helper chart SVG generik (dipakai laporan.php & perbandingan.php). */

namespace KKP {

class SvgChart
{
    public static function pal(string $k): array
    {
        return [
            'eks' => ['#1c3f63', '#3a7faf', '#5aa0c8'],
            'donut' => ['#1c3f63', '#2f6fa3', '#2d9c8f', '#ddb03a', '#c25b4e', '#7fa3c2', '#9fc0dd', '#b8c6d3'],
        ][$k];
    }

    public static function nice_ceil($v): float
    {
        if ($v <= 0) { return 1; }
        $mag = pow(10, floor(log10($v)));
        $raw = $v / $mag;
        foreach ([1, 2, 2.5, 5, 10] as $n) { if ($raw <= $n) { return $n * $mag; } }
        return 10 * $mag;
    }

    public static function bars(array $cats, array $series, array $o = []): string
    {
        $w = $o['w'] ?? 560; $h = $o['h'] ?? 230;
        $padL = 46; $padR = 10; $padT = 30; $padB = 30;
        $plotW = $w - $padL - $padR; $plotH = $h - $padT - $padB;
        $fmt = $o['fmt'] ?? null;
        $ymax = 0;
        foreach ($series as $s) { foreach ($s['values'] as $v) { $ymax = max($ymax, (float) $v); } }
        $ymax = self::nice_ceil($ymax) ?: 1;
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
                $col = ($o['colors'] ?? [])[$j] ?? $s['color'] ?? self::pal('eks')[$j % 3];
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
                $col = $s['color'] ?? self::pal('eks')[$j % 3];
                $out .= '<rect x="' . $lx . '" y="' . ($ly - 8) . '" width="10" height="10" rx="2" fill="' . $col . '"/>';
                $out .= '<text x="' . ($lx + 14) . '" y="' . $ly . '" font-size="10" fill="#33414e">' . htmlspecialchars($s['name']) . '</text>';
                $lx += 22 + strlen($s['name']) * 5.5;
            }
        }
        $out .= '</svg>';
        return $out;
    }

    public static function hbars(array $items, array $o = []): string
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

    public static function donut(array $items, array $o = []): string
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
            $col = $it[2] ?? self::pal('donut')[$k % 8];
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

    public static function banner(string $title, string $sub): string
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
}
}

namespace {
    /* alias fungsi di namespace global (kompatibilitas pemanggilan lama) */
    if (!function_exists('pk_chart_pal')) {
        function pk_chart_pal(string $k): array { return \KKP\SvgChart::pal($k); }
        function pk_nice_ceil($v): float { return \KKP\SvgChart::nice_ceil($v); }
        function pk_svg_bars(array $cats, array $series, array $o = []): string { return \KKP\SvgChart::bars($cats, $series, $o); }
        function pk_svg_hbars(array $items, array $o = []): string { return \KKP\SvgChart::hbars($items, $o); }
        function pk_svg_donut(array $items, array $o = []): string { return \KKP\SvgChart::donut($items, $o); }
        function pk_svg_banner(string $title, string $sub): string { return \KKP\SvgChart::banner($title, $sub); }
    }
}
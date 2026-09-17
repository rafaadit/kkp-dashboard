<?php

declare(strict_types=1);

namespace KKP;

/** Renderer view sederhana (layout + partial). */
final class View
{
    private static string $viewDir = BASE_PATH . '/views';

    public static function render(string $name, array $vars): void
    {
        $file = self::$viewDir . "/{$name}.php";
        if (!is_file($file)) {
            http_response_code(500);
            echo "View tidak ditemukan: {$name}";
            return;
        }
        $vars['__name__'] = $name;
        extract($vars, EXTR_SKIP);
        require self::$viewDir . '/layout/header.php';
        require $file;
        require self::$viewDir . '/layout/footer.php';
    }

    public static function renderPartial(string $name, array $vars): void
    {
        $file = self::$viewDir . "/{$name}.php";
        if (!is_file($file)) {
            return;
        }
        extract($vars, EXTR_SKIP);
        require $file;
    }

    public static function e(mixed $v): string
    {
        return htmlspecialchars((string) ($v ?? ''), ENT_QUOTES, 'UTF-8');
    }

    public static function num(mixed $v, int $dec = 0): string
    {
        return is_numeric($v) ? number_format((float) $v, $dec) : (string) ($v ?? '');
    }
}
<?php

declare(strict_types=1);

namespace KKP;

/** Sesi PHP + penyimpanan token API yang aman. */
final class Session
{
    private Config $config;
    private ApiClient $api;

    public function __construct(Config $config)
    {
        $this->config = $config;
        $this->api = new ApiClient($config->apiBaseUrl);
        if (session_status() === PHP_SESSION_NONE) {
            session_name('kkp_sid');
            session_start();
        }
        if ($this->token()) {
            $this->api->setToken($this->token());
        }
    }

    public function api(): ApiClient
    {
        return $this->api;
    }

    public function login(string $email, string $password): ?string
    {
        $res = $this->api->post('/api/auth/login', [
            'email' => $email,
            'password' => $password,
        ]);
        [$status, $body] = $res;
        if ($status !== 200) {
            return is_array($body) && isset($body['error']) ? (string) $body['error'] : 'Login gagal';
        }
        $_SESSION['token'] = $body['token'];
        $_SESSION['user'] = $body['user'] ?? null;
        $this->api->setToken($body['token']);
        return null;
    }

    public function logout(): void
    {
        if ($this->token()) {
            try {
                $this->api->post('/api/auth/logout', []);
            } catch (\Throwable $e) {
                // token mungkin sudah invalid; tetap lanjut logout lokal
            }
        }
        $_SESSION = [];
        // hapus cookie sesi
        if (ini_get('session.use_cookies')) {
            setcookie(session_name(), '', time() - 42000, '/');
        }
        session_destroy();
    }

    public function isLoggedIn(): bool
    {
        return (bool) $this->token();
    }

    public function token(): ?string
    {
        return isset($_SESSION['token']) ? (string) $_SESSION['token'] : null;
    }

    public function user(): array
    {
        $u = $_SESSION['user'] ?? null;
        if (is_array($u)) {
            return $u;
        }
        // fallback: ambil /me
        try {
            [$status, $body] = $this->api->get('/api/auth/me');
            if ($status === 200 && isset($body['user'])) {
                $_SESSION['user'] = $body['user'];
                return $body['user'];
            }
        } catch (\Throwable $e) {
            // offline
        }
        return ['email' => '', 'nama' => '', 'role' => ''];
    }

    public function hasPermission(string $kode): bool
    {
        $u = $this->user();
        if (($u['role'] ?? '') === 'super_admin') {
            return true;
        }
        return in_array($kode, $u['permissions'] ?? [], true);
    }
}
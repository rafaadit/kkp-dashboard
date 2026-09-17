<?php

declare(strict_types=1);

namespace KKP;

/** HttpClient ringan ke backend API (Flask, :8000). */
final class ApiClient
{
    private string $baseUrl;
    private ?string $token = null;

    public function __construct(string $baseUrl)
    {
        $this->baseUrl = rtrim($baseUrl, '/');
    }

    public function setToken(?string $token): void
    {
        $this->token = $token;
    }

    /**
     * @return array{0:int, 1:mixed} [status, body]
     */
    public function request(string $method, string $path, array $payload = []): array
    {
        $url = $this->baseUrl . $path;
        $ch = curl_init($url);
        $headers = ['Accept: application/json'];
        if ($this->token) {
            $headers[] = 'Authorization: Bearer ' . $this->token;
        }
        $body = null;
        if (in_array($method, ['POST', 'PUT', 'PATCH'])) {
            $body = json_encode($payload);
            $headers[] = 'Content-Type: application/json';
        }
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CUSTOMREQUEST => $method,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_POSTFIELDS => $body,
            CURLOPT_TIMEOUT => 30,
            CURLOPT_CONNECTTIMEOUT => 5,
        ]);
        $resp = curl_exec($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $err = curl_error($ch);

        if ($resp === false) {
            throw new \RuntimeException("API tidak terjangkau: $err");
        }
        $decoded = json_decode($resp, true);
        return [$status, $decoded === null ? $resp : $decoded];
    }

    public function get(string $path): array
    {
        return $this->request('GET', $path);
    }

    public function post(string $path, array $payload): array
    {
        return $this->request('POST', $path, $payload);
    }

    /** Ambil respons biner (untuk download file), return [status, blob, contentType]. */
    public function getRaw(string $path): array
    {
        $ch = curl_init($this->baseUrl . $path);
        $headers = [];
        if ($this->token) {
            $headers[] = 'Authorization: Bearer ' . $this->token;
        }
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_TIMEOUT => 60,
            CURLOPT_CONNECTTIMEOUT => 5,
        ]);
        $resp = curl_exec($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $ctype = (string) curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
        return [$status, $resp === false ? '' : $resp, $ctype];
    }
}
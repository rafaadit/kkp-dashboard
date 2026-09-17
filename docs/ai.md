# PHASE 8 — AI Assistant

Tanya-jawab seputar data EXIM (`raw_exim`) dengan dua mode.

## Mode

| Mode | Kapan | Cara |
|---|---|---|
| `lokal` | default, `AI_API_KEY` kosong | Penjawab deterministik: mengenali intent (total, komoditas utama, negara utama, tren) lalu menjawab dari query DB. **Tidak mengarang angka.** |
| `llm` | `AI_API_URL` + `AI_API_KEY` diisi | Kirim konteks data JSON ke endpoint OpenAI-compatible (`/chat/completions`); jawabannya dibatasi pada konteks. Bila LLM gagal → fallback ke mode lokal. |

Konfigurasi `.env`: `AI_API_URL`, `AI_API_KEY`, `AI_MODEL` (default `gpt-4`).

## API

`POST /api/ai/ask` (permission `ai.use`)

```json
{
  "question": "berapa total ekspor 2026?",
  "exim": "ekspor",          // ekspor | impor
  "mulai": "2026-01",        // atau "tahun": "2026"
  "akhir": "2026-06"
}
```

Respons: `question`, `answer`, `mode` (`lokal`/`llm`), `exim`, dan `konteks`
(totals + 10 top komoditas + 10 top negara). Semua interaksi dicatat di
`audit_logs` (`action='ai.ask'`, `after_data` berisi pertanyaan/jawaban/mode).

## Frontend

Halaman `/asisten` (menu **Asisten AI**): form pertanyaan + pilihan exim/periode,
jawaban ditampilkan dengan badge mode. Hanya tampil bila pengguna punya `ai.use`.

## Test

`.venv/bin/python tests/test_ai.py` — 10 assertions (proteksi, validasi,
konsistensi angka dengan DB, intent, audit log).
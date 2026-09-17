<?php
$question = '';
$answer = null;
$mode = null;
$api_error = null;

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST') {
    $question = trim((string) ($_POST['question'] ?? ''));
    if ($question === '') {
        $api_error = 'Pertanyaan tidak boleh kosong.';
    } else {
        try {
            $api = $session->api();
            [$st, $d] = $api->post('/api/ai/ask', [
                'question' => $question,
                'exim' => ($_POST['exim'] ?? 'ekspor'),
                'mulai' => trim((string) ($_POST['mulai'] ?? '')) ?: null,
                'akhir' => trim((string) ($_POST['akhir'] ?? '')) ?: null,
            ]);
            if ($st !== 200) {
                $api_error = is_array($d) ? ($d['error'] ?? 'gagal') : 'gagal';
            } else {
                $answer = (string) ($d['answer'] ?? '');
                $mode = (string) ($d['mode'] ?? '');
            }
        } catch (\Throwable $e) {
            $api_error = $e->getMessage();
        }
    }
}
$canUse = $session->hasPermission('ai.use');
?>
<h1>Asisten AI</h1>
<p class="muted">Tanya jawab seputar data EXIM. Angka diambil langsung dari database; asisten tidak mengarang data.</p>

<?php if (!$canUse): ?>
    <div class="alert">Anda tidak memiliki permission <code>ai.use</code>.</div>
<?php else: ?>
<form method="post" action="/asisten">
    <div class="filters">
        <input type="text" name="question" placeholder="Contoh: berapa total ekspor 2026? / komoditas utama ekspor" value="<?= \KKP\View::e($question); ?>" style="min-width:400px">
        <select name="exim">
            <option value="ekspor" <?= ($_POST['exim'] ?? '') === 'ekspor' ? 'selected' : ''; ?>>Ekspor</option>
            <option value="impor" <?= ($_POST['exim'] ?? '') === 'impor' ? 'selected' : ''; ?>>Impor</option>
        </select>
        <input type="text" name="mulai" placeholder="mulai (2026-01)" value="<?= \KKP\View::e((string) ($_POST['mulai'] ?? '')); ?>" style="width:130px">
        <input type="text" name="akhir" placeholder="akhir (2026-06)" value="<?= \KKP\View::e((string) ($_POST['akhir'] ?? '')); ?>" style="width:130px">
        <button class="btn btn-primary" type="submit">Tanya</button>
    </div>
</form>

<?php if ($api_error): ?><div class="alert alert-danger">Gagal: <?= \KKP\View::e($api_error); ?></div><?php endif; ?>

<?php if ($answer !== null): ?>
    <div class="card" style="margin-top:16px;padding:16px;background:#fff;border:1px solid #e2e8f0;border-radius:8px">
        <div class="muted" style="margin-bottom:6px">Jawaban <span class="badge <?= $mode === 'llm' ? 'ok' : 'warn'; ?>"><?= \KKP\View::e($mode); ?></span></div>
        <div style="white-space:pre-wrap;line-height:1.5"><?= \KKP\View::e($answer); ?></div>
    </div>
    <p class="muted" style="margin-top:8px">Mode <code>lokal</code> = penjawab deterministik dari database (LLM belum dikonfigurasi). Isi <code>AI_API_URL</code>/<code>AI_API_KEY</code> di <code>.env</code> untuk mengaktifkan LLM.</p>
<?php endif; ?>
<?php endif; ?>
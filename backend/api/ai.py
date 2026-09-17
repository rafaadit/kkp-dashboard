"""PHASE 8 — AI Assistant untuk data EXIM.

Mode:
  1. LLM eksternal (OpenAI-compatible) bila AI_API_KEY di-set pada .env.
  2. Fallback lokal (deterministik, tanpa jaringan): menjawab pertanyaan umum
     dari DB (top komoditas/negara, tren, total) — TIDAK mengarang angka.

Semua interaksi dicatat di audit_logs (action='ai.ask').
"""
import json
import os
import re
import urllib.request
import uuid

from flask import Blueprint, jsonify, request

from backend.db import get_connection
from backend.api.auth import require_perm
from backend.api.explore import _row
from backend.api.helpers import ApiError, parse_exim, parse_bulan

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

LM_SYSTEM = (
    "Anda asisten analis perdagangan hasil perikanan KKP. Jawab HANYA berdasarkan "
    "konteks data JSON yang diberikan; jangan mengarang angka. Jika data tidak ada, "
    "katakan tidak tersedia. Jawab ringkas dalam Bahasa Indonesia."
)


def _log_ask(user_id, question, answer, mode, data=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO audit_logs (app_user_id, action, entity, entity_id, after_data, correlation_id) "
            "VALUES (%s,'ai.ask','ai_assistant',NULL,%s,%s)",
            (user_id, json.dumps({"question": question, "mode": mode, "answer": answer[:2000],
                                  "data": data}), uuid.uuid4().hex),
        )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Fallback lokal: intent sederhana
# --------------------------------------------------------------------------
def _ctx_totals(exim, tb, tg):
    where = "exim_type=%s"
    params = [exim]
    if tb:
        where += " AND (tahun, bulan) >= (%s,%s)"
        params += [tb[0], tb[1] or 1]
    if tg:
        where += " AND (tahun, bulan) <= (%s,%s)"
        params += [tg[0], tg[1] or 12]
    r = _row("SELECT COUNT(*) baris, COALESCE(SUM(nil_usd),0) nilai_usd, "
             "COALESCE(SUM(vol_kg),0) vol_kg FROM raw_exim WHERE " + where, params)[0]
    return r


def _konteks(exim, tb, tg, limit=10):
    where = "exim_type=%s"
    params = [exim]
    if tb:
        where += " AND (tahun, bulan) >= (%s,%s)"
        params += [tb[0], tb[1] or 1]
    if tg:
        where += " AND (tahun, bulan) <= (%s,%s)"
        params += [tg[0], tg[1] or 12]
    komoditas = _row(
        "SELECT komoditas_5_2026 komoditas, COALESCE(SUM(nil_usd),0) nilai_usd, "
        "COALESCE(SUM(vol_kg),0) vol_kg FROM raw_exim WHERE " + where +
        " AND NULLIF(komoditas_5_2026,'') IS NOT NULL GROUP BY komoditas_5_2026 "
        "ORDER BY nilai_usd DESC LIMIT %s", params + [limit])
    negara = _row(
        "SELECT negara, kode_negara, COALESCE(SUM(nil_usd),0) nilai_usd FROM raw_exim WHERE " + where +
        " AND NULLIF(negara,'') IS NOT NULL GROUP BY negara, kode_negara "
        "ORDER BY nilai_usd DESC LIMIT %s", params + [limit])
    return {
        "exim": exim, "periode": {"mulai": tb, "akhir": tg},
        "totals": _ctx_totals(exim, tb, tg),
        "top_komoditas": komoditas, "top_negara": negara,
    }


def _local_answer(question, ctx):
    """Jawaban deterministik dari konteks (tanpa mengarang)."""
    q = question.lower()
    t = ctx["totals"]
    exim = ctx["exim"]
    komo = ctx["top_komoditas"]
    neg = ctx["top_negara"]
    lines = []

    if any(k in q for k in ("total", "berapa", "nilai", "volume")):
        lines.append(
            f"Total {exim}: US${float(t['nilai_usd']):,.0f} dari {int(t['baris']):,} baris, "
            f"volume {float(t['vol_kg']):,.0f} kg."
        )
    if any(k in q for k in ("komoditas", "produk", "utama", "terbesar", "top")):
        if komo:
            lines.append("Komoditas utama: " + "; ".join(
                f"{r['komoditas']} (US${float(r['nilai_usd']):,.0f})" for r in komo[:5]) + ".")
    if any(k in q for k in ("negara", "tujuan", "asal", "partner", "pasar")):
        if neg:
            lines.append("Negara utama: " + "; ".join(
                f"{r['negara'] or r['kode_negara']} (US${float(r['nilai_usd']):,.0f})" for r in neg[:5]) + ".")
    if any(k in q for k in ("tren", "perkembangan", "tumbuh", "naik", "turun")):
        lines.append("Untuk tren antar-periode, gunakan halaman Perbandingan "
                     "(endpoint /api/explore/perbandingan).")
    if not lines:
        lines.append(
            "Saya bisa menjawab pertanyaan tentang total nilai/volume, komoditas utama, "
            "dan negara utama. Contoh: \"berapa total ekspor 2026?\" atau "
            "\"komoditas utama ekspor\"."
        )
        lines.append(f"Ringkas: total {exim} = US${float(t['nilai_usd']):,.0f}, "
                     f"volume {float(t['vol_kg']):,.0f} kg.")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# LLM eksternal (opsional)
# --------------------------------------------------------------------------
def _llm_answer(question, ctx):
    api_url = os.environ.get("AI_API_URL", "").strip()
    api_key = os.environ.get("AI_API_KEY", "").strip()
    model = os.environ.get("AI_MODEL", "gpt-4")
    if not api_url or not api_key:
        return None
    url = api_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": LM_SYSTEM},
            {"role": "user", "content": "Konteks data JSON:\n" + json.dumps(ctx, default=str) +
             "\n\nPertanyaan: " + question},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        return f"[LLM gagal: {e}] " + (_local_answer(question, ctx))


@ai_bp.post("/ask")
@require_perm("ai.use")
def ask():
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        raise ApiError("question wajib diisi")
    exim = parse_exim(request, default=body.get("exim", "ekspor"))
    tb = parse_bulan(body.get("mulai")) or parse_bulan(str(body.get("tahun") or ""))
    tg = parse_bulan(body.get("akhir"))

    ctx = _konteks(exim, tb, tg)
    answer = _llm_answer(question, ctx)
    mode = "llm" if (answer and not answer.startswith("[LLM gagal")) else "lokal"
    if answer is None:
        answer = _local_answer(question, ctx)

    sess = request.environ["auth_session"]
    _log_ask(sess["user_id"], question, answer, mode, ctx)
    return jsonify({"question": question, "answer": answer, "mode": mode,
                    "exim": exim, "konteks": ctx})
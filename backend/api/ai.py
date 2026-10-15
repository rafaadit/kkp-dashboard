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

from functools import lru_cache

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


_SHOW_KEYS = (
    "tampilkan", "tampil", "lihat", "tunjuk", "show", "daftar", "list",
    "tabel", "raw exim", "raw_exim", "raw eksim", "raw exsim", "raw bps",
    "data bps", "data mentah", "data raw", "baris data",
)

_RAW_COLS = (
    "r.tahun", "r.bulan",
    "CONCAT(r.tahun,'-',LPAD(r.bulan,2,'0')) AS periode",
    "r.kode_hs_2022 AS kode_hs", "r.komoditas_5_2026 AS komoditas",
    "r.provinsi_asal", "r.kode_negara", "r.negara",
    "r.vol_kg", "r.nil_usd", "r.harga_usd_kg",
)

_RAW_COL_LABELS = {
    "periode": "Periode", "kode_hs": "Kode HS", "komoditas": "Komoditas",
    "provinsi_asal": "Provinsi Asal", "kode_negara": "Kode Negara",
    "negara": "Negara", "vol_kg": "Volume (kg)", "nil_usd": "Nilai (USD)",
    "harga_usd_kg": "Harga (USD/kg)",
}


def _want_rows(question):
    """True bila pengguna minta menampilkan/melihat baris data mentah."""
    ql = (question or "").lower()
    return any(k in ql for k in _SHOW_KEYS)


def _periode_label(periode):
    """Bentuk label '(periode 2026-01 s.d. 2026-06)' dari dict periode."""
    tb, tg = periode.get("mulai"), periode.get("akhir")
    if not tb and not tg:
        return ""
    def fmt(x):
        if not x:
            return None
        y, m = (x if isinstance(x, (list, tuple)) else (x, None))
        return f"{int(y):04d}-{int(m):02d}" if m else f"{int(y):04d}"
    a, b = fmt(tb), fmt(tg)
    if a and b and a != b:
        return f" (periode {a} s.d. {b})"
    return f" (periode {a or b})"


_BULAN_NAMA = {
    "januari": 1, "jan": 1, "january": 1,
    "februari": 2, "feb": 2, "february": 2,
    "maret": 3, "mar": 3, "march": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "jun": 6, "june": 6,
    "juli": 7, "jul": 7, "july": 7,
    "agustus": 8, "agu": 8, "ags": 8, "aug": 8, "august": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "oct": 10, "october": 10,
    "november": 11, "nov": 11,
    "desember": 12, "des": 12, "dec": 12, "december": 12,
}


def _periode_dari_teks(question):
    """Tarik periode dari teks: '2026-06', '06/2026', 'Juni 2026', atau '2025'.

    Return (tahun, bulan|None) atau None.
    """
    q = (question or "").lower()
    m = re.search(r"\b((?:19|20)\d{2})[-/](0?[1-9]|1[0-2])\b", q)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.search(r"\b(0?[1-9]|1[0-2])[-/]((?:19|20)\d{2})\b", q)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    for nama, bln in _BULAN_NAMA.items():
        if re.search(r"\b" + nama + r"\b", q):
            ym = re.search(r"\b((?:19|20)\d{2})\b", q)
            if ym:
                return (int(ym.group(1)), bln)
    ym = re.search(r"\b((?:19|20)\d{2})\b", q)
    if ym:
        return (int(ym.group(1)), None)
    return None


_NEGARA_ALIAS = {
    "amerika serikat": "US", "united states": "US", "usa": "US",
    "tiongkok": "CN", "cina": "CN", "china": "CN",
    "jepang": "JP", "japan": "JP",
    "korea selatan": "KR", "korsel": "KR", "korea utara": "KP",
    "inggris": "GB", "united kingdom": "GB", "britania raya": "GB",
    "prancis": "FR", "perancis": "FR", "france": "FR",
    "jerman": "DE", "germany": "DE",
    "belanda": "NL", "netherlands": "NL",
    "spanyol": "ES", "spain": "ES", "italia": "IT", "italy": "IT",
    "rusia": "RU", "russia": "RU",
    "thailand": "TH", "muangthai": "TH",
    "vietnam": "VN", "viet nam": "VN",
    "malaysia": "MY", "singapura": "SG", "singapore": "SG",
    "india": "IN", "australia": "AU",
    "chili": "CL", "chile": "CL",
    "norwegia": "NO", "norway": "NO",
    "kanada": "CA", "canada": "CA",
    "brasil": "BR", "brazil": "BR",
    "filipina": "PH", "philippines": "PH",
    "myanmar": "MM", "hongkong": "HK", "hong kong": "HK",
    "taiwan": "TW",
    "uni emirat arab": "AE", "united arab emirates": "AE",
    "arab saudi": "SA", "saudi arabia": "SA",
    "papua nugini": "PG", "selandia baru": "NZ", "new zealand": "NZ",
}

_KOMODITAS_ALIAS = {
    "cumi": "Cumi-Sotong-Gurita", "cumi-cumi": "Cumi-Sotong-Gurita",
    "sotong": "Cumi-Sotong-Gurita", "gurita": "Cumi-Sotong-Gurita",
    "tuna": "Tuna-Cakalang-Tongkol", "cakalang": "Tuna-Cakalang-Tongkol",
    "tongkol": "Tuna-Cakalang-Tongkol",
    "rumput laut": "Rumput Laut", "seaweed": "Rumput Laut",
    "rajungan": "Rajungan-Kepiting", "kepiting": "Rajungan-Kepiting",
    "udang": "Udang", "lobster": "Lobster", "udang karang": "Lobster",
    "kerapu": "Kerapu", "kakap": "Kakap Merah", "bandeng": "Bandeng",
    "makarel": "Makarel", "kembung": "Makarel", "mackerel": "Makarel",
    "salmon": "Salmon-Trout", "trout": "Salmon-Trout",
    "kerang": "Kekerangan", "remis": "Kekerangan",
    "teripang": "Teripang", "teri": "Teri",
    "sarden": "Sarden-Sardinella", "sardin": "Sarden-Sardinella",
    "sidat": "Sidat", "tilapia": "Tilapia", "nila": "Tilapia",
    "surimi": "Surimi", "mutiara": "Mutiara",
}


@lru_cache(maxsize=1)
def _ms_negara_list():
    rows = _row("SELECT nama_negara nama, kode_negara kode FROM ms_negara", [])
    return [(r["nama"], r["kode"]) for r in rows if r["nama"]]


@lru_cache(maxsize=1)
def _komoditas_list():
    rows = _row("SELECT DISTINCT komoditas_5_2026 k FROM raw_exim "
                "WHERE NULLIF(komoditas_5_2026,'') IS NOT NULL", [])
    return sorted((r["k"] for r in rows), key=len, reverse=True)


def _match_alias(alias_map, text):
    """Alias map: kunci dicari sebagai kata utuh (cocok terpanjang dulu)."""
    for alias, val in sorted(alias_map.items(), key=lambda kv: -len(kv[0])):
        if re.search(r"\b" + re.escape(alias) + r"\b", text):
            return val
    return None


def _detect_negara(question):
    """Tebak kode_negara (alpha-2) dari teks (nama Indonesia/Inggris)."""
    ql = " " + (question or "").lower() + " "
    kode = _match_alias(_NEGARA_ALIAS, ql)
    if kode:
        return kode
    for nama, kode in _ms_negara_list():
        if re.search(r"\b" + re.escape(nama.lower()) + r"\b", ql):
            return kode
    return None


def _detect_komoditas(question):
    """Tebak komoditas_5_2026 dari teks."""
    ql = (question or "").lower()
    nama = _match_alias(_KOMODITAS_ALIAS, ql)
    if nama:
        return nama
    for kandidat in _komoditas_list():
        if kandidat.lower() in ql:
            return kandidat
    return None


def _raw_rows(exim, tb, tg, komoditas=None, negara=None, limit=25):
    """Ambil baris raw_exim terfilter (periode/komoditas/negara) + total."""
    where = ["r.exim_type = %s"]
    params = [exim]
    if tb:
        where.append("(r.tahun, r.bulan) >= (%s,%s)")
        params += [tb[0], tb[1] or 1]
    if tg:
        where.append("(r.tahun, r.bulan) <= (%s,%s)")
        params += [tg[0], tg[1] or 12]
    if komoditas:
        where.append("r.komoditas_5_2026 LIKE %s")
        params.append("%" + komoditas + "%")
    if negara:
        where.append("r.kode_negara = %s")
        params.append(negara)
    w = " AND ".join(where)
    total = int(_row("SELECT COUNT(*) AS n FROM raw_exim r WHERE " + w, params)[0]["n"])
    rows = _row(
        "SELECT " + ", ".join(_RAW_COLS) + " FROM raw_exim r WHERE " + w +
        " ORDER BY r.tahun DESC, r.bulan DESC, r.nil_usd DESC LIMIT %s",
        params + [limit])
    kolom = [c for c in _RAW_COL_LABELS if c in rows[0]] if rows else \
        ["periode", "kode_hs", "komoditas", "negara", "vol_kg", "nil_usd", "harga_usd_kg"]
    return {"total": total, "ditampilkan": len(rows), "kolom": kolom,
            "labels": {k: _RAW_COL_LABELS.get(k, k) for k in kolom}, "rows": rows}


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
    per_tahun = _row(
        "SELECT tahun, COALESCE(SUM(nil_usd),0) nilai_usd, COALESCE(SUM(vol_kg),0) vol_kg, "
        "COUNT(*) baris FROM raw_exim WHERE " + where +
        " GROUP BY tahun ORDER BY tahun", params)
    return {
        "exim": exim, "periode": {"mulai": tb, "akhir": tg},
        "totals": _ctx_totals(exim, tb, tg),
        "per_tahun": per_tahun,
        "top_komoditas": komoditas, "top_negara": negara,
    }


def _local_answer(question, ctx):
    """Jawaban deterministik dari konteks (tanpa mengarang)."""
    q = question.lower()
    t = ctx["totals"]
    exim = ctx["exim"]
    komo = ctx["top_komoditas"]
    neg = ctx["top_negara"]
    baris_tbl = ctx.get("tabel")
    lines = []

    if baris_tbl:
        periodo = _periode_label(ctx.get("periode") or {})
        f = baris_tbl.get("filter") or {}
        filt = []
        if f.get("komoditas"):
            filt.append("komoditas " + f["komoditas"])
        if f.get("negara"):
            filt.append("negara " + f["negara"])
        fs = (" (filter: " + ", ".join(filt) + ")") if filt else ""
        lines.append(
            f"Menampilkan {baris_tbl['ditampilkan']} dari {baris_tbl['total']:,} baris "
            f"data {exim}{periodo}{fs} — urut nilai terbesar."
        )
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
    # Selaraskan arus dengan kata kunci pada pertanyaan (mis. pengguna memilih
    # "ekspor" di form tapi bertanya "berapa total impor 2025?").
    ql = question.lower()
    if "impor" in ql or "import" in ql:
        exim = "impor"
    elif "ekspor" in ql or "export" in ql:
        exim = "ekspor"
    tb = parse_bulan(body.get("mulai")) or parse_bulan(str(body.get("tahun") or ""))
    tg = parse_bulan(body.get("akhir"))
    # Bila tak ada periode eksplisit, coba tarik periode dari teks pertanyaan
    # (mis. "tampilkan data ekspor Juni 2026", "2026-06", atau "tahun 2025").
    if tb is None and tg is None:
        teks = _periode_dari_teks(question)
        if teks:
            tb = (teks[0], teks[1] or 1)
            tg = (teks[0], teks[1] or 12)

    ctx = _konteks(exim, tb, tg)

    # Intent "tampilkan data": sertakan baris raw_exim terfilter.
    tabel = None
    if _want_rows(question):
        komoditas = (body.get("komoditas") or "").strip() or _detect_komoditas(question)
        negara = (body.get("negara") or "").strip() or _detect_negara(question)
        tabel = _raw_rows(exim, tb, tg, komoditas=komoditas, negara=negara, limit=25)
        tabel["periode"] = {"mulai": tb, "akhir": tg}
        tabel["filter"] = {"komoditas": komoditas, "negara": negara}
        ctx["periode"] = {"mulai": tb, "akhir": tg}
        ctx["tabel"] = tabel
        ctx["contoh_baris"] = tabel["rows"][:10]

    answer = _llm_answer(question, ctx)
    mode = "llm" if (answer and not answer.startswith("[LLM gagal")) else "lokal"
    if answer is None:
        answer = _local_answer(question, ctx)

    sess = request.environ["auth_session"]
    _log_ask(sess["user_id"], question, answer, mode, {
        "exim": exim, "periode": {"mulai": tb, "akhir": tg},
        "tabel_total": (tabel or {}).get("total"),
    })
    return jsonify({"question": question, "answer": answer, "mode": mode,
                    "exim": exim, "konteks": ctx, "tabel": tabel})
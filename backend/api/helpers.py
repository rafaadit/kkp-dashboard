"""Helper bersama untuk API: parsing filter, serialisasi, validasi periode."""
from datetime import datetime
from decimal import Decimal


class ApiError(Exception):
    """Error yang ditampilkan sebagai HTTP 4xx dengan pesan JSON."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def parse_exim(request, default="ekspor", allow_all=False):
    raw = (request.args.get("exim") or default).strip().lower()
    if raw in ("ekspor", "export"):
        return "ekspor"
    if raw in ("impor", "import"):
        return "impor"
    if allow_all and raw in ("all", "semua", "keduanya"):
        return None
    raise ApiError(f"exim tidak dikenali: {raw!r} (pilihan: ekspor|impor)")


def parse_bulan(val):
    """Terima 'YYYY', 'YYYY-MM', 'YYYYMM', atau 'YYYY-M'. Return tuple (tahun, bulan)."""
    s = (val or "").strip()
    if not s:
        return None
    if len(s) == 6 and s.isdigit():
        return (int(s[:4]), int(s[4:6]))
    if len(s) == 4 and s.isdigit():
        return (int(s), None)
    sep = None
    for ch in ("-", "/", "."):
        if ch in s:
            sep = ch
            break
    if sep:
        parts = s.split(sep)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            if not (1 <= int(parts[1]) <= 12):
                raise ApiError(f"bulan di luar 1..12: {parts[1]!r}")
            return (int(parts[0]), int(parts[1]))
    raise ApiError(f"format periode tidak dikenali: {s!r} (contoh: 2025, 2026-06, 202606)")


def parse_periode(request, param="periode"):
    """
    Ambil rentang periode dari query param 'mulai' dan 'akhir'.
    Return (tahun_bulan_awal, tahun_bulan_akhir) sebagai tuple ke perbandingan.
    Jika kosong -> (None, None) (pakai seluruh data).
    """
    tb = parse_bulan(request.args.get("mulai")) or parse_bulan(request.args.get("tahun"))
    tg = parse_bulan(request.args.get("akhir"))
    if tb and tg and (tb[0], tb[1] or 1) > (tg[0], tg[1] or 12):
        raise ApiError("'mulai' tidak boleh setelah 'akhir'")
    return tb, tg


def apply_periode_filter(sql, where, params, tb, tg, period_col="id_ms_period"):
    """
    Tambahkan kondisi periode ke SQL. href
    tb/tg: (tahun, bulan|None) -> filter terhadap ms_period.
    Return (sql, where, params).
    """
    if tb or tg:
        conds = []
        if tb:
            conds.append(f"ms_p.tahun >= %s")
            params.append(tb[0])
            if tb[1]:
                conds.append(f"(ms_p.tahun > %s OR ms_p.bulan >= %s)")
                params += [tb[0], tb[1]]
        if tg:
            conds.append(f"ms_p.tahun <= %s")
            params.append(tg[0])
            if tg[1]:
                conds.append(f"(ms_p.tahun < %s OR ms_p.bulan <= %s)")
                params += [tg[0], tg[1]]
        where.append(" AND ".join(f"({c})" for c in conds))
    return sql, where, params


def value(v, nd=4):
    """Normalisasi Decimal/number -> float (JSON-safe), None tetap None."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, float) and v == int(v):
        return int(v)
    return round(v, nd) if isinstance(v, float) else v


def row_to_dict(row):
    return {k: value(v) for k, v in dict(row).items()}


def require_limit(request, default=10, maximum=100):
    try:
        limit = int(request.args.get("limit", default))
    except ValueError:
        raise ApiError("limit harus angka")
    if limit < 1 or limit > maximum:
        raise ApiError(f"limit harus 1..{maximum}")
    return limit


def require_page(request, default=1):
    try:
        page = int(request.args.get("page", default))
    except ValueError:
        raise ApiError("page harus angka")
    if page < 1:
        raise ApiError("page harus >= 1")
    return page


def to_ym(record):
    """Konversi (tahun, bulan) atau string menjadi 'YYYY-MM' + label."""
    if record is None:
        return None
    if isinstance(record, tuple):
        t, b = record
        b = b or (None if t is None else 12)
        ym = f"{int(t):04d}-{int(b):02d}"
    else:
        ym = record
    try:
        d = datetime.strptime(ym, "%Y-%m")
        label = d.strftime("%B %Y")
    except ValueError:
        label = ym
    return ym, label
"""Konfigurasi TradeMap: alias header, mapping trade flow, skala unit nilai, versi HS.

Semua pemetaan di sini adalah KONFIGURASI teknis (bukan business rule baru):
- alias header mengikuti keluaran ekspor ITC TradeMap yang sudah teramati
  pada file/fixture project (lihat tests/fixtures/trademap_sample.csv).
- skala unit nilai murni faktor konversi satuan yang dinyatakan pada header
  kolom (mis. "US$ Thousand" = x1000), bukan equivalence yang dikarang.
"""

# --- Alias header (case-insensitive, spasi/underscore disamakan) -------------
HEADER_ALIASES = {
    "reporter": [
        "reporter", "rep", "reporter iso", "reporting country", "reporter country",
    ],
    "partner": [
        "partner", "par", "partner iso", "counterpart", "partner country",
    ],
    "flow": [
        "flow", "trade flow", "flow type", "tradeflow", "type",
    ],
    "product_code": [
        "product code", "product_code", "product", "hs code", "hs", "commodity code",
        "product group",
    ],
    "product_desc": [
        "product description", "product_desc", "product label", "product name",
    ],
    "year": ["year", "years", "period", "year(s)"],
    "qty": ["quantity", "qty", "trade quantity", "net weight", "weight"],
    "qty_unit": ["quantity unit", "qty_unit", "unit", "quantity_unit"],
    "value": [
        "trade value", "value (us$ thousand)", "value_usd", "total value",
        "trade value (us$ thousand)", "value", "trade value usd",
    ],
    "value_unit": ["value unit", "value_unit", "currency", "value currency"],
    "hs_version": ["hs version", "hs_version", "nomenclature", "nomenclature version", "hs revision"],
    "period": ["period", "month", "date"],
}

# Kolom minimum agar file dianggap file TradeMap yang bisa diproses.
REQUIRED_HEADERS = ["product_code"]

# Baris header dicari pada N baris pertama (TradeMap kadang diawali metadata).
HEADER_SCAN_ROWS = 40

# --- Trade flow --------------------------------------------------------------
# Terminology TradeMap -> kanonikal project. Kunci lowercase.
FLOW_MAP = {
    "export": "EXPORT",
    "exports": "EXPORT",
    "e": "EXPORT",
    "exported": "EXPORT",
    "import": "IMPORT",
    "imports": "IMPORT",
    "i": "IMPORT",
    "imported": "IMPORT",
}

# Flow yang bisa dinormalisasi tetapi perlu ditandai (bukan Export/Import murni).
FLOW_NEEDS_VALIDATION = {
    "re-export": "EXPORT",
    "re-import": "IMPORT",
    "reimport": "IMPORT",
    "reexport": "EXPORT",
}

# --- Skala unit nilai --------------------------------------------------------
# Key = label unit pada header/kolom, value = faktor ke satuan USD.
VALUE_UNIT_SCALE = {
    "us$ thousand": 1000,
    "us$ 000": 1000,
    "usd thousand": 1000,
    "thousand usd": 1000,
    "us$ '000": 1000,
    "us$ million": 1000000,
    "usd million": 1000000,
    "us$ bn": 1000000000,
    "us$": 1,
    "usd": 1,
    "$": 1,
}

# --- HS versioning -----------------------------------------------------------
MASTER_HS_VERSION = "HS2022"
KNOWN_HS_VERSIONS = {"HS2012", "HS2017", "HS2022", "HS2022+", "HS2027"}

# Panjang kode HS yang dikenal (TradeMap umumnya 6 digit; master project 8 digit).
HS_LEVELS = (2, 4, 6, 8, 10)


def norm_header(text):
    """Normalisasi teks header menjadi bentuk pencocokan (lower, underscore->space)."""
    return " ".join(str(text or "").strip().lower().replace("_", " ").split())


def detect_value_scale(header_text):
    """Tebak faktor skala unit dari teks header kolom nilai.

    Return (faktor, label_unit). label 'US$' dst. Jika tidak dikenali -> (None, header_text).
    """
    h = norm_header(header_text)
    for label, scale in sorted(VALUE_UNIT_SCALE.items(), key=lambda kv: -len(kv[0])):
        if label in h:
            return scale, label.upper()
    return None, (str(header_text).strip() if header_text else None)

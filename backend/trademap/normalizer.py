"""TradeMapNormalizer — normalisasi tipe & format (tanpa akses DB).

- country/partner: trim + upper (kode) — resolusi ke master dilakukan mapper.
- product_code: hanya digit (mendukung '0306.17', '0306 17', dsb).
- year: int + validasi rentang.
- flow: kanonikal EXPORT/IMPORT via mapping konfigurasi.
- value/qty: Decimal, tangani kosong / 'n.a.' / pemisah ribuan.
- value_usd_norm: nilai * faktor skala unit (dinyatakan header), bukan business rule.
"""
from decimal import Decimal, InvalidOperation

from backend.trademap import config
from backend.trademap.models import Issue, RawRecord

NULL_TOKENS = {"", "-", "--", "n.a.", "na", "n/a", "nan", "null", "none", ".."}
YEAR_MIN, YEAR_MAX = 1990, 2100


def _clean(v):
    return "" if v is None else str(v).strip()


def _to_decimal(v):
    """Return (Decimal|None, is_invalid). Kosong -> (None, False)."""
    s = _clean(v)
    if s.lower() in NULL_TOKENS:
        return None, False
    neg = s.startswith("(") and s.endswith(")")
    s2 = s.strip("()").replace(",", "").replace("$", "").replace("\u00a0", "").strip()
    try:
        d = Decimal(s2)
    except (InvalidOperation, ValueError):
        return None, True
    return (-d if neg else d), False


def _digits_only(v):
    return "".join(ch for ch in _clean(v) if ch.isdigit())


class TradeMapNormalizer:
    def normalize(self, rec):
        issues = []
        nr = {}
        row = rec.row_ref

        # --- kode / label dasar ---
        product_code = _digits_only(rec.product_code)
        if product_code and product_code != _clean(rec.product_code):
            issues.append(Issue(row, "product_code", "HS_CODE_NORMALIZED",
                                rec.product_code, "WARNING", "kode HS dinormalisasi ke digit",
                                product_code))

        reporter_code = _clean(rec.reporter).upper()
        partner_code = _clean(rec.partner).upper()

        # --- trade flow ---
        flow_key = _clean(rec.flow).lower()
        flow_norm = config.FLOW_MAP.get(flow_key)
        if flow_norm is None and flow_key in config.FLOW_NEEDS_VALIDATION:
            flow_norm = config.FLOW_NEEDS_VALIDATION[flow_key]
            issues.append(Issue(row, "flow", "FLOW_NEEDS_VALIDATION", rec.flow, "WARNING",
                                "flow bukan Export/Import murni", "konfirmasi perlakuan flow"))
        elif flow_norm is None:
            issues.append(Issue(row, "flow", "FLOW_INVALID", rec.flow, "INVALID",
                                "flow tidak dikenali", "Export|Import"))

        # --- tahun ---
        year = None
        raw_year = _digits_only(rec.year) if rec.year is not None else ""
        if raw_year:
            if len(raw_year) in (7, 8):  # mis. 202401 / 20240115 -> ambil 4 pertama
                raw_year = raw_year[:4]
            try:
                year = int(raw_year)
            except ValueError:
                year = None
        if not raw_year:
            issues.append(Issue(row, "year", "YEAR_MISSING", rec.year, "INVALID",
                                "tahun tidak ada", "isi kolom year"))
        elif year is None or not (YEAR_MIN <= year <= YEAR_MAX):
            issues.append(Issue(row, "year", "YEAR_INVALID", rec.year, "INVALID",
                                "tahun di luar rentang wajar", "%d..%d" % (YEAR_MIN, YEAR_MAX)))

        # --- nilai & skala unit ---
        value, val_bad = _to_decimal(rec.value)
        scale, unit_label = config.detect_value_scale(rec.value_unit)
        if val_bad:
            issues.append(Issue(row, "value", "VALUE_NOT_NUMERIC", rec.value, "INVALID",
                                "nilai bukan angka", "perbaiki file sumber"))
        if value is not None and value < 0:
            issues.append(Issue(row, "value", "VALUE_NEGATIVE", rec.value, "INVALID",
                                "nilai negatif tidak wajar", "periksa file sumber"))
        if value is not None and scale is None and _clean(rec.value):
            issues.append(Issue(row, "value", "VALUE_UNIT_UNKNOWN", rec.value_unit, "WARNING",
                                "satuan nilai tidak dapat dipastikan",
                                "sebutkan satuan (mis. US$ Thousand)"))
        value_norm = None
        if value is not None and scale is not None:
            value_norm = value * scale

        # --- kuantitas & unit ---
        qty, qty_bad = _to_decimal(rec.qty)
        if qty_bad:
            issues.append(Issue(row, "qty", "QTY_NOT_NUMERIC", rec.qty, "INVALID",
                                "kuantitas bukan angka", "perbaiki file sumber"))
        qty_unit = _clean(rec.qty_unit).upper() or None
        if qty is not None and not qty_unit:
            issues.append(Issue(row, "qty_unit", "QTY_UNIT_UNKNOWN", rec.qty_unit, "WARNING",
                                "satuan kuantitas tidak dapat dipastikan",
                                "tambahkan kolom unit (kg/ton)"))

        # --- versi HS ---
        hs_version = _clean(rec.hs_version).upper()
        if hs_version and hs_version not in config.KNOWN_HS_VERSIONS:
            issues.append(Issue(row, "hs_version", "HS_VERSION_UNKNOWN", rec.hs_version, "WARNING",
                                "versi HS tidak dikenali", "HS2017|HS2022|HS2012"))

        nr.update(
            reporter_code=reporter_code, partner_code=partner_code, flow_norm=flow_norm or "",
            product_code=product_code, year=year, qty=qty, qty_unit=qty_unit,
            value=value, value_unit_source=unit_label, value_usd_norm=value_norm,
            hs_version=hs_version, issues=issues,
        )
        return nr

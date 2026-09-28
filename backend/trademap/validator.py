"""TradeMapValidator — menentukan status VALID / WARNING / INVALID per baris.

Status akhir = INVALID bila ada temuan severity INVALID, selain itu WARNING bila
ada temuan WARNING, selain itu VALID. Record INVALID tidak dimasukkan ke
trademap_trade, tetapi tetap tercatat di trademap_validation_results (lineage).
"""
from backend.trademap.models import Issue


class TradeMapValidator:
    def validate(self, record, extra_issues=None):
        """Isi record.validation_status/notes. Return list semua issue."""
        issues = list(getattr(record, "issues", []) or [])
        issues.extend(extra_issues or [])

        # temuan dari mapping (disisipkan processor)
        hs_status = record.hs_mapping_status
        if hs_status == "AMBIGUOUS":
            issues.append(Issue(record.raw.row_ref, "product_code", "HS_AMBIGUOUS",
                                record.product_code, "WARNING",
                                "kode HS cocok ke >1 tariff line master",
                                "pilih tariff line / gunakan level 6-digit"))
        elif hs_status in ("HS_MAPPING_REQUIRED", "NOT_FOUND"):
            issues.append(Issue(record.raw.row_ref, "product_code", "HS_MAPPING_REQUIRED",
                                record.product_code, "WARNING",
                                "kode HS belum terpetakan ke ms_hscode",
                                "tambahkan mapping HS ke master"))
        elif hs_status == "NEEDS_VALIDATION":
            issues.append(Issue(record.raw.row_ref, "hs_version", "HS_VERSION_MISMATCH",
                                record.hs_version, "WARNING",
                                "versi HS sumber berbeda dari master; perlu validasi",
                                record.hs_version or "HS2022"))

        if record.id_ms_komoditas is None and record.product_code:
            issues.append(Issue(record.raw.row_ref, "product_code", "COMMODITY_UNMAPPED",
                                record.product_code, "WARNING",
                                "komoditas_5_2026 tidak dapat ditentukan unik",
                                "periksa bridge ms_komoditas_hscode"))

        # required fields
        for field, val, kode in (
            ("reporter", record.reporter_code, "REPORTER_MISSING"),
            ("product_code", record.product_code, "PRODUCT_CODE_MISSING"),
        ):
            if not val:
                issues.append(Issue(record.raw.row_ref, field, kode, val, "INVALID",
                                    "field wajib kosong", "isi " + field))
        if record.flow_norm not in ("EXPORT", "IMPORT"):
            issues.append(Issue(record.raw.row_ref, "flow", "FLOW_INVALID",
                                record.raw.flow, "INVALID",
                                "trade flow tidak valid", "EXPORT|IMPORT"))
        if record.year is None:
            issues.append(Issue(record.raw.row_ref, "year", "YEAR_INVALID",
                                record.raw.year, "INVALID", "tahun tidak valid", "YYYY"))

        # nilai wajib untuk record yang lolos
        if record.value is None:
            issues.append(Issue(record.raw.row_ref, "value", "VALUE_MISSING",
                                record.raw.value, "INVALID", "nilai tidak ada", "isi nilai"))
        elif record.value == 0:
            issues.append(Issue(record.raw.row_ref, "value", "VALUE_ZERO",
                                record.raw.value, "WARNING", "nilai nol", "periksa sumber"))

        record.issues = issues
        record.validation_status = self._aggregate(issues)
        if issues:
            record.validation_notes = "; ".join(
                "%s:%s" % (i.kode, i.field) for i in issues)[:500]
        return issues

    @staticmethod
    def _aggregate(issues):
        if any(i.severity == "INVALID" for i in issues):
            return "INVALID"
        if any(i.severity == "WARNING" for i in issues):
            return "WARNING"
        return "VALID"

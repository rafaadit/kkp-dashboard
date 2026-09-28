"""Model data pipeline TradeMap (dataclass ringan, kompatibel Python 3.9)."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional


@dataclass
class RawRecord:
    """Satu baris data hasil parsing (belum dinormalisasi)."""
    row_ref: str
    reporter: str = ""
    partner: str = ""
    flow: str = ""
    product_code: str = ""
    product_desc: str = ""
    year: Any = None
    qty: Any = None
    qty_unit: str = ""
    value: Any = None
    value_unit: str = ""
    hs_version: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Issue:
    """Temuan validasi untuk satu field."""
    row_ref: str
    field: str
    kode: str
    source_value: Any = None
    severity: str = "WARNING"  # WARNING | INVALID
    reason: str = ""
    recommended: str = ""


@dataclass
class HSResult:
    """Hasil harmonisasi HS."""
    source_code: str
    source_version: str
    status: str  # MAPPED | AMBIGUOUS | HS_MAPPING_REQUIRED | NOT_FOUND | NEEDS_VALIDATION
    id_ms_hscode: Optional[int] = None
    id_ms_komoditas: Optional[int] = None
    candidate_count: int = 0
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""


@dataclass
class NormalizedRecord:
    """Baris setelah normalisasi + mapping + validasi."""
    raw: RawRecord
    reporter_code: str = ""
    partner_code: str = ""
    flow_norm: str = ""
    product_code: str = ""
    year: Optional[int] = None
    qty: Optional[Decimal] = None
    qty_unit: Optional[str] = None
    value: Optional[Decimal] = None
    value_unit_source: Optional[str] = None
    value_usd_norm: Optional[Decimal] = None
    hs_version: str = ""
    id_ms_negara_reporter: Optional[int] = None
    id_ms_negara: Optional[int] = None
    id_ms_hscode: Optional[int] = None
    id_ms_komoditas: Optional[int] = None
    hs_mapping_status: str = "HS_MAPPING_REQUIRED"
    hs_candidates: List[Dict[str, Any]] = field(default_factory=list)
    validation_status: str = "WARNING"
    validation_notes: str = ""
    issues: List[Issue] = field(default_factory=list)
    duplicate: bool = False


@dataclass
class ParseResult:
    path: str
    file_name: str
    file_format: str
    file_hash: str
    headers: List[str] = field(default_factory=list)
    value_header: str = ""
    records: List[RawRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors


@dataclass
class ProcessStats:
    total_rows: int = 0
    valid_rows: int = 0
    warning_rows: int = 0
    invalid_rows: int = 0
    duplicate_rows: int = 0
    mapped_rows: int = 0
    unmapped_rows: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0

    def as_dict(self):
        return {
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "warning_rows": self.warning_rows,
            "invalid_rows": self.invalid_rows,
            "duplicate_rows": self.duplicate_rows,
            "mapped_rows": self.mapped_rows,
            "unmapped_rows": self.unmapped_rows,
            "inserted_rows": self.inserted_rows,
            "updated_rows": self.updated_rows,
        }


@dataclass
class ProcessResult:
    ok: bool
    commit: bool
    stats: ProcessStats
    raw_id: Optional[int] = None
    job_id: Optional[int] = None
    file_hash: str = ""
    issues: List[Issue] = field(default_factory=list)
    records: List[NormalizedRecord] = field(default_factory=list)
    error: str = ""

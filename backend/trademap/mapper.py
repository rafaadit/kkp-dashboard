"""TradeMapMapper — resolusi ke master MySQL + harmonisasi HS.

Prinsip:
- Master data project (ms_negara/ms_hscode/ms_komoditas) adalah source of truth.
- Mapping TIDAK dikarang: kode HS TradeMap dicocokkan apa adanya ke kolom
  kanonikal ms_hscode (kode_hs), lalu ke tingkat subpos/pos/bab yang memang ada.
- Bila 6-digit cocok ke beberapa tariff line 8-digit -> AMBIGUOUS (bukan dipilih
  diam-diam). Bila tidak ada -> HS_MAPPING_REQUIRED.
- Komoditas diambil dari bridge ms_komoditas_hscode (kolom komoditas_5_2026),
  hanya jika hasilnya tunggal (tidak ambigu).
"""
import json

from backend.trademap import config
from backend.trademap.models import HSResult, Issue

KOMPODITAS_KOLOM = "komoditas_5_2026"


class TradeMapMapper:
    def __init__(self, conn):
        self.conn = conn
        self._country_code = {}
        self._country_name = {}
        self._hs_cache = {}
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        cur = self.conn.cursor()
        cur.execute("SELECT id, kode_negara, nama_negara FROM ms_negara")
        for r in cur.fetchall():
            self._country_code[r["kode_negara"].strip().upper()] = r["id"]
            self._country_name[r["nama_negara"].strip().upper()] = r["id"]
        self._loaded = True

    # -- negara -------------------------------------------------------------
    def map_country(self, value):
        """Return (id|None, nama|None). Coba kode ISO lalu nama."""
        self._load()
        v = (value or "").strip()
        if not v:
            return None, None
        up = v.upper()
        if up in self._country_code:
            return self._country_code[up], up
        if up in self._country_name:
            return self._country_name[up], up
        return None, v

    # -- HS + komoditas -----------------------------------------------------
    def _candidates(self, code):
        cur = self.conn.cursor()
        tiers = [
            ("kode_hs = %s", "kode_hs"),
            ("hs_subpos_6digit = %s", "hs_subpos_6digit"),
            ("hs_pos_4digit = %s", "hs_pos_4digit"),
            ("hs_bab_2digit = %s", "hs_bab_2digit"),
        ]
        for where, _ in tiers:
            cur.execute(
                "SELECT id, kode_hs, hs_subpos_6digit, uraian_en FROM ms_hscode "
                "WHERE " + where, (code,))
            rows = cur.fetchall()
            if rows:
                return rows
        return []

    def _commodity_ids(self, hscode_ids):
        if not hscode_ids:
            return []
        placeholders = ",".join(["%s"] * len(hscode_ids))
        cur = self.conn.cursor()
        cur.execute(
            "SELECT DISTINCT k.ms_komoditas_id AS id FROM ms_komoditas_hscode k "
            "WHERE k.ms_hscode_id IN (" + placeholders + ") AND k.kolom_sumber = %s",
            list(hscode_ids) + [KOMPODITAS_KOLOM],
        )
        return [r["id"] for r in cur.fetchall()]

    def map_hs(self, code, version=""):
        """Return HSResult (lihat models)."""
        code = (code or "").strip()
        version = (version or "").strip().upper()
        if not code:
            return HSResult(code, version, "NOT_FOUND", notes="kode HS kosong")

        cache_key = (code, version)
        if cache_key in self._hs_cache:
            return self._hs_cache[cache_key]

        rows = self._candidates(code)
        cands = [{"id": r["id"], "kode_hs": r["kode_hs"], "uraian_en": r["uraian_en"]} for r in rows]
        status = "HS_MAPPING_REQUIRED"
        id_hs = None
        if len(cands) == 1:
            status, id_hs = "MAPPED", cands[0]["id"]
        elif len(cands) > 1:
            status = "AMBIGUOUS"

        id_kom = None
        if cands:
            kom_ids = self._commodity_ids([c["id"] for c in cands])
            if len(kom_ids) == 1:
                id_kom = kom_ids[0]

        notes = []
        if status == "AMBIGUOUS":
            notes.append("%d kandidat tariff line untuk %s" % (len(cands), code))
        elif status == "HS_MAPPING_REQUIRED":
            notes.append("tidak ada ms_hscode yang cocok untuk %s" % code)

        # versi HS
        if version and version not in config.KNOWN_HS_VERSIONS:
            notes.append("versi %s tidak dikenali" % version)
        elif version and version != config.MASTER_HS_VERSION:
            notes.append("versi sumber %s != master %s" % (version, config.MASTER_HS_VERSION))
            if status == "MAPPED":
                status = "NEEDS_VALIDATION"
        elif not version:
            notes.append("versi HS sumber belum diketahui; kandidat dari %s" % config.MASTER_HS_VERSION)

        if cands and not id_kom:
            notes.append("komoditas %s tidak dapat ditentukan unik" % KOMPODITAS_KOLOM)

        result = HSResult(
            source_code=code, source_version=version or "", status=status,
            id_ms_hscode=id_hs, id_ms_komoditas=id_kom,
            candidate_count=len(cands), candidates=cands, notes="; ".join(notes))
        self._hs_cache[cache_key] = result
        return result

    def record_hs_mapping(self, result, sumber="trademap"):
        """Upsert hasil harmonisasi ke trademap_hs_mapping (cache/interface)."""
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO trademap_hs_mapping
               (source_code, source_version, ms_hscode_id, ms_komoditas_id, mapping_status,
                candidate_count, candidates_json, notes, sumber)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 ms_hscode_id=VALUES(ms_hscode_id), ms_komoditas_id=VALUES(ms_komoditas_id),
                 mapping_status=VALUES(mapping_status), candidate_count=VALUES(candidate_count),
                 candidates_json=VALUES(candidates_json), notes=VALUES(notes), sumber=VALUES(sumber)""",
            (result.source_code, result.source_version, result.id_ms_hscode, result.id_ms_komoditas,
             result.status, result.candidate_count,
             json.dumps(result.candidates, ensure_ascii=False), result.notes, sumber),
        )

    def country_issue(self, raw_value, mapped_id, field):
        if (raw_value or "").strip() and mapped_id is None:
            return Issue("", field, "COUNTRY_UNMAPPED", raw_value, "WARNING",
                         "negara tidak ditemukan di ms_negara",
                         "tambahkan/petakan ke ms_negara")
        return None

"""TradeMapParser — membaca file CSV/TSV/XLSX, deteksi header, ekstraksi baris.

Tidak meng-hardcode posisi kolom: header dideteksi lewat alias (config.HEADER_ALIASES)
dan baris header dicari pada beberapa baris awal (TradeMap kadang diawali metadata).
"""
import csv
import hashlib
import os

from backend.trademap import config
from backend.trademap.models import ParseResult, RawRecord


class TradeMapParser:
    def __init__(self, aliases=None, header_scan_rows=None):
        self.aliases = aliases or config.HEADER_ALIASES
        self.header_scan_rows = header_scan_rows or config.HEADER_SCAN_ROWS

    # -- util ---------------------------------------------------------------
    def _alias_map(self):
        amap = {}
        for key, aliases in self.aliases.items():
            for a in aliases:
                amap[config.norm_header(a)] = key
        return amap

    def _find_header(self, rows, amap):
        """Cari indeks baris header terbaik pada N baris pertama."""
        best_idx, best_map, best_score = None, {}, 0
        for i, row in enumerate(rows[: self.header_scan_rows]):
            fmap = {}
            for j, cell in enumerate(row):
                key = amap.get(config.norm_header(cell))
                if key and key not in fmap:
                    fmap[key] = j
            # header harus mengenali minimal kolom wajib
            if not all(k in fmap for k in config.REQUIRED_HEADERS):
                continue
            if len(fmap) > best_score:
                best_idx, best_map, best_score = i, fmap, len(fmap)
        return best_idx, best_map

    def _metadata_from_rows(self, rows):
        """Extract metadata 'Key: value' dari baris sebelum header."""
        meta = {}
        for row in rows:
            for cell in row:
                if not isinstance(cell, str) or ":" not in cell:
                    continue
                k, _, v = cell.partition(":")
                k, v = k.strip().lower(), v.strip()
                if k and v and len(k) <= 40:
                    meta.setdefault(k, v)
        return meta

    def _to_records(self, rows, fmap, value_header):
        records = []
        for i, row in enumerate(rows):
            vals = list(row)
            get = lambda key: (str(vals[fmap[key]]).strip()  # noqa: E731
                               if key in fmap and fmap[key] < len(vals) and vals[fmap[key]] is not None
                               else "")
            product_code = get("product_code")
            if not product_code:
                continue
            rec = RawRecord(
                row_ref="#%d" % (i + 1),
                reporter=get("reporter"),
                partner=get("partner"),
                flow=get("flow"),
                product_code=product_code,
                product_desc=get("product_desc"),
                year=get("year") or get("period") or None,
                qty=get("qty") or None,
                qty_unit=get("qty_unit"),
                value=get("value") or None,
                value_unit=get("value_unit") or value_header or "",
                hs_version=get("hs_version"),
            )
            records.append(rec)
        return records

    def _read_csv(self, path):
        with open(path, "rb") as fb:
            raw = fb.read()
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("tidak bisa decode file teks")
        sample = text[:8192]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = [r for r in csv.reader(text.splitlines(), dialect)]
        return rows

    def _read_xlsx(self, path):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            ws = wb.worksheets[0]
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
        finally:
            wb.close()
        return rows

    # -- public -------------------------------------------------------------
    def parse(self, path):
        file_name = os.path.basename(path)
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        fmt = {"csv": "csv", "tsv": "tsv", "txt": "txt", "xlsx": "xlsx", "xlsm": "xlsx"}.get(ext)
        res = ParseResult(path=path, file_name=file_name, file_format=fmt or ext, file_hash="")
        if not os.path.exists(path):
            res.errors.append("FILE_NOT_FOUND")
            return res
        with open(path, "rb") as fb:
            res.file_hash = hashlib.sha256(fb.read()).hexdigest()
        if os.path.getsize(path) == 0:
            res.errors.append("FILE_EMPTY")
            return res
        if fmt is None:
            res.errors.append("FORMAT_UNSUPPORTED:%s" % ext)
            return res

        try:
            rows = self._read_xlsx(path) if fmt == "xlsx" else self._read_csv(path)
        except Exception as e:  # noqa: BLE001
            res.errors.append("PARSE_ERROR:%s" % e)
            return res

        rows = [r for r in rows if r is not None and any(c not in (None, "") for c in r)]
        if not rows:
            res.errors.append("FILE_EMPTY")
            return res

        amap = self._alias_map()
        idx, fmap = self._find_header(rows, amap)
        if idx is None:
            res.errors.append("HEADER_NOT_FOUND")
            res.headers = [str(c) for c in rows[0]]
            return res

        res.headers = [str(c) for c in rows[idx]]
        res.metadata = self._metadata_from_rows(rows[:idx])
        value_header = ""
        if "value" in fmap and fmap["value"] < len(rows[idx]):
            value_header = str(rows[idx][fmap["value"]] or "")
        res.value_header = value_header
        res.records = self._to_records(rows[idx + 1:], fmap, value_header)
        if not res.records:
            res.errors.append("NO_DATA_ROWS")
        return res

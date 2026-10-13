"""Robot TradeMap TANPA API key — unduh grid query legacy.trademap.org.

ITC TradeMap tidak menyediakan API publik umum (API ber-token hanya diberikan
pada kasus khusus, lihat FAQ). Jalur yang memang dapat diakses tanpa kunci
adalah halaman query situs *legacy*: hasil query dirender sebagai HTML polos.
Robot ini mengikuti ketentuan unduh situs (tabel yang sedang ditampilkan per
query, bukan bulk seluruh dunia).

Alur:
  1. GET halaman query (param nvpm) -> ikuti redirect sesi cookieless ASP.NET
     (path berisi segment /(X(1)S(<id>))/ yang dipertahankan antar-request).
  2. Baca baris "Unit : ..." untuk skala nilai (informatif).
  3. Deteksi baris header grid (kolom *Exported/Imported <value|quantity> in
     <tahun>*) -> ambil arus (Export/Import), indikator, dan daftar tahun.
  4. Baca baris data [level, kode, label, v_y1..v_yn] -> melt ke bentuk panjang
     (satu baris per tahun) seperti format fixture TradeMap.
  5. Tulis CSV dgn header yang sudah dikenal pipeline:
       Reporter,Partner,Flow,Product code,Product Label,Year,Trade Value (US$ Thousand)
     Nilai sel DIBIARKAN pada skala situs ('US Dollar thousand'); normalizer
     pipeline yang mengalikan sesuai header kolom.

Catatan:
  - Granularity mengikuti level agregasi halaman yang dipilih (HS2/HS4/...).
  - Label produk bisa terpotong oleh situs ("...  . . .").
  - Baris "TOTAL" (agregat semua produk) TIDAK disimpan; ringkasannya bisa
    dihitung ulang dari data per kode.
"""
import csv
import html
import io
import os
import re
import time
import urllib.parse
import urllib.request

DEFAULT_URL = "https://legacy.trademap.org"
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_SESSION_PATH = re.compile(r"/(\(X\(1\)S\([0-9a-z]+\)\))/")


class WebError(RuntimeError):
    """Galat unduhan/interpretasi halaman TradeMap (harus ditandai FAILED)."""


class Grid:
    """Hasil parse satu halaman grid TradeMap."""

    def __init__(self, level, indicator, flow, years, unit, rows):
        self.level = level      # label level agregasi (mis. "HS4")
        self.indicator = indicator  # "value" | "quantity"
        self.flow = flow        # "Export" | "Import" | "Re-Export" | "Re-Import"
        self.years = years      # [int, ...]
        self.unit = unit        # baris unit mentah situs, mis. "US Dollar thousand"
        self.rows = rows        # [(product_code, product_label, [nilai..])]

    def __repr__(self):  # pragma: no cover - debug helper
        return "Grid(%s, %s/%s, years=%s..%s, rows=%d)" % (
            self.level, self.flow, self.indicator,
            self.years[0] if self.years else None,
            self.years[-1] if self.years else None, len(self.rows))


_FLOW_WORD = {
    "exported": "Export",
    "imported": "Import",
    "re exported": "Re-Export",
    "re imported": "Re-Import",
}

_HEADER_RE = re.compile(r"^(re[- ]?)?(ex-?ported|im-?ported)\s+(value|quantity)\s+in\s+(\d{4})$", re.I)

# Kombinasi flag nvpm yang terverifikasi menghasilkan grid nilai:
#   posisi ke-4 (1=Import, 2=Export); indikator = nilai (US$ Thousand).
_FLAG_IMPORT = "1|1|1|1|2|1|1|1|1|1"
_FLAG_EXPORT = "1|1|1|2|2|1|1|1|1|1"


def build_query(flow="Export", reporter="360", partner=None, product="TOTAL"):
    """Bangun path halaman query Country_SelProduct (reporter x <partner|world>).

    flow: Export | Import | Re-Export | Re-Import (fallback Export).
    reporter: kode ISO3-numerik TradeMap (default 360 = Indonesia).
    partner: kode ISO3-numerik partner (None/"" = seluruh dunia).
    product: kode HS (mis. "TOTAL", "03", "030617").
    Return path relatif untuk TradeMapWebSession.fetch().
    """
    flags = _FLAG_IMPORT if str(flow).lower().startswith("import") else _FLAG_EXPORT
    nvpm = "1|%s||%s||%s|||%s" % (reporter, partner or "", product, flags)
    return "/Country_SelProduct_TS.aspx?nvpm=%s" % urllib.parse.quote(nvpm)


def _cell_text(cell):
    t = re.sub(r"<[^>]+>", "", cell)
    return " ".join(html.unescape(t).split())


def _cell_rows(html_body):
    """Semua baris <tr> sebagai list cell teks."""
    return [
        [_cell_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", html_body, re.S)
    ]


def _clean_num(v):
    s = " ".join(str(v).split()).replace(",", "").replace(" ", "").strip()
    if not s or s.lower() in ("-", "--", "n.a.", "na", "n/a", ".."):
        return ""
    return s


def extract_grid(html_body):
    """Parse grid dari halaman TradeMap (lihat docstring modul).

    Return Grid. Raise WebError bila struktur halaman tidak dikenali.
    """
    rows = _cell_rows(html_body)
    header_idx = None
    for i, cs in enumerate(rows):
        if len(cs) >= 4 and cs[1] == "Code" and cs[2] == "Product label":
            header_idx = i
            break
    if header_idx is None:
        raise WebError("header grid TradeMap tidak ditemukan (situs mungkin berubah)")

    hdr = rows[header_idx]
    level = hdr[0] or ""
    years, indicator, flow = [], None, None
    for c in hdr[3:]:
        m = _HEADER_RE.match(c or "")
        if not m:
            break
        years.append(int(m.group(4)))
        indicator = m.group(3).lower()
        fk = ((m.group(1) or "") + " " + m.group(2)).strip().replace("-", " ").lower()
        flow = _FLOW_WORD.get(fk, fk.title())
    if not years:
        raise WebError("tidak ada kolom tahun pada grid (query berubah?)")

    unit = ""
    um = re.search(r"Unit\s*:\s*([^<&]{0,40})", html_body)
    if um:
        unit = " ".join(um.group(1).split())

    data_rows = []
    ncol = len(hdr)
    for cs in rows[header_idx + 1:]:
        if len(cs) != ncol:
            break  # akhir grid (pagination/footnote)
        code = cs[1].strip()
        if code.upper() == "TOTAL" or not re.fullmatch(r"\d+", code):
            continue
        values = [_clean_num(cs[3 + i]) for i in range(len(years))]
        data_rows.append((code, cs[2].strip(), values))
    if not data_rows:
        raise WebError("grid tanpa baris data")

    return Grid(level=level, indicator=indicator, flow=flow,
                years=years, unit=unit, rows=data_rows)


_SUBHEADER_RE = re.compile(r"^Value in (\d{4})$", re.I)


def extract_bilateral_grid(html_body, flow="Export"):
    """Parse grid *bilateral* (reporter x partner) dari halaman Country_SelProduct.

    Halaman hasil query dengan partner tertentu berisi header
    ['<level>', 'Product code', 'Product label', 'Reporter X to <partner>',
     '...imports from world', "Reporter's exports to world"] dan baris sub-header
    'Value in <tahun>' berulang per blok. Yang diambil hanya BLOK PERTAMA
    (arus Indonesia -> partner). Return Grid dengan rows [(code, label, values)].
    """
    rows = _cell_rows(html_body)
    header_idx = None
    for i, cs in enumerate(rows):
        if len(cs) >= 4 and cs[1] == "Product code" and cs[2] == "Product label":
            header_idx = i
            break
    if header_idx is None:
        raise WebError("header grid bilateral tidak ditemukan (situs mungkin berubah)")

    level = rows[header_idx][0] or ""
    sub = rows[header_idx + 1] if header_idx + 1 < len(rows) else []
    years = []
    for c in sub:
        m = _SUBHEADER_RE.match((c or "").strip())
        if m:
            years.append(int(m.group(1)))
        elif years:
            break
    if not years:
        raise WebError("tidak ada kolom tahun pada grid bilateral")

    unit = ""
    um = re.search(r"Unit\s*:\s*([^<&]{0,40})", html_body)
    if um:
        unit = " ".join(um.group(1).split())

    n = len(years)
    data_rows = []
    for cs in rows[header_idx + 2:]:
        code = (cs[1] or "").strip()
        if not code or code.upper() == "TOTAL" or not re.fullmatch(r"\d+", code):
            continue
        if len(cs) < 3 + n:
            break
        values = [_clean_num(cs[3 + i]) for i in range(n)]
        data_rows.append((code, cs[2].strip(), values))
    if not data_rows:
        raise WebError("grid bilateral tanpa baris data")

    fk = " ".join((flow or "").split()).title()
    return Grid(level=level, indicator="value", flow=fk,
                years=years, unit=unit, rows=data_rows)


def grid_to_csv(grid, reporter="ID", partner="WLD", flow=None):
    """Melt grid lebar -> CSV bentuk panjang siap dimakan pipeline.

    Kolom nilai memakai header 'Trade Value (US$ Thousand)' (skala x1000 oleh
    normalizer pipeline); untuk indikator quantity memakai header 'Quantity'.
    """
    csv_flow = flow or grid.flow
    val_col = ("Trade Value (US$ Thousand)" if grid.indicator == "value"
               else "Quantity")
    header = ["Reporter", "Partner", "Flow", "Product code", "Product Label",
              "Year", val_col]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for code, label, values in grid.rows:
        for i, year in enumerate(grid.years):
            v = values[i] if i < len(values) else ""
            w.writerow([reporter, partner, csv_flow, code, label, year, v])
    return buf.getvalue()


class TradeMapWebSession:
    """Sesi HTTP ringan ke legacy.trademap.org (stdlib saja).

    Mempertahankan cookie + prefix sesi cookieless ASP.NET agar halaman
    berikutnya pada sesi yang sama; throttle antar-request.
    """

    def __init__(self, base=None, user_agent=None, delay=1.0):
        self.base = (base or os.environ.get("TRADEMAP_WEB_URL") or DEFAULT_URL).rstrip("/")
        self.ua = user_agent or USER_AGENT
        self.delay = float(os.environ.get("TRADEMAP_WEB_DELAY", delay) or delay)
        self._jar = __import__("http.cookiejar").cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar))
        self._prefix = ""

    def _headers(self):
        return {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.8",
        }

    def target(self, path):
        if re.match(r"^https?://", path):
            return path
        if not path.startswith("/"):
            path = "/" + path
        if self._prefix:
            return "%s%s%s" % (self.base, self._prefix.rstrip("/"), path)
        return self.base + path

    def fetch(self, path, retries=2):
        url = self.target(path)
        last = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=self._headers())
                with self._opener.open(req, timeout=60) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    final = resp.geturl() or url
                m = _SESSION_PATH.search(final)
                if m:
                    self._prefix = m.group(0)
                return body
            except OSError as e:
                last = e
                time.sleep(self.delay * 2)
        raise WebError("unduh halaman TradeMap gagal: %s" % last)

    def post_form(self, path, data, retries=2):
        """POST form ASP.NET (urlencoded). Kembalikan body HTML halaman hasil."""
        url = self.target(path)
        last = None
        for attempt in range(retries):
            try:
                enc = urllib.parse.urlencode(data).encode()
                req = urllib.request.Request(url, data=enc, headers=self._headers())
                with self._opener.open(req, timeout=90) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    final = resp.geturl() or url
                m = _SESSION_PATH.search(final)
                if m:
                    self._prefix = m.group(0)
                return body
            except OSError as e:
                last = e
                time.sleep(self.delay * 2)
        raise WebError("POST form TradeMap gagal: %s" % last)


_BILATERAL_BASE = ("/Country_SelProduct_TS.aspx?nvpm="
                   "1%7c360%7c%7c%7c%7cTOTAL%7c%7c%7c1%7c1%7c1%7c2%7c2%7c1%7c1%7c1%7c1%7c1")
_FORM_FIELDS = {
    "ctl00$MenuControl$DDL_Language": "en",
    "ctl00$NavigationControl$DropDownList_Country": "360",
    "ctl00$NavigationControl$DropDownList_Country_Group": "-2",
    "ctl00$NavigationControl$DropDownList_Partner_Group": "-2",
    "ctl00$NavigationControl$DropDownList_TradeType": "E",
    "ctl00$NavigationControl$DropDownList_OutputType": "TSY",
    "ctl00$NavigationControl$DropDownList_OutputOption": "ByProduct",
    "ctl00$NavigationControl$DropDownList_Product": "TOTAL",
    "ctl00$NavigationControl$DropDownList_Product_Group": "0",
    "ctl00$NavigationControl$DropDownList_ProductClusterLevel": "2",
    "ctl00$NavigationControl$DropDownList_TS_Indicator": "V",
    "ctl00$NavigationControl$DropDownList_TS_Currency": "USD",
    "ctl00$PageContent$GridViewPanelControl$DropDownList_NumTimePeriod": "5",
    "ctl00$PageContent$GridViewPanelControl$DropDownList_PageSize": "10",
    "ctl00$NavigationControl$Country_Selection": "countries",
}


def _field(body, name):
    m = re.search(r'name="%(re)s" value="([^"]*)"' % {"re": re.escape(name)}, body)
    return m.group(1) if m else ""


def fetch_bilateral(flow, reporter_code, partner, product="TOTAL",
                    session=None):
    """Ambil grid bilateral reporter x partner via postback ASP.NET.

    Situs legacy.trademap.org hanya merender data bilateral lewat POST form
    (nvpm GET dengan partner diabaikan). Return Grid (blok Indonesia->partner).
    """
    flow = (flow or "Export").strip().title()
    is_import = str(flow).lower().startswith("import")
    sess = session or TradeMapWebSession()

    page = sess.fetch(_BILATERAL_BASE)
    data = dict(_FORM_FIELDS)
    data["ctl00$NavigationControl$DropDownList_Partner"] = partner
    data["ctl00$NavigationControl$DropDownList_TradeType"] = "I" if is_import else "E"
    data["__VIEWSTATE"] = _field(page, "__VIEWSTATE")
    data["__VIEWSTATEGENERATOR"] = _field(page, "__VIEWSTATEGENERATOR")
    data["__EVENTVALIDATION"] = _field(page, "__EVENTVALIDATION")
    data["ctl00$forgeryToken"] = _field(page, "ctl00$forgeryToken")

    body = sess.post_form("/Country_SelProduct_TS.aspx", data)
    return extract_bilateral_grid(body, flow=flow)


def run(flow="Export", reporter_id="ID", reporter_code="360", partner=None,
        product="TOTAL", download_dir=None, session=None):
    """Unduh + parse + tulis CSV untuk satu query.

    partner=None -> grid dunia (Indonesia ke seluruh dunia), GET biasa.
    partner set   -> grid bilateral (Indonesia -> negara partner), POST form
                     (halaman legacy hanya merender bilateral lewat postback).

    Return (path_cvs, Grid).
    """
    flow = flow or "Export"
    sess = session or TradeMapWebSession()
    if download_dir is None:
        download_dir = os.environ.get("TRADEMAP_WEB_DIR", "./data/trademap")
    os.makedirs(download_dir, exist_ok=True)

    if partner and str(partner).strip():
        # hanya bab 03 (hasil perikanan) yang disimpan bila product bab diminta
        keep = None
        if product and re.fullmatch(r"\d{2}", str(product)):
            keep = str(product)
        grid = fetch_bilateral(flow, reporter_code, str(partner).strip(),
                               product=product or "TOTAL", session=sess)
        rows = [r for r in grid.rows if keep is None or r[0] == keep]
        if not rows:
            raise WebError("bab %s tidak ada pada grid bilateral %s"
                           % (keep, partner))
        grid = Grid(grid.level, grid.indicator, grid.flow, grid.years,
                    grid.unit, rows)
        csv_text = grid_to_csv(grid, reporter=reporter_id,
                               partner=str(partner).strip(), flow=grid.flow)
        y0, y1 = grid.years[0], grid.years[-1]
        name = "trademap_web_%s_%d-%d_partner_%s.csv" % (
            flow.lower().replace("-", "_"), y0, y1, str(partner).strip())
    else:
        html_body = sess.fetch(build_query(flow, reporter=reporter_code,
                                           partner=None, product=product))
        grid = extract_grid(html_body)
        csv_text = grid_to_csv(grid, reporter=reporter_id,
                               partner="WLD", flow=grid.flow)
        y0, y1 = grid.years[0], grid.years[-1]
        name = "trademap_web_%s_%d-%d_%s.csv" % (
            flow.lower().replace("-", "_"), y0, y1, "world")
    path = os.path.join(download_dir, name)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(csv_text)
    return path, grid
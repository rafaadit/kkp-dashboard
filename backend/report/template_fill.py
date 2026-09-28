#!/usr/bin/env python3
"""
Template-driven PPT fill (rework PHASE 7 per user directive).

Menggunakan file template resmi `Draft_EKSIM_Jan-Juni_2026_06082026 (1).pptx`
dan *mengisi ulang* nilai-nilai di dalamnya dari DB raw_exim (bukan membangun
slide dari nol):

  - teks periode (cover + setiap slide),
  - kartu negara tujuan / negara asal + komoditas (+ pangsa % dan YoY),
  - daftar top-5 pada slide kinerja,
  - box total impor / nilai ekspor / volume,
  - data chart (chart.replace_data, format chart dipertahankan).

Pendekatan: content-driven *fill spec* — setiap teks pada template
dicocokkan secara normalisasi (norm) dengan referensi deck; yang cocok diganti
nilai hasil hitung DB. Teks yang tidak dikenal dilewati (tidak diutak-atik).
Referensi diambil langsung dari deck resmi sehingga aman terhadap tata letak.

Modul dipakai oleh `backend/report/generate_ppt.py`.
"""
from __future__ import annotations

import copy
import re

import pymysql  # noqa: F401  (agar error DB jelas sejak import)

from backend.db import get_connection

# --------------------------------------------------------------------------
# Konstanta nama bulan / label
# --------------------------------------------------------------------------
BULAN_ID = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
S_BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu",
           "Sep", "Okt", "Nov", "Des"]

# Nama tampilan untuk kelompok negara (partner) — (UPPERCASE card, title-case row)
PARTNER_UPPER = {
    "United States": "AMERIKA SERIKAT",
    "China": "TIONGKOK",
    "Japan": "JAPAN",
    "Asean": "ASEAN",
    "Uni Eropa": "UNI EROPA",
    "Lainnya": "LAINNYA",
    "Korea Selatan": "KOREA SELATAN",
    "Taiwan": "TAIWAN",
    "Timur Tengah": "TIMUR TENGAH",
    "Hong Kong": "HONG KONG",
    "United Kingdom": "UNITED KINGDOM",
    "Australia And New Zealand": "AUSTRALIA & NZ",
    "Canada": "CANADA",
    "Rusia": "RUSIA",
    "Indonesia": "INDONESIA",
}
PARTNER_TITLE = {
    "United States": "Amerika Serikat",
    "China": "Tiongkok",
    "Japan": "Jepang",
    "Asean": "ASEAN",
    "Uni Eropa": "Uni Eropa",
    "Lainnya": "Lainnya",
    "Korea Selatan": "Korea Selatan",
    "Taiwan": "Taiwan",
    "Timur Tengah": "Timur Tengah",
    "Hong Kong": "Hong Kong",
    "United Kingdom": "United Kingdom",
    "Australia And New Zealand": "Australia & NZ",
    "Canada": "Kanada",
    "Rusia": "Rusia",
    "Indonesia": "Indonesia",
}
# Nama tampilan komoditas (komoditas_5_2026)
KOMODITAS_UPPER = {
    "Udang": "UDANG",
    "Tuna-Cakalang-Tongkol": "TCT",
    "Cumi-Sotong-Gurita": "CSG",
    "Rajungan-Kepiting": "RK",
    "Rumput Laut": "RUMPUT LAUT",
    "Ikan Lainnya": "IKAN LAINNYA",
}
KOMODITAS_TITLE = {
    "Udang": "Udang",
    "Tuna-Cakalang-Tongkol": "Tuna – Cakalang - Tongkol",
    "Cumi-Sotong-Gurita": "Cumi – Sotong – Gurita",
    "Rajungan-Kepiting": "Rajungan - Kepiting",
    "Rumput Laut": "Rumput Laut",
    "Ikan Lainnya": "Ikan Lainnya",
    "Tepung Ikan-Pellet-Makanan Ikan": "Tepung Ikan-Pellet",
    "Salmon-Trout": "Salmon - Trout",
    "Cod": "Cod",
    "Haddock": "Haddock",
    "Mutiara": "Mutiara",
    "Layur Gulama": "Layur, Gulama",
    "Surimi": "Surimi",
    "Makarel": "Makarel",
    "Bahan Kimia": "Bahan Kimia",
    "Produk Farmasi": "Produk Farmasi",
    "Alat Ukur": "Alat Ukur",
    "Garam": "Garam",
    "Zat dan Enzim": "Zat dan Enzim",
    "Olahan Ikan Lainnya": "Olahan Ikan Lainnya",
}
KOMODITAS_LEGEND = {
    "Tuna-Cakalang-Tongkol": "TUNA - CAKALANG - TONGKOL",
    "Cumi-Sotong-Gurita": "CUMI - SOTONG - GURITA",
    "Rajungan-Kepiting": "RAJUNGAN - KEPITING",
    "Tepung Ikan-Pellet-Makanan Ikan": "TEPUNG IKAN - PELLET",
    "Salmon-Trout": "SALMON - TROUT",
    "Ikan Lainnya": "IKAN LAINNYA",
}

GROUP_TYPE = 6  # MSO_SHAPE_TYPE.GROUP.value


# --------------------------------------------------------------------------
# Format angka / persentase
# --------------------------------------------------------------------------
def id_fmt(v, nd=2):
    s = f"{float(v):,.{nd}f}"
    return s.replace(".", "\x00").replace(",", ".").replace("\x00", ",")


def miliar_id(v, nd=2):
    return id_fmt(float(v) / 1e9, nd)


def juta_id(v, nd=2):
    return id_fmt(float(v) / 1e6, nd)


def pct_id(v, nd=2):
    return id_fmt(v, nd) + "%"


def yoy_cur(prev, cur, label=False):
    """pertumbuhan (cur-prev)/prev*100 dlm bentuk '12,7%' / '0,03%' (negatif '-x')."""
    prev, cur = float(prev or 0), float(cur or 0)
    if not prev:
        return None
    p = (cur - prev) / prev * 100
    nd = 2 if abs(p) < 0.5 else 1
    s = pct_id(abs(p), nd)
    if label:
        naik = p >= 0
        return (("Naik" if naik else "Turun") + " " + s), p
    return (("-" if p < 0 else "") + s), p


def cagr(vals):
    vals = [float(v) for v in vals if v is not None]
    if len(vals) < 2 or not vals[0]:
        return None
    n = len(vals) - 1
    return (vals[-1] / vals[0]) ** (1.0 / n) - 1


# --------------------------------------------------------------------------
# Pengumpulan data
# --------------------------------------------------------------------------
def collect_data(conn, tahun, b1, b2):
    pa = "%d%02d" % (tahun, b1)
    pb = "%d%02d" % (tahun, b2)
    cur = conn.cursor()

    def q(sql, params=()):
        cur.execute(sql, params)
        return cur.fetchall()

    per = q("""
        SELECT tahun,
               SUM(CASE WHEN exim_type='ekspor' THEN nil_usd ELSE 0 END) eks_usd,
               SUM(CASE WHEN exim_type='impor'  THEN nil_usd ELSE 0 END) imp_usd,
               SUM(CASE WHEN exim_type='ekspor' THEN vol_kg ELSE 0 END) eks_kg,
               SUM(CASE WHEN exim_type='impor'  THEN vol_kg ELSE 0 END) imp_kg
        FROM raw_exim
        WHERE bulan BETWEEN %s AND %s AND tahun BETWEEN 2022 AND %s
        GROUP BY tahun ORDER BY tahun
    """, (b1, b2, tahun))
    if not per:
        raise RuntimeError("tidak ada data (raw_exim) untuk periode tsb")

    rot = "SELECT SUM(CASE WHEN exim_type='ekspor' THEN nil_usd ELSE 0 END) eks, " \
          "SUM(CASE WHEN exim_type='impor' THEN nil_usd ELSE 0 END) imp, " \
          "SUM(CASE WHEN exim_type='ekspor' THEN vol_kg ELSE 0 END) eks_kg, " \
          "SUM(CASE WHEN exim_type='impor' THEN vol_kg ELSE 0 END) imp_kg " \
          "FROM raw_exim WHERE tahun=%s AND bulan BETWEEN %s AND %s"
    cur_total = q(rot, (tahun, b1, b2))[0]
    cur_total_prev = q(rot, (tahun - 1, b1, b2))[0]

    # komposisi ekspor: (kelompok_negara x komoditas_5_2026)
    ek = q("""
        SELECT kelompok_negara, komoditas_5_2026, SUM(nil_usd) v
        FROM raw_exim WHERE exim_type='ekspor' AND tahun=%s AND bulan BETWEEN %s AND %s
          AND NULLIF(kelompok_negara,'') IS NOT NULL AND NULLIF(komoditas_5_2026,'') IS NOT NULL
        GROUP BY kelompok_negara, komoditas_5_2026
    """, (tahun, b1, b2))
    ek_prev = q("""
        SELECT kelompok_negara, SUM(nil_usd) v FROM raw_exim
        WHERE exim_type='ekspor' AND tahun=%s AND bulan BETWEEN %s AND %s
          AND NULLIF(kelompok_negara,'') IS NOT NULL GROUP BY kelompok_negara
    """, (tahun - 1, b1, b2))
    kprev = q("""
        SELECT komoditas_5_2026, SUM(nil_usd) v FROM raw_exim
        WHERE exim_type='ekspor' AND tahun=%s AND bulan BETWEEN %s AND %s
          AND NULLIF(komoditas_5_2026,'') IS NOT NULL GROUP BY komoditas_5_2026
    """, (tahun - 1, b1, b2))

    inm = q("""
        SELECT kelompok_negara, SUM(nil_usd) v FROM raw_exim
        WHERE exim_type='impor' AND tahun=%s AND bulan BETWEEN %s AND %s
          AND NULLIF(kelompok_negara,'') IS NOT NULL GROUP BY kelompok_negara
    """, (tahun, b1, b2))
    imp_prev = q("""
        SELECT kelompok_negara, SUM(nil_usd) v FROM raw_exim
        WHERE exim_type='impor' AND tahun=%s AND bulan BETWEEN %s AND %s
          AND NULLIF(kelompok_negara,'') IS NOT NULL GROUP BY kelompok_negara
    """, (tahun - 1, b1, b2))
    iko = q("""
        SELECT komoditas_5_2026, SUM(nil_usd) v FROM raw_exim
        WHERE exim_type='impor' AND tahun=%s AND bulan BETWEEN %s AND %s
          AND NULLIF(komoditas_5_2026,'') IS NOT NULL GROUP BY komoditas_5_2026
    """, (tahun, b1, b2))
    iko_prev = q("""
        SELECT komoditas_5_2026, SUM(nil_usd) v FROM raw_exim
        WHERE exim_type='impor' AND tahun=%s AND bulan BETWEEN %s AND %s
          AND NULLIF(komoditas_5_2026,'') IS NOT NULL GROUP BY komoditas_5_2026
    """, (tahun - 1, b1, b2))

    tot_eks = float(cur_total["eks"] or 0)
    tot_imp = float(cur_total["imp"] or 0)
    prev_eks = float(cur_total_prev["eks"] or 0)
    prev_imp = float(cur_total_prev["imp"] or 0)

    def yoy_map(prev_rows, keycol="kelompok_negara"):
        return {r[keycol]: float(r["v"] or 0) for r in prev_rows}

    # --- ekspor partner (top-5 + Lainnya) ---
    pv = {}
    for r in ek:
        pv[r["kelompok_negara"]] = pv.get(r["kelompok_negara"], 0) + float(r["v"])
    pprev = yoy_map(ek_prev)
    top5 = sorted((x for x in pv.items() if x[0] != "Lainnya"), key=lambda x: -x[1])[:5]
    lain_tot = tot_eks - sum(v for _, v in top5)
    items = [{"name": k, "v": v, "prev": pprev.get(k, 0)} for k, v in top5]
    if lain_tot > 0:
        items.append({"name": "Lainnya", "v": lain_tot, "prev": pprev.get("Lainnya", 0)})
    items.sort(key=lambda x: -x["v"])
    eks_partner = [
        {"name": it["name"], "v": it["v"], "share": it["v"] / tot_eks * 100,
         "yoy": yoy_cur(it["prev"], it["v"])[0],
         "yoy_p": yoy_cur(it["prev"], it["v"])[1]}
        for it in items
    ]

    # --- ekspor komoditas (top-5 + Ikan Lainnya) ---
    kv = {}
    for r in ek:
        kv[r["komoditas_5_2026"]] = kv.get(r["komoditas_5_2026"], 0) + float(r["v"])
    kprev_m = yoy_map(kprev, "komoditas_5_2026")
    top5k = sorted((x for x in kv.items() if x[0] != "Ikan Lainnya"), key=lambda x: -x[1])[:5]
    lain_ktot = tot_eks - sum(v for _, v in top5k)
    kitems = [{"name": k, "v": v, "prev": kprev_m.get(k, 0)} for k, v in top5k]
    if lain_ktot > 0:
        kitems.append({"name": "Ikan Lainnya", "v": lain_ktot, "prev": kprev_m.get("Ikan Lainnya", 0)})
    kitems.sort(key=lambda x: -x["v"])
    eks_komoditas = [
        {"name": it["name"], "v": it["v"], "share": it["v"] / tot_eks * 100,
         "yoy": yoy_cur(it["prev"], it["v"])[0],
         "yoy_p": yoy_cur(it["prev"], it["v"])[1]}
        for it in kitems
    ]

    # --- komposisi per partner (top komoditas) & per komoditas (top partner) ---
    pk = {}
    for r in ek:
        comp = pk.setdefault(r["kelompok_negara"], {})
        comp[r["komoditas_5_2026"]] = comp.get(r["komoditas_5_2026"], 0) + float(r["v"])
    per_partner_komoditas, per_komoditas_partner = {}, {}
    for name in [x["name"] for x in eks_partner if x["name"] != "Lainnya"]:
        comp = pk.get(name, {})
        tot_p = sum(comp.values()) or 1
        per_partner_komoditas[name] = [
            {"name": k, "v": v, "share": v / tot_p * 100}
            for k, v in sorted(comp.items(), key=lambda x: -x[1])[:5]
        ]
    for name in [x["name"] for x in eks_komoditas if x["name"] not in ("Ikan Lainnya",)]:
        comp = {n: vals[name] for n, vals in pk.items() if name in vals}
        tot_k = sum(comp.values()) or 1
        per_komoditas_partner[name] = [
            {"name": k, "v": v, "share": v / tot_k * 100}
            for k, v in sorted(comp.items(), key=lambda x: -x[1])[:5]
        ]

    # --- impor negara (top-6 + Lainnya) ---
    ipv = {r["kelompok_negara"]: float(r["v"]) for r in inm}
    ipprev = yoy_map(imp_prev)
    top6 = sorted((x for x in ipv.items() if x[0] != "Lainnya"), key=lambda x: -x[1])[:6]
    ilain = tot_imp - sum(v for _, v in top6)
    iitems = [{"name": k, "v": v, "prev": ipprev.get(k, 0)} for k, v in top6]
    if ilain > 0:
        iitems.append({"name": "Lainnya", "v": ilain, "prev": ipprev.get("Lainnya", 0)})
    iitems.sort(key=lambda x: -x["v"])
    imp_negara = [
        {"name": it["name"], "v": it["v"], "share": it["v"] / tot_imp * 100,
         "yoy": yoy_cur(it["prev"], it["v"])[0],
         "yoy_p": yoy_cur(it["prev"], it["v"])[1]}
        for it in iitems
    ]

    # --- impor komoditas (top-6 + Ikan Lainnya) ---
    ikv = {r["komoditas_5_2026"]: float(r["v"]) for r in iko}
    ikprev = yoy_map(iko_prev, "komoditas_5_2026")
    top6k = sorted((x for x in ikv.items() if x[0] != "Ikan Lainnya"), key=lambda x: -x[1])[:6]
    kilain = tot_imp - sum(v for _, v in top6k)
    kitems2 = [{"name": k, "v": v, "prev": ikprev.get(k, 0)} for k, v in top6k]
    if kilain > 0:
        kitems2.append({"name": "Ikan Lainnya", "v": kilain, "prev": ikprev.get("Ikan Lainnya", 0)})
    kitems2.sort(key=lambda x: -x["v"])
    imp_komoditas = [
        {"name": it["name"], "v": it["v"], "share": it["v"] / tot_imp * 100,
         "yoy": yoy_cur(it["prev"], it["v"])[0],
         "yoy_p": yoy_cur(it["prev"], it["v"])[1]}
        for it in kitems2
    ]

    series = [
        {"tahun": int(r["tahun"]), "eks_usd": float(r["eks_usd"] or 0),
         "imp_usd": float(r["imp_usd"] or 0), "eks_kg": float(r["eks_kg"] or 0),
         "imp_kg": float(r["imp_kg"] or 0)}
        for r in per
    ]

    return {
        "tahun": tahun, "b1": b1, "b2": b2,
        "period_cover": f"PERIODE {BULAN_ID[b1].upper()} – {BULAN_ID[b2].upper()} {tahun}",
        "period_hist": f"PERIODE {BULAN_ID[b1].upper()} – {BULAN_ID[b2].upper()} 2022-{tahun}",
        "period_slide": f"PERIODE {BULAN_ID[b1].upper()} – {BULAN_ID[b2].upper()} Tahun {tahun}",
        "period_impor": f"PERIODE {BULAN_ID[b1].upper()} – {BULAN_ID[b2].upper()} IMPOR Tahun {tahun}",
        "month_short": f"{S_BULAN[b1]}-{BULAN_ID[b2]} {tahun}",
        "month_upper": f"JAN-MAR {tahun}" if b2 <= 3
                       else f"JAN-{BULAN_ID[b2].upper()} {tahun}" if b1 == 1
                       else f"{BULAN_ID[b1].upper()[:3]}-{BULAN_ID[b2].upper()[:3]} {tahun}",
        "tot": {"eks": tot_eks, "imp": tot_imp,
                "eks_kg": float(cur_total["eks_kg"] or 0), "imp_kg": float(cur_total["imp_kg"] or 0)},
        "prev": {"eks": prev_eks, "imp": prev_imp},
        "yoy": {"eks": yoy_cur(prev_eks, tot_eks)[0], "imp": yoy_cur(prev_imp, tot_imp)[0],
                "ner": yoy_cur(prev_eks - prev_imp, tot_eks - tot_imp)[0]},
        "series": series,
        "cagr": {
            "eks_kg": pct_id((cagr([s["eks_kg"] for s in series]) or 0) * 100, 1),
            "eks_usd": pct_id((cagr([s["eks_usd"] for s in series]) or 0) * 100, 1),
            "imp_kg": pct_id((cagr([s["imp_kg"] for s in series]) or 0) * 100, 1),
            "imp_usd": pct_id((cagr([s["imp_usd"] for s in series]) or 0) * 100, 1),
        },
        "eks_partner": eks_partner,
        "eks_komoditas": eks_komoditas,
        "per_partner_komoditas": per_partner_komoditas,
        "per_komoditas_partner": per_komoditas_partner,
        "imp_negara": imp_negara,
        "imp_komoditas": imp_komoditas,
    }


# --------------------------------------------------------------------------
# Normalisasi + penulisan teks (font dipertahankan)
# --------------------------------------------------------------------------
def norm(t):
    """cocokkan teks: \x0b dianggap \n, spasi berlebih diringkas per baris."""
    t = str(t).replace("\x0b", "\n")
    return "\n".join(" ".join(x.split()) for x in t.split("\n")).strip()


def _set_structured(tf, text):
    """Mengganti teks text frame; \n = paragraf baru, \v = soft line break.
    Gaya (rPr) run pertama tiap paragraf disalin agar format visual tetap."""
    from lxml import etree
    from pptx.oxml.ns import qn as _qn

    body = tf._txBody if hasattr(tf, "_txBody") else tf._element
    paras = [p for p in body.findall(_qn("a:p"))]
    values = text.split("\n")

    for i, val in enumerate(values):
        segs = val.split("\v")
        p = paras[i] if i < len(paras) else etree.SubElement(body, _qn("a:p"))
        if i >= len(paras):
            paras.append(p)
        tpl = None
        for child in list(p):
            if child.tag == _qn("a:r"):
                rpr = child.find(_qn("a:rPr"))
                if rpr is not None:
                    tpl = copy.deepcopy(rpr)
                break
        for child in list(p):
            if child.tag in (_qn("a:r"), _qn("a:br"), _qn("a:fld"), _qn("a:br")):
                p.remove(child)
        for j, seg in enumerate(segs):
            r = etree.SubElement(p, _qn("a:r"))
            if tpl is not None:
                r.append(copy.deepcopy(tpl))
            t = etree.SubElement(r, _qn("a:t"))
            t.text = seg or " "
            if j < len(segs) - 1:
                br = etree.SubElement(p, _qn("a:br"))
                if tpl is not None:
                    br.append(copy.deepcopy(tpl))
    for p in paras[len(values):]:
        body.remove(p)


# --------------------------------------------------------------------------
# Penjelajahan shape
# --------------------------------------------------------------------------
class Node:
    __slots__ = ("shape", "path_shapes", "path_names", "path_texts", "text")

    def __init__(self, shape, path_shapes, path_names, path_texts, text):
        self.shape = shape
        self.path_shapes = path_shapes
        self.path_names = path_names
        self.path_texts = path_texts
        self.text = text


def _shape_text(sh):
    try:
        if not sh.has_text_frame:
            return None
        t = "\n".join(p.text for p in sh.text_frame.paragraphs)
        return t if t.strip() else None
    except Exception:
        return None


def iter_nodes(shapes, path_shapes=(), path_names=(), path_texts=()):
    for sh in shapes:
        text = _shape_text(sh)
        is_group = getattr(sh, "shape_type", None) == GROUP_TYPE
        if text is not None:
            yield Node(sh, path_shapes, path_names, path_texts, text)
        if is_group:
            yield from iter_nodes(sh.shapes,
                                  path_shapes + (sh,),
                                  path_names + (getattr(sh, "name", ""),),
                                  path_texts + (norm(text) if text else "",))


def replace_by_ref(nodes, ref, new):
    nref = norm(ref)
    hits = [n for n in nodes if norm(n.text) == nref]
    if len(hits) == 1:
        _set_structured(hits[0].shape.text_frame, new)
        return True
    if len(hits) > 1:
        return -len(hits)
    return False


# --------------------------------------------------------------------------
# Kata kunci pencocokan untuk data -> template
# --------------------------------------------------------------------------
def pcard(upper, dati):
    return dati


def kt(dati):
    return KOMODITAS_TITLE.get(dati, dati.title() if dati else dati)


def ku(dati):
    return KOMODITAS_UPPER.get(dati, dati.upper() if dati else dati)


def klegend(dati):
    return KOMODITAS_LEGEND.get(dati, ku(dati))


def pt(dati, impor=False):
    if impor and dati == "Lainnya":
        return "Negara Lainnya"
    return PARTNER_TITLE.get(dati, dati.title() if dati else dati)


def pu(dati, impor=False):
    if impor and dati == "Lainnya":
        return "NEGARA LAINNYA"
    return PARTNER_UPPER.get(dati, dati.upper() if dati else dati)


def getrow(rows, name):
    for r in rows:
        if r["name"] == name:
            return r
    return None


# --------------------------------------------------------------------------
# Fill per slide
# --------------------------------------------------------------------------
def _fill_slide0(nodes, d):
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI 2026", d["period_cover"])


def _fill_slide1(nodes, d):
    tot = d["tot"]; yoy = d["yoy"]
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI 2022-2026", d["period_hist"])
    replace_by_ref(nodes, "EKSPOR\nJan-Juni Tahun 2026",
                   f"EKSPOR\n{S_BULAN[d['b1']]}-{BULAN_ID[d['b2']]} Tahun {d['tahun']}")
    replace_by_ref(nodes, "USD 3,00 Miliar", f"USD {miliar_id(tot['eks'])} Miliar")
    if yoy["eks"]:
        replace_by_ref(nodes, "0,4% (YoY)", f"{yoy['eks']} (YoY)")
    replace_by_ref(nodes, "2,7%", d["cagr"]["eks_kg"])
    replace_by_ref(nodes, "0,2%", d["cagr"]["eks_usd"])

    for marker, kind in (("5 TOP NEGARA TUJUAN", "partner"), ("5 TOP KOMODITAS EKSPOR", "komoditas")):
        if kind == "partner":
            val_refs = ["Amerika Serikat\n1.010,64 Juta", "Tiongkok\n583,71 Juta",
                        "ASEAN\n416,48 Juta", "Jepang\n286,53 Juta", "UNI EROPA\n216,83 Juta"]
            yoy_refs = ["0,7%", "8,8%", "12,7%", "0,03%", "3,7%"]
            rows = d["eks_partner"][:5]
            is_nation = True
        else:
            val_refs = ["Udang\n872,71 Juta", "TCT\n490,44 Juta", "CSG\n433,49 Juta",
                        "Rajungan-Kepiting\n294,65 Juta", "Rumput Laut\n156,25 Juta"]
            yoy_refs = ["6,4%", "0,7%", "14,1 %", "15,3%", "7,6%"]
            rows = d["eks_komoditas"][:5]
            is_nation = False
        if is_nation:
            for i, ref in enumerate(val_refs):
                if i < len(rows):
                    replace_by_ref(nodes, ref, f"{pt(rows[i]['name'])}\n{juta_id(rows[i]['v'])} Juta")
            for i, ref in enumerate(yoy_refs):
                if i < len(rows) and rows[i]["yoy"]:
                    _assign_yoy(nodes, ref, rows[i]["yoy"], val_refs)
        else:
            for i, ref in enumerate(val_refs):
                if i < len(rows):
                    replace_by_ref(nodes, ref, f"{kt(rows[i]['name'])}\n{juta_id(rows[i]['v'])} Juta")
            for i, ref in enumerate(yoy_refs):
                if i < len(rows) and rows[i]["yoy"]:
                    _assign_yoy(nodes, ref, rows[i]["yoy"], val_refs)


def _assign_yoy(nodes, ref, new, markers):
    """Ganti teks node yoy yang berada dalam kelompok yang juga memuat salah
    satu marker (untuk memisahkan nilai-nilai yang identik antar grup)."""
    nref = norm(ref)
    for n in nodes:
        if norm(n.text) != nref:
            continue
        in_group = False
        for g in n.path_shapes:
            subs = {norm(x.text) for x in iter_nodes(g.shapes)}
            if any(norm(m) in subs for m in markers):
                in_group = True
                break
        if in_group:
            _set_structured(n.shape.text_frame, new)
            return True
    return False


def _fill_slide2(nodes, d):
    tot = d["tot"]; yoy = d["yoy"]
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI 2022-2026", d["period_hist"])
    replace_by_ref(nodes, "3,00\nMiliar", f"{miliar_id(tot['eks'])}\nMiliar")
    replace_by_ref(nodes, "0,38\nMiliar", f"{miliar_id(tot['imp'])}\nMiliar")
    replace_by_ref(nodes, "2,62\nMiliar", f"{miliar_id(tot['eks'] - tot['imp'])}\nMiliar")
    if yoy["eks"]:
        replace_by_ref(nodes, "0,4%\n(YoY)", f"{yoy['eks']}\n(YoY)")
    if yoy["imp"]:
        replace_by_ref(nodes, "31,4%\n(YoY)", f"{yoy['imp']}\n(YoY)")
    if yoy["ner"]:
        replace_by_ref(nodes, "3,0%\n(YoY)", f"{yoy['ner']}\n(YoY)")


def _iter_chart_shapes(shapes):
    for sh in shapes:
        if getattr(sh, "has_chart", False) and sh.has_chart:
            yield sh
        if sh.shape_type == 6:
            yield from _iter_chart_shapes(sh.shapes)


def fill_charts(slide, kind, d):
    """kind: 'eks_kinerja' | 'neraca' | 'imp_kinerja'"""
    cats = [str(s["tahun"]) for s in d["series"]]
    if kind == "eks_kinerja":
        series = [("Volume (juta ton)", [s["eks_kg"] / 1e9 for s in d["series"]]),
                  ("Nilai (USD miliar)", [s["eks_usd"] / 1e9 for s in d["series"]])]
    elif kind == "imp_kinerja":
        series = [("Volume (juta ton)", [s["imp_kg"] / 1e9 for s in d["series"]]),
                  ("Nilai (USD miliar)", [s["imp_usd"] / 1e9 for s in d["series"]])]
    else:  # neraca 3 panel
        eks = [s["eks_usd"] / 1e9 for s in d["series"]]
        imp = [s["imp_usd"] / 1e9 for s in d["series"]]
        ner = [e - i for e, i in zip(eks, imp)]
        panels = {"eks": eks, "imp": imp, "ner": ner}
        n = 0
        for sh in _iter_chart_shapes(slide.shapes):
            xin = (sh.left or 0) / 914400 if (sh.left or 0) else 0
            col = "eks" if xin < 3 else ("imp" if xin < 7 else "ner")
            _replace_chart(sh.chart, cats, [("Nilai", panels[col])])
            n += 1
        return n
    cnt = 0
    for sh in _iter_chart_shapes(slide.shapes):
        _replace_chart(sh.chart, cats, series)
        cnt += 1
    return cnt


def _replace_chart(chart, cats, series):
    from pptx.chart.data import CategoryChartData
    cd = CategoryChartData()
    cd.categories = list(cats)
    for name, vals in series:
        cd.add_series(name, list(vals))
    try:
        chart.replace_data(cd)
    except Exception:
        pass


def _fill_slide3(nodes, d):
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI Tahun 2026", d["period_slide"])
    cards = [
        "AMERIKA SERIKAT\nUSD 1.010,64 Juta\n0,7% (YoY)",
        "TIONGKOK\nUSD 583,71 Juta\n8,8% (YoY)",
        "LAINNYA\nUSD 480,99 Juta\n2,1% (YoY)",
        "ASEAN\nUSD 416,48 Juta\n12,7% (YoY)",
        "JAPAN\nUSD 286,53 Juta\n0,03% (YoY)",
        "UNI EROPA\nUSD 216,83 Juta\n3,7% (YoY)",
    ]
    shares = ["33,74%", "19,49%", "16,06%", "13,90%", "9,57%", "7,24%"]
    for i, ref in enumerate(cards):
        if i >= len(d["eks_partner"]):
            break
        r = d["eks_partner"][i]
        yo = r["yoy"] or "-"
        replace_by_ref(nodes, ref, f"{pu(r['name'])}\nUSD {juta_id(r['v'])} Juta\n{yo} (YoY)")
    for i, ref in enumerate(shares):
        if i >= len(d["eks_partner"]):
            break
        r = d["eks_partner"][i]
        replace_by_ref(nodes, ref, pct_id(r["share"]))


def _fill_slide4(nodes, d):
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI Tahun 2026", d["period_slide"])
    cards = [
        ("UDANG\nUSD 872,71 Juta\x0bTurun 6,4% (YoY)", "29,1%", "Udang"),
        ("TCT\nUSD 490,44 Juta\x0bTurun 0,7% (YoY)", "16,4%", "Tuna-Cakalang-Tongkol"),
        ("CSG\nUSD 433,49 Juta\x0bNaik 14,1% (YoY)", "14,5%", "Cumi-Sotong-Gurita"),
        ("RK\nUSD 294,65 Juta\x0bNaik 15,3% (YoY)", "9,8%", "Rajungan-Kepiting"),
        ("RUMPUT LAUT\nUSD 156,25 Juta\x0bNaik 7,6% (YoY)", "5,2%", "Rumput Laut"),
        ("IKAN LAINNYA\nUSD 747,63 Juta\x0bTurun 3,9% (YoY)", "25%", "Ikan Lainnya"),
    ]
    for card_ref, share_ref, key in cards:
        r = getrow(d["eks_komoditas"], key)
        if not r:
            continue
        naik = "Turun" if (r["yoy_p"] or 0) < 0 else "Naik"
        yo = pct_id(abs(r["yoy_p"]), 1) if r["yoy_p"] is not None else "-"
        replace_by_ref(nodes, card_ref,
                       f"{ku(r['name'])}\nUSD {juta_id(r['v'])} Juta\x0b{naik} {yo} (YoY)")
        replace_by_ref(nodes, share_ref, pct_id(r["share"], 1 if key == "Ikan Lainnya" else 2))


def _fill_slide5(nodes, d):
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI Tahun 2026", d["period_slide"])
    cards = [
        ("UDANG\nUSD 872,71 Juta\x0b6,4% (YoY)", "29,1 %", "Udang"),
        ("TCT\nUSD 490,44 Juta\x0b0,7% (YoY)", "16,4 %", "Tuna-Cakalang-Tongkol"),
        ("CSG\nUSD 433,49 Juta\x0b14,1% (YoY)", "14,5 %", "Cumi-Sotong-Gurita"),
        ("RK\nUSD 294,65 Juta\x0b15,3% (YoY)", "9,8%", "Rajungan-Kepiting"),
        ("RUMPUT LAUT\nUSD 156,25 Juta\x0b7,6% (YoY)", "5,2 %", "Rumput Laut"),
    ]
    for card_ref, share_ref, key in cards:
        r = getrow(d["eks_komoditas"], key)
        if not r:
            continue
        yo = r["yoy"] or "-"
        replace_by_ref(nodes, card_ref,
                       f"{ku(r['name'])}\nUSD {juta_id(r['v'])} Juta\x0b{yo} (YoY)")
        replace_by_ref(nodes, share_ref, pct_id(r["share"]))

    rows5 = {
        "USD 552,77 Juta": ("Udang", 0), "USD 138,59Juta": ("Udang", 1),
        "USD 60,18 Juta": ("Udang", 2), "USD 33,45 Juta": ("Udang", 3),
        "USD 25,75 Juta": ("Udang", 4),
        "USD 64,41 Juta": ("Tuna-Cakalang-Tongkol", 0), "USD 50,68 Juta": ("Tuna-Cakalang-Tongkol", 1),
        "USD 123,64 Juta": ("Tuna-Cakalang-Tongkol", 2), "USD 93,07 Juta": ("Tuna-Cakalang-Tongkol", 3),
        "USD 89,92 Juta": ("Tuna-Cakalang-Tongkol", 4),
        "USD 201,83 Juta": ("Cumi-Sotong-Gurita", 0), "USD 114,63 Juta": ("Cumi-Sotong-Gurita", 1),
        "USD 46,26 Juta": ("Cumi-Sotong-Gurita", 2), "USD 21,65 Juta": ("Cumi-Sotong-Gurita", 3),
        "USD 16,28 Juta": ("Cumi-Sotong-Gurita", 4),
        "USD 202,80 Juta": ("Rajungan-Kepiting", 0), "USD 48,40 Juta": ("Rajungan-Kepiting", 1),
        "USD 17,00 Juta": ("Rajungan-Kepiting", 2), "USD 9,51 Juta": ("Rajungan-Kepiting", 3),
        "USD 5,72 Juta": ("Rajungan-Kepiting", 4),
        "USD 104,23 Juta": ("Rumput Laut", 0), "USD 17,64 Juta": ("Rumput Laut", 1),
        "USD 5,65 Juta": ("Rumput Laut", 2), "USD 4,74 Juta": ("Rumput Laut", 3),
        "USD 3,70 Juta": ("Rumput Laut", 4),
    }
    for ref_val, (kom, rank) in rows5.items():
        hit = [n for n in nodes if norm(n.text) == norm(ref_val)]
        if len(hit) != 1:
            continue
        node = hit[0]
        if not node.path_shapes:
            continue
        grp = node.path_shapes[-1]
        sub = list(iter_nodes(grp.shapes))
        share_node = [n for n in sub if n is not node and re.match(r"^\s*\([^)]*\)\s*$", n.text)]
        name_nodes = [n for n in sub if n is not node and not re.match(r"^\s*\([^)]*\)\s*$", n.text)]
        rows = d["per_komoditas_partner"].get(kom, [])
        if rank >= len(rows):
            continue
        r = rows[rank]
        _set_structured(node.shape.text_frame, f"USD {juta_id(r['v'])} Juta")
        if share_node:
            _set_structured(share_node[0].shape.text_frame, f"({pct_id(r['share'])})")
        if name_nodes:
            _set_structured(name_nodes[0].shape.text_frame, pt(r["name"]))


def _fill_slide6(nodes, d):
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI Tahun 2026", d["period_slide"])
    cards = [
        ("AMERIKA SERIKAT\nUSD 1.010,64 Juta\x0b\n0,7% (YoY)", "33,74%", "United States"),
        ("TIONGKOK\nUSD 583,71 Juta\x0b\n8,8% (YoY)", "19,49%", "China"),
        ("ASEAN\nUSD 416,48 Juta\x0b\n12,7% (YoY)", "13,90%", "Asean"),
        ("JEPANG\nUSD 286,53 Juta\x0b\n0,03% (YoY)", "9,57%", "Japan"),
        ("UNI EROPA\nUSD 216,83 Juta\x0b\n3,7% (YoY)", "7,24%", "Uni Eropa"),
    ]
    products_ref = {
        "United States": [
            "Udang\nUSD 552,77 Juta (54,7%) ", "Rajungan - Kepiting\nUSD 202,80 Juta (20,1%)",
            "Tuna – Cakalang - Tongkol\nUSD 93,07 Juta (9,2%)", "Tilapia\nUSD 25,99 Juta (2,6%)",
            "Cumi – Sotong – Gurita\nUSD 21,65 Juta (2,1%)"],
        "China": [
            "Cumi-Sotong-Gurita\nUSD 201,83 Juta (34,6%) ", "Rumput Laut \nUSD 104,23 Juta (17,9%)",
            "Udang\nUSD 60,18 Juta (10,3%)", "Rajungan Kepiting\nUSD 48,40 Juta (8,3%)",
            "Layur, Gulama\nUSD 20,32 Juta (3,5%)"],
        "Asean": [
            "Tuna-Cakalang-Tongkol\nUSD 123,64 Juta (29,7%) ", "Cumi-Sotong-Gurita\nUSD 114,63 Juta (27,5%)",
            "Udang\nUSD 33,45 Juta (8,0%)", "Rajungan-Kepiting\nUSD 17,00 Juta (4,1%)",
            "Surimi\nUSD 8,62 Juta (2,1%)"],
        "Japan": [
            "Udang\nUSD 138,59 Juta (48,4%) ", "Tuna-Cakalang-Tongkol\nUSD 89,92 Juta (31,4%)",
            "Cumi-Sotong-Gurita\nUSD 10,46 Juta (3,7%)", "Mutiara\nUSD 10,16 Juta (3,5%)",
            "Rajungan Kepiting\nUSD 5,72 Juta (2,0%)"],
        "Uni Eropa": [
            "Tuna-Cakalang-Tongkol\nUSD 64,41 Juta (29,1%) ", "Cumi-Sotong-Gurita\nUSD 46,26 Juta (21,3%)",
            "Udang\nUSD 25,75 Juta (11,9%)", "Rumput Laut \nUSD 17,64 Juta (8,1%)",
            "Rajungan-Kepiting\nUSD 9,51 Juta (4,4%)"],
    }
    for card_ref, share_ref, key in cards:
        r = getrow(d["eks_partner"], key)
        if not r:
            continue
        yo = r["yoy"] or "-"
        replace_by_ref(nodes, card_ref,
                       f"{pu(r['name'])}\nUSD {juta_id(r['v'])} Juta\x0b\n{yo} (YoY)")
        replace_by_ref(nodes, share_ref, pct_id(r["share"]))
        hit = [n for n in nodes if norm(n.text) == norm(card_ref)]
        if len(hit) != 1 or not hit[0].path_shapes:
            continue
        grp = hit[0].path_shapes[-1]
        sub = list(iter_nodes(grp.shapes))
        prod_refs = [norm(x) for x in products_ref.get(key, [])]
        prod_nodes = [n for n in sub if norm(n.text) in prod_refs]
        prod_nodes.sort(key=lambda n: sub.index(n))
        prods = d["per_partner_komoditas"].get(key, [])
        for i, pn in enumerate(prod_nodes):
            if i >= len(prods):
                break
            pr = prods[i]
            _set_structured(pn.shape.text_frame,
                            f"{kt(pr['name'])}\nUSD {juta_id(pr['v'])} Juta ({pct_id(pr['share'], 1)})")


def _fill_slide7(nodes, d):
    tot = d["tot"]
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI 2022-2026", d["period_hist"])
    replace_by_ref(nodes, "14,7%", d["cagr"]["imp_kg"])
    replace_by_ref(nodes, "8,3%", d["cagr"]["imp_usd"])
    yo_n = d["yoy"]["imp"] or "-"
    replace_by_ref(nodes, "NILAI IMPOR\nUSD 0,38 Miliar\n     31,4% (YoY)",
                   f"NILAI IMPOR\nUSD {miliar_id(tot['imp'])} Miliar\n     {yo_n} (YoY)")
    yo_v = None
    if len(d["series"]) >= 2:
        vprev = d["series"][-2]["imp_kg"]
        vcur = d["series"][-1]["imp_kg"]
        yo_v = yoy_cur(vprev, vcur)[0]
    replace_by_ref(nodes, "VOLUME IMPOR\n0,23 Juta Ton\n     19,7% (YoY)",
                   f"VOLUME IMPOR\n{id_fmt(tot['imp_kg'] / 1e6, 2)} Juta Ton\n     {yo_v or '-'} (YoY)")

    refs_neg = ["Tiongkok\n60,12 Juta", "Norway\n55,60 Juta", "Amerika Serikat\n42,02 Juta",
                "Uni Eropa\n36,34 Juta", "ASEAN\n28,54 Juta", "Jepang\n22,24 Juta"]
    yoys_neg = ["0,6%", "107,3%", "25,5%", "107,6%", "20,1%", "49,8%"]
    refs_kom = ["Udang\n46,92 Juta", "Salmon - Trout\n42,88 Juta", "Tepung Ikan - Pellet\n42,24 Juta",
                "Makarel\n37,36 Juta", "COD\n33,65 Juta", "Haddock\n32,23 Juta"]
    yoys_kom = ["169,7%", "22,4%", "35,0%", "37,1%", "66,3%", "296,3%"]
    for i, ref in enumerate(refs_neg):
        if i >= len(d["imp_negara"]):
            break
        r = d["imp_negara"][i]
        replace_by_ref(nodes, ref, f"{pt(r['name'], impor=True) if r['name'] != 'Lainnya' else pt(r['name'])}\n{juta_id(r['v'])} Juta")
        if r["yoy"]:
            replace_by_ref(nodes, yoys_neg[i], r["yoy"])
    for i, ref in enumerate(refs_kom):
        if i >= len(d["imp_komoditas"]):
            break
        r = d["imp_komoditas"][i]
        replace_by_ref(nodes, ref, f"{kt(r['name'])}\n{juta_id(r['v'])} Juta")
        if r["yoy"]:
            replace_by_ref(nodes, yoys_kom[i], r["yoy"])


def _fill_slide8(nodes, d):
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI IMPOR Tahun 2026", d["period_impor"])
    rows = ["Tiongkok\n60,12 Juta", "Norway\n55,60 Juta", "Amerika Serikat\n42,02 Juta",
            "UNI EROPA\n36,34 Juta", "ASEAN\n28,54 Juta", "Jepang\n22,24 Juta",
            "Negara Lainnya\n134,79 Juta"]
    shares = ["15,8%", "14,6%", "11,1%", "9,6%", "7,5%", "5,9%", "35,5%"]
    legend = ["TIONGKOK", "NORWAY", "AMERIKA SERIKAT", "UNI EROPA", "JEPANG", "ASEAN"]
    yo_lbl = ["0,6%\n(YoY)", "107,3%\n(YoY)", "25,5%\n(YoY)", "107,6%\n(YoY)",
              "20,1%\n(YoY)", "49,8%\n(YoY)"]
    for i, ref in enumerate(rows):
        if i >= len(d["imp_negara"]):
            break
        r = d["imp_negara"][i]
        replace_by_ref(nodes, ref, f"{pu(r['name'], impor=True)}\n{juta_id(r['v'])} Juta")
        replace_by_ref(nodes, shares[i], pct_id(r["share"]))
    for i, ref in enumerate(legend):
        if i >= len(d["imp_negara"]):
            break
        r = d["imp_negara"][i]
        replace_by_ref(nodes, ref, pu(r["name"], impor=True))
        if r["yoy"]:
            replace_by_ref(nodes, yo_lbl[i], f"{r['yoy']}\n(YoY)")
    replace_by_ref(nodes, "TOTAL IMPOR\nJAN-JUNI 2026\nUSD \n379,65\nJUTA",
                   f"TOTAL IMPOR\n{d['month_upper']}\nUSD \n{juta_id(d['tot']['imp'])}\nJUTA")


def _fill_slide9(nodes, d):
    replace_by_ref(nodes, "PERIODE JANUARI – JUNI Tahun 2026", d["period_slide"])
    rows = ["UDANG\nUSD 46,92 Juta", "SALMON - TROUT\nUSD 42,88 Juta",
            "TEPUNG IKAN - PELLET\nUSD 42,24 Juta", "MAKAREL\nUSD 37,36 Juta",
            "COD\nUSD 33,65 Juta", "HADDOCK\nUSD 32,23 Juta", "IKAN LAINNYA\nUSD 71,33 Juta"]
    shares = ["23,3%", "15,3%", "14,0%", "13,8%", "12,2%", "11%", "10,5%"]
    legend = ["UDANG", "SALMON - TROUT", "TEPUNG IKAN - PELLET", "MAKAREL", "COD", "HADDOCK"]
    yo_lbl = ["169,7%\n(YoY)", "22,4%\n(YoY)", "35,0%\n(YoY)", "37,1%\n(YoY)",
              "66,3%\n(YoY)", "296,3%\n(YoY)"]
    for i, ref in enumerate(rows):
        if i >= len(d["imp_komoditas"]):
            break
        r = d["imp_komoditas"][i]
        replace_by_ref(nodes, ref, f"{klegend(r['name'])}\nUSD {juta_id(r['v'])} Juta")
        replace_by_ref(nodes, shares[i], pct_id(r["share"]))
    for i, ref in enumerate(legend):
        if i >= len(d["imp_komoditas"]):
            break
        r = d["imp_komoditas"][i]
        replace_by_ref(nodes, ref, klegend(r["name"]))
        if r["yoy"]:
            replace_by_ref(nodes, yo_lbl[i], f"{r['yoy']}\n(YoY)")
    replace_by_ref(nodes, "TOTAL IMPOR\nJAN-MAR 2026\nUSD \n137,55\nJUTA",
                   f"TOTAL IMPOR\n{d['month_upper']}\nUSD \n{juta_id(d['tot']['imp'])}\nJUTA")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def fill_presentation(prs, data):
    """Mengisi per-slide pada objek Presentation template. Mengembalikan
    dict statistik mengingat jumlah teks tergantikan per slide."""
    stats = {}
    fillers = {
        0: _fill_slide0, 1: _fill_slide1, 2: _fill_slide2, 3: _fill_slide3,
        4: _fill_slide4, 5: _fill_slide5, 6: _fill_slide6, 7: _fill_slide7,
        8: _fill_slide8, 9: _fill_slide9,
    }
    for idx, slide in enumerate(prs.slides):
        if idx > 9:
            break
        nodes = list(iter_nodes(slide.shapes))
        before = {n.shape.shape_id: n.text for n in nodes}
        fn = fillers.get(idx)
        if fn:
            fn(nodes, data)
        if idx == 1:
            n = fill_charts(slide, "eks_kinerja", data)
        elif idx == 2:
            n = fill_charts(slide, "neraca", data)
        elif idx == 7:
            n = fill_charts(slide, "imp_kinerja", data)
        after = {n.shape.shape_id: n.text for n in iter_nodes(slide.shapes)}
        changed = sum(1 for sid in after if norm(after[sid]) != norm(before.get(sid, "")))
        stats[idx] = changed
    return stats
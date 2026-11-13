#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — fabrique un PSD de test pour l'import avancé (étape PSD I).

    python3 tools/fixtures/make_psd.py sortie.psd

Calques (du bas vers le haut) :
  1  « Fond »            pixels blancs
  2  « Titre »           texte de point, 2 styles (rouge gras / bleu), DejaVu Sans
  3  « Paragraphe »      texte de paragraphe centré, tourné de 15°, déformation Arc 50 %
  4  « Police absente »  texte en « FooBarSans-Regular » (police manquante)
  5  « Rectangle »       calque de forme : fond vert, contour noir 4 px centré
  6  « Photo masquée »   pixels orange + masque vectoriel (losange)
  7  « Effets »          pixels bleus + ombre portée, contour, incrustation couleur

Le contenu en pixels des calques de texte et de forme est un simple
aplat : c'est l'import ChopGimp qui doit reconstruire la version
modifiable. Le format suit la spécification Adobe (descripteurs version 16,
EngineData, enregistrements de chemin de 26 octets).
"""
import math
import struct
import sys

W, H = 800, 600


# ─── descripteurs ───────────────────────────────────────────────────────

def ustr(s):
    s = s + "\x00"
    return struct.pack(">I", len(s)) + s.encode("utf-16-be")


def key(k):
    b = k.encode("latin-1")
    if len(b) == 4:
        return struct.pack(">I", 0) + b
    return struct.pack(">I", len(b)) + b


class Enum:
    def __init__(self, typ, val):
        self.typ, self.val = typ, val


class Unit:
    def __init__(self, unit, val):
        self.unit, self.val = unit, val


class Obj(dict):
    def __init__(self, cls, *a, **kw):
        super().__init__(*a, **kw)
        self.cls = cls


def value(v):
    if isinstance(v, bool):
        return b"bool" + struct.pack(">B", v)
    if isinstance(v, int):
        return b"long" + struct.pack(">i", v)
    if isinstance(v, float):
        return b"doub" + struct.pack(">d", v)
    if isinstance(v, str):
        return b"TEXT" + ustr(v)
    if isinstance(v, Enum):
        return b"enum" + key(v.typ) + key(v.val)
    if isinstance(v, Unit):
        return b"UntF" + v.unit.encode() + struct.pack(">d", v.val)
    if isinstance(v, bytes):
        return b"tdta" + struct.pack(">I", len(v)) + v
    if isinstance(v, list):
        return b"VlLs" + struct.pack(">I", len(v)) + b"".join(value(x) for x in v)
    if isinstance(v, Obj):
        return b"Objc" + desc(v)
    raise TypeError(v)


def desc(d):
    out = ustr("") + key(getattr(d, "cls", "null")) + struct.pack(">I", len(d))
    for k, v in d.items():
        out += key(k) + value(v)
    return out


def rgb(r, g, b):
    return Obj("RGBC", {"Rd  ": float(r), "Grn ": float(g), "Bl  ": float(b)})


# ─── EngineData ─────────────────────────────────────────────────────────

def ed_str(s):
    b = b"\xfe\xff" + s.encode("utf-16-be")
    b = b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + b + b")"


def ed(v):
    if isinstance(v, bool):
        return b"true" if v else b"false"
    if isinstance(v, int):
        return str(v).encode()
    if isinstance(v, float):
        return ("%.5f" % v).encode()
    if isinstance(v, str):
        return ed_str(v)
    if isinstance(v, list):
        return b"[ " + b" ".join(ed(x) for x in v) + b" ]"
    if isinstance(v, dict):
        return b"<<\n" + b"".join(b"/" + k.encode() + b" " + ed(x) + b"\n" for k, x in v.items()) + b">>"
    raise TypeError(v)


def tysh(text, runs, fonts, transform, bounds, justification=0, box=None, warp=None):
    """runs : [(longueur, {Font, FontSize, FauxBold, color (r,g,b)})]"""
    run_array = []
    for n, st in runs:
        ssd = {"Font": st.get("Font", 0), "FontSize": float(st.get("FontSize", 24.0)),
               "FauxBold": st.get("FauxBold", False), "FauxItalic": False,
               "AutoLeading": True, "Tracking": st.get("Tracking", 0),
               "FillColor": {"Type": 1, "Values": [1.0] + [float(c) for c in st.get("color", (0, 0, 0))]}}
        run_array.append({"StyleSheet": {"StyleSheetData": ssd}})
    shape = {"ShapeType": 1 if box else 0}
    if box:
        shape["Cookie"] = {"Photoshop": {"ShapeType": 1, "BoxBounds": [float(v) for v in box]}}
    engine = {
        "EngineDict": {
            "Editor": {"Text": text + "\r"},
            "ParagraphRun": {"RunArray": [{"ParagraphSheet": {"Properties": {"Justification": justification}}}],
                             "RunLengthArray": [len(text) + 1]},
            "StyleRun": {"RunArray": run_array, "RunLengthArray": [n for n, _ in runs]},
            "Rendered": {"Shapes": {"Children": [shape]}},
        },
        "ResourceDict": {
            "FontSet": [{"Name": f, "Script": 0, "FontType": 1} for f in fonts],
            "StyleSheetSet": [{"Name": "Normal RGB", "StyleSheetData": {"Font": 0, "FontSize": 12.0}}],
        },
    }
    engine_bytes = b"\n\n" + ed(engine) + b"\n"
    l, t, r, b = bounds
    textd = Obj("TxLr", {
        "Txt ": text + "\r",
        "textGridding": Enum("textGridding", "None"),
        "Ornt": Enum("Ornt", "Hrzn"),
        "AntA": Enum("Annt", "antiAliasSharp"),
        "bounds": Obj("bounds", {"Left": Unit("#Pnt", l), "Top ": Unit("#Pnt", t),
                                 "Rght": Unit("#Pnt", r), "Btom": Unit("#Pnt", b)}),
        "TextIndex": 0,
        "EngineData": engine_bytes,
    })
    style, bend = warp if warp else ("warpNone", 0.0)
    warpd = Obj("warp", {"warpStyle": Enum("warpStyle", style), "warpValue": float(bend),
                         "warpPerspective": 0.0, "warpPerspectiveOther": 0.0,
                         "warpRotate": Enum("Ornt", "Hrzn")})
    return (struct.pack(">H", 1) + struct.pack(">6d", *transform) + struct.pack(">H", 50) +
            struct.pack(">I", 16) + desc(textd) + struct.pack(">H", 1) + struct.pack(">I", 16) +
            desc(warpd) + struct.pack(">4i", 0, 0, 0, 0))


# ─── chemins ────────────────────────────────────────────────────────────

def path_records(points, closed=True):
    """points en pixels → enregistrements vmsk (ancres sans poignées)."""
    def fix(v, size):
        return int(round(v / size * 16777216.0))
    out = struct.pack(">II", 3, 0)
    out += struct.pack(">H", 6) + b"\x00" * 24               # règle de remplissage
    out += struct.pack(">HH", 0 if closed else 3, len(points)) + b"\x00" * 22
    for x, y in points:
        p = struct.pack(">ii", fix(y, H), fix(x, W))
        out += struct.pack(">H", 1 if closed else 4) + p * 3
    return out


# ─── fichier ────────────────────────────────────────────────────────────

def block(k, data):
    if len(data) % 2:
        data += b"\x00"
    return b"8BIM" + k.encode() + struct.pack(">I", len(data)) + data


def pascal(name):
    b = name.encode("mac_roman", "replace")[:255]
    s = bytes([len(b)]) + b
    while len(s) % 4:
        s += b"\x00"
    return s


class L:
    def __init__(self, name, lid, rect, color, blocks=(), alpha=255):
        self.name, self.lid, self.rect, self.color, self.blocks, self.alpha = name, lid, rect, color, blocks, alpha


def build():
    font_ok = "DejaVuSans"
    font_bold = "DejaVuSans-Bold"
    layers = [L("Fond", 1, (0, 0, W, H), (255, 255, 255))]

    t1 = "Bonjour ChopGimp"
    layers.append(L("Titre", 2, (50, 60, 500, 120), (200, 30, 30), [
        block("TySh", tysh(t1, [(8, {"Font": 1, "FontSize": 48.0, "FauxBold": False, "color": (0.8, 0.1, 0.1)}),
                               (len(t1) - 8 + 1, {"Font": 0, "FontSize": 48.0, "color": (0.1, 0.2, 0.9)})],
                           [font_ok, font_bold], (1, 0, 0, 1, 50.0, 110.0), (0.0, -46.0, 430.0, 12.0))),
    ]))

    a = math.radians(15)
    t2 = "Texte de paragraphe"
    layers.append(L("Paragraphe", 3, (100, 200, 500, 320), (20, 20, 20), [
        block("TySh", tysh(t2, [(len(t2) + 1, {"Font": 0, "FontSize": 32.0, "color": (0.0, 0.0, 0.0)})],
                           [font_ok], (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 120.0, 220.0),
                           (0.0, 0.0, 360.0, 90.0), justification=2, box=(0.0, 0.0, 360.0, 90.0),
                           warp=("warpArc", 50.0))),
    ]))

    t3 = "Police absente"
    layers.append(L("Police absente", 4, (50, 420, 400, 470), (40, 120, 40), [
        block("TySh", tysh(t3, [(len(t3) + 1, {"Font": 0, "FontSize": 36.0, "color": (0.15, 0.5, 0.15)})],
                           ["FooBarSans-Regular"], (1, 0, 0, 1, 50.0, 460.0), (0.0, -34.0, 300.0, 9.0))),
    ]))

    rect = [(520, 80), (760, 80), (760, 240), (520, 240)]
    vstk = Obj("strokeStyle", {
        "strokeStyleVersion": 2, "strokeEnabled": True, "fillEnabled": True,
        "strokeStyleLineWidth": Unit("#Pxl", 4.0),
        "strokeStyleLineAlignment": Enum("strokeStyleLineAlignment", "strokeStyleAlignCenter"),
        "strokeStyleLineCapType": Enum("strokeStyleLineCapType", "strokeStyleButtCap"),
        "strokeStyleLineJoinType": Enum("strokeStyleLineJoinType", "strokeStyleMiterJoin"),
        "strokeStyleOpacity": Unit("#Prc", 100.0),
        "strokeStyleContent": Obj("solidColorLayer", {"Clr ": rgb(0, 0, 0)}),
    })
    layers.append(L("Rectangle", 5, (518, 78, 762, 242), (40, 170, 60), [
        block("vscg", b"SoCo" + struct.pack(">I", 16) + desc(Obj("null", {"Clr ": rgb(40, 170, 60)}))),
        block("vmsk", path_records(rect)),
        block("vstk", struct.pack(">II", 2, 16) + desc(vstk)),
    ]))

    diamond = [(650, 300), (760, 420), (650, 540), (540, 420)]
    layers.append(L("Photo masquée", 6, (540, 300, 760, 540), (240, 140, 20), [
        block("vmsk", path_records(diamond)),
    ]))

    fx = Obj("null", {
        "Scl ": Unit("#Prc", 100.0),
        "masterFXSwitch": True,
        "DrSh": Obj("DrSh", {"enab": True, "Md  ": Enum("BlnM", "Mltp"), "Clr ": rgb(0, 0, 0),
                             "Opct": Unit("#Prc", 75.0), "uglg": False, "lagl": Unit("#Ang", 135.0),
                             "Dstn": Unit("#Pxl", 10.0), "Ckmt": Unit("#Pxl", 0.0),
                             "blur": Unit("#Pxl", 8.0)}),
        "FrFX": Obj("FrFX", {"enab": True, "Styl": Enum("FStl", "OutF"), "PntT": Enum("FrFl", "SClr"),
                             "Md  ": Enum("BlnM", "Nrml"), "Opct": Unit("#Prc", 100.0),
                             "Sz  ": Unit("#Pxl", 3.0), "Clr ": rgb(255, 255, 0)}),
        "SoFi": Obj("SoFi", {"enab": True, "Md  ": Enum("BlnM", "Nrml"), "Opct": Unit("#Prc", 100.0),
                             "Clr ": rgb(200, 0, 200)}),
    })
    layers.append(L("Effets", 7, (300, 500, 480, 570), (30, 80, 200), [
        block("lfx2", struct.pack(">II", 0, 16) + desc(fx)),
    ]))
    return layers


def write(path):
    layers = build()
    recs, chans = b"", b""
    for ly in layers:
        l, t, r, b = ly.rect
        w, h = r - l, b - t
        chdata = []
        for cid, val in ((-1, ly.alpha), (0, ly.color[0]), (1, ly.color[1]), (2, ly.color[2])):
            chdata.append((cid, struct.pack(">H", 0) + bytes([val]) * (w * h)))
        rec = struct.pack(">4i", t, l, b, r) + struct.pack(">H", len(chdata))
        for cid, d in chdata:
            rec += struct.pack(">hI", cid, len(d))
        rec += b"8BIMnorm" + bytes([255, 0, 0, 0])
        extra = struct.pack(">I", 0) + struct.pack(">I", 0) + pascal(ly.name)
        extra += block("luni", struct.pack(">I", len(ly.name)) + ly.name.encode("utf-16-be"))
        extra += block("lyid", struct.pack(">I", ly.lid))
        for bl in ly.blocks:
            extra += bl
        rec += struct.pack(">I", len(extra)) + extra
        recs += rec
        chans += b"".join(d for _, d in chdata)
    info = struct.pack(">h", len(layers)) + recs + chans
    if len(info) % 2:
        info += b"\x00"
    layer_info = struct.pack(">I", len(info)) + info
    lm = layer_info + struct.pack(">I", 0)

    res = b"8BIM" + struct.pack(">H", 1005) + b"\x00\x00" + struct.pack(">I", 16) + \
        struct.pack(">IHHIHH", 72 << 16, 1, 1, 72 << 16, 1, 1)

    with open(path, "wb") as f:
        f.write(b"8BPS" + struct.pack(">H", 1) + b"\x00" * 6 + struct.pack(">HIIHH", 3, H, W, 8, 3))
        f.write(struct.pack(">I", 0))
        f.write(struct.pack(">I", len(res)) + res)
        f.write(struct.pack(">I", len(lm)) + lm)
        f.write(struct.pack(">H", 0) + b"\xff" * (W * H * 3))   # composite blanc


if __name__ == "__main__":
    write(sys.argv[1] if len(sys.argv) > 1 else "chopgimp-test.psd")

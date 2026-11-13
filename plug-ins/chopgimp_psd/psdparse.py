# -*- coding: utf-8 -*-
"""
ChopGimp — lecture des informations modifiables d'un fichier PSD / PSB.

Python pur, sans dépendance. Lit uniquement la section « calques » du
fichier : en-tête, ressources utiles, enregistrements de calque et leurs
blocs d'information supplémentaires. Les pixels ne sont jamais lus (on
saute par les longueurs) : un fichier de 400 Mo est analysé en quelques
dixièmes de seconde.

Écrit d'après la spécification Adobe « Photoshop File Formats » et la
structure documentée par psd-tools (MIT).

    psd = parse(chemin)
    psd.width, psd.height, psd.depth, psd.version, psd.resources
    for layer in psd.layers:          # du bas vers le haut, comme le fichier
        layer.id, layer.name, layer.bbox, layer.blocks   # blocs bruts
        layer.text()      -> TextInfo ou None   (TySh)
        layer.shape()     -> ShapeInfo ou None  (vmsk/vsms + vscg/SoCo + vstk)
        layer.effects()   -> dict ou None       (lfx2)
"""
import struct

# ─── lecture binaire ────────────────────────────────────────────────────


class Reader:
    def __init__(self, data, pos=0, end=None):
        self.data = data
        self.pos = pos
        self.end = len(data) if end is None else end

    def read(self, n):
        if self.pos + n > self.end:
            raise ValueError("PSD tronqué (lecture de %d octets en %d)" % (n, self.pos))
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def fmt(self, f):
        f = ">" + f
        return struct.unpack(f, self.read(struct.calcsize(f)))

    def u8(self):
        return self.fmt("B")[0]

    def u16(self):
        return self.fmt("H")[0]

    def i16(self):
        return self.fmt("h")[0]

    def u32(self):
        return self.fmt("I")[0]

    def i32(self):
        return self.fmt("i")[0]

    def u64(self):
        return self.fmt("Q")[0]

    def f64(self):
        return self.fmt("d")[0]

    def skip(self, n):
        self.pos += n

    def left(self):
        return self.end - self.pos

    def pascal(self, pad):
        n = self.u8()
        s = self.read(n)
        total = n + 1
        if total % pad:
            self.skip(pad - total % pad)
        return s.decode("mac_roman", "replace")

    def unicode(self):
        n = self.u32()
        s = self.read(n * 2).decode("utf-16-be", "replace")
        return s.rstrip("\x00")


# ─── descripteurs Adobe (« Action descriptor ») ─────────────────────────


class Descriptor(dict):
    """dict des éléments (clé → valeur) + classe."""
    classID = ""
    name = ""


class Enum(str):
    """Valeur énumérée : le texte est l'énumération, .type le type."""
    type = ""


class Unit(float):
    """Valeur avec unité (#Pxl, #Prc, #Ang, #Pnt…)."""
    unit = ""


def _key(r):
    n = r.u32()
    return r.read(n if n else 4).decode("latin-1")


def read_descriptor(r):
    d = Descriptor()
    d.name = r.unicode()
    d.classID = _key(r)
    for _ in range(r.u32()):
        key = _key(r)
        d[key] = _value(r, r.read(4).decode("latin-1"))
    return d


def _value(r, t):
    if t in ("Objc", "GlbO"):
        return read_descriptor(r)
    if t == "VlLs":
        return [_value(r, r.read(4).decode("latin-1")) for _ in range(r.u32())]
    if t == "doub":
        return r.f64()
    if t == "UntF":
        u = r.read(4).decode("latin-1")
        v = Unit(r.f64())
        v.unit = u
        return v
    if t == "UnFl":
        u = r.read(4).decode("latin-1")
        return [r.f64() for _ in range(r.u32())]
    if t == "TEXT":
        return r.unicode()
    if t == "enum":
        typ = _key(r)
        v = Enum(_key(r))
        v.type = typ
        return v
    if t == "long":
        return r.i32()
    if t == "comp":
        return r.fmt("q")[0]
    if t == "bool":
        return bool(r.u8())
    if t in ("type", "GlbC"):
        r.unicode()
        return _key(r)
    if t in ("alis", "tdta", "Pth "):
        return r.read(r.u32())
    if t == "obj ":
        items = []
        for _ in range(r.u32()):
            k = r.read(4).decode("latin-1")
            if k == "prop":
                r.unicode(); _key(r); items.append(_key(r))
            elif k == "Clss":
                r.unicode(); items.append(_key(r))
            elif k == "Enmr":
                r.unicode(); _key(r); _key(r); items.append(_key(r))
            elif k == "rele":
                r.unicode(); _key(r); items.append(r.i32())
            elif k in ("Idnt", "indx"):
                items.append(r.i32())
            elif k == "name":
                r.unicode(); _key(r); items.append(r.unicode())
            else:
                raise ValueError("référence inconnue %r" % k)
        return items
    if t == "ObAr":       # tableau d'objets (rare) : on le lit pour le sauter
        r.u32()
        r.unicode(); _key(r)
        out = {}
        for _ in range(r.u32()):
            k = _key(r)
            typ = r.read(4).decode("latin-1")
            if typ == "UnFl":
                r.read(4)
                out[k] = [r.f64() for _ in range(r.u32())]
            else:
                out[k] = _value(r, typ)
        return out
    raise ValueError("type de descripteur inconnu %r" % t)


def descriptor_block(data, version_bytes=4):
    """Bloc « version (4) + version du descripteur (4) + descripteur »."""
    r = Reader(data)
    r.skip(version_bytes)
    r.u32()                     # 16
    return read_descriptor(r)


# ─── EngineData (texte) : syntaxe proche du PostScript ──────────────────


def parse_engine_data(data):
    i, n = 0, len(data)
    ws = b" \t\r\n\x00"
    delim = ws + b"[]<>()/"

    def skip():
        nonlocal i
        while i < n and data[i] in ws:
            i += 1

    def value():
        nonlocal i
        skip()
        c = data[i:i + 2]
        if c == b"<<":
            i += 2
            d = {}
            while True:
                skip()
                if data[i:i + 2] == b">>":
                    i += 2
                    return d
                if data[i:i + 1] != b"/":
                    i += 1
                    continue
                i += 1
                j = i
                while i < n and data[i] not in delim:
                    i += 1
                k = data[j:i].decode("latin-1")
                d[k] = value()
        if c[:1] == b"[":
            i += 1
            arr = []
            while True:
                skip()
                if data[i:i + 1] == b"]":
                    i += 1
                    return arr
                arr.append(value())
        if c[:1] == b"(":
            i += 1
            out = bytearray()
            while i < n and data[i:i + 1] != b")":
                if data[i:i + 1] == b"\\":
                    i += 1
                    e = data[i:i + 1]
                    out += {b"n": b"\n", b"r": b"\r", b"t": b"\t"}.get(e, e)
                else:
                    out += data[i:i + 1]
                i += 1
            i += 1
            b = bytes(out)
            if b.startswith(b"\xfe\xff"):
                return b[2:].decode("utf-16-be", "replace")
            return b.decode("latin-1")
        if c[:1] == b"/":
            i += 1
            j = i
            while i < n and data[i] not in delim:
                i += 1
            return "/" + data[j:i].decode("latin-1")
        j = i
        while i < n and data[i] not in delim:
            i += 1
        tok = data[j:i].decode("latin-1")
        if tok == "true":
            return True
        if tok == "false":
            return False
        try:
            return int(tok)
        except ValueError:
            try:
                return float(tok)
            except ValueError:
                return tok

    return value()


# ─── chemins (vmsk / vsms / vsms d'origine) ─────────────────────────────


def parse_path(data, width, height):
    """Retourne (sous-chemins, inversé). Sous-chemin : (fermé, points),
    point = (entrée, ancre, sortie) en pixels du document."""
    r = Reader(data)
    r.u32()                     # version 3
    flags = r.u32()
    subs, cur, closed = [], None, False
    while r.left() >= 26:
        sel = r.u16()
        if sel in (0, 3):
            r.u16()
            r.skip(22)
            closed = sel == 0
            cur = []
            subs.append((closed, cur))
        elif sel in (1, 2, 4, 5):
            pts = []
            for _ in range(3):
                y, x = r.i32(), r.i32()
                pts.append((x / 16777216.0 * width, y / 16777216.0 * height))
            if cur is None:
                cur = []
                subs.append((sel in (1, 2), cur))
            cur.append(tuple(pts))
        else:
            r.skip(24)
    return subs, bool(flags & 1)


# ─── modèle de données ──────────────────────────────────────────────────

LENGTH8_KEYS = {"LMsk", "Lr16", "Lr32", "Layr", "Mt16", "Mt32", "Mtrn", "Alph", "FMsk",
                "lnk2", "FEid", "FXid", "PxSD", "lnkE", "lnk3", "cinf"}


class TextInfo:
    """Texte d'un calque (TySh) ramené à des données simples."""

    def __init__(self):
        self.text = ""
        self.transform = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)   # xx xy yx yy tx ty
        self.bounds = None          # (gauche, haut, droite, bas) relatifs à l'origine
        self.box = None             # cadre de paragraphe (g, h, d, b) ou None (texte de point)
        self.vertical = False
        self.runs = []              # [(longueur, style)] ; style = dict (voir _style)
        self.justification = 0      # 0 gauche, 1 droite, 2 centre, 3+ justifié
        self.warp = None            # (style, courbure %, dist. h %, dist. v %, vertical)
        self.fonts = []             # noms PostScript


class ShapeInfo:
    def __init__(self):
        self.paths = []             # sous-chemins (voir parse_path)
        self.inverted = False
        self.fill = None            # (r, g, b) 0..1, ou None
        self.fill_kind = None       # "solid", "gradient", "pattern" ou None
        self.fill_enabled = True
        self.stroke = None          # dict ou None
        self.is_shape = False       # calque de forme (sinon : masque vectoriel)


def _color(d):
    """Couleur d'un descripteur (RGBC, Grsc, CMYC, HSBC) → (r, g, b) 0..1."""
    if not isinstance(d, dict):
        return None
    c = d.get("Clr ", d)
    if not isinstance(c, dict):
        return None
    cls = getattr(c, "classID", "")
    if "Rd  " in c:
        return tuple(min(1.0, max(0.0, c[k] / 255.0)) for k in ("Rd  ", "Grn ", "Bl  "))
    if "redFloat" in c:
        return (c["redFloat"], c["greenFloat"], c["blueFloat"])
    if "Gry " in c:
        v = 1.0 - c["Gry "] / 100.0
        return (v, v, v)
    if "Cyn " in c:
        cy, m, y, k = (c[x] / 100.0 for x in ("Cyn ", "Mgnt", "Ylw ", "Blck"))
        return ((1 - cy) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    if "H   " in c:
        import colorsys
        return colorsys.hsv_to_rgb((c["H   "] % 360) / 360.0, c["Strt"] / 100.0, c["Brgh"] / 100.0)
    del cls
    return None


def _engine_color(v):
    if isinstance(v, dict) and "Values" in v:
        a, r, g, b = (list(v["Values"]) + [0, 0, 0, 0])[:4]
        return (r, g, b, a)
    return None


def _style(ssd, fonts):
    st = {}
    if "Font" in ssd and 0 <= ssd["Font"] < len(fonts):
        st["font"] = fonts[ssd["Font"]]
    for k, name in (("FontSize", "size"), ("Tracking", "tracking"), ("Leading", "leading"),
                    ("HorizontalScale", "hscale"), ("VerticalScale", "vscale"),
                    ("BaselineShift", "baseline")):
        if k in ssd:
            st[name] = float(ssd[k])
    for k, name in (("FauxBold", "bold"), ("FauxItalic", "italic"), ("Underline", "underline"),
                    ("Strikethrough", "strike"), ("AutoLeading", "autoleading")):
        if k in ssd:
            st[name] = bool(ssd[k])
    if "FontCaps" in ssd:
        st["caps"] = int(ssd["FontCaps"])
    if "FillColor" in ssd:
        c = _engine_color(ssd["FillColor"])
        if c:
            st["color"] = c
    if "StrokeColor" in ssd and ssd.get("OutlineWidth"):
        pass
    return st


WARP_STYLES = {
    "warpArc": "arc", "warpArcLower": "arc-lower", "warpArcUpper": "arc-upper",
    "warpArch": "arch", "warpBulge": "bulge", "warpShellLower": "shell-lower",
    "warpShellUpper": "shell-upper", "warpFlag": "flag", "warpWave": "wave",
    "warpFish": "fish", "warpRise": "rise", "warpFisheye": "fisheye",
    "warpInflate": "inflate", "warpSqueeze": "squeeze", "warpTwist": "twist",
}


def _bounds(d):
    if not isinstance(d, dict):
        return None
    try:
        return tuple(float(d[k]) for k in ("Left", "Top ", "Rght", "Btom"))
    except KeyError:
        return None


def parse_tysh(data):
    r = Reader(data)
    r.u16()                     # version 1
    t = TextInfo()
    t.transform = r.fmt("6d")
    r.u16()                     # version du texte (50)
    r.u32()                     # 16
    desc = read_descriptor(r)
    try:
        r.u16()
        r.u32()
        warp = read_descriptor(r)
    except ValueError:
        warp = {}

    t.text = desc.get("Txt ", "")
    t.vertical = str(desc.get("Ornt", "")) == "Vrtc"
    t.bounds = _bounds(desc.get("bounds")) or _bounds(desc.get("boundingBox"))

    ws = str(warp.get("warpStyle", "warpNone"))
    if ws in WARP_STYLES:
        t.warp = (WARP_STYLES[ws], float(warp.get("warpValue", 0.0)),
                  float(warp.get("warpPerspective", 0.0)),
                  float(warp.get("warpPerspectiveOther", 0.0)),
                  str(warp.get("warpRotate", "Hrzn")) == "Vrtc")

    ed = desc.get("EngineData")
    if not isinstance(ed, bytes):
        return t
    try:
        eng = parse_engine_data(ed)
    except (IndexError, ValueError):
        return t
    engine = eng.get("EngineDict", {})
    res = eng.get("ResourceDict", eng.get("DocumentResources", {}))
    fonts = [f.get("Name", "") for f in res.get("FontSet", []) if isinstance(f, dict)]
    t.fonts = fonts

    default = {}
    sheets = res.get("StyleSheetSet", [])
    if sheets and isinstance(sheets[0], dict):
        default = _style(sheets[0].get("StyleSheetData", {}), fonts)

    editor_text = engine.get("Editor", {}).get("Text")
    if isinstance(editor_text, str) and editor_text:
        t.text = editor_text

    srun = engine.get("StyleRun", {})
    lengths = srun.get("RunLengthArray", [])
    for n, run in zip(lengths, srun.get("RunArray", [])):
        st = dict(default)
        st.update(_style(run.get("StyleSheet", {}).get("StyleSheetData", {}), fonts))
        t.runs.append((int(n), st))
    if not t.runs:
        t.runs = [(len(t.text), default)]

    prun = engine.get("ParagraphRun", {}).get("RunArray", [])
    if prun:
        props = prun[0].get("ParagraphSheet", {}).get("Properties", {})
        t.justification = int(props.get("Justification", 0))

    try:
        shape = engine["Rendered"]["Shapes"]["Children"][0]
        if shape.get("ShapeType") == 1:
            box = shape["Cookie"]["Photoshop"]["BoxBounds"]
            t.box = tuple(float(v) for v in box)
    except (KeyError, IndexError, TypeError):
        pass
    return t


def parse_stroke(desc):
    st = {
        "enabled": bool(desc.get("strokeEnabled", False)),
        "fill_enabled": bool(desc.get("fillEnabled", True)),
        "width": float(desc.get("strokeStyleLineWidth", 1.0)),
        "align": {"strokeStyleAlignInside": "inside", "strokeStyleAlignOutside": "outside"}
                 .get(str(desc.get("strokeStyleLineAlignment", "")), "center"),
        "cap": {"strokeStyleRoundCap": "round", "strokeStyleSquareCap": "square"}
               .get(str(desc.get("strokeStyleLineCapType", "")), "butt"),
        "join": {"strokeStyleRoundJoin": "round", "strokeStyleBevelJoin": "bevel"}
                .get(str(desc.get("strokeStyleLineJoinType", "")), "miter"),
        "opacity": float(desc.get("strokeStyleOpacity", 100.0)) / 100.0,
        "dashes": [float(v) for v in desc.get("strokeStyleLineDashSet", []) or []],
        "color": None,
    }
    content = desc.get("strokeStyleContent")
    if isinstance(content, dict):
        st["color"] = _color(content)
        if st["color"] is None:
            st["kind"] = "gradient" if "Grad" in content else "pattern"
    return st


class Layer:
    def __init__(self, psd):
        self.psd = psd
        self.id = None
        self.name = ""
        self.bbox = (0, 0, 0, 0)      # gauche, haut, droite, bas
        self.opacity = 255
        self.blend = "norm"
        self.clipping = False
        self.visible = True
        self.blocks = {}
        self.section = 0              # lsct : 1/2 groupe, 3 fin de groupe
        self.mask = None              # (gauche, haut, droite, bas, couleur par défaut, désactivé)

    def __repr__(self):
        return "<Layer %s %r %s>" % (self.id, self.name, sorted(self.blocks))

    def text(self):
        if "TySh" not in self.blocks:
            return None
        try:
            return parse_tysh(self.blocks["TySh"])
        except (ValueError, struct.error, KeyError):
            return None

    def shape(self):
        key = "vmsk" if "vmsk" in self.blocks else "vsms" if "vsms" in self.blocks else None
        if key is None:
            return None
        s = ShapeInfo()
        try:
            s.paths, s.inverted = parse_path(self.blocks[key], self.psd.width, self.psd.height)
        except (ValueError, struct.error):
            return None
        if "vscg" in self.blocks:
            kind = self.blocks["vscg"][:4].decode("latin-1")
            s.is_shape = True
            s.fill_kind = {"SoCo": "solid", "GdFl": "gradient", "PtFl": "pattern"}.get(kind)
            if kind == "SoCo":
                try:
                    s.fill = _color(descriptor_block(self.blocks["vscg"][4:], 0))
                except (ValueError, struct.error):
                    pass
        elif "SoCo" in self.blocks:
            s.is_shape = True
            s.fill_kind = "solid"
            try:
                s.fill = _color(descriptor_block(self.blocks["SoCo"], 0))
            except (ValueError, struct.error):
                pass
        elif "GdFl" in self.blocks or "PtFl" in self.blocks:
            s.is_shape = True
            s.fill_kind = "gradient" if "GdFl" in self.blocks else "pattern"
        if "vstk" in self.blocks:
            try:
                s.stroke = parse_stroke(descriptor_block(self.blocks["vstk"]))
                s.fill_enabled = s.stroke["fill_enabled"]
            except (ValueError, struct.error):
                pass
        return s

    def effects(self):
        if "lfx2" in self.blocks:
            try:
                return descriptor_block(self.blocks["lfx2"])
            except (ValueError, struct.error):
                return None
        if "lmfx" in self.blocks:
            try:
                return descriptor_block(self.blocks["lmfx"])
            except (ValueError, struct.error):
                return None
        return None


class PSD:
    def __init__(self):
        self.version = 1
        self.width = self.height = 0
        self.depth = 8
        self.mode = 3
        self.resources = {}
        self.layers = []
        self.global_angle = 120
        self.global_altitude = 30
        self.resolution = 72.0


def _read_layer_info(r, psd, end):
    psb = psd.version == 2
    count = r.i16()
    count = abs(count)
    layers, chan_total = [], 0
    for _ in range(count):
        L = Layer(psd)
        top, left, bottom, right = r.fmt("4i")
        L.bbox = (left, top, right, bottom)
        nch = r.u16()
        for _ in range(nch):
            r.i16()
            chan_total += r.u64() if psb else r.u32()
        r.read(4)                               # 8BIM
        L.blend = r.read(4).decode("latin-1")
        L.opacity = r.u8()
        L.clipping = r.u8() == 1
        flags = r.u8()
        L.visible = not (flags & 2)
        r.u8()
        extra = r.u32()
        xend = r.pos + extra
        mlen = r.u32()
        if mlen >= 20:
            mt, ml, mb, mr = r.fmt("4i")
            dc = r.u8()
            mf = r.u8()
            L.mask = (ml, mt, mr, mb, dc, bool(mf & 2))
            r.skip(mlen - 18)
        else:
            r.skip(mlen)
        r.skip(r.u32())                         # plages de fusion
        L.name = r.pascal(4)
        _read_blocks(r, xend, psb, L.blocks)
        r.pos = xend
        if "luni" in L.blocks:
            try:
                L.name = Reader(L.blocks["luni"]).unicode() or L.name
            except ValueError:
                pass
        if "lyid" in L.blocks:
            L.id = struct.unpack(">I", L.blocks["lyid"][:4])[0]
        sec = L.blocks.get("lsct") or L.blocks.get("lsdk")
        if sec and len(sec) >= 4:
            L.section = struct.unpack(">I", sec[:4])[0]
        layers.append(L)
    return layers


def _read_blocks(r, end, psb, out):
    while r.pos + 12 <= end:
        sig = r.read(4)
        if sig not in (b"8BIM", b"8B64"):
            break
        key = r.read(4).decode("latin-1")
        n = r.u64() if (psb and key in LENGTH8_KEYS) else r.u32()
        out[key] = r.read(n) if r.pos + n <= end else r.read(end - r.pos)
        # les blocs sont alignés sur 2 (souvent sur 4) octets
        while r.pos < end and r.pos % 2:
            r.pos += 1


def parse(path):
    with open(path, "rb") as f:
        head = f.read(26)
        if head[:4] != b"8BPS":
            raise ValueError("pas un fichier PSD")
        psd = PSD()
        (psd.version, ) = struct.unpack(">H", head[4:6])
        psd.height, psd.width = struct.unpack(">II", head[14:22])
        psd.depth, psd.mode = struct.unpack(">HH", head[22:26])
        psb = psd.version == 2

        (n, ) = struct.unpack(">I", f.read(4))   # données du mode couleur
        f.seek(n, 1)
        (n, ) = struct.unpack(">I", f.read(4))   # ressources de l'image
        _read_resources(Reader(f.read(n)), psd)

        n = struct.unpack(">Q" if psb else ">I", f.read(8 if psb else 4))[0]
        base = f.tell()
        # on lit l'info des calques (petite) puis on saute les pixels
        ln = struct.unpack(">Q" if psb else ">I", f.read(8 if psb else 4))[0]
        info = f.read(ln)
        if ln:
            psd.layers = _read_layer_info(Reader(info), psd, ln)
        # masque global puis blocs de document (Lr16/Lr32 pour 16/32 bits)
        f.seek(base + (8 if psb else 4) + ln)
        (gm, ) = struct.unpack(">I", f.read(4))
        f.seek(gm, 1)
        rest = base + n - f.tell()
        if rest > 0:
            # ne lire que les en-têtes de blocs : Lr16/Lr32 peuvent être énormes
            doc = {}
            while rest >= 12:
                hdr = f.read(8)
                if hdr[:4] not in (b"8BIM", b"8B64"):
                    break
                key = hdr[4:8].decode("latin-1")
                ln8 = psb and key in LENGTH8_KEYS
                bl = struct.unpack(">Q" if ln8 else ">I", f.read(8 if ln8 else 4))[0]
                start = f.tell()
                if key in ("Lr16", "Lr32", "Layr") and not psd.layers:
                    sub = f.read(min(bl, 64 << 20))
                    psd.layers = _read_layer_info(Reader(sub), psd, len(sub))
                elif bl < (4 << 20):
                    doc[key] = f.read(bl)
                f.seek(start + bl + (bl & 1))
                rest = base + n - f.tell()
            psd.doc_blocks = doc
    return psd


def _read_resources(r, psd):
    while r.left() >= 12:
        if r.read(4) != b"8BIM":
            break
        rid = r.u16()
        r.pascal(2)
        n = r.u32()
        data = r.read(n)
        if n & 1:
            r.skip(1)
        psd.resources[rid] = data
    if 1037 in psd.resources:
        psd.global_angle = struct.unpack(">i", psd.resources[1037][:4])[0]
    if 1049 in psd.resources:
        psd.global_altitude = struct.unpack(">i", psd.resources[1049][:4])[0]
    if 1005 in psd.resources:
        psd.resolution = struct.unpack(">I", psd.resources[1005][:4])[0] / 65536.0

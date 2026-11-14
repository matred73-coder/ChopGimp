# -*- coding: utf-8 -*-
"""
ChopGimp — lecture d'un enregistrement CairoScript (cairo.ScriptSurface).

poppler dessine une page PDF sur une surface « script » : chaque opération
de dessin y est écrite en clair (tracés, couleurs, remplissages, contours,
dégradés, images). On la rejoue ici pour en tirer des objets :

    objs = parse(texte)
    obj.kind  : "path" (fond et/ou contour), "image"
    path      : liste de sous-chemins [(fermé, [(entrée, ancre, sortie), …])]
                en coordonnées de la surface (pixels)
    fill      : (r, g, b, a) ou None       fill_kind : "solid", "gradient"
    stroke    : dict (couleur, épaisseur, extrémités, angles) ou None
    image     : (largeur, hauteur, octets RGBA, 4 coins en pixels)

Le texte (glyphes) est ignoré : il est repris à part avec l'API texte de
poppler, comme calques de texte modifiables. Les découpes (clip) sont
notées mais pas appliquées ; ce qui n'est pas reconnu est compté.
"""
import base64
import math
import re
import struct
import zlib

TOKEN = re.compile(rb"""
    (?P<ws>\s+|%[^\n]*)
  | (?P<b85><[~|].*?~>)
  | (?P<str>\((?:\\.|[^\\)])*\))
  | (?P<open><<|\[|\{)
  | (?P<close>>>|\]|\})
  | (?P<lit>//?[^\s\[\]{}()<>/%]+)
  | (?P<word>[^\s\[\]{}()<>/%]+)
""", re.X | re.S)


class Matrix:
    __slots__ = ("xx", "yx", "xy", "yy", "x0", "y0")

    def __init__(self, xx=1.0, yx=0.0, xy=0.0, yy=1.0, x0=0.0, y0=0.0):
        self.xx, self.yx, self.xy, self.yy, self.x0, self.y0 = xx, yx, xy, yy, x0, y0

    def mul(self, o):
        """self puis o (comme cairo_matrix_multiply(r, self, o))."""
        return Matrix(self.xx * o.xx + self.yx * o.xy, self.xx * o.yx + self.yx * o.yy,
                      self.xy * o.xx + self.yy * o.xy, self.xy * o.yx + self.yy * o.yy,
                      self.x0 * o.xx + self.y0 * o.xy + o.x0, self.x0 * o.yx + self.y0 * o.yy + o.y0)

    def apply(self, x, y):
        return (self.xx * x + self.xy * y + self.x0, self.yx * x + self.yy * y + self.y0)

    def invert(self):
        det = self.xx * self.yy - self.yx * self.xy
        if abs(det) < 1e-12:
            return Matrix()
        xx, yx, xy, yy = self.yy / det, -self.yx / det, -self.xy / det, self.xx / det
        return Matrix(xx, yx, xy, yy, -(xx * self.x0 + xy * self.y0), -(yx * self.x0 + yy * self.y0))

    def scale_factor(self):
        return math.sqrt(abs(self.xx * self.yy - self.yx * self.xy))


class Pattern:
    def __init__(self, kind):
        self.kind = kind            # "linear", "radial", "image"
        self.stops = []
        self.matrix = Matrix()
        self.image = None


class Obj:
    def __init__(self, kind):
        self.kind = kind
        self.path = []
        self.fill = None
        self.fill_kind = None
        self.stroke = None
        self.image = None
        self.clipped = False


def decode_data(tok):
    """<~…~> (base85) ou <|…~> (longueur + zlib, base85)."""
    body = tok[2:-2]
    raw = base64.a85decode(body, adobe=False)
    if tok[:2] == b"<|":
        return zlib.decompress(raw[4:])
    return raw


def image_rgba(d):
    """Dictionnaire d'image CairoScript → (largeur, hauteur, octets RGBA)."""
    w, h = int(d.get("width", 0)), int(d.get("height", 0))
    fmt = d.get("format", "RGB24").lstrip("/")
    data = d.get("source", b"")
    if not w or not h or not data:
        return None
    out = bytearray(w * h * 4)
    if fmt == "RGB24" and len(data) >= w * h * 3:
        for i in range(w * h):
            out[i * 4:i * 4 + 3] = data[i * 3:i * 3 + 3]
            out[i * 4 + 3] = 255
    elif fmt == "ARGB32" and len(data) >= w * h * 4:
        # pixels natifs (B, V, R, A sur x86), prémultipliés
        for i in range(w * h):
            b, g, r, a = data[i * 4:i * 4 + 4]
            if a:
                r, g, b = (min(255, c * 255 // a) for c in (r, g, b))
            out[i * 4:i * 4 + 4] = bytes((r, g, b, a))
    elif fmt == "A8" and len(data) >= w * h:
        for i in range(w * h):
            out[i * 4 + 3] = data[i]
    else:
        return None
    return w, h, bytes(out)


def parse(text):
    """→ (objets, statistiques)"""
    if isinstance(text, str):
        text = text.encode("latin-1")
    stack = []
    marks = []
    ctm = Matrix()
    ctm_stack = []
    state = {"source": (0.0, 0.0, 0.0, 1.0), "width": 2.0, "cap": "butt", "join": "miter",
             "dash": [], "clip": False}
    state_stack = []
    path = []            # [(fermé, [ (cin, anchor, cout) ])]
    cur = None
    objs = []
    stats = {"unknown": {}, "glyphs": 0, "gradients": 0, "clips": 0}

    def num(v):
        return float(v) if isinstance(v, (int, float)) else 0.0

    def pop_nums(n):
        vals = []
        for _ in range(n):
            vals.append(num(stack.pop()) if stack else 0.0)
        return vals[::-1]

    def start_sub(x, y):
        nonlocal cur
        cur = [False, [[(x, y), (x, y), (x, y)]]]
        path.append(cur)

    def line_to(x, y):
        if cur is None:
            start_sub(x, y)
            return
        cur[1].append([(x, y), (x, y), (x, y)])

    def curve_to(x1, y1, x2, y2, x3, y3):
        if cur is None:
            start_sub(x1, y1)
        cur[1][-1][2] = (x1, y1)
        cur[1].append([(x2, y2), (x3, y3), (x3, y3)])

    def close():
        nonlocal cur
        if cur is not None:
            k = cur[1]
            # point final confondu avec le départ : on le fusionne
            if len(k) > 1 and abs(k[-1][1][0] - k[0][1][0]) < 1e-6 and abs(k[-1][1][1] - k[0][1][1]) < 1e-6:
                k[0][0] = k[-1][0]
                k.pop()
            cur[0] = True
        cur = None

    def finished_path():
        return [(c, [tuple(p) for p in pts]) for c, pts in path if len(pts) > 1]

    def color_of(src):
        if isinstance(src, tuple):
            return src, "solid"
        if isinstance(src, Pattern) and src.stops:
            n = len(src.stops)
            avg = tuple(sum(s[i] for s in src.stops) / n for i in range(1, 5))
            return avg, "gradient"
        return None, None

    def emit_fill():
        src = state["source"]
        if isinstance(src, Pattern) and src.kind == "image" and src.image:
            # image posée par un remplissage (poppler : rectangle + motif image)
            iw, ih, data = src.image
            to_dev = src.matrix.invert().mul(ctm)
            corners = [to_dev.apply(x, y) for x, y in ((0, 0), (iw, 0), (iw, ih), (0, ih))]
            o = Obj("image")
            o.image = (iw, ih, data, corners, 1.0)
            o.clipped = state["clip"]
            objs.append(o)
            return None
        o = Obj("path")
        o.path = finished_path()
        o.fill, o.fill_kind = color_of(state["source"])
        o.clipped = state["clip"]
        if o.fill_kind == "gradient":
            stats["gradients"] += 1
        if o.path and o.fill is not None:
            objs.append(o)
        return o

    def emit_stroke(prev_fill):
        col, kind = color_of(state["source"])
        if col is None:
            return
        stroke = {"color": col, "width": state["width"] * ctm.scale_factor(),
                  "cap": state["cap"], "join": state["join"], "dash": list(state["dash"])}
        p = finished_path()
        # remplissage + contour du même tracé : un seul objet
        if prev_fill is not None and prev_fill.path == p and prev_fill.stroke is None and prev_fill in objs:
            prev_fill.stroke = stroke
            return
        o = Obj("path")
        o.path = p
        o.stroke = stroke
        o.clipped = state["clip"]
        if o.path:
            objs.append(o)

    last_fill = None
    for m in TOKEN.finditer(text):
        kind = m.lastgroup
        tok = m.group(kind)
        if kind == "ws":
            continue
        if kind == "b85":
            try:
                stack.append(decode_data(tok))
            except (ValueError, zlib.error):
                stack.append(b"")
            continue
        if kind == "str":
            stack.append(tok[1:-1])
            continue
        if kind == "open":
            marks.append((tok, len(stack)))
            continue
        if kind == "close":
            if not marks:
                continue
            opener, at = marks.pop()
            items = stack[at:]
            del stack[at:]
            if opener == b"<<":
                d = {}
                for i in range(0, len(items) - 1, 2):
                    k = items[i]
                    if isinstance(k, str) and k.startswith("/"):
                        d[k[1:]] = items[i + 1]
                stack.append(d)
            else:
                stack.append(list(items))
            continue
        if kind == "lit":
            stack.append(tok.decode("latin-1"))
            continue
        w = tok.decode("latin-1")
        try:
            stack.append(float(w) if any(c in w for c in ".eE") else int(w))
            continue
        except ValueError:
            pass

        # ── opérateurs ──
        if w == "n":
            path.clear()
            cur = None
        elif w == "m":
            x, y = pop_nums(2)
            start_sub(x, y)
        elif w == "l":
            x, y = pop_nums(2)
            line_to(x, y)
        elif w == "c":
            curve_to(*pop_nums(6))
        elif w == "h":
            close()
        elif w == "rectangle":
            x, y, rw, rh = pop_nums(4)
            start_sub(x, y)
            line_to(x + rw, y)
            line_to(x + rw, y + rh)
            line_to(x, y + rh)
            close()
        elif w in ("fill", "fill+"):
            last_fill = emit_fill()
            if w == "fill":
                path.clear()
                cur = None
        elif w in ("stroke", "stroke+"):
            emit_stroke(last_fill)
            last_fill = None
            if w == "stroke":
                path.clear()
                cur = None
        elif w in ("clip", "clip+"):
            state["clip"] = True
            state["clip_path"] = finished_path()
            stats["clips"] += 1
            if w == "clip":
                path.clear()
                cur = None
        elif w == "reset-clip":
            state["clip"] = False
            state["clip_path"] = None
        elif w == "rgb":
            r, g, b = pop_nums(3)
            stack.append((r, g, b, 1.0))
        elif w == "rgba":
            stack.append(tuple(pop_nums(4)))
        elif w == "g":
            v, = pop_nums(1)
            stack.append((v, v, v, 1.0))
        elif w == "ga":
            v, a = pop_nums(2)
            stack.append((v, v, v, a))
        elif w == "linear":
            pop_nums(4)
            stack.append(Pattern("linear"))
        elif w == "radial":
            pop_nums(6)
            stack.append(Pattern("radial"))
        elif w == "add-color-stop":
            vals = pop_nums(5)
            if stack and isinstance(stack[-1], Pattern):
                stack[-1].stops.append(tuple(vals))
        elif w == "image":
            d = stack.pop() if stack and isinstance(stack[-1], dict) else {}
            stack.append(image_rgba(d))
        elif w == "pattern":
            img = stack.pop() if stack else None
            p = Pattern("image")
            p.image = img if isinstance(img, tuple) else None
            stack.append(p)
        elif w == "identity":
            stack.append(Matrix())
        elif w == "set-matrix":
            mt = stack.pop() if stack else None
            if isinstance(mt, list) and len(mt) == 6:
                mt = Matrix(*[num(v) for v in mt])
            if not isinstance(mt, Matrix):
                mt = Matrix()
            if stack and isinstance(stack[-1], Pattern):
                stack[-1].matrix = mt
            else:
                ctm = mt
        elif w == "scale":
            sx, sy = pop_nums(2)
            ctm = Matrix(sx, 0, 0, sy, 0, 0).mul(ctm)
        elif w == "translate":
            tx, ty = pop_nums(2)
            ctm = Matrix(1, 0, 0, 1, tx, ty).mul(ctm)
        elif w == "rotate":
            a, = pop_nums(1)
            c, s = math.cos(a), math.sin(a)
            ctm = Matrix(c, s, -s, c, 0, 0).mul(ctm)
        elif w == "transform":
            mt = stack.pop() if stack else None
            if isinstance(mt, list) and len(mt) == 6:
                ctm = Matrix(*[num(v) for v in mt]).mul(ctm)
        elif w == "set-source":
            src = stack.pop() if stack else None
            if isinstance(src, (tuple, Pattern)):
                state["source"] = src
        elif w == "set-line-width":
            state["width"], = pop_nums(1)
        elif w == "set-line-cap":
            v = stack.pop() if stack else ""
            state["cap"] = {"//LINE_CAP_ROUND": "round", "//LINE_CAP_SQUARE": "square"}.get(v, "butt")
        elif w == "set-line-join":
            v = stack.pop() if stack else ""
            state["join"] = {"//LINE_JOIN_ROUND": "round", "//LINE_JOIN_BEVEL": "bevel"}.get(v, "miter")
        elif w == "set-dash":
            off = stack.pop() if stack else 0
            d = stack.pop() if stack else []
            state["dash"] = [num(v) * ctm.scale_factor() for v in d] if isinstance(d, list) else []
        elif w in ("paint", "paint-with-alpha"):
            alpha = pop_nums(1)[0] if w == "paint-with-alpha" else 1.0
            src = state["source"]
            if isinstance(src, Pattern) and src.kind in ("linear", "radial") and state.get("clip_path"):
                # dégradé PDF (« sh ») : découpe + peinture → forme remplie
                o = Obj("path")
                o.path = list(state["clip_path"])
                o.fill, o.fill_kind = color_of(src)
                if o.fill is not None:
                    stats["gradients"] += 1
                    objs.append(o)
            elif isinstance(src, Pattern) and src.kind == "image" and src.image:
                iw, ih, data = src.image
                # pattern → appareil : inverse de la matrice du motif, puis la CTM
                to_dev = src.matrix.invert().mul(ctm)
                corners = [to_dev.apply(x, y) for x, y in ((0, 0), (iw, 0), (iw, ih), (0, ih))]
                o = Obj("image")
                o.image = (iw, ih, data, corners, alpha)
                o.clipped = state["clip"]
                objs.append(o)
        elif w == "dup":
            if stack:
                stack.append(stack[-1])
        elif w == "exch":
            if len(stack) >= 2:
                stack[-1], stack[-2] = stack[-2], stack[-1]
        elif w == "def":
            del stack[-2:]
        elif w == "get":
            del stack[-2:]
            stack.append(None)
        elif w == "save":
            state_stack.append(dict(state))
            ctm_stack.append(ctm)
        elif w == "restore":
            if state_stack:
                state = state_stack.pop()
                ctm = ctm_stack.pop()
        elif w in ("show-glyphs", "show-text-glyphs", "glyph-path"):
            stats["glyphs"] += 1
            if w == "show-text-glyphs" and len(stack) >= 3:
                del stack[-3:]
            elif stack:
                stack.pop()
        elif w in ("surface", "context", "set-font-face", "font", "set-font-matrix", "set-font-options",
                   "set-tolerance", "set-antialias", "set-fill-rule", "set-miter-limit", "set-operator",
                   "set-extend", "set-filter", "push-group", "pop-group", "pop", "copy-page", "show-page",
                   "set-scaled-font", "scaled-font", "set-device-offset", "set-device-scale"):
            # arguments éventuels : on les retire sans les interpréter
            if w in ("set-font-face", "set-font-matrix", "set-font-options", "set-tolerance",
                     "set-antialias", "set-fill-rule", "set-miter-limit", "set-operator", "set-extend",
                     "set-filter", "pop") and stack:
                stack.pop()
        else:
            stats["unknown"][w] = stats["unknown"].get(w, 0) + 1
    return objs, stats

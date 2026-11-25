# -*- coding: utf-8 -*-
"""
ChopGimp 3.27.2 (lot V4) — objets des calques vectoriels pour l'import.

Arbre d'objets (VNode) au format du parasite « chopgimp-vobjects »
(app/path/chopgimp-vobject.c) : to_xml() l'écrit pour la procédure
chopgimp-vobjects-set-xml, from_xml() relit chopgimp-vobjects-get-xml.

- SVG (SvgImport) : lecture directe du XML (xml.etree) :
    groupes <g> (id, inkscape:label), transformations, styles (attributs,
    style=, feuille <style> simple), formes (path, rect, circle, ellipse,
    line, polyline, polygon, use), dégradés linéaires et radiaux (→
    coordonnées relatives à la boîte de l'objet, userSpaceOnUse converti),
    découpes (clip-path → groupe « masque d'écrêtage »), mix-blend-mode,
    fill-opacity / stroke-opacity (→ opacité du fond / du contour),
    marqueurs simples (marker-start / -end → pointes de flèche du contour),
    piles « Aspect » exportées par ChopGimp (<g chopgimp:aspect="1">).
    Les calques Inkscape et les groupes qui contiennent du texte ou des
    images deviennent des calques de groupe ; chaque suite d'objets, UN
    calque vectoriel à plusieurs objets.
- PDF / AI / EPS (pdf_nodes) : les objets relus par cairoscript, un objet
  par élément dessiné, découpes en groupes de masque, dégradés vectoriels.

Format du modèle : version 2 (3.27.2) : pile « Aspect » de fonds et
contours (VNode.entries, sinon VNode.fill sous VNode.stroke), chacun avec
opacity, mode, visible, global et, pour un contour, profile, arrow_start,
arrow_end, arrow_scale (clés des dictionnaires de peinture).

Pur Python (aucune dépendance à GIMP) : testable seul
(tools/dev/test_svg_vobjects.py).
"""
import base64
import math
import os
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

from cairoscript import Matrix

SVG_NS = "{http://www.w3.org/2000/svg}"
INK_NS = "{http://www.inkscape.org/namespaces/inkscape}"
SODI_NS = "{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}"
XLINK_NS = "{http://www.w3.org/1999/xlink}"
CHOP_NS = "{http://chopgimp.org/namespaces/chopgimp}"

KAPPA = 0.5522847498307936


# ─── arbre d'objets ─────────────────────────────────────────────────────

class VNode:
    """Objet d'un calque vectoriel : « path » (sous-chemins) ou « group »."""
    __slots__ = ("kind", "name", "transform", "opacity", "mode", "visible", "locked", "clip",
                 "children", "subpaths", "fill", "stroke", "nonzero", "entries", "symbol")

    def __init__(self, kind, name=""):
        self.kind = kind
        self.name = name or ""
        self.transform = None          # Matrix local → parent, None : identité
        self.opacity = 1.0
        self.mode = "normal"
        self.visible = True
        self.locked = False
        self.clip = False              # groupe : l'enfant du dessus découpe les autres
        self.symbol = None             # 3.28.1 : groupe, occurrence du symbole (id)
        self.children = []
        self.subpaths = []             # [(fermé, [(entrée, ancre, sortie)])]
        self.fill = {"type": "color", "rgba": (0.0, 0.0, 0.0, 1.0)}
        self.stroke = {"type": "none"}
        self.nonzero = True
        # pile « Aspect » (format 2) quand fill / stroke ne suffisent pas :
        # [{"kind": "fill" | "stroke", peinture…}] du bas vers le haut
        self.entries = None

    def leaves(self):
        if self.kind == "path":
            yield self
        for c in self.children:
            yield from c.leaves()

    def count(self):
        return 1 + sum(c.count() for c in self.children)


def entries_of(n):
    """Pile « Aspect » d'un objet tracé : [(« fill » | « stroke », peinture)]
    du bas vers le haut."""
    if n.entries is not None:
        return [(e["kind"], e) for e in n.entries]
    return [("fill", n.fill), ("stroke", n.stroke)]


def path_node(name, subpaths, fill=None, stroke=None, nonzero=True):
    n = VNode("path", name)
    n.subpaths = subpaths
    n.fill = fill or {"type": "none"}
    n.stroke = stroke or {"type": "none"}
    n.nonzero = nonzero
    return n


def is_identity(m):
    return m is None or (abs(m.xx - 1) < 1e-12 and abs(m.yx) < 1e-12 and abs(m.xy) < 1e-12 and
                         abs(m.yy - 1) < 1e-12 and abs(m.x0) < 1e-12 and abs(m.y0) < 1e-12)


def compose(inner, outer):
    """inner puis outer (None = identité)."""
    if is_identity(inner):
        return outer
    if is_identity(outer):
        return inner
    return inner.mul(outer)


# ─── géométrie ──────────────────────────────────────────────────────────

def tf_subpaths(subs, m):
    if is_identity(m):
        return subs
    return [(c, [tuple(m.apply(*p) for p in k) for k in knots]) for c, knots in subs]


def _segments(subpaths):
    for closed, knots in subpaths:
        n = len(knots)
        if n == 1:
            a = knots[0][1]
            yield a, a, a, a
        for i in range(n - 1 + (1 if closed and n > 1 else 0)):
            k0, k1 = knots[i], knots[(i + 1) % n]
            yield k0[1], k0[2], k1[0], k1[1]


def _extent(p0, p1, p2, p3):
    lo, hi = min(p0, p3), max(p0, p3)
    if min(p1, p2) >= lo and max(p1, p2) <= hi:
        return lo, hi
    a = -p0 + 3 * p1 - 3 * p2 + p3
    b = 2 * (p0 - 2 * p1 + p2)
    c = p1 - p0
    ts = []
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            ts.append(-c / b)
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            s = math.sqrt(disc)
            ts += [(-b + s) / (2 * a), (-b - s) / (2 * a)]
    for t in ts:
        if 0 < t < 1:
            mt = 1 - t
            v = mt ** 3 * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t ** 3 * p3
            lo, hi = min(lo, v), max(hi, v)
    return lo, hi


def bbox(subpaths):
    """Boîte exacte (courbes comprises) → (x1, y1, x2, y2) ou None."""
    x1 = y1 = math.inf
    x2 = y2 = -math.inf
    for p0, p1, p2, p3 in _segments(subpaths):
        lo, hi = _extent(p0[0], p1[0], p2[0], p3[0])
        x1, x2 = min(x1, lo), max(x2, hi)
        lo, hi = _extent(p0[1], p1[1], p2[1], p3[1])
        y1, y2 = min(y1, lo), max(y2, hi)
    return None if x1 == math.inf else (x1, y1, x2, y2)


def node_bbox(node, m=None):
    """Boîte d'un objet (groupes compris) dans l'espace de m."""
    m = compose(node.transform, m)
    if node.kind == "path":
        return bbox(tf_subpaths(node.subpaths, m))
    boxes = [b for b in (node_bbox(c, m) for c in node.children) if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def local_bbox(node):
    """Boîte d'un objet dans son propre espace (sans sa transformation)."""
    if node.kind == "path":
        return bbox(node.subpaths)
    boxes = [b for b in (node_bbox(c) for c in node.children) if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def bbox_units(subpaths):
    """Espace local → unités de la boîte (comme le rendu : cairo_path_extents,
    côté nul → 1)."""
    b = bbox(subpaths) or (0.0, 0.0, 1.0, 1.0)
    w, h = b[2] - b[0], b[3] - b[1]
    if w < 1e-6:
        w = 1.0
    if h < 1e-6:
        h = 1.0
    return Matrix(1.0 / w, 0, 0, 1.0 / h, -b[0] / w, -b[1] / h), (w, h)


class PathBuilder:
    """Sous-chemins au format (fermé, [(entrée, ancre, sortie)])."""

    def __init__(self):
        self.subs = []
        self.cur = None
        self.start = (0.0, 0.0)
        self.pt = (0.0, 0.0)

    def move(self, p):
        self._flush()
        self.cur = [[p, p, p]]
        self.start = self.pt = p

    def _ensure(self):
        if self.cur is None:
            self.cur = [[self.pt, self.pt, self.pt]]
            self.start = self.pt

    def line(self, p):
        self._ensure()
        self.cur.append([p, p, p])
        self.pt = p

    def curve(self, c1, c2, p):
        self._ensure()
        self.cur[-1][2] = c1
        self.cur.append([c2, p, p])
        self.pt = p

    def close(self):
        if self.cur is not None:
            k = self.cur
            if len(k) > 1 and abs(k[-1][1][0] - k[0][1][0]) < 1e-9 and abs(k[-1][1][1] - k[0][1][1]) < 1e-9:
                k[0][0] = k[-1][0]
                k.pop()
            if len(k) > 1:
                self.subs.append((True, [tuple(x) for x in k]))
            self.cur = None
        self.pt = self.start

    def _flush(self):
        if self.cur is not None and len(self.cur) > 1:
            self.subs.append((False, [tuple(x) for x in self.cur]))
        self.cur = None

    def result(self):
        self._flush()
        return self.subs


def arc_to_curves(b, p1, rx, ry, phi, fa, fs, p2):
    x1, y1 = p1
    x2, y2 = p2
    if (abs(x1 - x2) < 1e-12 and abs(y1 - y2) < 1e-12):
        return
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-12 or ry < 1e-12:
        b.line(p2)
        return
    phi = math.radians(phi)
    cs, sn = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p, y1p = cs * dx + sn * dy, -sn * dx + cs * dy
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, num / den)) if den > 0 else 0.0
    if fa == fs:
        coef = -coef
    cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
    cx = cs * cxp - sn * cyp + (x1 + x2) / 2.0
    cy = sn * cxp + cs * cyp + (y1 + y2) / 2.0

    def ang(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    t1 = ang(1, 0, ux, uy)
    dt = ang(ux, uy, vx, vy)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    n = max(1, int(math.ceil(abs(dt) / (math.pi / 2) - 1e-9)))
    d = dt / n
    t = 4.0 / 3.0 * math.tan(d / 4)

    def mp(x, y):
        return (cx + rx * cs * x - ry * sn * y, cy + rx * sn * x + ry * cs * y)

    for i in range(n):
        a1 = t1 + i * d
        a2 = a1 + d
        c1 = mp(math.cos(a1) - t * math.sin(a1), math.sin(a1) + t * math.cos(a1))
        c2 = mp(math.cos(a2) + t * math.sin(a2), math.sin(a2) - t * math.cos(a2))
        end = p2 if i == n - 1 else mp(math.cos(a2), math.sin(a2))
        b.curve(c1, c2, end)


class _Scan:
    NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

    def __init__(self, s):
        self.s, self.i = s, 0

    def skip(self):
        s, i = self.s, self.i
        while i < len(s) and s[i] in " \t\r\n,":
            i += 1
        self.i = i

    def cmd(self):
        self.skip()
        if self.i < len(self.s) and self.s[self.i].isalpha():
            self.i += 1
            return self.s[self.i - 1]
        return None

    def has_num(self):
        self.skip()
        return self.i < len(self.s) and (self.s[self.i].isdigit() or self.s[self.i] in "+-.")

    def num(self):
        self.skip()
        m = self.NUM.match(self.s, self.i)
        if not m:
            raise ValueError("nombre attendu")
        self.i = m.end()
        return float(m.group(0))

    def flag(self):
        self.skip()
        if self.i < len(self.s) and self.s[self.i] in "01":
            self.i += 1
            return self.s[self.i - 1] == "1"
        raise ValueError("drapeau attendu")


def parse_d(d):
    """Données d'un <path> (toutes les commandes SVG) → sous-chemins."""
    b = PathBuilder()
    sc = _Scan(d or "")
    cmd = None
    last_c = None      # dernier point de contrôle (S / T)
    last_kind = None
    try:
        while True:
            c = sc.cmd()
            if c is None:
                if cmd is None or not sc.has_num():
                    break
                c = cmd
            elif c in "Zz":
                b.close()
                cmd, last_kind = None, None
                continue
            rel = c.islower()
            C = c.upper()
            x0, y0 = b.pt

            def P(x, y):
                return (x0 + x, y0 + y) if rel else (x, y)

            if C == "M":
                b.move(P(sc.num(), sc.num()))
                cmd = "l" if rel else "L"
                last_kind = None
                continue
            if C == "L":
                b.line(P(sc.num(), sc.num()))
                last_kind = None
            elif C == "H":
                x = sc.num()
                b.line((x0 + x if rel else x, y0))
                last_kind = None
            elif C == "V":
                y = sc.num()
                b.line((x0, y0 + y if rel else y))
                last_kind = None
            elif C == "C":
                c1, c2, p = P(sc.num(), sc.num()), P(sc.num(), sc.num()), P(sc.num(), sc.num())
                b.curve(c1, c2, p)
                last_c, last_kind = c2, "C"
            elif C == "S":
                c1 = (2 * x0 - last_c[0], 2 * y0 - last_c[1]) if last_kind == "C" else (x0, y0)
                c2, p = P(sc.num(), sc.num()), P(sc.num(), sc.num())
                b.curve(c1, c2, p)
                last_c, last_kind = c2, "C"
            elif C == "Q":
                q, p = P(sc.num(), sc.num()), P(sc.num(), sc.num())
                b.curve((x0 + 2 / 3.0 * (q[0] - x0), y0 + 2 / 3.0 * (q[1] - y0)),
                        (p[0] + 2 / 3.0 * (q[0] - p[0]), p[1] + 2 / 3.0 * (q[1] - p[1])), p)
                last_c, last_kind = q, "Q"
            elif C == "T":
                q = (2 * x0 - last_c[0], 2 * y0 - last_c[1]) if last_kind == "Q" else (x0, y0)
                p = P(sc.num(), sc.num())
                b.curve((x0 + 2 / 3.0 * (q[0] - x0), y0 + 2 / 3.0 * (q[1] - y0)),
                        (p[0] + 2 / 3.0 * (q[0] - p[0]), p[1] + 2 / 3.0 * (q[1] - p[1])), p)
                last_c, last_kind = q, "Q"
            elif C == "A":
                rx, ry, phi = sc.num(), sc.num(), sc.num()
                fa, fs = sc.flag(), sc.flag()
                p = P(sc.num(), sc.num())
                arc_to_curves(b, (x0, y0), rx, ry, phi, fa, fs, p)
                last_kind = None
            else:
                break
            cmd = c
    except (ValueError, TypeError):
        pass          # comme les navigateurs : on garde ce qui précède l'erreur
    return b.result()


def ellipse_subpaths(cx, cy, rx, ry):
    kx, ky = KAPPA * rx, KAPPA * ry
    return [(True, [((cx + rx, cy - ky), (cx + rx, cy), (cx + rx, cy + ky)),
                    ((cx + kx, cy + ry), (cx, cy + ry), (cx - kx, cy + ry)),
                    ((cx - rx, cy + ky), (cx - rx, cy), (cx - rx, cy - ky)),
                    ((cx - kx, cy - ry), (cx, cy - ry), (cx + kx, cy - ry))])]


def _fmt(v, prec=4):
    s = ("%." + str(prec) + "f") % v
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def subpaths_to_d(subs):
    """Comme path_to_d() du modèle : M, C, Z en absolu."""
    out = []
    for closed, knots in subs:
        if not knots:
            continue
        pt = lambda p: "%s %s" % (_fmt(p[0]), _fmt(p[1]))  # noqa: E731
        out.append("M" + pt(knots[0][1]))
        for k in range(1, len(knots)):
            out.append("C%s %s %s" % (pt(knots[k - 1][2]), pt(knots[k][0]), pt(knots[k][1])))
        if closed:
            out.append("C%s %s %s Z" % (pt(knots[-1][2]), pt(knots[0][0]), pt(knots[0][1])))
    return " ".join(out)


# ─── peintures et dégradés ──────────────────────────────────────────────

def linear_to_units(p1, p2, t):
    """Dégradé linéaire de p1 à p2 (espace du dégradé) ; t : espace du
    dégradé → unités de la boîte. Exact pour toute transformation affine :
    la valeur reste une fonction linéaire de la position."""
    q1 = t.apply(*p1)
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    dd = dx * dx + dy * dy
    if dd < 1e-18:
        return q1 + q1
    inv = t.invert()
    # gradient de la valeur dans les unités de la boîte : Aᵀ·d / |d|²
    gx = (inv.xx * dx + inv.yx * dy) / dd
    gy = (inv.xy * dx + inv.yy * dy) / dd
    gg = gx * gx + gy * gy
    if gg < 1e-18:
        return q1 + q1
    return q1 + (q1[0] + gx / gg, q1[1] + gy / gg)


def radial_to_units(c, r, f, t):
    """→ (centre, rayon, foyer, exact). Exact si t est une similitude."""
    det = abs(t.xx * t.yy - t.yx * t.xy)
    exact = (abs(t.xx - t.yy) < 1e-6 * max(1, abs(t.xx)) and abs(t.yx + t.xy) < 1e-6 * max(1, abs(t.yx))) or \
            (abs(t.xx + t.yy) < 1e-6 * max(1, abs(t.xx)) and abs(t.yx - t.xy) < 1e-6 * max(1, abs(t.yx)))
    return t.apply(*c), r * math.sqrt(det), t.apply(*f), exact


def gradient_paint(kind, coords, stops, t, alpha=1.0):
    """Peinture du modèle ; kind « linear » : coords (x1, y1, x2, y2) ;
    « radial » : (cx, cy, r, fx, fy). → (peinture, exact)"""
    st = [(max(0.0, min(1.0, o)), (rgba[0], rgba[1], rgba[2], rgba[3] * alpha)) for o, rgba in stops]
    exact = True
    if kind == "linear":
        x1, y1, x2, y2 = linear_to_units(coords[0:2], coords[2:4], t)
        p = {"type": "linear", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "r": 0.5}
    else:
        (cx, cy), r, (fx, fy), exact = radial_to_units(coords[0:2], coords[2], coords[3:5], t)
        p = {"type": "radial", "x1": cx, "y1": cy, "x2": fx, "y2": fy, "r": r}
    p["stops"] = st
    return p, exact


# ─── écriture / lecture du XML du modèle ────────────────────────────────

def _color(rgba):
    return " ".join(_fmt(max(0.0, min(1.0, v)), 6) for v in rgba)


def _paint_xml(out, element, p, stroke=None):
    t = p.get("type", "none")
    a = ['<%s type="%s"' % (element, t)]
    if t == "color":
        a.append(' color="%s"' % _color(p["rgba"]))
    elif t in ("linear", "radial"):
        for k in ("x1", "y1", "x2", "y2", "r"):
            a.append(' %s="%s"' % (k, _fmt(p.get(k, 0.0), 6)))
    if stroke is not None:
        a.append(' width="%s" align="%s" cap="%s" join="%s" miter="%s"'
                 % (_fmt(stroke.get("width", 1.0), 6), stroke.get("align", "center"),
                    stroke.get("cap", "butt"), stroke.get("join", "miter"),
                    _fmt(stroke.get("miter", 4.0), 6)))
        if stroke.get("dash"):
            a.append(' dash="%s" dash-offset="%s"'
                     % (" ".join(_fmt(v, 6) for v in stroke["dash"]), _fmt(stroke.get("dash_offset", 0.0), 6)))
    # format 2 : seulement hors valeurs par défaut (comme write_entry())
    op = max(0.0, min(1.0, p.get("opacity", 1.0)))
    if op < 1.0:
        a.append(' opacity="%s"' % _fmt(op, 6))
    if p.get("mode", "normal") not in ("normal", None, ""):
        a.append(' mode="%s"' % p["mode"])
    if not p.get("visible", True):
        a.append(' visible="0"')
    if p.get("global"):
        a.append(' global=%s' % quoteattr(_clean(p["global"])))
    if stroke is not None:
        if p.get("profile") not in (None, "", "uniform"):
            a.append(' profile=%s' % quoteattr(_clean(p["profile"])))
        for k in ("arrow_start", "arrow_end"):
            if p.get(k):
                a.append(' %s=%s' % (k.replace("_", "-"), quoteattr(p[k])))
        if (p.get("arrow_start") or p.get("arrow_end")) and p.get("arrow_scale", 1.0) != 1.0:
            a.append(' arrow-scale="%s"' % _fmt(p["arrow_scale"], 6))
    stops = p.get("stops") if t in ("linear", "radial") else None
    if not stops:
        out.append("".join(a) + "/>\n")
        return
    out.append("".join(a) + ">\n")
    for o, rgba in stops:
        out.append('<stop offset="%s" color="%s"/>\n' % (_fmt(o, 6), _color(rgba)))
    out.append("</%s>\n" % element)


def _clean(s):
    return "".join(ch for ch in (s or "") if ch >= " " or ch in "\t\n")


def to_xml(nodes, progress=None):
    """Objets de la racine, du bas vers le haut (ordre du modèle et du SVG)
    → texte pour chopgimp-vobjects-set-xml."""
    out = []
    ids = [0]
    total = max(1, sum(n.count() for n in nodes))

    def obj(n):
        ids[0] += 1
        if progress and ids[0] % 500 == 0:
            progress(ids[0] / float(total))
        tag = "group" if n.kind == "group" else "path"
        a = ['<%s id="%d" name=%s' % (tag, ids[0], quoteattr(_clean(n.name)))]
        if not is_identity(n.transform):
            m = n.transform
            a.append(' transform="%s"' % " ".join(_fmt(v, 8) for v in (m.xx, m.yx, m.xy, m.yy, m.x0, m.y0)))
        a.append(' opacity="%s" mode="%s" visible="%d" locked="%d"'
                 % (_fmt(max(0.0, min(1.0, n.opacity)), 6), n.mode or "normal",
                    1 if n.visible else 0, 1 if n.locked else 0))
        if n.kind == "path":
            a.append(' fill-rule="%s" antialias="1" d="%s">\n'
                     % ("nonzero" if n.nonzero else "evenodd", subpaths_to_d(n.subpaths)))
            out.append("".join(a))
            for kind, e in entries_of(n):
                _paint_xml(out, kind, e, e if kind == "stroke" else None)
        else:
            if getattr(n, "symbol", None):
                a.append(' symbol=%s' % quoteattr(_clean(n.symbol)))
            a.append(' clip="1">\n' if n.clip else ">\n")
            out.append("".join(a))
            for c in n.children:
                obj(c)
        out.append("</%s>\n" % tag)

    for n in nodes:
        obj(n)
    head = '<chopgimp-vobjects version="2" next-id="%d">\n<group id="0" name="">\n' % (ids[0] + 1)
    return head + "".join(out) + "</group>\n</chopgimp-vobjects>\n"


def _num_list(s):
    return [float(v) for v in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", s or "")]


def from_xml(text):
    """XML du modèle (chopgimp-vobjects-get-xml) → liste des objets de la racine."""
    root = ET.fromstring(text)
    g = root.find("group")
    if g is None:
        return []

    def paint(el):
        p = {"type": el.get("type", "none")}
        # format 2
        if el.get("opacity") is not None:
            p["opacity"] = max(0.0, min(1.0, float(el.get("opacity"))))
        if el.get("mode") not in (None, "normal"):
            p["mode"] = el.get("mode")
        if el.get("visible", "1") == "0":
            p["visible"] = False
        if el.get("global"):
            p["global"] = el.get("global")
        if el.tag == "stroke":
            if el.get("profile") not in (None, "", "uniform"):
                p["profile"] = el.get("profile")
            for k in ("arrow-start", "arrow-end"):
                if el.get(k):
                    p[k.replace("-", "_")] = el.get(k)
            if el.get("arrow-scale") is not None:
                p["arrow_scale"] = float(el.get("arrow-scale"))
        if p["type"] == "color":
            p["rgba"] = tuple((_num_list(el.get("color")) + [0, 0, 0, 1])[:4])
        elif p["type"] in ("linear", "radial"):
            for k, dv in (("x1", 0.0), ("y1", 0.0), ("x2", 1.0), ("y2", 0.0), ("r", 0.5)):
                p[k] = float(el.get(k, dv))
            p["stops"] = [(float(s.get("offset", 0)), tuple((_num_list(s.get("color")) + [0, 0, 0, 1])[:4]))
                          for s in el.findall("stop")]
        return p

    def obj(el):
        n = VNode("group" if el.tag == "group" else "path", el.get("name", ""))
        tf = _num_list(el.get("transform"))
        if len(tf) == 6:
            n.transform = Matrix(*tf)
        n.opacity = float(el.get("opacity", 1))
        n.mode = el.get("mode", "normal")
        n.visible = el.get("visible", "1") != "0"
        n.locked = el.get("locked", "0") != "0"
        if n.kind == "group":
            n.clip = el.get("clip", "0") != "0"
            n.children = [obj(c) for c in el if c.tag in ("group", "path")]
        else:
            n.nonzero = el.get("fill-rule") == "nonzero"
            n.subpaths = parse_d(el.get("d"))
            stack = []
            for c in el:
                if c.tag not in ("fill", "stroke"):
                    continue
                p = paint(c)
                if c.tag == "stroke":
                    p.update(width=float(c.get("width", 1)), align=c.get("align", "center"),
                             cap=c.get("cap", "butt"), join=c.get("join", "miter"),
                             miter=float(c.get("miter", 10)), dash=_num_list(c.get("dash")),
                             dash_offset=float(c.get("dash-offset", 0)))
                stack.append((c.tag, p))
            kinds = [k for k, _ in stack]
            fills = [p for k, p in stack if k == "fill"]
            strokes = [p for k, p in stack if k == "stroke"]
            n.fill = fills[0] if fills else {"type": "none"}
            n.stroke = strokes[-1] if strokes else {"type": "none"}
            # un fond sous un contour au plus : fill / stroke suffisent
            if not (len(fills) <= 1 and len(strokes) <= 1 and kinds in (["fill", "stroke"], ["fill"],
                                                                         ["stroke"], [])):
                n.entries = [dict(p, kind=k) for k, p in stack]
        return n

    return [obj(c) for c in g if c.tag in ("group", "path")]


# ─── « Fusionner les objets de même style » ─────────────────────────────

def _style_key(n):
    def pk(p):
        return tuple(sorted((k, tuple(map(tuple, v)) if k == "stops" else
                             (tuple(v) if isinstance(v, (list, tuple)) else v)) for k, v in p.items()))
    m = n.transform
    return (pk(n.fill), pk(n.stroke), tuple(pk(e) for e in n.entries or ()), n.nonzero,
            round(n.opacity, 4), n.mode, n.visible,
            None if is_identity(m) else tuple(round(v, 6) for v in (m.xx, m.yx, m.xy, m.yy, m.x0, m.y0)))


def merge_similar(nodes, limit=400):
    """Objets voisins de même style → un seul objet (plusieurs sous-chemins).
    Les dégradés (relatifs à la boîte de chaque objet) ne sont pas réunis ;
    la forme de découpe (dessus d'un masque) reste seule."""
    out = []
    for n in nodes:
        if n.kind == "group":
            if n.clip and n.children:
                n.children = merge_similar(n.children[:-1], limit) + n.children[-1:]
            else:
                n.children = merge_similar(n.children, limit)
            out.append(n)
            continue
        prev = out[-1] if out else None
        if prev is not None and prev.kind == "path" and \
                all(e.get("type") not in ("linear", "radial") for _, e in entries_of(n)) and \
                len(prev.subpaths) < limit and _style_key(prev) == _style_key(n):
            prev.subpaths = prev.subpaths + n.subpaths
            continue
        out.append(n)
    return out


# ─── SVG ────────────────────────────────────────────────────────────────

INHERITED = {"fill", "fill-opacity", "fill-rule", "stroke", "stroke-width", "stroke-opacity",
             "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-dasharray",
             "stroke-dashoffset", "visibility", "clip-rule", "color", "font-size", "font-family",
             "marker", "marker-start", "marker-mid", "marker-end",
             "font-weight", "font-style", "text-anchor"}
PROPS = INHERITED | {"opacity", "display", "clip-path", "mask", "filter", "mix-blend-mode",
                     "stop-color", "stop-opacity"}

BLEND = {"multiply": "multiply", "screen": "screen", "overlay": "overlay", "darken": "darken-only",
         "lighten": "lighten-only", "color-dodge": "dodge", "color-burn": "burn",
         "hard-light": "hardlight", "soft-light": "softlight", "difference": "difference",
         "exclusion": "exclusion", "hue": "lch-hue", "saturation": "lch-chroma", "color": "hsl-color",
         "luminosity": "lch-lightness", "plus-lighter": "addition"}

NAMED = {
    "black": "000000", "white": "ffffff", "red": "ff0000", "lime": "00ff00", "green": "008000",
    "blue": "0000ff", "yellow": "ffff00", "cyan": "00ffff", "aqua": "00ffff", "magenta": "ff00ff",
    "fuchsia": "ff00ff", "gray": "808080", "grey": "808080", "silver": "c0c0c0", "maroon": "800000",
    "olive": "808000", "purple": "800080", "teal": "008080", "navy": "000080", "orange": "ffa500",
    "pink": "ffc0cb", "brown": "a52a2a", "gold": "ffd700", "indigo": "4b0082", "violet": "ee82ee",
    "darkgray": "a9a9a9", "darkgrey": "a9a9a9", "lightgray": "d3d3d3", "lightgrey": "d3d3d3",
    "dimgray": "696969", "darkred": "8b0000", "darkgreen": "006400", "darkblue": "00008b",
    "lightblue": "add8e6", "skyblue": "87ceeb", "steelblue": "4682b4", "royalblue": "4169e1",
    "crimson": "dc143c", "tomato": "ff6347", "coral": "ff7f50", "salmon": "fa8072",
    "khaki": "f0e68c", "beige": "f5f5dc", "ivory": "fffff0", "tan": "d2b48c", "chocolate": "d2691e",
    "firebrick": "b22222", "forestgreen": "228b22", "seagreen": "2e8b57", "limegreen": "32cd32",
    "turquoise": "40e0d0", "orchid": "da70d6", "plum": "dda0dd", "lavender": "e6e6fa",
    "whitesmoke": "f5f5f5", "gainsboro": "dcdcdc", "slategray": "708090", "darkorange": "ff8c00",
    "hotpink": "ff69b4", "deeppink": "ff1493", "midnightblue": "191970", "darkviolet": "9400d3",
}


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def parse_color(v, current=None):
    """→ (r, g, b, a) ou None (none / invalide)."""
    v = (v or "").strip()
    low = v.lower()
    if not v or low in ("none", "transparent"):
        return None
    if low == "currentcolor":
        return parse_color(current) if current else (0.0, 0.0, 0.0, 1.0)
    m = re.fullmatch(r"#([0-9a-fA-F]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) in (6, 8):
            vals = [int(h[i:i + 2], 16) / 255.0 for i in range(0, len(h), 2)]
            return tuple(vals[:3]) + ((vals[3],) if len(vals) == 4 else (1.0,))
        return None
    m = re.fullmatch(r"rgba?\(([^)]*)\)", low)
    if m:
        parts = [p for p in re.split(r"[\s,/]+", m.group(1).strip()) if p]
        out = []
        for i, p in enumerate(parts[:4]):
            if p.endswith("%"):
                out.append(float(p[:-1]) / 100.0)
            else:
                out.append(float(p) / (255.0 if i < 3 else 1.0))
        while len(out) < 4:
            out.append(1.0 if len(out) == 3 else 0.0)
        return tuple(max(0.0, min(1.0, x)) for x in out)
    if low in NAMED:
        h = NAMED[low]
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)
    return None


def parse_number(v, default=0.0):
    m = re.match(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)(%?)", v or "")
    if not m:
        return default
    x = float(m.group(1))
    return x / 100.0 if m.group(2) else x


UNITS = {"px": 1.0, "pt": 96 / 72.0, "pc": 16.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0,
         "em": 16.0, "ex": 8.0, "": 1.0}


def parse_length(v, ref=100.0, default=0.0):
    m = re.match(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-zA-Z%]*)", v or "")
    if not m:
        return default
    x, u = float(m.group(1)), m.group(2).lower()
    if u == "%":
        return x / 100.0 * ref
    return x * UNITS.get(u, 1.0)


def svg_matrix(transform):
    """Attribut transform → Matrix (translate, scale, rotate, skewX/Y, matrix)."""
    m = Matrix()
    for op, args in re.findall(r"(\w+)\s*\(([^)]*)\)", transform or ""):
        v = _num_list(args)
        if op == "translate" and v:
            t = Matrix(1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif op == "scale" and v:
            t = Matrix(v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif op == "rotate" and v:
            a = math.radians(v[0])
            t = Matrix(math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) >= 3:
                cx, cy = v[1], v[2]
                t = Matrix(1, 0, 0, 1, -cx, -cy).mul(t).mul(Matrix(1, 0, 0, 1, cx, cy))
        elif op == "skewX" and v:
            t = Matrix(1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif op == "skewY" and v:
            t = Matrix(1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        elif op == "matrix" and len(v) == 6:
            t = Matrix(*v)
        else:
            continue
        # « A B » : B s'applique d'abord, puis A
        m = t.mul(m)
    return None if is_identity(m) else m


def parse_style_attr(s):
    d = {}
    for item in (s or "").split(";"):
        if ":" in item:
            k, v = item.split(":", 1)
            d[k.strip().lower()] = v.strip()
    return d


SKIP = {"defs", "style", "metadata", "title", "desc", "namedview", "clipPath", "mask",
        "linearGradient", "radialGradient", "pattern", "marker", "symbol", "filter", "script",
        "foreignObject", "font", "font-face", "cursor", "view", "guide", "perspective"}
SHAPES = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
ARROWS = ("triangle", "arrow", "circle", "square", "bar")
GROUPS = {"g", "a", "switch"}
AUTO_ID = re.compile(r"^(path|rect|circle|ellipse|line|polyline|polygon|g|use|obj|group|vobj|"
                     r"clip|clippath|grad|lineargradient|radialgradient|layer|svg|stop|text|tspan)"
                     r"[-_]?\d+(-\d+)?$", re.I)
DEFAULT_NAMES = {"path": "Tracé", "rect": "Rectangle", "circle": "Cercle", "ellipse": "Ellipse",
                 "line": "Ligne", "polyline": "Polyligne", "polygon": "Polygone", "g": "Groupe",
                 "a": "Groupe", "switch": "Groupe", "use": "Clone"}


def _is_rect(pts):
    """4 sommets à angles droits."""
    for i in range(4):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % 4]
        u, v = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
        nu, nv = math.hypot(*u), math.hypot(*v)
        if nu < 1e-9 or nv < 1e-9 or abs(u[0] * v[0] + u[1] * v[1]) > 1e-3 * nu * nv:
            return False
    return True


def image_size(w, h):
    """Taille en pixels entiers d'un document de w × h px : arrondie au-dessus,
    sauf les à-peu-près entiers (400.0003 px, largeur « 4.16667in » : 400 et
    pas 401, qui décalerait tout d'un demi-pixel par le centrage du
    viewBox)."""
    def snap(v):
        r = round(v)
        # 6 chiffres significatifs : erreur relative < 5e-6
        return int(r) if abs(v - r) < max(1e-3, 1e-5 * abs(v)) else int(math.ceil(v))
    return snap(w), snap(h)


def element_name(el, fallback=""):
    label = el.get(INK_NS + "label")
    if label:
        return label
    i = el.get("id")
    if i and not AUTO_ID.match(i):
        return i
    return fallback or DEFAULT_NAMES.get(local(el.tag), "")


def is_layer(el):
    return local(el.tag) == "g" and el.get(INK_NS + "groupmode") == "layer"


class SvgImport:
    """Lecture d'un document SVG en plan d'import :

    items = [{"kind": "vector", "name", "visible", "opacity", "nodes": [VNode]},
             {"kind": "group",  "name", "visible", "opacity", "items": [...]},
             {"kind": "image",  "name", "visible", "opacity", "href", "corners"},
             {"kind": "text",   "name", "visible", "text", "x", "y", "size", "family",
                                "bold", "italic", "rgba"}]
    du bas vers le haut, coordonnées en pixels de l'image (base : viewBox →
    pixels)."""

    def __init__(self, root, base=None, name="SVG", hidden_layers=True, texts=True):
        self.root = root
        self.base = base
        self.doc_name = name
        self.hidden_layers = hidden_layers
        self.texts = texts
        self.ids = {}
        for el in root.iter():
            i = el.get("id")
            if i and i not in self.ids:
                self.ids[i] = el
        self.css = self._read_css()
        vb = _num_list(root.get("viewBox"))
        if len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
            self.vw, self.vh = vb[2], vb[3]
        else:
            self.vw = parse_length(root.get("width"), 100.0, 100.0) or 100.0
            self.vh = parse_length(root.get("height"), 100.0, 100.0) or 100.0
        self.vd = math.sqrt((self.vw ** 2 + self.vh ** 2) / 2.0)
        self.stats = {"objects": 0, "groups": 0, "clips": 0, "gradients": 0, "gradients_approx": 0,
                      "patterns": 0, "patterns_approx": 0, "masks": 0, "masks_clip": 0, "filters": 0, "images": 0, "texts": 0,
                      "lost_clips": 0, "markers": 0, "unknown": {}}
        self._use_depth = 0

    # ── CSS ──
    def _read_css(self):
        rules = []
        order = 0
        for el in self.root.iter():
            if local(el.tag) != "style":
                continue
            txt = re.sub(r"/\*.*?\*/", "", "".join(el.itertext()), flags=re.S)
            for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", txt):
                decl = parse_style_attr(body)
                for s in sel.split(","):
                    s = s.strip()
                    m = re.fullmatch(r"(\*|[a-zA-Z][\w-]*)?((?:[.#][\w-]+)*)", s)
                    if not s or s.startswith("@") or not m:
                        continue
                    tag = m.group(1) if m.group(1) not in (None, "*") else None
                    parts = re.findall(r"([.#])([\w-]+)", m.group(2))
                    ids = [p for k, p in parts if k == "#"]
                    classes = [p for k, p in parts if k == "."]
                    spec = (len(ids), len(classes), 1 if tag else 0)
                    order += 1
                    rules.append((spec, order, tag, ids, classes, decl))
        rules.sort(key=lambda r: (r[0], r[1]))
        return rules

    def _own_style(self, el):
        d = {}
        for k in PROPS:
            v = el.get(k)
            if v is not None:
                d[k] = v.strip()
        if self.css:
            tag = local(el.tag)
            cls = set((el.get("class") or "").split())
            eid = el.get("id")
            for _, _, t, ids, classes, decl in self.css:
                if (t is None or t == tag) and all(i == eid for i in ids) and all(c in cls for c in classes):
                    d.update(decl)
        d.update(parse_style_attr(el.get("style")))
        return d

    def style(self, el, parent):
        own = self._own_style(el)
        st = {k: v for k, v in parent.items() if k in INHERITED}
        for k, v in own.items():
            if v == "inherit":
                if k in parent:
                    st[k] = parent[k]
                continue
            st[k] = v
        return st

    # ── références ──
    def ref(self, v):
        m = re.match(r"\s*url\(\s*['\"]?#([^)'\"]+)['\"]?\s*\)", v or "")
        if m:
            return self.ids.get(m.group(1))
        if v and v.startswith("#"):
            return self.ids.get(v[1:])
        return None

    def href(self, el):
        return el.get(XLINK_NS + "href") or el.get("href")

    # ── dégradés ──
    def _grad_attr(self, el, name, seen=None):
        seen = seen or set()
        while el is not None and id(el) not in seen:
            seen.add(id(el))
            if el.get(name) is not None:
                return el.get(name)
            el = self.ref(self.href(el) or "")
        return None

    def _grad_stops(self, el):
        seen = set()
        while el is not None and id(el) not in seen:
            seen.add(id(el))
            stops = [s for s in el if local(s.tag) == "stop"]
            if stops:
                out, last = [], 0.0
                for s in stops:
                    st = self.style(s, {})
                    off = max(last, max(0.0, min(1.0, parse_number(s.get("offset"), 0.0))))
                    last = off
                    rgba = parse_color(st.get("stop-color", "black"), st.get("color")) or (0, 0, 0, 0)
                    a = parse_number(st.get("stop-opacity"), 1.0)
                    out.append((off, (rgba[0], rgba[1], rgba[2], rgba[3] * a)))
                return out
            el = self.ref(self.href(el) or "")
        return []

    def gradient(self, el, subpaths, alpha):
        tag = local(el.tag)
        stops = self._grad_stops(el)
        if not stops:
            return None
        if len(stops) == 1:
            o, rgba = stops[0]
            return {"type": "color", "rgba": (rgba[0], rgba[1], rgba[2], rgba[3] * alpha)}
        obb = (self._grad_attr(el, "gradientUnits") or "objectBoundingBox") != "userSpaceOnUse"
        gt = svg_matrix(self._grad_attr(el, "gradientTransform")) or Matrix()
        if self._grad_attr(el, "spreadMethod") in ("reflect", "repeat"):
            self.stats["gradients_approx"] += 1

        def L(name, default, ref):
            v = self._grad_attr(el, name)
            if v is None:
                return default
            if obb:
                return parse_number(v, default)
            return parse_length(v, ref, default)

        to_units, _ = bbox_units(subpaths)
        t = gt if obb else gt.mul(to_units)
        self.stats["gradients"] += 1
        if tag == "linearGradient":
            coords = (L("x1", 0.0, self.vw), L("y1", 0.0, self.vh),
                      L("x2", 1.0 if obb else self.vw, self.vw), L("y2", 0.0, self.vh))
            p, _ = gradient_paint("linear", coords, stops, t, alpha)
        else:
            cx = L("cx", 0.5 if obb else self.vw / 2, self.vw)
            cy = L("cy", 0.5 if obb else self.vh / 2, self.vh)
            r = L("r", 0.5 if obb else self.vd / 2, self.vd)
            fx = L("fx", cx, self.vw)
            fy = L("fy", cy, self.vh)
            p, exact = gradient_paint("radial", (cx, cy, r, fx, fy), stops, t, alpha)
            if not exact:
                self.stats["gradients_approx"] += 1
        return p

    def paint(self, value, opacity, st, subpaths):
        v = (value or "").strip()
        if v.startswith("url("):
            target = self.ref(v)
            fallback = v[v.find(")") + 1:].strip()
            if target is not None and local(target.tag) in ("linearGradient", "radialGradient"):
                p = self.gradient(target, subpaths, opacity)
                if p:
                    return p
            elif target is not None and local(target.tag) == "pattern":
                # 3.28.2 : un motif devient la couleur moyenne de ses formes
                # (pondérée par leur aire), signalé comme approché
                avg = self.pattern_color(target)
                if avg is not None:
                    self.stats["patterns_approx"] += 1
                    return {"type": "color", "rgba": (avg[0], avg[1], avg[2], avg[3] * opacity)}
                self.stats["patterns"] += 1
                if not fallback:
                    return {"type": "color", "rgba": (0.5, 0.5, 0.5, opacity)}
            v = fallback
        rgba = parse_color(v, st.get("color"))
        if rgba is None:
            return {"type": "none"}
        return {"type": "color", "rgba": (rgba[0], rgba[1], rgba[2], rgba[3] * opacity)}

    def pattern_color(self, pat, depth=0):
        if pat is None or depth > 4:
            return None
        kids = [c for c in pat.iter() if c is not pat and isinstance(c.tag, str)]
        if not kids:
            h = self.href(pat)
            return self.pattern_color(self.ref(h), depth + 1) if h else None
        tot, acc = 0.0, [0.0, 0.0, 0.0, 0.0]
        for c in kids:
            if local(c.tag) not in SHAPES:
                continue
            st = self.style(c, {})
            rgba = parse_color(st.get("fill", "black"), st.get("color"))
            if rgba is None:
                continue
            b = bbox(self.geometry(c) or [])
            area = max(1e-6, (b[2] - b[0]) * (b[3] - b[1])) if b else 1.0
            for i in range(4):
                acc[i] += rgba[i] * area
            tot += area
        if tot <= 0:
            return None
        return tuple(v / tot for v in acc)

    # ── géométrie des formes ──
    def geometry(self, el):
        tag = local(el.tag)
        L = parse_length
        if tag == "path":
            return parse_d(el.get("d"))
        if tag == "rect":
            x, y = L(el.get("x"), self.vw), L(el.get("y"), self.vh)
            w, h = L(el.get("width"), self.vw), L(el.get("height"), self.vh)
            if w <= 0 or h <= 0:
                return []
            rx, ry = el.get("rx"), el.get("ry")
            rx = L(rx, self.vw) if rx not in (None, "auto") else None
            ry = L(ry, self.vh) if ry not in (None, "auto") else None
            if rx is None:
                rx = ry or 0.0
            if ry is None:
                ry = rx
            rx, ry = min(max(rx, 0.0), w / 2), min(max(ry, 0.0), h / 2)
            if rx <= 0 or ry <= 0:
                return parse_d("M%r %r H%r V%r H%r Z" % (x, y, x + w, y + h, x))
            return parse_d("M%r %r H%r A%r %r 0 0 1 %r %r V%r A%r %r 0 0 1 %r %r H%r "
                           "A%r %r 0 0 1 %r %r V%r A%r %r 0 0 1 %r %r Z"
                           % (x + rx, y, x + w - rx, rx, ry, x + w, y + ry, y + h - ry, rx, ry,
                              x + w - rx, y + h, x + rx, rx, ry, x, y + h - ry, y + ry, rx, ry,
                              x + rx, y))
        if tag in ("circle", "ellipse"):
            cx, cy = L(el.get("cx"), self.vw), L(el.get("cy"), self.vh)
            if tag == "circle":
                rx = ry = L(el.get("r"), self.vd)
            else:
                rx, ry = L(el.get("rx"), self.vw), L(el.get("ry"), self.vh)
            if rx <= 0 or ry <= 0:
                return []
            return ellipse_subpaths(cx, cy, rx, ry)
        if tag == "line":
            p1 = (L(el.get("x1"), self.vw), L(el.get("y1"), self.vh))
            p2 = (L(el.get("x2"), self.vw), L(el.get("y2"), self.vh))
            return [(False, [(p1, p1, p1), (p2, p2, p2)])]
        if tag in ("polyline", "polygon"):
            v = _num_list(el.get("points"))
            pts = [(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]
            if len(pts) < 2:
                return []
            return [(tag == "polygon", [(p, p, p) for p in pts])]
        return []

    def stroke(self, st, subpaths, el):
        op = max(0.0, min(1.0, parse_number(st.get("stroke-opacity"), 1.0)))
        p = self.paint(st.get("stroke", "none"), 1.0, st, subpaths)
        width = parse_length(st.get("stroke-width"), self.vd, 1.0)
        if p["type"] == "none" or width <= 0:
            return {"type": "none", "width": max(width, 0.0) or 1.0}
        if op < 1.0:
            p["opacity"] = op        # format 2 : opacité du contour
        p["width"] = width
        p["cap"] = st.get("stroke-linecap", "butt") if st.get("stroke-linecap") in ("butt", "round", "square") else "butt"
        p["join"] = {"miter": "miter", "miter-clip": "miter", "arcs": "round", "round": "round",
                     "bevel": "bevel"}.get(st.get("stroke-linejoin"), "miter")
        p["miter"] = parse_number(st.get("stroke-miterlimit"), 4.0)
        align = el.get(CHOP_NS + "stroke-align")
        p["align"] = align if align in ("inside", "outside") else "center"
        dash = st.get("stroke-dasharray")
        if dash and dash.strip() != "none":
            vals = [parse_length(v, self.vd) for v in re.split(r"[\s,]+", dash.strip()) if v]
            if vals and sum(vals) > 0 and all(v >= 0 for v in vals):
                if len(vals) % 2:
                    vals = vals * 2
                p["dash"] = [v / width for v in vals]
                p["dash_offset"] = parse_length(st.get("stroke-dashoffset"), self.vd, 0.0)
        self.arrows(p, st, subpaths)
        return p

    # ── marqueurs → pointes de flèche ──
    def arrows(self, p, st, subpaths):
        """marker-start / marker-end → arrow_start / arrow_end du contour p
        quand le marqueur est une pointe simple (triangle, flèche, rond,
        carré, barre) ; sinon ignoré et signalé (stats « markers »)."""
        for prop, key, idx in (("marker-start", "arrow_start", 0), ("marker-end", "arrow_end", -1)):
            v = st.get(prop) or st.get("marker")
            if v in (None, "", "none"):
                continue
            m = self.ref(v)
            shape = self.marker_shape(m, p.get("width", 1.0)) if m is not None else None
            # le modèle ne dessine les pointes qu'aux bouts ouverts
            if shape and subpaths and not subpaths[idx][0]:
                p[key] = shape[0]
                if abs(shape[1] - 1.0) > 1e-3 or "arrow_scale" in p:
                    p["arrow_scale"] = shape[1]
            else:
                self.stats["markers"] += 1
        v = st.get("marker-mid") or st.get("marker")
        if v not in (None, "", "none"):
            self.stats["markers"] += 1

    def marker_shape(self, m, width):
        """<marker> → (forme du modèle, échelle) ou None. Taille du modèle :
        longueur = largeur = 4 × épaisseur × échelle."""
        if local(m.tag) != "marker":
            return None
        shape = m.get(CHOP_NS + "arrow")
        if shape in ARROWS:
            return shape, max(0.1, min(20.0, parse_number(m.get(CHOP_NS + "arrow-scale"), 1.0)))
        kids = [c for c in m.iter() if c is not m and isinstance(c.tag, str) and local(c.tag) in SHAPES | {"use"}]
        if len(kids) != 1 or local(kids[0].tag) == "use":
            return None
        el = kids[0]
        tag = local(el.tag)
        # repère du contenu → unités du marqueur (viewBox), puis de l'objet
        mt = Matrix()
        cur = el
        while cur is not None and cur is not m:
            t = svg_matrix(cur.get("transform"))
            if t is not None:
                mt = mt.mul(t)
            cur = self._parent(cur, m)
        vb = _num_list(m.get("viewBox"))
        mw = parse_length(m.get("markerWidth"), 3.0, 3.0)
        mh = parse_length(m.get("markerHeight"), 3.0, 3.0)
        if len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
            k = min(mw / vb[2], mh / vb[3])
            mt = mt.mul(Matrix(k, 0, 0, k, 0, 0))
        if m.get("markerUnits", "strokeWidth") != "userSpaceOnUse":
            mt = mt.mul(Matrix(width, 0, 0, width, 0, 0))
        subs = self.geometry(el)
        if not subs or len(subs) != 1:
            return None
        closed, knots = subs[0]
        b = bbox(tf_subpaths(subs, mt))
        if not b:
            return None
        size = max(b[2] - b[0], b[3] - b[1])
        mst = self.style(el, self.style(m, {}))
        filled = mst.get("fill", "black") != "none"
        curved = any(k[0] != k[1] or k[2] != k[1] for k in knots)
        pts = [k[1] for k in knots]
        if closed and len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
            pts = pts[:-1]
        if tag in ("circle", "ellipse") or (curved and closed):
            shape = "circle"
        elif curved:
            return None
        elif tag == "rect" or (closed and len(pts) == 4 and _is_rect(pts)):
            w, h = b[2] - b[0], b[3] - b[1]
            shape = "bar" if min(w, h) < 0.4 * max(w, h) else "square"
        elif closed and len(pts) in (3, 4) and filled:
            shape = "triangle"        # triangle, ou « dard » (Arrow1 d'Inkscape)
        elif not closed and len(pts) == 3:
            shape = "arrow"
        elif not closed and len(pts) == 2:
            shape, size = "bar", max(b[2] - b[0], b[3] - b[1])
        else:
            return None
        scale = size / (4.0 * max(width, 0.5))
        return shape, max(0.1, min(20.0, round(scale, 3)))

    def _parent(self, el, top):
        for p in top.iter():
            for c in p:
                if c is el:
                    return p
        return None

    def common(self, n, el, st):
        n.transform = svg_matrix(el.get("transform"))
        n.opacity = max(0.0, min(1.0, parse_number(st.get("opacity"), 1.0)))
        n.mode = BLEND.get((st.get("mix-blend-mode") or "").strip(), "normal")
        if st.get("display") == "none" or st.get("visibility") in ("hidden", "collapse"):
            n.visible = False
        if el.get(SODI_NS + "insensitive") == "true":
            n.locked = True
        # 3.28.2 : un masque simple (formes blanches opaques) devient un
        # masque d'écrêtage dans convert() ; les autres restent signalés
        if st.get("mask") not in (None, "none") and not self.simple_mask(self.ref(st.get("mask"))):
            self.stats["masks"] += 1
        if st.get("filter") not in (None, "none"):
            self.stats["filters"] += 1

    # ── éléments → objets ──
    def convert(self, el, parent_st):
        """Un élément de dessin (forme, <g> sans texte ni image, <use>) →
        VNode ou None."""
        tag = local(el.tag)
        st = self.style(el, parent_st)
        if tag in SHAPES:
            subs = self.geometry(el)
            if not subs:
                return None
            n = VNode("path", element_name(el))
            fill_op = max(0.0, min(1.0, parse_number(st.get("fill-opacity"), 1.0)))
            n.fill = self.paint(st.get("fill", "black"), 1.0, st, subs)
            if fill_op < 1.0 and n.fill["type"] != "none":
                n.fill["opacity"] = fill_op     # format 2 : opacité du fond
            n.stroke = self.stroke(st, subs, el)
            n.nonzero = st.get("fill-rule", "nonzero") != "evenodd"
            n.subpaths = subs
            self.common(n, el, st)
            self.stats["objects"] += 1
        elif tag == "g" and el.get(CHOP_NS + "aspect") == "1" and self._aspect_ok(el):
            n = self.aspect(el, st)
            if n is None:
                return None
            self.common(n, el, st)
            self.stats["objects"] += 1
        elif tag in GROUPS:
            kids = [c for c in el if isinstance(c.tag, str) and local(c.tag) not in SKIP]
            if tag == "switch":
                kids = kids[:1]
            # <g style="display:none"> autour d'un seul objet (export des
            # calques masqués) : l'objet, masqué
            if tag == "g" and len(kids) == 1 and not (el.get("id") or el.get(INK_NS + "label") or
                                                     el.get("transform") or el.get("class") or
                                                     st.get("clip-path") not in (None, "none") or
                                                     st.get("opacity") not in (None, "1")):
                n = self.convert(kids[0], st)
                if n is not None and (st.get("display") == "none" or st.get("visibility") == "hidden"):
                    n.visible = False
                return n
            n = VNode("group", element_name(el))
            for c in kids:
                cn = self.convert(c, st)
                if cn is not None:
                    n.children.append(cn)
            if not n.children:
                return None
            self.common(n, el, st)
            self.stats["groups"] += 1
        elif tag == "use":
            target = self.ref(self.href(el) or "")
            if target is None or self._use_depth > 8:
                return None
            self._use_depth += 1
            try:
                n = VNode("group", element_name(el))
                if local(target.tag) == "symbol":
                    # 3.28.1 : occurrence d'un symbole ChopGimp (vérifiée à l'import)
                    n.symbol = "svg-" + (target.get("id") or "symbole")
                    for c in target:
                        if isinstance(c.tag, str) and local(c.tag) not in SKIP:
                            cn = self.convert(c, st)
                            if cn is not None:
                                n.children.append(cn)
                else:
                    cn = self.convert(target, st)
                    if cn is not None:
                        n.children.append(cn)
            finally:
                self._use_depth -= 1
            if not n.children:
                return None
            self.common(n, el, st)
            x, y = parse_length(el.get("x"), self.vw), parse_length(el.get("y"), self.vh)
            if x or y:
                n.transform = compose(Matrix(1, 0, 0, 1, x, y), n.transform)
            self.stats["groups"] += 1
        else:
            if tag not in SKIP and tag not in ("text", "image"):
                self.stats["unknown"][tag] = self.stats["unknown"].get(tag, 0) + 1
            return None
        clip = st.get("clip-path")
        if clip not in (None, "none"):
            n = self.apply_clip(n, self.ref(clip))
        mask = st.get("mask")
        if mask not in (None, "none"):
            mel = self.ref(mask)
            if self.simple_mask(mel):
                self.stats["masks_clip"] += 1
                n = self.apply_clip(n, mel, mask=True)
        return n

    def simple_mask(self, mel):
        """3.28.2 : <mask> fait seulement de formes blanches (ou presque),
        opaques, sans dégradé ni image : équivaut à une découpe."""
        if mel is None or local(mel.tag) != "mask":
            return False
        if mel.get("maskContentUnits") == "objectBoundingBox":
            return False
        found = False
        for c in mel.iter():
            if c is mel or not isinstance(c.tag, str):
                continue
            tag = local(c.tag)
            if tag in ("g", "use"):
                continue
            if tag not in SHAPES:
                return False
            st = self.style(c, {})
            rgba = parse_color(st.get("fill", "black"), st.get("color"))
            if rgba is None or min(rgba[:3]) < 0.9 or rgba[3] < 0.99:
                return False
            if parse_number(st.get("fill-opacity"), 1.0) < 0.99 or \
               parse_number(st.get("opacity"), 1.0) < 0.99:
                return False
            if st.get("stroke") not in (None, "none"):
                return False
            found = True
        return found

    def _aspect_ok(self, el):
        kids = [c for c in el if isinstance(c.tag, str) and local(c.tag) not in SKIP]
        return bool(kids) and all(local(c.tag) == "path" for c in kids)

    def aspect(self, el, st):
        """<g chopgimp:aspect="1"> (export de ChopGimp) : un <path> par fond
        / contour d'un même objet → un objet avec sa pile « Aspect »."""
        kids = [c for c in el if isinstance(c.tag, str) and local(c.tag) not in SKIP]
        if not kids or any(local(c.tag) != "path" for c in kids):
            return None
        n = VNode("path", element_name(el))
        entries, d = [], None
        for c in kids:
            cst = self.style(c, st)
            mode = BLEND.get((cst.get("mix-blend-mode") or "").strip(), "normal")
            hidden = cst.get("display") == "none"
            if c.get(CHOP_NS + "arrows") == "1":
                # pointes d'un contour à profil : marqueurs du tracé lui-même
                d = d or c.get("d")
                if entries and entries[-1]["kind"] == "stroke":
                    self.arrows(entries[-1], cst, parse_d(c.get("d")))
                continue
            if c.get(CHOP_NS + "profile"):
                # contour à profil exporté en contour plein
                src = c.get(CHOP_NS + "d") or ""
                d = d or src
                subs = parse_d(src)
                p = self.paint(cst.get("fill", "black"), 1.0, cst, subs)
                if p["type"] == "none":
                    continue
                op = max(0.0, min(1.0, parse_number(cst.get("fill-opacity"), 1.0)))
                p.update(kind="stroke", width=parse_number(c.get(CHOP_NS + "stroke-width"), 1.0),
                         cap="butt", join="miter", miter=4.0, align="center",
                         profile=c.get(CHOP_NS + "profile"))
                group = [p]
            else:
                d = d or c.get("d")
                subs = parse_d(c.get("d"))
                group = []
                fill_op = max(0.0, min(1.0, parse_number(cst.get("fill-opacity"), 1.0)))
                f = self.paint(cst.get("fill", "black"), 1.0, cst, subs)
                if f["type"] != "none":
                    if fill_op < 1.0:
                        f["opacity"] = fill_op
                    f["kind"] = "fill"
                    group.append(f)
                s_ = self.stroke(cst, subs, c)
                if s_["type"] != "none":
                    s_["kind"] = "stroke"
                    group.append(s_)
                op = None
            for p in group:
                if op is not None and op < 1.0:
                    p["opacity"] = op
                if mode != "normal":
                    p["mode"] = mode
                if hidden:
                    p["visible"] = False
                entries.append(p)
        subs = parse_d(d) if d else []
        if not subs:
            return None
        n.subpaths = subs
        n.nonzero = self.style(kids[0], st).get("fill-rule", "nonzero") != "evenodd"
        fills = [e for e in entries if e["kind"] == "fill"]
        strokes = [e for e in entries if e["kind"] == "stroke"]
        n.fill = {k: v for k, v in fills[0].items() if k != "kind"} if fills else {"type": "none"}
        n.stroke = {k: v for k, v in strokes[-1].items() if k != "kind"} if strokes else {"type": "none"}
        n.entries = entries
        return n

    def clip_shape(self, cp, target):
        """<clipPath> → un objet (tous ses tracés), dans l'espace de l'élément."""
        cst = self.style(cp, {})
        m = svg_matrix(cp.get("transform"))
        if cp.get("clipPathUnits") == "objectBoundingBox":
            b = local_bbox(target)
            if b:
                m = compose(m, Matrix(b[2] - b[0], 0, 0, b[3] - b[1], b[0], b[1]))
        subs, nonzero, names = [], True, []
        for c in cp.iter():
            if c is cp or not isinstance(c.tag, str):
                continue
            tag = local(c.tag)
            el = c
            cm = svg_matrix(c.get("transform"))
            if tag == "use":
                el = self.ref(self.href(c) or "")
                if el is None:
                    continue
                tag = local(el.tag)
                x, y = parse_length(c.get("x"), self.vw), parse_length(c.get("y"), self.vh)
                cm = compose(compose(svg_matrix(el.get("transform")), Matrix(1, 0, 0, 1, x, y)), cm)
            if tag not in SHAPES:
                continue
            st = self.style(el, cst)
            if st.get("display") == "none":
                continue
            nonzero = st.get("clip-rule", "nonzero") != "evenodd"
            subs += tf_subpaths(self.geometry(el), compose(cm, m))
            names.append(element_name(el, ""))
        if not subs:
            return None
        name = names[0] if len(names) == 1 and names[0] else element_name(cp, "Découpe")
        return path_node(name, subs, {"type": "color", "rgba": (0.0, 0.0, 0.0, 1.0)}, None, nonzero)

    def apply_clip(self, n, cp, mask=False):
        if cp is None or local(cp.tag) != ("mask" if mask else "clipPath"):
            return n
        shape = self.clip_shape(cp, n)
        if shape is None:
            return n
        if not mask:
            self.stats["clips"] += 1
        if n.kind == "group" and not n.clip:
            n.clip = True
            n.children.append(shape)
            return n
        # un tracé (ou un groupe déjà découpé) : groupe « masque d'écrêtage »
        # qui prend sa transformation, son opacité et son mode
        g = VNode("group", "Masque d'écrêtage")
        g.transform, n.transform = n.transform, None
        g.opacity, n.opacity = n.opacity, 1.0
        g.mode, n.mode = n.mode, "normal"
        g.visible, n.visible = n.visible, True
        g.clip = True
        g.children = [n, shape]
        return g

    # ── plan ──
    def _has_complex(self, el):
        for c in el.iter():
            if c is el or not isinstance(c.tag, str):
                continue
            t = local(c.tag)
            if (t == "text" and self.texts) or t == "image" or is_layer(c):
                return True
        return False

    def plan(self):
        items, pure = self.container(self.root, self.base, {}, self.doc_name)
        if pure:
            items[0]["name"] = self.doc_name
        return items

    def container(self, el, m, st, name):
        """→ (éléments du plan, pur : une seule suite d'objets)."""
        items, run, breaks = [], [], False

        def flush():
            if not run:
                return
            nodes = []
            for c in run:
                n = self.convert(c, st)
                if n is not None:
                    n.transform = compose(n.transform, m)
                    nodes.append(n)
            if nodes:
                if len(run) == 1:
                    vname = element_name(run[0])
                else:
                    vname = name
                items.append({"kind": "vector", "name": vname, "visible": True, "opacity": 1.0,
                              "nodes": nodes})
            del run[:]

        for c in el:
            if not isinstance(c.tag, str):
                continue
            tag = local(c.tag)
            if tag in SKIP:
                continue
            if is_layer(c) or (tag in GROUPS and self._has_complex(c)):
                flush()
                breaks = True
                cst = self.style(c, st)
                visible = cst.get("display") != "none" and cst.get("visibility") != "hidden"
                if not visible and not self.hidden_layers:
                    continue
                if cst.get("clip-path") not in (None, "none") or cst.get("mask") not in (None, "none"):
                    self.stats["lost_clips"] += 1
                cm = compose(svg_matrix(c.get("transform")), m)
                cname = element_name(c)
                kids, pure = self.container(c, cm, cst, cname)
                if not kids:
                    continue
                opacity = max(0.0, min(1.0, parse_number(cst.get("opacity"), 1.0)))
                if pure:
                    kids[0].update(name=cname, visible=visible, opacity=opacity)
                    items.append(kids[0])
                else:
                    items.append({"kind": "group", "name": cname, "visible": visible,
                                  "opacity": opacity, "items": kids})
            elif tag == "image":
                flush()
                breaks = True
                it = self.image(c, st, m)
                if it:
                    items.append(it)
            elif tag == "text":
                flush()
                breaks = True
                if self.texts:
                    items += self.text(c, st, m)
            else:
                run.append(c)
        flush()
        return items, (not breaks and len(items) == 1)

    def image(self, el, st, m):
        cst = self.style(el, st)
        if cst.get("display") == "none":
            return None
        href = self.href(el)
        if not href:
            return None
        x, y = parse_length(el.get("x"), self.vw), parse_length(el.get("y"), self.vh)
        w, h = parse_length(el.get("width"), self.vw), parse_length(el.get("height"), self.vh)
        self.stats["images"] += 1
        return {"kind": "image", "name": element_name(el, "Image"), "visible": True,
                "opacity": max(0.0, min(1.0, parse_number(cst.get("opacity"), 1.0))),
                "href": href, "rect": (x, y, w, h),
                "preserve": el.get("preserveAspectRatio") or "xMidYMid meet",
                "matrix": compose(svg_matrix(el.get("transform")), m) or Matrix()}

    def text(self, el, st, m):
        """Une ligne par <tspan> positionné, sinon le texte entier."""
        cst = self.style(el, st)
        if cst.get("display") == "none":
            return []
        tm = compose(svg_matrix(el.get("transform")), m) or Matrix()
        spans = [c for c in el if local(c.tag) == "tspan" and c.get("y") is not None]
        out = []
        for it in (spans or [el]):
            txt = "".join(it.itertext()).strip()
            if not txt:
                continue
            ist = self.style(it, cst) if it is not el else cst
            x = parse_length((it.get("x") or el.get("x") or "0").split()[0], self.vw)
            y = parse_length((it.get("y") or el.get("y") or "0").split()[0], self.vh)
            px, py = tm.apply(x, y)
            size = parse_length(ist.get("font-size"), 16.0, 16.0) * tm.scale_factor()
            fw = ist.get("font-weight", "")
            rgba = parse_color(ist.get("fill", "black"), ist.get("color")) or (0.0, 0.0, 0.0, 1.0)
            self.stats["texts"] += 1
            out.append({"kind": "text", "name": txt[:40], "visible": True, "text": txt,
                        "x": px, "y": py, "size": size,
                        "family": (ist.get("font-family") or "Sans").split(",")[0].strip("'\" "),
                        "bold": fw in ("bold", "bolder", "600", "700", "800", "900"),
                        "italic": ist.get("font-style") in ("italic", "oblique"), "rgba": rgba})
        return out


def svg_base_matrix(root, w0, h0, zoom=1.0):
    """viewBox (preserveAspectRatio) → pixels du rendu (w0 × h0), puis zoom."""
    vb = _num_list(root.get("viewBox"))
    if len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
        sx, sy = w0 / vb[2], h0 / vb[3]
        par = (root.get("preserveAspectRatio") or "xMidYMid meet").split()
        tx = ty = 0.0
        if par and par[0] != "none":
            s = max(sx, sy) if len(par) > 1 and par[1] == "slice" else min(sx, sy)
            al = par[0]
            dx, dy = w0 - vb[2] * s, h0 - vb[3] * s
            tx = dx / 2 if "xMid" in al else (dx if "xMax" in al else 0.0)
            ty = dy / 2 if "YMid" in al else (dy if "YMax" in al else 0.0)
            sx = sy = s
        base = Matrix(sx, 0, 0, sy, tx - vb[0] * sx, ty - vb[1] * sy)
    else:
        # sans viewBox : unités utilisateur = px à 96 ppp
        wl = parse_length(root.get("width"), 0.0, 0.0)
        k = (w0 / wl) if wl > 0 else 1.0
        base = Matrix(k, 0, 0, k, 0, 0)
    if zoom != 1.0:
        base = base.mul(Matrix(zoom, 0, 0, zoom, 0, 0))
    return base


def image_corners(item):
    """Coins (haut-gauche, haut-droit, bas-droit, bas-gauche) d'une image du
    plan de taille iw × ih (preserveAspectRatio)."""
    def corners(iw, ih):
        x, y, w, h = item["rect"]
        if w <= 0 or h <= 0:
            w, h = float(iw), float(ih)
        par = item["preserve"].split()
        if par and par[0] != "none" and iw > 0 and ih > 0:
            s = (max if len(par) > 1 and par[1] == "slice" else min)(w / iw, h / ih)
            nw, nh = iw * s, ih * s
            al = par[0]
            x += (w - nw) / 2 if "xMid" in al else ((w - nw) if "xMax" in al else 0.0)
            y += (h - nh) / 2 if "YMid" in al else ((h - nh) if "YMax" in al else 0.0)
            w, h = nw, nh
        m = item["matrix"]
        return [m.apply(px, py) for px, py in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))]
    return corners


def image_bytes(href, base_dir):
    """Contenu d'une image (data: ou fichier) → octets, ou None."""
    if href.startswith("data:"):
        head, _, data = href.partition(",")
        try:
            return base64.b64decode(data) if ";base64" in head else data.encode("latin-1")
        except Exception:
            return None
    path = href
    if path.startswith("file://"):
        path = path[7:]
    if not os.path.isabs(path):
        path = os.path.join(base_dir or ".", path)
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def count_plan(items):
    n = 0
    for it in items:
        if it["kind"] == "vector":
            n += sum(x.count() for x in it["nodes"])
        elif it["kind"] == "group":
            n += count_plan(it["items"])
        else:
            n += 1
    return n


# ─── PDF / AI / EPS : objets de cairoscript ─────────────────────────────

def _cairo_paint(o_fill, gradient, subpaths, stats):
    if gradient is not None and getattr(gradient, "coords", None) and len(gradient.stops) >= 2:
        to_units, _ = bbox_units(subpaths)
        t = gradient.matrix.invert().mul(to_units)
        stops = [(s[0], tuple(s[1:5])) for s in gradient.stops]
        if gradient.kind == "linear":
            p, _ = gradient_paint("linear", gradient.coords, stops, t)
        else:
            cx0, cy0, r0, cx1, cy1, r1 = gradient.coords
            p, exact = gradient_paint("radial", (cx1, cy1, r1, cx0, cy0), stops, t)
            if not exact or r0 > 1e-9:
                stats["gradients_approx"] = stats.get("gradients_approx", 0) + 1
        stats["gradients_vector"] = stats.get("gradients_vector", 0) + 1
        return p
    if o_fill is None:
        return {"type": "none"}
    return {"type": "color", "rgba": tuple(o_fill[:4])}


def _color_name(rgba):
    return "#%02x%02x%02x" % tuple(int(round(max(0, min(1, v)) * 255)) for v in rgba[:3])


def cairo_node(o, n, stats):
    """Un objet « path » de cairoscript → VNode (coordonnées de l'image)."""
    what = []
    fill = _cairo_paint(o.fill, getattr(o, "gradient", None), o.path, stats)
    if fill["type"] == "color":
        what.append("fond " + _color_name(fill["rgba"]))
    elif fill["type"] != "none":
        what.append("dégradé")
    stroke = {"type": "none", "width": 1.0}
    st = o.stroke
    if st:
        stroke = _cairo_paint(st["color"], st.get("gradient"), o.path, stats)
        width = max(0.01, st["width"])
        stroke.update(width=width, cap=st["cap"], join=st["join"], miter=st.get("miter", 10.0),
                      align="center")
        if st["dash"]:
            stroke["dash"] = [v / width for v in st["dash"]]
            stroke["dash_offset"] = st.get("dash_offset", 0.0)
        what.append("contour " + _color_name(st["color"]))
    node = path_node(("Forme %d — " % n) + ", ".join(what) if what else "Forme %d" % n,
                     o.path, fill, stroke, getattr(o, "fill_rule", "nonzero") != "evenodd")
    return node


def pdf_nodes(objs, stats, start=1):
    """Objets « path » consécutifs de cairoscript → arbre d'objets ; les
    découpes successives (o.clips : ((clé, sous-chemins, nonzero), …))
    deviennent des groupes « masque d'écrêtage » imbriqués."""
    root = []
    stack = []        # [(clé, VNode groupe, forme de découpe)]
    n = start - 1

    def close_to(k):
        while len(stack) > k:
            key, g, shape = stack.pop()
            g.children.append(shape)
            (stack[-1][1].children if stack else root).append(g)

    for o in objs:
        if o.kind != "path":
            continue
        chain = getattr(o, "clips", ()) or ()
        k = 0
        while k < len(stack) and k < len(chain) and stack[k][0] == chain[k][0]:
            k += 1
        close_to(k)
        for key, subs, nonzero in chain[k:]:
            g = VNode("group", "Masque d'écrêtage")
            g.clip = True
            stats["clips_vector"] = stats.get("clips_vector", 0) + 1
            shape = path_node("Découpe", subs, {"type": "color", "rgba": (0.0, 0.0, 0.0, 1.0)}, None, nonzero)
            stack.append((key, g, shape))
        n += 1
        (stack[-1][1].children if stack else root).append(cairo_node(o, n, stats))
    close_to(0)
    return root


def collect_symbols(items):
    """3.28.1 : les occurrences <use> d'un <symbol> du plan d'import →
    {id: (nom, xml des objets)} quand toutes les occurrences d'un symbole ont
    les mêmes objets (sinon ce ne sont plus des occurrences : style hérité
    différent). Les marques des autres sont retirées."""
    found = {}

    def walk(nodes):
        for n in nodes:
            if n.kind != "group":
                continue
            if getattr(n, "symbol", None):
                found.setdefault(n.symbol, []).append(n)
            walk(n.children)

    def walk_items(its):
        for it in its:
            if it.get("kind") == "vector":
                walk(it["nodes"])
            elif it.get("kind") == "group":
                walk_items(it["items"])

    walk_items(items)
    defs = {}
    for sid, occ in found.items():
        texts = set(re.sub(r' id="[0-9]+"', "", to_xml(o.children)) for o in occ)
        if len(texts) == 1:
            defs[sid] = (sid[4:] if sid.startswith("svg-") else sid, texts.pop())
        else:
            for o in occ:
                o.symbol = None
    return defs


def symbols_parasite_text(old_text, defs):
    """Ajoute les définitions au texte du parasite « chopgimp-symbols »."""
    body = "".join('<symbol id=%s name=%s><![CDATA[%s]]></symbol>\n'
                   % (quoteattr(_clean(sid)), quoteattr(_clean(name)), xml)
                   for sid, (name, xml) in defs.items()
                   if not old_text or ('id="%s"' % sid) not in old_text)
    if old_text and "</chopgimp-symbols>" in old_text:
        return old_text.replace("</chopgimp-symbols>", body + "</chopgimp-symbols>")
    return '<chopgimp-symbols version="1">\n' + body + "</chopgimp-symbols>\n"

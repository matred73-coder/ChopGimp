#!/usr/bin/env python3
"""
PhotoGIMP Pro v2 — générateur du jeu d'icônes « PS-Line ».

Icônes ORIGINALES (dessinées ici, aucune ressource Adobe) dans l'esprit
des outils Photoshop 2024 : pictogrammes fins, monochromes, grille 16 px.

Contrainte GTK3 : les icônes « -symbolic » sont recolorées en forçant
`fill` sur tous les <path>/<rect>/<circle>. Aucun trait (stroke) n'est donc
utilisé : chaque ligne est convertie en polygone plein (voir helpers).

Sortie : icons/PS-Line/overlay/scalable/apps/<nom>.svg et <nom>-symbolic.svg
L'installeur copie le thème Default de GIMP puis applique cette surcouche.
"""
import math
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "PS-Line", "overlay", "scalable", "apps")
FG = "#bebebe"          # couleur de référence des icônes symboliques GIMP
W = 1.2                 # épaisseur de trait standard


# ─── Primitives (toutes en formes pleines) ──────────────────────────────
def f(v):
    return ("%.3f" % v).rstrip("0").rstrip(".")


def pts(points):
    return " ".join("%s,%s" % (f(x), f(y)) for x, y in points)


def polygon(points, op=None):
    o = ' opacity="%s"' % op if op is not None else ""
    return '<path d="M%sZ"%s/>' % (" L".join("%s,%s" % (f(x), f(y)) for x, y in points), o)


def circle(cx, cy, r, op=None):
    o = ' opacity="%s"' % op if op is not None else ""
    return '<circle cx="%s" cy="%s" r="%s"%s/>' % (f(cx), f(cy), f(r), o)


def rect(x, y, w, h, rx=0, op=None):
    o = ' opacity="%s"' % op if op is not None else ""
    r = ' rx="%s"' % f(rx) if rx else ""
    return '<rect x="%s" y="%s" width="%s" height="%s"%s%s/>' % (f(x), f(y), f(w), f(h), r, o)


def line(x1, y1, x2, y2, w=W, caps=True, op=None):
    """Segment épais = quadrilatère (+ bouts ronds)."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    s = polygon([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
                 (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)], op)
    if caps:
        s += circle(x1, y1, w / 2, op) + circle(x2, y2, w / 2, op)
    return s


def polyline(points, w=W, closed=False, op=None):
    p = list(points)
    if closed:
        p.append(p[0])
    s = ""
    for a, b in zip(p, p[1:]):
        s += line(a[0], a[1], b[0], b[1], w, caps=False, op=op)
    for x, y in p:
        s += circle(x, y, w / 2, op)
    return s


def rect_outline(x, y, w, h, t=W, op=None):
    o = ' opacity="%s"' % op if op is not None else ""
    return ('<path fill-rule="evenodd" d="M%s,%sh%sv%sh%sZ M%s,%sv%sh%sv%sZ"%s/>'
            % (f(x), f(y), f(w), f(h), f(-w),
               f(x + t), f(y + t), f(h - 2 * t), f(w - 2 * t), f(-(h - 2 * t)), o))


def ring(cx, cy, r, t=W, op=None):
    o = ' opacity="%s"' % op if op is not None else ""
    ri = r - t
    return ('<path fill-rule="evenodd" d="M%s,%s a%s,%s 0 1,0 %s,0 a%s,%s 0 1,0 %s,0Z '
            'M%s,%s a%s,%s 0 1,0 %s,0 a%s,%s 0 1,0 %s,0Z"%s/>'
            % (f(cx - r), f(cy), f(r), f(r), f(2 * r), f(r), f(r), f(-2 * r),
               f(cx - ri), f(cy), f(ri), f(ri), f(2 * ri), f(ri), f(ri), f(-2 * ri), o))


def arc(cx, cy, r, a0, a1, w=W, n=24, op=None):
    """Arc épais approché par une polyligne (angles en degrés, 0 = droite, sens horaire)."""
    p = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        p.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return polyline(p, w, op=op)


def dashed_rect(x, y, w, h, t=1.1, dash=2.0, gap=1.4):
    s = ""
    for (x1, y1, x2, y2) in [(x, y, x + w, y), (x + w, y, x + w, y + h),
                             (x + w, y + h, x, y + h), (x, y + h, x, y)]:
        L = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        d = 0
        while d < L:
            e = min(d + dash, L)
            ax, ay = x1 + ux * d, y1 + uy * d
            bx, by = x1 + ux * e, y1 + uy * e
            rx, ry = min(ax, bx) - (t / 2 if uy else 0), min(ay, by) - (t / 2 if ux else 0)
            rw = abs(bx - ax) if ux else t
            rh = abs(by - ay) if uy else t
            s += rect(rx, ry, max(rw, t) if not ux else rw, max(rh, t) if not uy else rh)
            d = e + gap
    return s


def dashed_ellipse(cx, cy, rx, ry, n=12, t=1.2, frac=0.55):
    s = ""
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + 2 * math.pi / n * frac
        p = [(cx + rx * math.cos(a0 + (a1 - a0) * k / 4), cy + ry * math.sin(a0 + (a1 - a0) * k / 4))
             for k in range(5)]
        s += polyline(p, t)
    return s


def rotate(points, cx, cy, deg):
    a = math.radians(deg)
    c, s_ = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s_, cy + (x - cx) * s_ + (y - cy) * c) for x, y in points]


def rrect_poly(x, y, w, h, deg, cx, cy):
    return rotate([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], cx, cy, deg)


def star4(cx, cy, r, k=0.28):
    p = []
    for i in range(8):
        a = math.radians(-90 + i * 45)
        rr = r if i % 2 == 0 else r * k
        p.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return polygon(p)


def arrow_head(x, y, deg, size=2.6):
    """Pointe de flèche pleine dirigée selon deg, sommet en (x, y)."""
    base = [(0, 0), (-size, -size * 0.75), (-size, size * 0.75)]
    return polygon([(x + px, y + py) for px, py in rotate(base, 0, 0, deg)])


# ─── Pictogrammes réutilisables ─────────────────────────────────────────
def cursor_arrow(x, y, s=1.0):
    """Flèche de pointeur (contour plein)."""
    p = [(0, 0), (0, 10.5), (2.6, 8.1), (4.4, 12.2), (6.0, 11.5), (4.3, 7.5), (7.8, 7.5)]
    outer = [(x + a * s, y + b * s) for a, b in p]
    return polygon(outer)


def brush(cx, cy, deg=45, scale=1.0):
    """Pinceau : manche fin, virole, touffe en goutte. Dessiné vertical puis tourné."""
    s = scale
    parts = []
    handle = [(-0.8 * s, -7.5 * s), (0.8 * s, -7.5 * s), (0.6 * s, -1.6 * s), (-0.6 * s, -1.6 * s)]
    ferrule = [(-1.3 * s, -1.6 * s), (1.3 * s, -1.6 * s), (1.3 * s, 0.4 * s), (-1.3 * s, 0.4 * s)]
    tuft = [(-1.6 * s, 0.6 * s), (1.6 * s, 0.6 * s), (1.5 * s, 3.2 * s), (0.4 * s, 6.6 * s),
            (-0.6 * s, 6.0 * s), (-1.5 * s, 3.2 * s)]
    for shape in (handle, ferrule, tuft):
        parts.append(polygon([(cx + x, cy + y) for x, y in rotate(shape, 0, 0, deg)]))
    return "".join(parts)


def svg(body, name):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!-- PhotoGIMP Pro v2 — PS-Line — %s — icône originale -->\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            '<g fill="%s">%s</g></svg>\n' % (name, FG, body))


# ─── Icônes ─────────────────────────────────────────────────────────────
ICONS = {}


def icon(name):
    def deco(fn):
        ICONS[name] = fn
        return fn
    return deco


@icon("gimp-tool-move")
def _move():
    # Pointeur + croix fléchée (outil Déplacement)
    s = cursor_arrow(1.5, 1.0, 0.95)
    cx, cy = 11.5, 11.5
    s += line(cx - 3.2, cy, cx + 3.2, cy, 1.0) + line(cx, cy - 3.2, cx, cy + 3.2, 1.0)
    s += arrow_head(cx + 4.2, cy, 0, 1.6) + arrow_head(cx - 4.2, cy, 180, 1.6)
    s += arrow_head(cx, cy + 4.2, 90, 1.6) + arrow_head(cx, cy - 4.2, -90, 1.6)
    return s


@icon("gimp-tool-rect-select")
def _rect_select():
    return dashed_rect(2, 3, 12, 10, 1.2, 2.2, 1.4)


@icon("gimp-tool-ellipse-select")
def _ellipse_select():
    return dashed_ellipse(8, 8, 6.2, 5.2, 12, 1.2)


@icon("gimp-tool-free-select")
def _lasso():
    # Boucle de lasso + queue
    p = []
    for i in range(0, 300, 12):
        a = math.radians(i - 200)
        p.append((8.3 + 5.8 * math.cos(a), 6.2 + 3.9 * math.sin(a)))
    s = polyline(p, W)
    # nœud + queue
    x0, y0 = p[-1]
    s += polyline([(x0, y0), (5.2, 9.6), (4.0, 11.4), (5.6, 13.2), (4.4, 15.0)], W)
    s += ring(5.6, 9.4, 1.4, 1.0)
    return s


@icon("gimp-tool-fuzzy-select")
def _wand():
    s = line(2.2, 13.8, 9.2, 6.8, 1.6)
    s += star4(11.4, 4.6, 3.6, 0.26)
    s += star4(5.2, 3.6, 1.6, 0.3) + star4(13.6, 10.4, 1.4, 0.3)
    return s


@icon("gimp-tool-by-color-select")
def _by_color():
    s = dashed_rect(1.5, 1.5, 9, 9, 1.1, 1.8, 1.3)
    s += rect(7, 7, 7.5, 7.5, 1.0)
    return s


@icon("gimp-tool-foreground-select")
def _quick_select():
    # « Sélection rapide » : pinceau + cercle pointillé
    s = dashed_ellipse(6.0, 6.0, 4.6, 4.6, 10, 1.1)
    s += brush(11.3, 11.3, -45, 0.62)
    return s


@icon("gimp-tool-paint-select")
def _paint_select():
    s = brush(6.5, 7.5, 45, 0.78)
    s += dashed_ellipse(11.0, 11.0, 3.6, 3.6, 8, 1.0)
    return s


@icon("gimp-tool-iscissors")
def _scissors():
    s = ring(4.2, 12.0, 2.3, 1.1) + ring(11.8, 12.0, 2.3, 1.1)
    s += line(5.8, 10.4, 11.2, 1.4, 1.3) + line(10.2, 10.4, 4.8, 1.4, 1.3)
    s += circle(8, 6.6, 0.8)
    return s


@icon("gimp-tool-crop")
def _crop():
    # Deux équerres croisées
    s = polyline([(4.2, 0.8), (4.2, 11.8), (15.2, 11.8)], 1.5)
    s += polyline([(0.8, 4.2), (11.8, 4.2), (11.8, 15.2)], 1.5)
    return s


@icon("gimp-tool-color-picker")
def _eyedropper():
    # Pipette : tube fin vers le bas-gauche, bague, poire en haut-droite
    tube = [(-0.9, -1.4), (0.9, -1.4), (0.9, 5.4), (0, 7.0), (-0.9, 5.4)]
    s = polygon([(7.0 + x, 9.0 + y) for x, y in rotate(tube, 0, 0, 45)])
    collar = [(-2.2, -3.0), (2.2, -3.0), (2.2, -1.5), (-2.2, -1.5)]
    s += polygon([(7.0 + x, 9.0 + y) for x, y in rotate(collar, 0, 0, 45)])
    s += circle(11.4, 4.6, 2.7)
    return s


@icon("gimp-tool-measure")
def _ruler():
    pts_ = rotate([(1, 6), (15, 6), (15, 10), (1, 10)], 8, 8, -45)
    s = ('<path fill-rule="evenodd" d="M%sZ M%sZ"/>'
         % (" L".join("%s,%s" % (f(x), f(y)) for x, y in pts_),
            " L".join("%s,%s" % (f(x), f(y)) for x, y in rotate([(2.1, 7.1), (13.9, 7.1), (13.9, 8.9), (2.1, 8.9)], 8, 8, -45))))
    for i, x in enumerate([3.5, 5.5, 7.5, 9.5, 11.5]):
        h = 2.0 if i % 2 == 0 else 1.2
        s += polygon(rotate([(x - 0.45, 7.1), (x + 0.45, 7.1), (x + 0.45, 7.1 + h), (x - 0.45, 7.1 + h)], 8, 8, -45))
    return s


@icon("gimp-tool-heal")
def _bandage():
    # Pansement en diagonale
    outer = rrect_poly(1.0, 5.0, 14.0, 6.0, -45, 8, 8)
    inner = rrect_poly(5.2, 5.0, 5.6, 6.0, -45, 8, 8)
    s = polygon(outer, 0.45) + polygon(inner)
    for dx, dy in [(-0.9, -0.9), (0.9, -0.9), (-0.9, 0.9), (0.9, 0.9)]:
        x, y = rotate([(8 + dx, 8 + dy)], 8, 8, -45)[0]
        s += circle(x, y, 0.45, 0.0)
    return s


@icon("gimp-tool-clone")
def _stamp():
    s = circle(8, 3.4, 2.6)
    s += polygon([(6.8, 5.6), (9.2, 5.6), (9.6, 9.0), (6.4, 9.0)])
    s += rect(2.2, 9.2, 11.6, 2.8, 0.8)
    s += rect(3.2, 13.0, 9.6, 1.4, 0.4)
    return s


@icon("gimp-tool-perspective-clone")
def _pstamp():
    s = circle(8, 3.4, 2.4)
    s += polygon([(6.9, 5.4), (9.1, 5.4), (9.5, 8.6), (6.5, 8.6)])
    s += polygon([(3.6, 8.8), (12.4, 8.8), (14.8, 12.0), (1.2, 12.0)])
    s += polygon([(1.0, 13.0), (15.0, 13.0), (15.6, 14.6), (0.4, 14.6)], 0.6)
    return s


@icon("gimp-tool-seamless-clone")
def _sclone():
    s = circle(6, 3.2, 2.2)
    s += polygon([(5.0, 5.0), (7.0, 5.0), (7.4, 7.8), (4.6, 7.8)])
    s += rect(1.2, 8.0, 9.6, 2.4, 0.7)
    s += dashed_rect(8.4, 8.4, 6.6, 6.6, 1.0, 1.6, 1.1)
    return s


@icon("gimp-tool-paintbrush")
def _paintbrush():
    return brush(8.6, 7.6, 45, 1.0)


@icon("gimp-tool-pencil")
def _pencil():
    body = [(-1.6, -7.0), (1.6, -7.0), (1.6, 3.2), (0, 6.8), (-1.6, 3.2)]
    s = polygon([(8 + x, 8 + y) for x, y in rotate(body, 0, 0, 45)])
    # gomme en tête (séparée par un liseré)
    cap = [(-1.6, -7.6), (1.6, -7.6), (1.6, -6.0), (-1.6, -6.0)]
    s += polygon([(8 + x, 8 + y) for x, y in rotate(cap, 0, 0, 45)], 0.55)
    return s


@icon("gimp-tool-airbrush")
def _airbrush():
    s = brush(9.6, 6.4, 45, 0.8)
    for (x, y, r) in [(2.4, 13.6, 0.7), (4.2, 12.2, 0.55), (2.0, 11.2, 0.5), (4.6, 14.6, 0.5),
                      (5.6, 10.6, 0.45), (1.2, 14.8, 0.4), (3.2, 9.8, 0.4)]:
        s += circle(x, y, r)
    return s


@icon("gimp-tool-ink")
def _pen_nib():
    return _path_shape(8, 8, 1.0)


@icon("gimp-tool-mypaint-brush")
def _mypaint():
    return brush(7.2, 8.8, 45, 0.85) + star4(12.6, 3.4, 2.8, 0.28)


@icon("gimp-tool-eraser")
def _eraser():
    outer = rrect_poly(2.0, 5.0, 12.0, 6.0, -45, 8, 8)
    half = rrect_poly(2.0, 5.0, 5.0, 6.0, -45, 8, 8)
    s = polygon(outer, 0.45) + polygon(half)
    s += rect(7.0, 14.2, 8.0, 1.1)
    return s


@icon("gimp-tool-bucket-fill")
def _bucket():
    body = rotate([(3.0, 4.0), (11.0, 4.0), (10.0, 13.0), (4.0, 13.0)], 7, 8.5, -35)
    s = polygon(body)
    s += arc(7.2, 5.0, 3.2, 180, 330, 1.1)
    # goutte
    s += polygon([(13.6, 8.6), (15.2, 12.0), (14.6, 13.4), (13.6, 13.8), (12.6, 13.4), (12.0, 12.0)])
    return s


@icon("gimp-tool-gradient")
def _gradient():
    s = ""
    n = 7
    for i in range(n):
        s += rect(1.5 + i * (13.0 / n), 3.0, 13.0 / n + 0.02, 10.0, op="%.2f" % (1.0 - i * 0.13))
    return s


@icon("gimp-tool-blur")
def _drop():
    p = [(8, 1.2)]
    for i in range(0, 181, 10):
        a = math.radians(i)
        p.append((8 + 4.8 * math.cos(a), 10.0 + 4.8 * math.sin(a)))
    p = [(8, 1.2), (12.8, 10.0)] + p[1:] + [(3.2, 10.0)]
    return polygon(p)


@icon("gimp-tool-smudge")
def _smudge():
    # Doigt stylisé (doigt tendu vers le bas-gauche)
    # Doigt arrondi en diagonale + traînée en arc
    s = line(14.2, 1.8, 7.0, 9.0, 3.6)
    s += polygon([(14.6, 0.6), (15.6, 1.6), (13.0, 4.2), (12.0, 3.2)], 0.0)
    s += arc(4.6, 9.0, 3.6, 70, 160, 1.0, 10)
    s += arc(4.6, 9.0, 6.0, 80, 135, 1.0, 10)
    return s


@icon("gimp-tool-dodge")
def _dodge():
    s = ring(10.0, 6.0, 4.4, 1.3)
    s += line(6.9, 9.1, 1.6, 14.4, 1.5)
    return s


def _path_shape(cx, cy, s):
    # Plume (outil Plume) : pointe vers le bas-gauche
    nib = [(0, -6.6), (3.6, -1.6), (2.4, 3.0), (-2.4, 3.0), (-3.6, -1.6)]
    nib = [(cx + x * s, cy + 0.6 + y * s) for x, y in nib]
    out = ('<path fill-rule="evenodd" d="M%sZ M%s,%s a%s,%s 0 1,0 %s,0 a%s,%s 0 1,0 %s,0Z"/>'
           % (" L".join("%s,%s" % (f(x), f(y)) for x, y in nib),
              f(cx - 1.0 * s), f(cy - 0.6), f(1.0 * s), f(1.0 * s), f(2.0 * s),
              f(1.0 * s), f(1.0 * s), f(-2.0 * s)))
    out += rect(cx - 2.6 * s, cy + 4.2 * s, 5.2 * s, 2.0 * s, 0.4)
    out += line(cx, cy - 5.6 * s, cx, cy - 1.8 * s, 0.6 * s, op="0")
    return out


@icon("gimp-tool-path")
def _pen():
    return "".join([_path_shape(8, 7.6, 1.05)])


@icon("gimp-tool-text")
def _text():
    s = polygon([(2.0, 2.0), (14.0, 2.0), (14.0, 5.2), (12.8, 5.2), (12.2, 3.6), (9.0, 3.6),
                 (9.0, 12.8), (10.8, 13.4), (10.8, 14.4), (5.2, 14.4), (5.2, 13.4), (7.0, 12.8),
                 (7.0, 3.6), (3.8, 3.6), (3.2, 5.2), (2.0, 5.2)])
    return s


@icon("gimp-tool-zoom")
def _zoom():
    s = ring(6.6, 6.6, 5.0, 1.4)
    s += line(10.3, 10.3, 14.4, 14.4, 2.0)
    return s


@icon("gimp-tool-align")
def _align():
    s = rect(1.5, 1.0, 1.3, 14.0)
    s += rect(4.0, 3.0, 10.5, 3.6, 0.6) + rect(4.0, 9.4, 6.5, 3.6, 0.6)
    return s


@icon("gimp-tool-offset")
def _offset():
    s = rect_outline(2.5, 2.5, 11, 11, 1.1)
    s += line(5.0, 8.0, 11.0, 8.0, 1.0) + arrow_head(12.0, 8.0, 0, 2.0)
    s += line(8.0, 5.0, 8.0, 11.0, 1.0) + arrow_head(8.0, 12.0, 90, 2.0)
    return s


@icon("gimp-tool-rotate")
def _rotate():
    s = arc(8, 8, 5.6, -160, 110, 1.4)
    s += arrow_head(8 + 5.6 * math.cos(math.radians(112)) - 0.2,
                    8 + 5.6 * math.sin(math.radians(112)) + 0.2, 200, 2.8)
    s += rect(6.2, 6.2, 3.6, 3.6, 0.6)
    return s


@icon("gimp-tool-scale")
def _scale():
    s = rect_outline(1.5, 1.5, 13, 13, 1.1)
    s += rect(1.5, 9.0, 5.5, 5.5)
    s += line(8.0, 8.0, 11.6, 4.4, 1.1) + arrow_head(12.4, 3.6, -45, 2.4)
    return s


@icon("gimp-tool-shear")
def _shear():
    s = polyline([(5.0, 3.0), (15.0, 3.0), (11.0, 13.0), (1.0, 13.0)], 1.2, closed=True)
    s += rect_outline(1.0, 3.0, 10.0, 10.0, 0.8, op="0.4")
    return s


@icon("gimp-tool-perspective")
def _perspective():
    s = polyline([(4.5, 3.0), (11.5, 3.0), (15.0, 13.0), (1.0, 13.0)], 1.2, closed=True)
    for x, y in [(4.5, 3.0), (11.5, 3.0), (15.0, 13.0), (1.0, 13.0)]:
        s += rect(x - 1.2, y - 1.2, 2.4, 2.4)
    return s


@icon("gimp-tool-flip")
def _flip():
    s = polygon([(7.0, 2.0), (7.0, 14.0), (1.0, 14.0)])
    s += polyline([(9.0, 2.0), (9.0, 14.0), (15.0, 14.0)], 1.1, closed=True)
    return s


@icon("gimp-tool-unified-transform")
def _unified():
    s = rect_outline(2.5, 2.5, 11, 11, 1.0)
    for x, y in [(2.5, 2.5), (13.5, 2.5), (2.5, 13.5), (13.5, 13.5), (8, 2.5), (8, 13.5), (2.5, 8), (13.5, 8)]:
        s += rect(x - 1.3, y - 1.3, 2.6, 2.6)
    s += circle(8, 8, 1.0)
    return s


@icon("gimp-tool-handle-transform")
def _handle():
    s = polyline([(2.5, 3.5), (13.5, 2.0), (14.0, 13.5), (2.0, 12.5)], 1.0, closed=True)
    for x, y in [(5.0, 6.0), (11.0, 9.5), (6.5, 11.0)]:
        s += ring(x, y, 1.6, 1.0)
    return s


@icon("gimp-tool-cage")
def _cage():
    p = [(3.0, 2.0), (12.0, 3.0), (14.0, 9.0), (9.5, 14.0), (2.0, 11.0)]
    s = polyline(p, 1.0, closed=True)
    for x, y in p:
        s += rect(x - 1.2, y - 1.2, 2.4, 2.4)
    return s


@icon("gimp-tool-warp")
def _warp():
    s = ""
    for k, y in enumerate([4.0, 8.0, 12.0]):
        p = [(1.0 + i * 0.5, y + 1.6 * math.sin((i * 0.5) / 14.0 * 2 * math.pi + k * 0.6)) for i in range(29)]
        s += polyline(p, 1.1)
    return s


@icon("gimp-tool-n-point-deformation")
def _npd():
    p = [(2.5, 12.5), (6.0, 4.0), (10.0, 11.0), (13.5, 3.0)]
    s = polyline(p, 0.9, op="0.6")
    for x, y in p:
        s += circle(x, y, 1.8)
    return s


@icon("gimp-tool-transform-3d")
def _cube():
    s = polyline([(8, 1.5), (14, 4.8), (14, 11.2), (8, 14.5), (2, 11.2), (2, 4.8)], 1.1, closed=True)
    s += polyline([(2, 4.8), (8, 8.1), (14, 4.8)], 1.1) + line(8, 8.1, 8, 14.5, 1.1)
    return s


# Panneaux / divers
@icon("gimp-tools")
def _tools():
    return _move()


@icon("gimp-layers")
def _layers():
    s = polygon([(8, 1.5), (15, 5.0), (8, 8.5), (1, 5.0)])
    s += polyline([(1.6, 8.0), (8, 11.2), (14.4, 8.0)], 1.2)
    s += polyline([(1.6, 11.0), (8, 14.2), (14.4, 11.0)], 1.2)
    return s


@icon("gimp-channels")
def _channels():
    return ring(5.6, 6.0, 3.8, 1.1) + ring(10.4, 6.0, 3.8, 1.1) + ring(8.0, 10.2, 3.8, 1.1)


@icon("gimp-paths")
def _paths():
    s = arc(8, 14, 9, -150, -30, 1.1)
    for x, y in [(8 + 9 * math.cos(math.radians(a)), 14 + 9 * math.sin(math.radians(a))) for a in (-150, -90, -30)]:
        s += rect(x - 1.4, y - 1.4, 2.8, 2.8)
    return s


@icon("gimp-undo-history")
def _history():
    s = rect(1.5, 2.0, 2.4, 2.4) + rect(5.5, 2.5, 9.0, 1.4)
    s += rect(1.5, 6.8, 2.4, 2.4) + rect(5.5, 7.3, 9.0, 1.4)
    s += rect(1.5, 11.6, 2.4, 2.4, op="0.5") + rect(5.5, 12.1, 9.0, 1.4, op="0.5")
    return s


@icon("photogimp-adjustment")
def _adjustment():
    # Cercle mi-plein (bouton « calque de réglage » de Photoshop)
    s = ring(8, 8, 6.2, 1.3)
    p = [(8, 1.8)] + [(8 + 6.2 * math.cos(math.radians(a)), 8 + 6.2 * math.sin(math.radians(a)))
                      for a in range(-90, 91, 10)] + [(8, 14.2)]
    s += polygon(p)
    return s


def _stylus():
    # Stylet en diagonale (pointe en bas à gauche)
    body = [(-1.4, -7.0), (1.4, -7.0), (1.4, 3.0), (0, 6.0), (-1.4, 3.0)]
    return polygon([(10.5 + x, 6.5 + y) for x, y in rotate(body, 0, 0, 45)])


@icon("chopgimp-pressure-size")
def _pressure_size():
    # Stylet + deux disques de tailles différentes (pression → taille)
    return _stylus() + circle(3.0, 13.2, 1.1) + circle(6.6, 12.6, 2.0)


@icon("chopgimp-pressure-opacity")
def _pressure_opacity():
    # Stylet + damier (pression → opacité)
    s = _stylus()
    for i in range(3):
        for j in range(3):
            if (i + j) % 2 == 0:
                s += rect(0.8 + i * 2.2, 9.6 + j * 2.2, 2.2, 2.2)
    s += rect_outline(0.8, 9.6, 6.6, 6.6, 0.6, op="0.6")
    return s


@icon("chopgimp-tool-hand")
def _hand():
    # Main ouverte : paume + 4 doigts + pouce (formes pleines)
    s = rect(4.6, 7.2, 8.0, 6.8, 2.4)
    for x, top in [(4.6, 2.8), (6.7, 1.6), (8.8, 1.8), (10.9, 3.2)]:
        s += rect(x, top, 1.8, 7.6, 0.9)
    thumb = rotate([(0, 0), (1.8, 0), (1.8, 4.6), (0, 4.6)], 0, 0, -40)
    s += polygon([(1.6 + x, 8.4 + y) for x, y in thumb])
    return s


@icon("chopgimp-tool-rotate-view")
def _rotate_view():
    # Flèche circulaire + petite feuille (rotation de la vue)
    s = arc(8, 8, 6.0, 200, 470, 1.3)
    a = math.radians(472)
    s += arrow_head(8 + 6.0 * math.cos(a), 8 + 6.0 * math.sin(a), 562, 2.8)
    s += rect(6.0, 5.2, 4.0, 5.6, 0.8)
    return s


@icon("chopgimp-tool-spot-heal")
def _spot_heal():
    # Pansement plus petit + éclat (Correcteur localisé)
    outer = rrect_poly(4.0, 6.0, 11.0, 4.6, -45, 9.5, 8.3)
    inner = rrect_poly(7.3, 6.0, 4.4, 4.6, -45, 9.5, 8.3)
    s = polygon(outer, 0.45) + polygon(inner)
    s += polygon([(3.0, 0.6), (3.6, 2.4), (5.4, 3.0), (3.6, 3.6), (3.0, 5.4), (2.4, 3.6), (0.6, 3.0), (2.4, 2.4)])
    return s


@icon("chopgimp-tool-shape")
def _shape():
    # Carré + cercle superposés (outil Forme)
    s = rect(1.5, 1.5, 8.5, 8.5, 0.6)
    s += ring(10.5, 10.5, 4.6, 1.3)
    return s


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in sorted(ICONS.items()):
        body = fn()
        for fname in (name + ".svg", name + "-symbolic.svg"):
            with open(os.path.join(OUT, fname), "w") as fh:
                fh.write(svg(body, name))
    print("%d icônes générées dans %s" % (len(ICONS), OUT))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
ChopGimp — jeu de curseurs « façon Photoshop » (dessins originaux).

Un curseur par outil, avec son point actif au bon endroit (pointe de la
pipette, étincelle de la baguette, bout du lasso…), en noir bordé de blanc
pour rester visible sur tous les fonds. Les modificateurs (+ − × …) sont des
petits symboles en bas à droite, ajoutés par GIMP (app/widgets/gimpcursor.c).

Sortie : cursors/PS-Line/<nom>.png (32 px), <nom>-x2.png (64 px) et
chopgimp-cursors.ini (points actifs). Rendu avec librsvg (python3-gi).
Les noms suivent GimpToolCursorType / GimpCursorModifier de GIMP 3.2.

Usage : build_cursors.py
"""
import math
import os
import sys

import gi
gi.require_version("Rsvg", "2.0")
import cairo
from gi.repository import Rsvg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "cursors", "PS-Line")
OUTLINE = 2.6        # bord blanc (px, à 32 px)


def f(v):
    return ("%.3f" % v).rstrip("0").rstrip(".")


def poly(points, closed=True):
    d = "M" + " L".join("%s,%s" % (f(x), f(y)) for x, y in points)
    return '<path d="%s%s"/>' % (d, "Z" if closed else "")


def line(x1, y1, x2, y2, w=1.6):
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    return poly([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)])


def polyline(points, w=1.6, closed=False):
    pts = list(points) + ([points[0]] if closed else [])
    s = "".join(line(a[0], a[1], b[0], b[1], w) for a, b in zip(pts, pts[1:]))
    s += "".join(circle(x, y, w / 2) for x, y in pts)
    return s


def circle(cx, cy, r):
    return '<circle cx="%s" cy="%s" r="%s"/>' % (f(cx), f(cy), f(r))


def ring(cx, cy, r, w=1.6, n=40):
    return polyline([(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
                     for k in range(n)], w, closed=True)


def ellipse_ring(cx, cy, rx, ry, w=1.6, n=40, a0=0, a1=360):
    pts = [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
           for a in [a0 + (a1 - a0) * k / n for k in range(n + 1)]]
    return polyline(pts, w)


def arc(cx, cy, r, a0, a1, w=1.6, n=24):
    return ellipse_ring(cx, cy, r, r, w, n, a0, a1)


def rect(x, y, w, h):
    return '<rect x="%s" y="%s" width="%s" height="%s"/>' % (f(x), f(y), f(w), f(h))


def rect_outline(x, y, w, h, t=1.6):
    return polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], t, closed=True)


def arrow_head(x, y, deg, size=4.0):
    a = math.radians(deg)
    p1 = (x + size * math.cos(a + 2.6), y + size * math.sin(a + 2.6))
    p2 = (x + size * math.cos(a - 2.6), y + size * math.sin(a - 2.6))
    return poly([(x, y), p1, p2])


def double_arrow(x1, y1, x2, y2, w=1.6, head=4.5):
    deg = math.degrees(math.atan2(y2 - y1, x2 - x1))
    return line(x1, y1, x2, y2, w) + arrow_head(x2, y2, deg, head) + arrow_head(x1, y1, deg + 180, head)


def star4(cx, cy, r, k=0.3):
    pts = []
    for i in range(8):
        a = math.radians(i * 45 - 90)
        rr = r if i % 2 == 0 else r * k
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return poly(pts)


def rotate(points, cx, cy, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in points]


# ─── éléments communs ─────────────────────────────────────────────────

def cross(cx=15.5, cy=15.5, arm=9, gap=2.5, w=1.4):
    """Croix fine de Photoshop (sélections, dégradé, règle)."""
    return (line(cx - arm, cy, cx - gap, cy, w) + line(cx + gap, cy, cx + arm, cy, w) +
            line(cx, cy - arm, cx, cy - gap, w) + line(cx, cy + gap, cx, cy + arm, w))


def pointer(x=1.0, y=1.0, s=1.0):
    """Flèche de sélection (pointe en x, y)."""
    pts = [(0, 0), (0, 17), (4.2, 13), (7, 19.5), (9.6, 18.4), (6.9, 12.2), (12.2, 12.2)]
    return poly([(x + px * s, y + py * s) for px, py in pts])


def lasso_loop(polygonal=False):
    if polygonal:
        loop = polyline([(9, 13), (6, 6), (14, 2), (27, 4), (29, 11), (19, 14)], 1.7, closed=True)
    else:
        loop = ellipse_ring(17.5, 8.5, 11, 6.2, 1.7, 48)
    rope = polyline([(10.5, 13.2), (8.6, 17.5), (5.8, 21.5), (3, 26)], 1.6)
    return loop + rope


def pen_nib(tip=(2.5, 2.5)):
    """Plume de la plume Photoshop, pointe en haut à gauche."""
    tx, ty = tip
    body = [(0, 0), (8.5, 3.2), (14.5, 9), (13, 13), (9, 14.5), (3.2, 8.5)]
    pts = [(tx + x, ty + y) for x, y in body]
    s = poly(pts)
    s += poly([(tx + 13.4, ty + 11.4), (tx + 18.6, ty + 16.6), (tx + 16.6, ty + 18.6), (tx + 11.4, ty + 13.4)])
    return s


def eyedropper():
    s = line(4, 27.5, 18, 13.5, 3.2)                   # tube
    s += poly([(2, 30), (3, 26), (6, 29)])             # pointe
    s += line(16, 11.5, 20.5, 16, 2.6)                 # bague
    s += circle(23.2, 8.8, 4.6)                        # poire
    return s


def wand():
    s = line(10, 10, 27, 27, 3.0)
    s += line(8.5, 8.5, 11.5, 11.5, 4.0)
    s += star4(6, 6, 5.2)
    return s


def bucket():
    body = rotate([(8, 6), (22, 6), (20.5, 22), (9.5, 22)], 15, 14, -35)
    s = poly(body)
    s += arc(15, 7, 6.5, 200, 340, 1.4)
    # goutte qui tombe (point actif)
    s += poly([(4.5, 27.5), (2.6, 24.4), (3.2, 22.2), (5.0, 21.4), (6.6, 22.4), (6.8, 24.6)])
    return s


def i_beam():
    s = line(15.5, 5, 15.5, 26, 1.5)
    s += line(11, 4.5, 14.8, 4.5, 1.5) + line(16.2, 4.5, 20, 4.5, 1.5)
    s += line(11, 26.5, 14.8, 26.5, 1.5) + line(16.2, 26.5, 20, 26.5, 1.5)
    s += line(12.5, 20.5, 18.5, 20.5, 1.2)
    return s


def loupe():
    return ring(12, 12, 8.2, 2.0) + line(18.2, 18.2, 27, 27, 3.4)


def hand():
    s = ""
    for x, top in [(8.5, 9), (12.2, 5.5), (15.9, 4.6), (19.6, 6.5)]:
        s += rect(x - 1.6, top, 3.2, 14)
        s += circle(x, top, 1.6)
    s += poly([(6.9, 14), (21.2, 14), (22.5, 21), (20, 27), (10.5, 27), (5.5, 22), (2.5, 16.5),
               (4.4, 14.8), (6.9, 17)])
    s += poly([(21.2, 14), (24.6, 11.6), (26.2, 12.8), (22.5, 21)])
    return s


def crop():
    s = polyline([(8, 1.5), (8, 24), (30.5, 24)], 2.0)
    s += polyline([(1.5, 8), (24, 8), (24, 30.5)], 2.0)
    return s


def tool_icon_cursor(icon_name, scale=1.4, x=4, y=4):
    """Icône PS-Line de l'outil (16 px) agrandie, pour les outils sans
    dessin dédié (pinceaux masqués par le contour de brosse en temps
    normal)."""
    sys.path.insert(0, os.path.join(ROOT, "icons"))
    import build_icons
    body = build_icons.ICONS[icon_name]()
    return '<g transform="translate(%s,%s) scale(%s)">%s</g>' % (f(x), f(y), f(scale), body)


# ─── les curseurs : nom → (dessin, x, y du point actif) ─────────────────

CURSORS = {
    "tool-rect-select":      (cross(), 15, 15),
    "tool-ellipse-select":   (cross(), 15, 15),
    "tool-free-select":      (lasso_loop(), 3, 26),
    "tool-polygon-select":   (lasso_loop(True), 3, 26),
    "tool-fuzzy-select":     (wand(), 6, 6),
    "tool-iscissors":        (lasso_loop() + polyline([(23, 17), (23, 22), (29, 22), (29, 17)], 2.0), 3, 26),
    "tool-paths":            (pen_nib(), 2, 2),
    "tool-paths-anchor":     (pen_nib() + rect(22, 3, 6, 6), 2, 2),
    "tool-paths-control":    (pen_nib() + circle(25, 6, 3.2), 2, 2),
    "tool-paths-segment":    (pen_nib() + arc(25, 12, 6, 200, 340, 1.6), 2, 2),
    "tool-move":             (pointer(1, 1) + double_arrow(16, 21, 26, 21, 1.4, 3.2) +
                              double_arrow(21, 16, 21, 26, 1.4, 3.2), 1, 1),
    "tool-zoom":             (loupe(), 12, 12),
    "tool-crop":             (crop(), 8, 8),
    "tool-resize":           (double_arrow(6, 25, 25, 6, 1.8), 15, 15),
    "tool-rotate":           (arc(15.5, 15.5, 10, 200, 520, 1.8) +
                              arrow_head(15.5 + 10 * math.cos(math.radians(520)),
                                         15.5 + 10 * math.sin(math.radians(520)), 520 + 90, 5),
                              15, 15),
    "tool-shear":            (double_arrow(4, 15.5, 27, 15.5, 1.8) + line(9, 24, 22, 7, 1.2), 15, 15),
    "tool-perspective":      (pointer(1, 1) + polyline([(17, 18), (29, 18), (27, 29), (19, 29)], 1.4,
                                                       closed=True), 1, 1),
    "tool-transform-3d-camera": (pointer(1, 1) + rect_outline(17, 19, 12, 9, 1.4) + circle(23, 23.5, 2.4), 1, 1),
    "tool-flip-horizontal":  (double_arrow(4, 15.5, 27, 15.5, 1.8) + line(15.5, 6, 15.5, 25, 1.0), 15, 15),
    "tool-flip-vertical":    (double_arrow(15.5, 4, 15.5, 27, 1.8) + line(6, 15.5, 25, 15.5, 1.0), 15, 15),
    "tool-text":             (i_beam(), 15, 20),
    "tool-color-picker":     (eyedropper(), 2, 29),
    "tool-bucket-fill":      (bucket(), 4, 27),
    "tool-gradient":         (cross(), 15, 15),
    "tool-measure":          (cross() + line(19, 26, 29, 16, 2.4), 15, 15),
    "tool-warp":             (cross() + ring(15.5, 15.5, 6, 1.0), 15, 15),
    "tool-hand":             (hand(), 14, 15),
}

# outils de peinture : leur icône (le contour de brosse remplace le curseur)
for _name, _icon, _hx, _hy in [
        ("tool-pencil", "gimp-tool-pencil", 5, 26), ("tool-paintbrush", "gimp-tool-paintbrush", 5, 26),
        ("tool-airbrush", "gimp-tool-airbrush", 5, 26), ("tool-ink", "gimp-tool-ink", 5, 26),
        ("tool-clone", "gimp-tool-clone", 15, 26), ("tool-heal", "gimp-tool-heal", 15, 15),
        ("tool-eraser", "gimp-tool-eraser", 7, 24), ("tool-smudge", "gimp-tool-smudge", 5, 26),
        ("tool-blur", "gimp-tool-blur", 15, 26), ("tool-dodge", "gimp-tool-dodge", 8, 8),
        ("tool-burn", "gimp-tool-dodge", 8, 8)]:
    CURSORS[_name] = (_icon, _hx, _hy)


# modificateurs : symbole en bas à droite (centre 26.5, 26.5)
MX, MY = 26.5, 26.5
MODIFIERS = {
    "modifier-plus":       line(MX - 3.6, MY, MX + 3.6, MY, 1.6) + line(MX, MY - 3.6, MX, MY + 3.6, 1.6),
    "modifier-minus":      line(MX - 3.6, MY, MX + 3.6, MY, 1.6),
    "modifier-intersect":  line(MX - 3, MY - 3, MX + 3, MY + 3, 1.6) + line(MX + 3, MY - 3, MX - 3, MY + 3, 1.6),
    "modifier-bad":        ring(MX, MY, 3.8, 1.4) + line(MX - 2.7, MY + 2.7, MX + 2.7, MY - 2.7, 1.4),
    "modifier-move":       double_arrow(MX - 4.2, MY, MX + 4.2, MY, 1.1, 2.4) +
                           double_arrow(MX, MY - 4.2, MX, MY + 4.2, 1.1, 2.4),
    "modifier-resize":     double_arrow(MX - 3.6, MY + 3.6, MX + 3.6, MY - 3.6, 1.2, 2.6),
    "modifier-rotate":     arc(MX, MY, 3.6, 200, 470, 1.2) + arrow_head(MX + 3.6 * math.cos(math.radians(470)),
                                                                        MY + 3.6 * math.sin(math.radians(470)),
                                                                        560, 2.6),
    "modifier-zoom":       ring(MX - 0.8, MY - 0.8, 2.6, 1.1) + line(MX + 1.2, MY + 1.2, MX + 4, MY + 4, 1.4),
    "modifier-control":    circle(MX, MY, 2.4),
    "modifier-anchor":     rect(MX - 2.6, MY - 2.6, 5.2, 5.2),
    "modifier-foreground": rect(MX - 3.4, MY - 3.4, 6.8, 6.8),
    "modifier-background": rect_outline(MX - 3, MY - 3, 6, 6, 1.2),
    "modifier-pattern":    rect(MX - 3.4, MY - 3.4, 3.4, 3.4) + rect(MX, MY, 3.4, 3.4),
    "modifier-join":       ring(MX, MY, 3.4, 1.1) + line(MX - 1.8, MY, MX + 1.8, MY, 1.1) +
                           line(MX, MY - 1.8, MX, MY + 1.8, 1.1),
    "modifier-select":     pointer(MX - 3.5, MY - 4.5, 0.42),
}


def to_svg(body, size):
    """Noir bordé de blanc : la même forme tracée en blanc épais dessous."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 32 32">'
            '<g fill="#ffffff" stroke="#ffffff" stroke-width="%s" stroke-linejoin="round">%s</g>'
            '<g fill="#000000">%s</g></svg>' % (size, size, f(OUTLINE), body, body))


def render(body, path, size):
    handle = Rsvg.Handle.new_from_data(to_svg(body, size).encode())
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    vp = Rsvg.Rectangle()
    vp.x, vp.y, vp.width, vp.height = 0, 0, size, size
    handle.render_document(ctx, vp)
    surface.write_to_png(path)


def main():
    os.makedirs(OUT, exist_ok=True)
    ini = ["# ChopGimp — points actifs des curseurs (généré par tools/build_cursors.py)"]
    for name, (body, hx, hy) in sorted(CURSORS.items()):
        if body.startswith("gimp-tool-"):
            body = tool_icon_cursor(body)
        render(body, os.path.join(OUT, name + ".png"), 32)
        render(body, os.path.join(OUT, name + "-x2.png"), 64)
        ini += ["", "[%s]" % name, "hot=%d;%d" % (hx, hy)]
    for name, body in sorted(MODIFIERS.items()):
        render(body, os.path.join(OUT, name + ".png"), 32)
        render(body, os.path.join(OUT, name + "-x2.png"), 64)
    open(os.path.join(OUT, "chopgimp-cursors.ini"), "w").write("\n".join(ini) + "\n")
    print("%d curseurs et %d modificateurs dans %s" % (len(CURSORS), len(MODIFIERS), OUT))


if __name__ == "__main__":
    main()

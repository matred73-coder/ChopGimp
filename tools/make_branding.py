#!/usr/bin/env python3
"""
ChopGimp — génère l'identité visuelle (création originale, monogramme « Cg ») :

  branding/chopgimp.svg                 icône de l'application (texte vectorisé)
  branding/png/chopgimp-<taille>.png    icône aux tailles hicolor
  branding/chopgimp-symbolic.svg        version monochrome (thème d'icônes)
  branding/logo-128.png                 logo de la fenêtre « À propos »
  branding/splash.png                   écran de démarrage (1591×1080)

Usage : make_branding.py   (nécessite pycairo + PyGObject Pango/PangoCairo)
"""
import math
import os

import cairo
import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "branding")
os.makedirs(os.path.join(OUT, "png"), exist_ok=True)

NAVY = (0.08, 0.15, 0.38)       # #142661
BLUE = (0.15, 0.38, 0.86)       # #2661DB
CYAN = (0.13, 0.83, 0.93)       # #22D3EE
FONT = "Noto Sans Bold"


def text_layout(cr, text, size, font=FONT):
    layout = PangoCairo.create_layout(cr)
    fd = Pango.FontDescription.from_string(font)
    fd.set_absolute_size(size * Pango.SCALE)
    layout.set_font_description(fd)
    layout.set_text(text, -1)
    return layout


def draw_badge(cr, cx, cy, r, mono=False):
    """Pastille ronde à dégradé + « Cg » blanc (en tracés)."""
    cr.save()
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    if mono:
        cr.set_source_rgb(0.745, 0.745, 0.745)
    else:
        g = cairo.LinearGradient(cx - r, cy + r, cx + r, cy - r)
        g.add_color_stop_rgb(0.0, *NAVY)
        g.add_color_stop_rgb(0.55, *BLUE)
        g.add_color_stop_rgb(1.0, *CYAN)
        cr.set_source(g)
    cr.fill()
    if not mono:
        # léger reflet en haut
        hl = cairo.RadialGradient(cx - r * 0.35, cy - r * 0.55, 0, cx - r * 0.35, cy - r * 0.55, r * 1.1)
        hl.add_color_stop_rgba(0, 1, 1, 1, 0.22)
        hl.add_color_stop_rgba(1, 1, 1, 1, 0.0)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source(hl)
        cr.fill()
    # « Cg » vectorisé
    layout = text_layout(cr, "Cg", r * 1.05)
    ink, logical = layout.get_pixel_extents()
    cr.move_to(cx - ink.x - ink.width / 2.0, cy - ink.y - ink.height / 2.0 - r * 0.02)
    PangoCairo.layout_path(cr, layout)
    if mono:
        # lettres « percées » dans la pastille (rendu symbolique)
        cr.set_operator(cairo.OPERATOR_CLEAR)
    else:
        cr.set_source_rgb(1, 1, 1)
    cr.fill()
    cr.restore()


def icon_svg(path, size=256, mono=False):
    surf = cairo.SVGSurface(path, size, size)
    cr = cairo.Context(surf)
    if mono:
        # symbolique : anneau + lettres pleines (GTK force la couleur de remplissage)
        r = size * 0.47
        cr.arc(size / 2, size / 2, r, 0, 2 * math.pi)
        cr.arc_negative(size / 2, size / 2, r - size * 0.07, 2 * math.pi, 0)
        cr.set_source_rgb(0.745, 0.745, 0.745)
        cr.fill()
        layout = text_layout(cr, "Cg", size * 0.5)
        ink, _ = layout.get_pixel_extents()
        cr.move_to(size / 2 - ink.x - ink.width / 2.0, size / 2 - ink.y - ink.height / 2.0)
        PangoCairo.layout_path(cr, layout)
        cr.fill()
    else:
        draw_badge(cr, size / 2, size / 2, size * 0.47)
    surf.finish()


def icon_png(path, size):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    draw_badge(cr, size / 2, size / 2, size * 0.47)
    surf.write_to_png(path)


def splash(path, w=1591, h=1080):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)
    bg = cairo.LinearGradient(0, 0, w, h)
    bg.add_color_stop_rgb(0, 0.09, 0.09, 0.10)
    bg.add_color_stop_rgb(1, 0.15, 0.16, 0.20)
    cr.set_source(bg)
    cr.paint()
    # halo
    halo = cairo.RadialGradient(w * 0.32, h * 0.45, 0, w * 0.32, h * 0.45, h * 0.55)
    halo.add_color_stop_rgba(0, *BLUE, 0.35)
    halo.add_color_stop_rgba(1, *BLUE, 0.0)
    cr.set_source(halo)
    cr.paint()
    draw_badge(cr, w * 0.32, h * 0.45, h * 0.20)
    # titre
    cr.set_source_rgb(1, 1, 1)
    lay = text_layout(cr, "ChopGimp", h * 0.11)
    cr.move_to(w * 0.47, h * 0.33)
    PangoCairo.show_layout(cr, lay)
    cr.set_source_rgba(1, 1, 1, 0.75)
    lay = text_layout(cr, "Retouche d'images professionnelle", h * 0.035, "Noto Sans")
    cr.move_to(w * 0.475, h * 0.48)
    PangoCairo.show_layout(cr, lay)
    cr.set_source_rgba(1, 1, 1, 0.45)
    lay = text_layout(cr, "Basé sur GIMP 3.2.8 — logiciel libre (GPLv3)", h * 0.022, "Noto Sans")
    cr.move_to(w * 0.477, h * 0.545)
    PangoCairo.show_layout(cr, lay)
    surf.write_to_png(path)


if __name__ == "__main__":
    icon_svg(os.path.join(OUT, "chopgimp.svg"))
    icon_svg(os.path.join(OUT, "chopgimp-symbolic.svg"), 16, mono=True)
    for s in (16, 22, 24, 32, 36, 48, 64, 72, 96, 128, 192, 256, 512):
        icon_png(os.path.join(OUT, "png", "chopgimp-%d.png" % s), s)
    icon_png(os.path.join(OUT, "logo-128.png"), 128)
    splash(os.path.join(OUT, "splash.png"))
    print("identité ChopGimp générée dans", OUT)

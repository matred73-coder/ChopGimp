#!/usr/bin/env python3
"""
ChopGimp — génère l'identité visuelle (tête de loup, 4.2.4 ; source :
branding/source/loup.png, loup brun détouré de blanc devant la lune,
fond transparent) :

  branding/chopgimp.svg                 icône de l'application (texte vectorisé)
  branding/png/chopgimp-<taille>.png    icône aux tailles hicolor
  branding/chopgimp-symbolic.svg        version monochrome (thème d'icônes)
  branding/logo-128.png                 logo de la fenêtre « À propos »
  branding/splash.png                   écran de démarrage (1591×1080), avec
                                        le numéro de VERSION

Lancé par « make manifest » : l'écran de démarrage suit chaque version.

Usage : make_branding.py   (nécessite pycairo + PyGObject Pango/PangoCairo)
"""
import io
import math
import os
import random

import cairo
import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "branding")
WOLF = os.path.join(OUT, "source", "loup.png")
VERSION = open(os.path.join(ROOT, "VERSION")).read().strip()
# Yeux du loup dans loup.png (838×764, loup devant la lune), pour la
# lueur rouge de l'écran
EYES = ((435, 332, 24), (579, 349, 18))
RED = (0.99, 0.0, 0.01)
os.makedirs(os.path.join(OUT, "png"), exist_ok=True)

FONT = "Noto Sans Bold"


def text_layout(cr, text, size, font=FONT):
    layout = PangoCairo.create_layout(cr)
    fd = Pango.FontDescription.from_string(font)
    fd.set_absolute_size(size * Pango.SCALE)
    layout.set_font_description(fd)
    layout.set_text(text, -1)
    return layout


def wolf_bbox(im):
    """Cadre du dessin, sans les pixels presque transparents (halo)."""
    return im.split()[3].point(lambda v: 255 if v >= 20 else 0).getbbox()


def wolf_surface(height):
    """Loup redimensionné (PIL, Lanczos) en surface cairo ARGB."""
    from PIL import Image
    im = Image.open(WOLF).convert("RGBA")
    im = im.crop(wolf_bbox(im))
    w = max(1, round(im.width * height / im.height))
    im = im.resize((w, height), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    buf.seek(0)
    return cairo.ImageSurface.create_from_png(buf), im


def draw_wolf_square(cr, size, pad=0.02):
    """Loup centré dans un carré, proportions gardées."""
    from PIL import Image
    src = Image.open(WOLF).convert("RGBA")
    src = src.crop(wolf_bbox(src))
    inner = size * (1 - 2 * pad)
    scale = min(inner / src.width, inner / src.height)
    h = max(1, round(src.height * scale))
    surf, im = wolf_surface(h)
    cr.set_source_surface(surf, (size - im.width) / 2.0, (size - im.height) / 2.0)
    cr.paint()


def icon_svg(path, size=256, mono=False):
    surf = cairo.SVGSurface(path, size, size)
    cr = cairo.Context(surf)
    if mono:
        # symbolique : silhouette du loup en rectangles pleins (GTK recolore
        # le remplissage), tirée de la couche alpha sur une grille 32×32
        from PIL import Image
        im = Image.open(WOLF).convert("RGBA")
        im = im.crop(wolf_bbox(im))
        n = 32
        sc = min(n / im.width, n / im.height)
        gw, gh = max(1, round(im.width * sc)), max(1, round(im.height * sc))
        a = im.split()[3].resize((gw, gh), Image.LANCZOS)
        cell = size / float(n)
        ox, oy = (n - gw) / 2.0, (n - gh) / 2.0
        for y in range(gh):
            x = 0
            while x < gw:
                if a.getpixel((x, y)) >= 128:
                    x0 = x
                    while x < gw and a.getpixel((x, y)) >= 128:
                        x += 1
                    cr.rectangle((ox + x0) * cell, (oy + y) * cell,
                                 (x - x0) * cell, cell)
                else:
                    x += 1
        cr.set_source_rgb(0.745, 0.745, 0.745)
        cr.fill()
    else:
        draw_wolf_square(cr, size)
    surf.finish()


def icon_png(path, size):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    draw_wolf_square(cr, size)
    surf.write_to_png(path)


def splash(path, w=1591, h=1080):
    """Fond noir-brun à grain, loup en grand à gauche aux yeux lumineux,
    titre, sous-titre et version à droite ; le bas reste libre pour le
    texte de progression de GIMP."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)
    bg = cairo.RadialGradient(w * 0.30, h * 0.45, 0, w * 0.30, h * 0.45, w * 0.85)
    bg.add_color_stop_rgb(0.0, 0.17, 0.09, 0.04)
    bg.add_color_stop_rgb(0.5, 0.08, 0.05, 0.035)
    bg.add_color_stop_rgb(1.0, 0.035, 0.03, 0.03)
    cr.set_source(bg)
    cr.paint()
    # grain : petits points clairs et sombres, déterministe
    rnd = random.Random(73)
    for _ in range(26000):
        x, y = rnd.random() * w, rnd.random() * h
        v = rnd.random()
        cr.set_source_rgba(1, 0.9, 0.8, 0.035) if v > 0.5 else cr.set_source_rgba(0, 0, 0, 0.12)
        cr.rectangle(x, y, 1.4, 1.4)
        cr.fill()
    # loup
    wh = int(h * 0.80)
    wsurf, wim = wolf_surface(wh)
    from PIL import Image
    src = Image.open(WOLF).convert("RGBA")
    bx0, by0, bx1, by1 = wolf_bbox(src)
    k = wh / float(by1 - by0)
    wx = w * 0.28 - wim.width / 2.0
    wy = h * 0.055
    # ombre portée douce sous le loup
    cr.save()
    cr.set_source_rgba(0, 0, 0, 0.55)
    cr.translate(wx + 14, wy + 18)
    cr.mask_surface(wsurf, 0, 0)
    cr.restore()
    cr.set_source_surface(wsurf, wx, wy)
    cr.paint()
    # lueur rouge des yeux
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    for ex, ey, r in EYES:
        cx, cy = wx + (ex - bx0) * k, wy + (ey - by0) * k
        g = cairo.RadialGradient(cx, cy, 0, cx, cy, r * k * 2.6)
        g.add_color_stop_rgba(0.0, 1.0, 0.15, 0.05, 0.55)
        g.add_color_stop_rgba(0.35, 0.8, 0.05, 0.0, 0.22)
        g.add_color_stop_rgba(1.0, 0.5, 0.0, 0.0, 0.0)
        cr.set_source(g)
        cr.arc(cx, cy, r * k * 2.6, 0, 2 * math.pi)
        cr.fill()
    cr.restore()
    # titre
    tx = w * 0.53
    cr.set_source_rgb(0.98, 0.95, 0.90)
    lay = text_layout(cr, "ChopGimp", h * 0.12)
    cr.move_to(tx, h * 0.30)
    PangoCairo.show_layout(cr, lay)
    ink, logical = lay.get_pixel_extents()
    # filet rouge sous le titre
    cr.set_source_rgb(*RED)
    cr.rectangle(tx + ink.x + 4, h * 0.30 + ink.y + ink.height + h * 0.025, h * 0.16, h * 0.007)
    cr.fill()
    cr.set_source_rgba(0.98, 0.95, 0.90, 0.80)
    lay = text_layout(cr, "Retouche d'images professionnelle", h * 0.036, "Noto Sans")
    cr.move_to(tx + 4, h * 0.505)
    PangoCairo.show_layout(cr, lay)
    cr.set_source_rgb(0.93, 0.20, 0.15)
    lay = text_layout(cr, "Version " + VERSION, h * 0.030, FONT)
    cr.move_to(tx + 5, h * 0.575)
    PangoCairo.show_layout(cr, lay)
    cr.set_source_rgba(0.98, 0.95, 0.90, 0.45)
    lay = text_layout(cr, "Basé sur GIMP 3.2.8 — logiciel libre (GPLv3)", h * 0.022, "Noto Sans")
    cr.move_to(tx + 5, h * 0.635)
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

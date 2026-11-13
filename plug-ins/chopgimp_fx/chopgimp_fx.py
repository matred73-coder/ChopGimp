#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — effets façon Photoshop / Illustrator pour les formes et les calques.

  Calque > Effets de tracé > Zigzag, Rugosité, Ondulation, Contracter/Dilater,
                             Torsion, Largeur variable          (a)
  Calque > Effets de tracé > Flèches                             (f)
  Calque > Effets de tracé > Position du contour                 (g)
  Calque > Effets de tracé > Contour au pinceau                  (d)
  Calque > Style de calque > Incrustation de dégradé             (e)
  Calque > Style de calque > Style de calque… (fenêtre unique)   (h)
  Calque > Effets de tracé > Modifier l'effet… / Supprimer l'effet

Les effets restent modifiables (« effets dynamiques ») : la forme d'origine,
l'effet et ses réglages sont mémorisés dans le calque résultat (parasite
« chopgimp-fx ») ; « Modifier l'effet… » régénère le résultat avec de nouveaux
réglages, « Supprimer l'effet » rend la forme d'origine.
"""
import json
import math
import random
import sys

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gegl", "0.4")
gi.require_version("Gtk", "3.0")
from gi.repository import Gimp, GimpUi, Gegl, GLib, GObject, Gtk

AUTHOR = "ChopGimp"
YEAR = "2026"
STYLE_PREFIX = "Style : "


def ok(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def fail(procedure, msg):
    return procedure.new_return_values(
        Gimp.PDBStatusType.EXECUTION_ERROR,
        GLib.Error.new_literal(GLib.quark_from_string("chopgimp"), msg, 0))


def gegl_color(r, g, b, a=1.0):
    """Couleur sRGB (0..1, comme Gdk.RGBA) → Gegl.Color ; set_rgba() seul
    attendrait du RGB linéaire et éclaircirait la couleur."""
    c = Gegl.Color.new("black")
    c.set_rgba_with_space(r, g, b, a, None)
    return c


# ─── Mémoire des effets (parasites) ──────────────────────────────────────
FX_PARASITE = "chopgimp-fx"
STYLE_PARASITE = "chopgimp-style"


def parasite_get(item, name):
    try:
        par = item.get_parasite(name)
    except Exception:
        par = None
    if par is None:
        return None
    try:
        return json.loads(bytes(par.get_data()).decode("utf-8"))
    except Exception:
        return None


def parasite_set(item, name, data):
    # 1 = persistant (enregistré dans le XCF), 2 = annulable
    item.attach_parasite(Gimp.Parasite.new(name, 3, list(json.dumps(data).encode("utf-8"))))


def rgba(c):
    r, g, b, a = c.get_rgba_with_space(None)
    return [r, g, b, a]


def from_rgba(v):
    return gegl_color(*v)


class NoSelection:
    """Retire temporairement la sélection (remplissages et tracés sur tout le calque)."""

    def __init__(self, image):
        self.image, self.saved = image, None

    def __enter__(self):
        if not Gimp.Selection.is_empty(self.image):
            self.saved = Gimp.Selection.save(self.image)
            Gimp.Selection.none(self.image)
        return self

    def __exit__(self, *exc):
        if self.saved is not None:
            self.image.select_item(Gimp.ChannelOps.REPLACE, self.saved)
            self.image.remove_channel(self.saved)
        return False


def capture_source(layer, path=None):
    """Forme d'origine (sous-chemins + style) d'un calque vectoriel ou d'un chemin."""
    path = path or layer.get_path()
    strokes = []
    for sid in path.get_strokes():
        t, pts, closed = path.stroke_get_points(sid)
        strokes.append([int(t), list(pts), bool(closed)])
    src = {"name": layer.get_name() if layer else path.get_name(), "strokes": strokes}
    if isinstance(layer, Gimp.VectorLayer):
        src.update({"fill": layer.get_enable_fill(), "fill-color": rgba(layer.get_fill_color()),
                    "stroke": layer.get_enable_stroke(), "stroke-color": rgba(layer.get_stroke_color()),
                    "stroke-width": layer.get_stroke_width()})
    return src


def source_path(image, src):
    path = Gimp.Path.new(image, src["name"])
    for t, pts, closed in src["strokes"]:
        path.stroke_new_from_points(Gimp.PathStrokeType(t), pts, closed)
    image.insert_path(path, None, 0)
    return path


def rebuild_source(image, ref, src):
    """Recrée, à la place de ref, le calque vectoriel d'origine mémorisé."""
    nl = Gimp.VectorLayer.new(image, source_path(image, src))
    nl.set_name(src["name"])
    if isinstance(ref, Gimp.VectorLayer):
        copy_vector_style(ref, nl)
    else:
        nl.set_opacity(ref.get_opacity())
    if "fill" in src:
        nl.set_enable_fill(src["fill"])
        nl.set_fill_color(from_rgba(src["fill-color"]))
        nl.set_enable_stroke(src["stroke"])
        nl.set_stroke_color(from_rgba(src["stroke-color"]))
        nl.set_stroke_width(src["stroke-width"])
    image.insert_layer(nl, ref.get_parent(), image.get_item_position(ref))
    nl.refresh()
    return nl


# ─── Géométrie des chemins ───────────────────────────────────────────────

def stroke_polyline(path, sid, precision=0.5):
    """Points (x, y) d'un sous-chemin, échantillonnés, et indicateur fermé."""
    coords, closed = path.stroke_interpolate(sid, precision)
    pts = [(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
    # dédoublonnage
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    if closed and len(out) > 2 and abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out, closed


def resample(pts, closed, n):
    """n points régulièrement espacés le long de la polyligne."""
    seq = pts + [pts[0]] if closed else list(pts)
    seg = [math.hypot(seq[i + 1][0] - seq[i][0], seq[i + 1][1] - seq[i][1]) for i in range(len(seq) - 1)]
    total = sum(seg)
    if total == 0 or n < 2:
        return list(pts), 0.0
    step = total / (n if closed else n - 1)
    out, i, acc = [], 0, 0.0
    for k in range(n):
        d = k * step
        while i < len(seg) - 1 and acc + seg[i] < d:
            acc += seg[i]
            i += 1
        t = 0.0 if seg[i] == 0 else (d - acc) / seg[i]
        t = min(max(t, 0.0), 1.0)
        out.append((seq[i][0] + t * (seq[i + 1][0] - seq[i][0]),
                    seq[i][1] + t * (seq[i + 1][1] - seq[i][1])))
    return out, total


def normals(pts, closed):
    n = len(pts)
    res = []
    for i in range(n):
        if closed:
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        l = math.hypot(dx, dy) or 1.0
        res.append((-dy / l, dx / l))
    return res


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def bezier_points(pts, closed, smooth):
    """Liste plate de points de contrôle (poignée, ancre, poignée) pour GIMP."""
    n = len(pts)
    flat = []
    for i in range(n):
        p = pts[i]
        if smooth:
            if closed:
                a, b = pts[(i - 1) % n], pts[(i + 1) % n]
            else:
                a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
            tx, ty = (b[0] - a[0]) / 6.0, (b[1] - a[1]) / 6.0
            cin, cout = (p[0] - tx, p[1] - ty), (p[0] + tx, p[1] + ty)
        else:
            cin = cout = p
        flat += [cin[0], cin[1], p[0], p[1], cout[0], cout[1]]
    return flat


# ─── Calques vectoriels ─────────────────────────────────────────────────

def selected_vector_layers(layers):
    return [l for l in layers if isinstance(l, Gimp.VectorLayer)]


def copy_vector_style(src, dst):
    for getter, setter in [("get_enable_fill", "set_enable_fill"), ("get_fill_color", "set_fill_color"),
                           ("get_enable_stroke", "set_enable_stroke"), ("get_stroke_color", "set_stroke_color"),
                           ("get_stroke_width", "set_stroke_width"),
                           ("get_stroke_width_unit", "set_stroke_width_unit"),
                           ("get_stroke_cap_style", "set_stroke_cap_style"),
                           ("get_stroke_join_style", "set_stroke_join_style"),
                           ("get_stroke_miter_limit", "set_stroke_miter_limit"),
                           ("get_stroke_dash_pattern", "set_stroke_dash_pattern"),
                           ("get_stroke_dash_offset", "set_stroke_dash_offset")]:
        try:
            getattr(dst, setter)(getattr(src, getter)())
        except Exception:
            pass
    dst.set_opacity(src.get_opacity())
    dst.set_mode(src.get_mode())


def new_vector_layer_like(image, src, path, name, position_layer=None):
    image.insert_path(path, None, 0)
    nl = Gimp.VectorLayer.new(image, path)
    nl.set_name(name)
    copy_vector_style(src, nl)
    ref = position_layer or src
    image.insert_layer(nl, ref.get_parent(), image.get_item_position(ref))
    return nl


def replace_shape(image, layer, transform, suffix):
    """Applique transform(points, closed) -> (points, closed, smooth) à chaque
    sous-chemin et remplace le calque par un calque vectoriel équivalent."""
    path = layer.get_path()
    new_path = Gimp.Path.new(image, layer.get_name())
    built = 0
    for sid in path.get_strokes():
        pts, closed = stroke_polyline(path, sid)
        if len(pts) < 2:
            continue
        res = transform(pts, closed)
        if not res:
            continue
        npts, nclosed, smooth = res
        if len(npts) < 2:
            continue
        new_path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER,
                                        bezier_points(npts, nclosed, smooth), nclosed)
        built += 1
    if not built:
        return None
    nl = new_vector_layer_like(image, layer, new_path, layer.get_name())
    image.remove_layer(layer)
    nl.refresh()
    return nl


# ─── Effets de tracé (a) ─────────────────────────────────────────────────

def fx_zigzag(size, ridges, smooth):
    def t(pts, closed):
        _, total = resample(pts, closed, 2)
        n = max(4, int(ridges) * 2)
        rp, _ = resample(pts, closed, n + (0 if closed else 1))
        nr = normals(rp, closed)
        out = [(p[0] + nr[i][0] * size * (1 if i % 2 else -1),
                p[1] + nr[i][1] * size * (1 if i % 2 else -1)) for i, p in enumerate(rp)]
        return out, closed, smooth
    return t


def fx_roughen(size, detail, seed):
    rnd = random.Random(seed)

    def t(pts, closed):
        rp, total = resample(pts, closed, 2)
        n = max(8, int(total / max(1.0, 100.0 / detail)))
        rp, _ = resample(pts, closed, n)
        nr = normals(rp, closed)
        out = []
        for i, p in enumerate(rp):
            d = rnd.uniform(-size, size)
            out.append((p[0] + nr[i][0] * d + rnd.uniform(-size, size) * 0.3,
                        p[1] + nr[i][1] * d + rnd.uniform(-size, size) * 0.3))
        return out, closed, True
    return t


def fx_wave(amplitude, wavelength):
    def t(pts, closed):
        _, total = resample(pts, closed, 2)
        n = max(16, int(total / max(2.0, wavelength / 8.0)))
        rp, total = resample(pts, closed, n)
        nr = normals(rp, closed)
        k = 2 * math.pi / max(1.0, wavelength)
        out = []
        for i, p in enumerate(rp):
            s = total * i / (n if closed else n - 1)
            d = amplitude * math.sin(k * s)
            out.append((p[0] + nr[i][0] * d, p[1] + nr[i][1] * d))
        return out, closed, True
    return t


def fx_pucker_bloat(amount):
    """amount > 0 : dilater (gonfle les côtés), < 0 : contracter (étoile)."""
    def t(pts, closed):
        _, total = resample(pts, closed, 2)
        n = max(8, int(total / 6.0))
        rp, _ = resample(pts, closed, n)
        cx, cy = centroid(rp)
        corners = max(3, min(12, len(pts) if len(pts) <= 12 else 6))
        out = []
        for i, p in enumerate(rp):
            phase = (i % (n / corners)) / (n / corners)
            w = math.sin(math.pi * phase)          # 0 aux sommets, 1 au milieu des côtés
            f = 1.0 + (amount / 100.0) * w
            out.append((cx + (p[0] - cx) * f, cy + (p[1] - cy) * f))
        return out, closed, True
    return t


def fx_twist(angle_deg):
    def t(pts, closed):
        _, total = resample(pts, closed, 2)
        rp, _ = resample(pts, closed, max(16, int(total / 4.0)))
        cx, cy = centroid(rp)
        rmax = max(math.hypot(p[0] - cx, p[1] - cy) for p in rp) or 1.0
        out = []
        for p in rp:
            r = math.hypot(p[0] - cx, p[1] - cy)
            a = math.radians(angle_deg) * (1.0 - r / rmax)
            dx, dy = p[0] - cx, p[1] - cy
            out.append((cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)))
        return out, closed, True
    return t


PROFILES = ["Effilé aux deux bouts", "Pointe à la fin", "Pointe au début", "Renflé au milieu"]


def width_at(profile, t):
    if profile == 0:
        return math.sin(math.pi * t) ** 0.6
    if profile == 1:
        return 1.0 - t
    if profile == 2:
        return t
    return 0.35 + 0.65 * math.sin(math.pi * t)


def variable_width(image, layer, width, profile):
    """Le contour devient une forme pleine dont l'épaisseur varie (Illustrator)."""
    path = layer.get_path()
    new_path = Gimp.Path.new(image, layer.get_name())
    built = 0
    for sid in path.get_strokes():
        pts, closed = stroke_polyline(path, sid)
        if len(pts) < 2:
            continue
        _, total = resample(pts, False, 2)
        n = max(24, int(total / 3.0))
        rp, _ = resample(pts + ([pts[0]] if closed else []), False, n)
        nr = normals(rp, False)
        left, right = [], []
        for i, p in enumerate(rp):
            w = width * width_at(profile, i / (n - 1)) / 2.0
            left.append((p[0] + nr[i][0] * w, p[1] + nr[i][1] * w))
            right.append((p[0] - nr[i][0] * w, p[1] - nr[i][1] * w))
        outline = left + right[::-1]
        new_path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER,
                                        bezier_points(outline, True, True), True)
        built += 1
    if not built:
        return None
    nl = new_vector_layer_like(image, layer, new_path, layer.get_name() + " (largeur variable)")
    nl.set_enable_fill(True)
    nl.set_fill_color(layer.get_stroke_color() if layer.get_enable_stroke() else layer.get_fill_color())
    nl.set_enable_stroke(False)
    image.remove_layer(layer)
    nl.refresh()
    return nl


# ─── Flèches (f) ────────────────────────────────────────────────────────

def add_arrows(image, layer, at_start, at_end, size_factor):
    path = layer.get_path()
    width = max(1.0, layer.get_stroke_width() if layer.get_enable_stroke() else 4.0)
    L, W = width * size_factor, width * size_factor * 0.8
    apath = Gimp.Path.new(image, layer.get_name() + " — flèches")
    count = 0
    for sid in path.get_strokes():
        pts, closed = stroke_polyline(path, sid)
        if closed or len(pts) < 2:
            continue
        ends = []
        if at_end:
            ends.append((pts[-1], pts[-2] if len(pts) > 1 else pts[0]))
        if at_start:
            ends.append((pts[0], pts[1]))
        for tip, prev in ends:
            dx, dy = tip[0] - prev[0], tip[1] - prev[1]
            l = math.hypot(dx, dy) or 1.0
            ux, uy = dx / l, dy / l
            bx, by = tip[0] - ux * L, tip[1] - uy * L
            tri = [(tip[0] + ux * width * 0.5, tip[1] + uy * width * 0.5),
                   (bx - uy * W / 2, by + ux * W / 2), (bx + uy * W / 2, by - ux * W / 2)]
            apath.stroke_new_from_points(Gimp.PathStrokeType.BEZIER, bezier_points(tri, True, False), True)
            count += 1
    if not count:
        return "Les flèches s'appliquent aux traits ouverts (lignes, chemins non fermés)."
    parent = layer.get_parent()
    pos = image.get_item_position(layer)
    group = Gimp.GroupLayer.new(image, layer.get_name() + " fléchée")
    image.insert_layer(group, parent, pos)
    image.reorder_item(layer, group, 0)
    image.insert_path(apath, None, 0)
    al = Gimp.VectorLayer.new(image, apath)
    al.set_name("Flèches")
    al.set_enable_fill(True)
    al.set_fill_color(layer.get_stroke_color())
    al.set_enable_stroke(False)
    image.insert_layer(al, group, 0)
    al.refresh()
    image.set_selected_layers([group])
    return group


# ─── Position du contour (g) ─────────────────────────────────────────────

def stroke_position(image, layer, outside):
    if not layer.get_enable_stroke():
        return "Ce calque n'a pas de contour."
    path = layer.get_path()
    parent = layer.get_parent()
    pos = image.get_item_position(layer)
    group = Gimp.GroupLayer.new(image, layer.get_name() + (" (contour extérieur)" if outside
                                                          else " (contour intérieur)"))
    image.insert_layer(group, parent, pos)

    # contour : épaisseur doublée, masqué par l'intérieur (ou l'extérieur) de la forme
    spath = path.copy()
    image.insert_path(spath, None, 0)
    s = Gimp.VectorLayer.new(image, spath)
    s.set_name("Contour")
    copy_vector_style(layer, s)
    s.set_enable_fill(False)
    s.set_stroke_width(layer.get_stroke_width() * 2.0)
    image.insert_layer(s, group, 0)
    s.refresh()
    with NoSelection(image):          # la sélection de l'utilisateur est rendue ensuite
        image.select_item(Gimp.ChannelOps.REPLACE, path)
        if outside:
            Gimp.Selection.invert(image)
        mask = s.create_mask(Gimp.AddMaskType.SELECTION)
        s.add_mask(mask)
        Gimp.Selection.none(image)

    if layer.get_enable_fill():
        fpath = path.copy()
        image.insert_path(fpath, None, 0)
        f = Gimp.VectorLayer.new(image, fpath)
        f.set_name("Fond")
        copy_vector_style(layer, f)
        f.set_enable_stroke(False)
        image.insert_layer(f, group, 0 if outside else 1)
        f.refresh()

    image.remove_layer(layer)
    image.set_selected_layers([group])
    return group


# ─── Contour au pinceau (d) ──────────────────────────────────────────────

def brush_stroke(image, layer, simulate=True, target=None, src_path=None, color=None):
    """Trace le chemin avec la brosse active dans un calque raster (target
    réutilisé lors d'une modification)."""
    path = src_path or (layer.get_path() if isinstance(layer, Gimp.VectorLayer) else None)
    if path is None:
        paths = image.get_selected_paths()
        path = paths[0] if paths else None
    if path is None:
        return "Sélectionnez une forme (calque vectoriel) ou un chemin."
    if target is None:
        raster = Gimp.Layer.new(image, "Contour au pinceau", image.get_width(), image.get_height(),
                                Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
        image.insert_layer(raster, layer.get_parent(), image.get_item_position(layer))
    else:
        raster = target
    raster.fill(Gimp.FillType.TRANSPARENT)
    if color is None and isinstance(layer, Gimp.VectorLayer) and layer.get_enable_stroke():
        color = layer.get_stroke_color()
    Gimp.context_push()
    try:
        if color is not None:
            Gimp.context_set_foreground(color)
        Gimp.context_set_stroke_method(Gimp.StrokeMethod.PAINT_METHOD)
        Gimp.context_set_paint_method("gimp-paintbrush")
        Gimp.context_set_emulate_brush_dynamics(bool(simulate))
        with NoSelection(image):
            raster.edit_stroke_item(path)
    finally:
        Gimp.context_pop()
    image.set_selected_layers([raster])
    return raster


# ─── Incrustation de dégradé (e) ─────────────────────────────────────────

def gradient_fill(image, g, angle, reverse, c1, c2):
    w, h = g.get_width(), g.get_height()
    a = math.radians(angle)
    cx, cy, r = w / 2.0, h / 2.0, (abs(w * math.cos(a)) + abs(h * math.sin(a))) / 2.0
    x1, y1 = cx - r * math.cos(a), cy - r * math.sin(a)
    x2, y2 = cx + r * math.cos(a), cy + r * math.sin(a)
    if reverse:
        x1, y1, x2, y2 = x2, y2, x1, y1
    Gimp.context_push()
    try:
        if c1 is not None:
            Gimp.context_set_foreground(c1)
        if c2 is not None:
            Gimp.context_set_background(c2)
        Gimp.context_set_gradient_fg_bg_rgb()
        with NoSelection(image):
            g.fill(Gimp.FillType.TRANSPARENT)
            g.edit_gradient_fill(Gimp.GradientType.LINEAR, 0, False, 1, 0, True, x1, y1, x2, y2)
    finally:
        Gimp.context_pop()


def gradient_overlay(image, layer, angle, reverse, c1=None, c2=None, target=None):
    ok_, x, y = layer.get_offsets()
    w, h = layer.get_width(), layer.get_height()
    if target is not None:
        g = target
        if (g.get_width(), g.get_height()) != (w, h):
            g.resize(w, h, 0, 0)
        g.set_offsets(x, y)
        gradient_fill(image, g, angle, reverse, c1, c2)
        return g
    g = Gimp.Layer.new(image, "Incrustation de dégradé", w, h, Gimp.ImageType.RGBA_IMAGE, 100,
                       Gimp.LayerMode.NORMAL)
    image.insert_layer(g, layer.get_parent(), image.get_item_position(layer))
    g.set_offsets(x, y)
    gradient_fill(image, g, angle, reverse, c1, c2)
    image.set_selected_layers([g])
    # masque d'écrêtage sur le calque du dessous (plug-in photogimp_ps)
    pdb = Gimp.get_pdb()
    proc = pdb.lookup_procedure("photogimp-clipping-toggle")
    if proc:
        cfg = proc.create_config()
        cfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
        cfg.set_property("image", image)
        cfg.set_core_object_array("drawables", [g])
        proc.run(cfg)
    return g


# ─── Fenêtre « Style de calque » (h) ─────────────────────────────────────
# Chaque effet : (clé, libellé, opération GEGL, paramètres réglables)
STYLES = [
    ("overlay", "Incrustation couleur", "gegl:color-overlay", []),
    ("inner-shadow", "Ombre interne", "gegl:inner-glow",
     [("Distance", "dist", 0, 100, 5), ("Taille", "radius", 0, 100, 8), ("Angle", "angle", -180, 180, 120)]),
    ("inner-glow", "Lueur interne", "gegl:inner-glow", [("Taille", "radius", 0, 100, 10)]),
    ("bevel", "Biseau et estampage", "gegl:bevel",
     [("Taille", "radius", 1, 100, 6), ("Profondeur", "depth", 1, 100, 20), ("Angle", "angle", -180, 180, 120)]),
    ("stroke", "Contour", "gegl:dropshadow", [("Taille", "size", 1, 100, 3)]),
    ("outer-glow", "Lueur externe", "gegl:dropshadow", [("Taille", "radius", 1, 100, 18)]),
    ("drop-shadow", "Ombre portée", "gegl:dropshadow",
     [("Distance", "dist", 0, 200, 8), ("Taille", "radius", 0, 100, 10), ("Angle", "angle", -180, 180, 120)]),
]
DEFAULT_COLORS = {"overlay": (0.85, 0.2, 0.2), "inner-shadow": (0, 0, 0), "inner-glow": (1, 1, 0.75),
                  "bevel": (1, 1, 1), "stroke": (0, 0, 0), "outer-glow": (1, 0.93, 0.6),
                  "drop-shadow": (0, 0, 0)}


def style_props(key, v, color, opacity):
    if key == "overlay":
        return {"value": color}
    if key == "inner-shadow":
        a = math.radians(v["angle"])
        return {"x": -math.cos(a) * v["dist"], "y": math.sin(a) * v["dist"], "radius": v["radius"],
                "value": color, "opacity": opacity}
    if key == "inner-glow":
        return {"x": 0.0, "y": 0.0, "radius": v["radius"], "value": color, "opacity": opacity}
    if key == "bevel":
        return {"radius": v["radius"], "depth": int(v["depth"]), "azimuth": v["angle"]}
    if key == "stroke":
        return {"x": 0.0, "y": 0.0, "radius": 0.0, "grow-radius": float(v["size"]), "color": color,
                "opacity": opacity}
    if key == "outer-glow":
        return {"x": 0.0, "y": 0.0, "radius": v["radius"], "grow-radius": 2.0, "color": color,
                "opacity": opacity}
    a = math.radians(v["angle"])
    return {"x": -math.cos(a) * v["dist"], "y": math.sin(a) * v["dist"], "radius": v["radius"],
            "color": color, "opacity": opacity}


def apply_styles(layer, chosen, keep=None):
    """Remplace les filtres de style du calque par ceux de « chosen ».
    keep : identifiants de filtres à ne pas supprimer (aperçu)."""
    keep = keep or set()
    for f in list(layer.get_filters() or []):
        if f.get_name().startswith(STYLE_PREFIX) and f.get_id() not in keep:
            f.delete()
    for key, label, op, _ in STYLES:
        if key not in chosen:
            continue
        values, color, opacity = chosen[key]
        f = Gimp.DrawableFilter.new(layer, op, STYLE_PREFIX + label)
        cfg = f.get_config()
        for k, val in style_props(key, values, color, opacity).items():
            try:
                cfg.set_property(k, val)
            except Exception:
                pass
        f.set_blend_mode(Gimp.LayerMode.NORMAL)
        f.update()
        layer.append_filter(f)


def style_to_json(chosen):
    return {k: [v, rgba(c), o] for k, (v, c, o) in chosen.items()}


def style_from_json(data):
    return {k: (v, from_rgba(c), o) for k, (v, c, o) in (data or {}).items()}


def layer_style_dialog(image, layer):
    """Fenêtre Style de calque avec aperçu en direct (comme Photoshop) :
    chaque réglage est appliqué immédiatement au calque ; Annuler rétablit
    le style d'origine."""
    GimpUi.init("chopgimp_fx")
    dialog = GimpUi.Dialog(title="Style de calque — " + layer.get_name(), role="chopgimp-layer-style",
                           modal=True)
    dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("A_ppliquer", Gtk.ResponseType.APPLY)
    dialog.add_button("_OK", Gtk.ResponseType.OK)
    box = dialog.get_content_area()
    grid = Gtk.Grid(column_spacing=10, row_spacing=6, margin=12)
    box.pack_start(grid, True, True, 0)

    present = {f.get_name()[len(STYLE_PREFIX):] for f in (layer.get_filters() or [])
               if f.get_name().startswith(STYLE_PREFIX)}
    saved = parasite_get(layer, STYLE_PARASITE) or {}
    widgets = {}
    row = 0
    for key, label, op, params in STYLES:
        mem = saved.get(key)
        check = Gtk.CheckButton(label=label)
        check.set_active(label in present)
        grid.attach(check, 0, row, 1, 1)
        col = mem[1][:3] if mem else DEFAULT_COLORS[key]
        cbtn = Gtk.ColorButton.new_with_rgba(Gdk_rgba(col))
        grid.attach(cbtn, 1, row, 1, 1)
        op_adj = Gtk.Adjustment(value=round(mem[2] * 100) if mem else 75, lower=0, upper=100,
                                step_increment=1)
        op_spin = Gtk.SpinButton(adjustment=op_adj, digits=0)
        op_spin.set_tooltip_text("Opacité (%)")
        grid.attach(op_spin, 2, row, 1, 1)
        pw = {}
        c = 3
        for plabel, pkey, lo, hi, default in params:
            lab = Gtk.Label(label=plabel)
            lab.get_style_context().add_class("dim-label")
            grid.attach(lab, c, row, 1, 1)
            value = mem[0].get(pkey, default) if mem else default
            adj = Gtk.Adjustment(value=value, lower=lo, upper=hi, step_increment=1)
            sp = Gtk.SpinButton(adjustment=adj, digits=0)
            grid.attach(sp, c + 1, row, 1, 1)
            pw[pkey] = sp
            c += 2
        widgets[key] = (check, cbtn, op_spin, pw)
        row += 1

    preview = Gtk.CheckButton(label="Aperçu")
    preview.set_active(True)
    grid.attach(preview, 0, row, 2, 1)

    def collect():
        chosen = {}
        for key, (check, cbtn, op_spin, pw) in widgets.items():
            if not check.get_active():
                continue
            rgba_ = cbtn.get_rgba()
            color = gegl_color(rgba_.red, rgba_.green, rgba_.blue)
            chosen[key] = ({k: sp.get_value() for k, sp in pw.items()}, color, op_spin.get_value() / 100.0)
        return chosen

    # L'aperçu ne doit laisser aucune trace dans l'historique : les filtres
    # d'origine sont seulement masqués pendant l'aperçu (Annuler les rend
    # tels quels, réglages faits ailleurs compris) et l'historique est gelé ;
    # OK applique le résultat en une seule étape d'annulation.
    state = {}

    def snapshot():
        state["orig"] = [f for f in (layer.get_filters() or [])
                         if f.get_name().startswith(STYLE_PREFIX)]
        state["ids"] = {f.get_id() for f in state["orig"]}
        state["vis"] = {f.get_id(): f.get_visible() for f in state["orig"]}

    def show_originals(show):
        for f in state["orig"]:
            f.set_visible(show and state["vis"][f.get_id()])

    def back_to_original():
        apply_styles(layer, {}, keep=state["ids"])
        show_originals(True)

    snapshot()
    image.undo_freeze()
    pending = [0]

    def refresh():
        pending[0] = 0
        if preview.get_active():
            show_originals(False)
            apply_styles(layer, collect(), keep=state["ids"])
        else:
            back_to_original()
        Gimp.displays_flush()
        return False

    def changed(*_):
        if pending[0]:
            GLib.source_remove(pending[0])
        pending[0] = GLib.timeout_add(120, refresh)

    for check, cbtn, op_spin, pw in widgets.values():
        check.connect("toggled", changed)
        cbtn.connect("color-set", changed)
        op_spin.connect("value-changed", changed)
        for sp in pw.values():
            sp.connect("value-changed", changed)
    preview.connect("toggled", changed)

    dialog.show_all()
    try:
        while True:
            resp = dialog.run()
            if pending[0]:
                GLib.source_remove(pending[0])
                pending[0] = 0
            back_to_original()
            image.undo_thaw()
            if resp in (Gtk.ResponseType.APPLY, Gtk.ResponseType.OK):
                final = collect()
                image.undo_group_start()
                try:
                    apply_styles(layer, final)
                    parasite_set(layer, STYLE_PARASITE, style_to_json(final))
                finally:
                    image.undo_group_end()
            Gimp.displays_flush()
            if resp != Gtk.ResponseType.APPLY:
                break
            snapshot()
            image.undo_freeze()
    finally:
        dialog.destroy()


def Gdk_rgba(rgb):
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = rgb[0], rgb[1], rgb[2], 1.0
    return c


# ─── Déclaration des procédures ─────────────────────────────────────────
TRACE = "<Image>/Layer/Effets de tracé"
TRACE_L = "<Layers>/Layers Menu/Effets de tracé"
STYLE = "<Image>/Layer/Style de calque"
STYLE_L = "<Layers>/Layers Menu/Style de calque"

PROCS = {
    "chopgimp-fx-zigzag": ("Zigzag…", [TRACE, TRACE_L],
                           [("double", "size", "Amplitude", 1, 500, 8),
                            ("int", "ridges", "Nombre de dents", 2, 400, 24),
                            ("boolean", "smooth", "Vagues arrondies", None, None, False)]),
    "chopgimp-fx-roughen": ("Rugosité…", [TRACE, TRACE_L],
                            [("double", "size", "Amplitude", 0.5, 200, 4),
                             ("double", "detail", "Détail", 1, 100, 20),
                             ("int", "seed", "Variante", 0, 99999, 1)]),
    "chopgimp-fx-wave": ("Ondulation…", [TRACE, TRACE_L],
                         [("double", "amplitude", "Amplitude", 1, 500, 10),
                          ("double", "wavelength", "Longueur d'onde", 4, 2000, 60)]),
    "chopgimp-fx-pucker": ("Contracter / Dilater…", [TRACE, TRACE_L],
                           [("double", "amount", "Contracter (−) / Dilater (+) %", -100, 100, 40)]),
    "chopgimp-fx-twist": ("Torsion…", [TRACE, TRACE_L],
                          [("double", "angle", "Angle (°)", -720, 720, 90)]),
    "chopgimp-fx-width": ("Largeur variable…", [TRACE, TRACE_L],
                          [("double", "width", "Largeur maximale", 1, 500, 16),
                           ("choice", "profile", "Profil", None, None, 0)]),
    "chopgimp-fx-arrows": ("Flèches…", [TRACE, TRACE_L],
                           [("boolean", "at-end", "Flèche à la fin", None, None, True),
                            ("boolean", "at-start", "Flèche au début", None, None, False),
                            ("double", "size", "Taille (× épaisseur)", 1, 20, 4)]),
    "chopgimp-fx-stroke-inside": ("Contour à l'intérieur", [TRACE, TRACE_L], []),
    "chopgimp-fx-stroke-outside": ("Contour à l'extérieur", [TRACE, TRACE_L], []),
    "chopgimp-fx-brush-stroke": ("Contour au pinceau (brosse active)…", [TRACE, TRACE_L],
                                 [("boolean", "simulate", "Simuler la pression (trait effilé)",
                                   None, None, True)]),
    "chopgimp-fx-gradient-overlay": ("Incrustation de dégradé…", [STYLE, STYLE_L],
                                     [("double", "angle", "Angle (°)", -180, 180, 90),
                                      ("boolean", "reverse", "Inverser", None, None, False),
                                      ("color", "color1", "Couleur de départ", None, None, (0, 0, 0)),
                                      ("color", "color2", "Couleur d'arrivée", None, None, (1, 1, 1))]),
    "chopgimp-layer-style": ("Style de calque (fenêtre)…", [STYLE, STYLE_L], []),
    "chopgimp-fx-edit": ("Modifier l'effet…", [TRACE, TRACE_L, STYLE, STYLE_L], []),
    "chopgimp-fx-remove": ("Supprimer l'effet", [TRACE, TRACE_L, STYLE, STYLE_L], []),
    "chopgimp-content-aware-fill": ("Remplir d'après le contenu", ["<Image>/Edit"], []),
}
VECTOR_FX = {"chopgimp-fx-zigzag", "chopgimp-fx-roughen", "chopgimp-fx-wave", "chopgimp-fx-pucker",
             "chopgimp-fx-twist", "chopgimp-fx-width", "chopgimp-fx-arrows",
             "chopgimp-fx-stroke-inside", "chopgimp-fx-stroke-outside"}
STROKE_SIDES = [("chopgimp-fx-stroke-inside", "Contour à l'intérieur"),
                ("chopgimp-fx-stroke-outside", "Contour à l'extérieur")]


def store_args(name, A):
    out = {}
    for kind, key, *_ in PROCS[name][2]:
        v = A(key)
        out[key] = rgba(v) if kind == "color" else v
    return out


def load_args(name, cfg, stored):
    for kind, key, *_ in PROCS[name][2]:
        if key in stored:
            v = stored[key]
            cfg.set_property(key, from_rgba(v) if kind == "color" else v)


def apply_vector_fx(image, layer, name, A):
    """Applique un effet de tracé et mémorise forme d'origine + réglages dans le résultat."""
    src = capture_source(layer)
    res = None
    if name == "chopgimp-fx-zigzag":
        res = replace_shape(image, layer, fx_zigzag(A("size"), A("ridges"), A("smooth")), "zigzag")
    elif name == "chopgimp-fx-roughen":
        res = replace_shape(image, layer, fx_roughen(A("size"), A("detail"), A("seed")), "rugosité")
    elif name == "chopgimp-fx-wave":
        res = replace_shape(image, layer, fx_wave(A("amplitude"), A("wavelength")), "ondulation")
    elif name == "chopgimp-fx-pucker":
        res = replace_shape(image, layer, fx_pucker_bloat(A("amount")), "contracter")
    elif name == "chopgimp-fx-twist":
        res = replace_shape(image, layer, fx_twist(A("angle")), "torsion")
    elif name == "chopgimp-fx-width":
        res = variable_width(image, layer, A("width"), int(A("profile")))
    elif name == "chopgimp-fx-arrows":
        res = add_arrows(image, layer, A("at-start"), A("at-end"), A("size"))
    elif name == "chopgimp-fx-stroke-inside":
        res = stroke_position(image, layer, outside=False)
    elif name == "chopgimp-fx-stroke-outside":
        res = stroke_position(image, layer, outside=True)
    if res is None:
        return "L'effet n'a rien produit (forme vide ?)."
    if isinstance(res, str):
        return res
    parasite_set(res, FX_PARASITE, {"proc": name, "args": store_args(name, A), "src": src})
    return res


def choose_stroke_side(current):
    GimpUi.init("chopgimp_fx")
    dialog = GimpUi.Dialog(title="Position du contour", role="chopgimp-stroke-side", modal=True)
    dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("_OK", Gtk.ResponseType.OK)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=12)
    dialog.get_content_area().pack_start(box, True, True, 0)
    group, buttons = None, {}
    for proc, label in STROKE_SIDES:
        rb = Gtk.RadioButton.new_with_label_from_widget(group, label)
        group = group or rb
        rb.set_active(proc == current)
        box.pack_start(rb, False, False, 0)
        buttons[proc] = rb
    dialog.show_all()
    resp = dialog.run()
    choice = next((p for p, rb in buttons.items() if rb.get_active()), current)
    dialog.destroy()
    return choice if resp == Gtk.ResponseType.OK else None


def find_layer(image, tattoo):
    if not tattoo:
        return None
    try:
        return image.get_layer_by_tattoo(tattoo)
    except Exception:
        return None


class ChopGimpFx(Gimp.PlugIn):

    def do_query_procedures(self):
        return list(PROCS)

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        label, paths, args = PROCS[name]
        p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        p.set_image_types("*")
        p.set_attribution(AUTHOR, AUTHOR, YEAR)
        p.set_menu_label(label)
        for path in paths:
            p.add_menu_path(path)
        p.set_documentation(label.rstrip("…"), label.rstrip("…"), name)
        p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                               Gimp.ProcedureSensitivityMask.DRAWABLES)
        for kind, key, nick, lo, hi, default in args:
            if kind == "double":
                p.add_double_argument(key, nick, nick, lo, hi, default, GObject.ParamFlags.READWRITE)
            elif kind == "int":
                p.add_int_argument(key, nick, nick, lo, hi, default, GObject.ParamFlags.READWRITE)
            elif kind == "boolean":
                p.add_boolean_argument(key, nick, nick, default, GObject.ParamFlags.READWRITE)
            elif kind == "color":
                p.add_color_argument(key, nick, nick, False, gegl_color(*default),
                                     GObject.ParamFlags.READWRITE)
            elif kind == "choice":
                ch = Gimp.Choice.new()
                for i, label_ in enumerate(PROFILES):
                    ch.add(str(i), i, label_, "")
                p.add_choice_argument(key, nick, nick, ch, "0", GObject.ParamFlags.READWRITE)
        return p

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        layers = [d for d in drawables if isinstance(d, Gimp.Layer)]
        if not layers:
            return fail(procedure, "Sélectionnez un calque.")
        cancel = procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())

        if name == "chopgimp-content-aware-fill":
            return self.content_aware_fill(procedure, image, layers)

        if name in ("chopgimp-fx-edit", "chopgimp-fx-remove"):
            if name == "chopgimp-fx-edit":
                # (les dialogues d'abord, l'étape d'annulation ensuite)
                msg = self.edit_effect(image, layers[0], run_mode)
            else:
                image.undo_group_start()
                try:
                    msg = self.remove_effect(image, layers[0])
                finally:
                    image.undo_group_end()
            Gimp.displays_flush()
            if msg == "cancel":
                return cancel
            return fail(procedure, msg) if msg else ok(procedure)

        if run_mode == Gimp.RunMode.INTERACTIVE and PROCS[name][2]:
            if name == "chopgimp-fx-gradient-overlay":
                config.set_property("color1", Gimp.context_get_foreground())
                config.set_property("color2", Gimp.context_get_background())
            GimpUi.init("chopgimp_fx")
            dialog = GimpUi.ProcedureDialog.new(procedure, config, PROCS[name][0].rstrip("…"))
            dialog.fill(None)
            if not dialog.run():
                dialog.destroy()
                return cancel
            dialog.destroy()

        def A(k):
            return config.get_property(k)

        if name == "chopgimp-layer-style" and run_mode == Gimp.RunMode.INTERACTIVE:
            layer_style_dialog(image, layers[0])      # gère son historique
            return ok(procedure)

        image.undo_group_start()
        try:
            if name == "chopgimp-layer-style":
                chosen = {"drop-shadow": ({"dist": 8, "radius": 10, "angle": 120},
                                          gegl_color(0, 0, 0), 0.75)}
                apply_styles(layers[0], chosen)
                parasite_set(layers[0], STYLE_PARASITE, style_to_json(chosen))
                return ok(procedure)
            if name == "chopgimp-fx-gradient-overlay":
                g = gradient_overlay(image, layers[0], A("angle"), A("reverse"), A("color1"), A("color2"))
                parasite_set(g, FX_PARASITE, {"proc": name, "args": store_args(name, A),
                                              "src-tattoo": layers[0].get_tattoo()})
                return ok(procedure)
            if name == "chopgimp-fx-brush-stroke":
                layer = layers[0]
                vec = isinstance(layer, Gimp.VectorLayer)
                paths = image.get_selected_paths()
                res = brush_stroke(image, layer, A("simulate"))
                if isinstance(res, str):
                    return fail(procedure, res)
                src = capture_source(layer) if vec else capture_source(None, paths[0])
                parasite_set(res, FX_PARASITE, {"proc": name, "args": store_args(name, A), "src": src,
                                                "src-tattoo": layer.get_tattoo() if vec else 0})
                return ok(procedure)

            vlayers = selected_vector_layers(layers)
            if not vlayers:
                return fail(procedure, "Sélectionnez une forme (calque vectoriel).")
            for layer in vlayers:
                res = apply_vector_fx(image, layer, name, A)
                if isinstance(res, str):
                    return fail(procedure, res)
        finally:
            image.undo_group_end()
            Gimp.displays_flush()
        return ok(procedure)

    # Calque > Effets de tracé > Modifier l'effet… : régénère le résultat à
    # partir de la forme d'origine mémorisée, avec de nouveaux réglages.
    def edit_effect(self, image, layer, run_mode):
        interactive = run_mode == Gimp.RunMode.INTERACTIVE
        info = parasite_get(layer, FX_PARASITE)
        if not info:
            styled = any(f.get_name().startswith(STYLE_PREFIX) for f in (layer.get_filters() or []))
            if styled and interactive:
                layer_style_dialog(image, layer)
                return None
            return ("Ce calque n'a pas d'effet modifiable (effet de tracé, contour au pinceau "
                    "ou incrustation de dégradé).")
        target = info["proc"]
        if target in ("chopgimp-fx-stroke-inside", "chopgimp-fx-stroke-outside"):
            if interactive:
                target = choose_stroke_side(target)
                if target is None:
                    return "cancel"
            A = None
        else:
            proc = Gimp.get_pdb().lookup_procedure(target)
            cfg = proc.create_config()
            load_args(target, cfg, info.get("args", {}))
            if interactive and PROCS[target][2]:
                GimpUi.init("chopgimp_fx")
                dlg = GimpUi.ProcedureDialog.new(proc, cfg, "Modifier — " + PROCS[target][0].rstrip("…"))
                dlg.fill(None)
                accepted = dlg.run()
                dlg.destroy()
                if not accepted:
                    return "cancel"
            A = cfg.get_property

        # les boîtes de dialogue sont fermées : une seule étape d'annulation
        image.undo_group_start()
        try:
            return self.apply_edit(image, layer, info, target, A)
        finally:
            image.undo_group_end()

    def apply_edit(self, image, layer, info, target, A):
        if target in VECTOR_FX:
            src = rebuild_source(image, layer, info["src"])
            res = apply_vector_fx(image, src, target, A)
            if isinstance(res, str):
                image.remove_layer(src)
                return res
            image.remove_layer(layer)
            image.set_selected_layers([res])
            return None

        source = find_layer(image, info.get("src-tattoo"))
        if target == "chopgimp-fx-brush-stroke":
            if isinstance(source, Gimp.VectorLayer):
                path, tmp, color = source.get_path(), None, None
                info["src"] = capture_source(source)
            else:
                source = None
                path = tmp = source_path(image, info["src"])
                c = info["src"].get("stroke-color")
                color = from_rgba(c) if c and info["src"].get("stroke") else None
            res = brush_stroke(image, source, A("simulate"), target=layer, src_path=path, color=color)
            if tmp is not None:
                image.remove_path(tmp)
            if isinstance(res, str):
                return res
        elif target == "chopgimp-fx-gradient-overlay":
            gradient_overlay(image, source or layer, A("angle"), A("reverse"), A("color1"), A("color2"),
                             target=layer)
        info["args"] = store_args(target, A)
        parasite_set(layer, FX_PARASITE, info)
        image.set_selected_layers([layer])
        return None

    # Calque > Effets de tracé > Supprimer l'effet : rend la forme d'origine.
    def remove_effect(self, image, layer):
        info = parasite_get(layer, FX_PARASITE)
        if info:
            if info["proc"] in VECTOR_FX:
                src = rebuild_source(image, layer, info["src"])
                image.remove_layer(layer)
                image.set_selected_layers([src])
            else:
                source = find_layer(image, info.get("src-tattoo"))
                image.remove_layer(layer)
                if source is not None:
                    image.set_selected_layers([source])
            return None
        if any(f.get_name().startswith(STYLE_PREFIX) for f in (layer.get_filters() or [])):
            apply_styles(layer, {})
            try:
                layer.detach_parasite(STYLE_PARASITE)
            except Exception:
                pass
            return None
        return "Ce calque n'a pas d'effet à supprimer."

    # Édition > Remplir d'après le contenu (Maj+F5) : la zone sélectionnée est
    # reconstruite à partir de son entourage (moteur Resynthesizer).
    def content_aware_fill(self, procedure, image, layers):
        if Gimp.Selection.is_empty(image):
            return fail(procedure, "Sélectionnez d'abord la zone à remplir (lasso, rectangle…).")
        heal = Gimp.get_pdb().lookup_procedure("plug-in-heal-selection")
        if heal is None:
            return fail(procedure, "Le module Resynthesizer n'est pas installé.")
        cfg = heal.create_config()
        args = [a.name for a in heal.get_arguments()]
        cfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
        cfg.set_property("image", image)
        cfg.set_core_object_array("drawables", [layers[0]])
        extra = [a for a in args if a not in ("run-mode", "image", "drawables")]
        defaults = [50, 0, 0]      # largeur d'échantillonnage, tout autour, ordre aléatoire
        for name_, val in zip(extra, defaults):
            try:
                cfg.set_property(name_, val)
            except TypeError:
                cfg.set_property(name_, str(val))
        res = heal.run(cfg)
        Gimp.displays_flush()
        if res.index(0) != Gimp.PDBStatusType.SUCCESS:
            return fail(procedure, "Le remplissage d'après le contenu a échoué.")
        return ok(procedure)


if __name__ == "__main__":
    Gimp.main(ChopGimpFx.__gtype__, sys.argv)

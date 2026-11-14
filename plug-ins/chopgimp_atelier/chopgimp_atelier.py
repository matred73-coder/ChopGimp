#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — atelier de dessin et de BD (étape « Dessin III »).

Calque > Nouveau calque de croquis       crayonné bleu non imprimable (masqué
                                         à l'export), Affichage > Croquis pour
                                         tout montrer / cacher
Calque > Aplats sous l'encrage…          une couleur par zone fermée du dessin,
                                         sur un calque sous l'encrage
BD > Cases…                              planche découpée en cases (gouttières)
BD > Bulle                               bulle vectorielle + queue + texte centré
BD > Trame…                              demi-teintes non destructives
BD > Lignes de vitesse… / concentriques…  traits vectoriels
Calque > Effets de tracé > Gomme vectorielle   retire la sélection d'une forme
Affichage > Guides de perspective…       1, 2 ou 3 points de fuite (calque
                                         assistant masqué à l'export)
Couleurs > Harmonies…                    complémentaire, triade, analogues,
                                         tétrade de la couleur de premier plan
Fenêtres > Références…                   images de référence épinglées
Fichier > Exporter le timelapse…         vidéo de l'enregistrement en accéléré
"""
import colorsys
import math
import os
import random
import sys

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gegl", "0.4")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gimp, GimpUi, Gegl, GLib, GdkPixbuf, Gtk

from chopgimp_common import (ok, fail, srgb as color, walk_layers, pdb_call,
                             copy_vector_style, remove_layer_and_paths)

BD = "<Image>/Filters/BD"
PROCS = {
    "chopgimp-sketch-layer": ("Nouveau calque de croquis", "<Image>/Layer"),
    "chopgimp-sketch-toggle": ("Croquis : afficher / masquer", "<Image>/View"),
    "chopgimp-flats": ("Aplats sous l'encrage…", "<Image>/Layer"),
    "chopgimp-comic-panels": ("Cases…", BD),
    "chopgimp-comic-balloon": ("Bulle", BD),
    "chopgimp-screentone": ("Trame (demi-teintes)…", BD),
    "chopgimp-speed-lines": ("Lignes de vitesse…", BD),
    "chopgimp-focus-lines": ("Lignes concentriques…", BD),
    "chopgimp-vector-eraser": ("Gomme vectorielle (retirer la sélection)", "<Image>/Layer/Effets de tracé"),
    "chopgimp-perspective-guides": ("Guides de perspective…", "<Image>/View"),
    "chopgimp-harmonies": ("Harmonies de couleurs…", "<Image>/Colors"),
    "chopgimp-references": ("Références…", "<Image>/Windows"),
    "chopgimp-timelapse-export": ("Exporter le timelapse…", "<Image>/File/Export"),
}
SKETCH = "chopgimp-sketch"


def insert_top(image, layer):
    sel = image.get_selected_layers()
    parent = sel[0].get_parent() if sel else None
    pos = image.get_item_position(sel[0]) if sel else 0
    image.insert_layer(layer, parent, pos)


def mark_sketch(layer):
    layer.attach_parasite(Gimp.Parasite.new(SKETCH, Gimp.PARASITE_PERSISTENT, [1]))


def is_sketch(layer):
    return layer.get_parasite(SKETCH) is not None


def vector_from_points(image, name, strokes, fill=None, stroke=None, width=2.0, closed=True):
    """strokes : listes de points (x, y) ; segments droits."""
    path = Gimp.Path.new(image, name)
    for pts in strokes:
        flat = []
        for x, y in pts:
            flat += [x, y, x, y, x, y]
        path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER, flat, closed)
    image.insert_path(path, None, -1)
    vl = Gimp.VectorLayer.new(image, path)
    vl.set_name(name)
    vl.set_enable_fill(fill is not None)
    if fill is not None:
        vl.set_fill_color(fill)
    vl.set_enable_stroke(stroke is not None)
    if stroke is not None:
        vl.set_stroke_color(stroke)
        vl.set_stroke_width(width)
    return vl


def path_boolean(image, paths, op):
    """Pathfinder de ChopGimp : 0 union, 1 le premier moins les autres. → chemin
    inséré dans l'image, ou None."""
    res = pdb_call("chopgimp-path-boolean", paths=paths, operation=op)
    if res is None:
        return None
    path = res.index(1)
    if path is None:
        return None
    try:
        image.insert_path(path, None, -1)
    except Exception:
        pass
    return path


def spin_dialog(title, rows):
    """rows : [(clé, libellé, mini, maxi, défaut, pas)] → dict ou None"""
    GimpUi.init("chopgimp_atelier")
    dlg = GimpUi.Dialog(title=title, role="chopgimp-atelier", modal=True)
    dlg.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dlg.add_button("_OK", Gtk.ResponseType.OK)
    grid = Gtk.Grid(column_spacing=10, row_spacing=6, margin=12)
    dlg.get_content_area().pack_start(grid, True, True, 0)
    spins = {}
    for i, (k, lab, lo, hi, val, step) in enumerate(rows):
        grid.attach(Gtk.Label(label=lab, xalign=0), 0, i, 1, 1)
        sp = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=val, lower=lo, upper=hi, step_increment=step),
                            digits=0 if step >= 1 else 2)
        grid.attach(sp, 1, i, 1, 1)
        spins[k] = sp
    dlg.show_all()
    resp = dlg.run()
    out = {k: s.get_value() for k, s in spins.items()}
    dlg.destroy()
    return out if resp == Gtk.ResponseType.OK else None


def defaults(rows):
    return {k: val for k, _, _, _, val, _ in rows}


# ─── croquis ────────────────────────────────────────────────────────────

def sketch_layer(image):
    w, h = image.get_width(), image.get_height()
    layer = Gimp.Layer.new(image, "✎ Croquis", w, h, Gimp.ImageType.RGBA_IMAGE, 60, Gimp.LayerMode.NORMAL)
    insert_top(image, layer)
    layer.fill(Gimp.FillType.TRANSPARENT)
    layer.set_color_tag(Gimp.ColorTag.BLUE)
    mark_sketch(layer)
    # crayonné « bleu non photo » : ce qu'on y dessine apparaît en bleu clair
    f = Gimp.DrawableFilter.new(layer, "gimp:colorize", "Croquis bleu")
    cfg = f.get_config()
    for k, v in (("hue", 0.58), ("saturation", 0.7), ("lightness", 0.35)):
        try:
            cfg.set_property(k, v)
        except (TypeError, ValueError):
            pass
    f.update()
    layer.append_filter(f)
    image.set_selected_layers([layer])
    return None


def sketch_toggle(image):
    sketches = [l for l in walk_layers(image.get_layers()) if is_sketch(l)]
    if not sketches:
        return "Aucun calque de croquis (Calque > Nouveau calque de croquis)."
    show = not any(l.get_visible() for l in sketches)
    for l in sketches:
        l.set_visible(show)
    return None


# ─── aplats ─────────────────────────────────────────────────────────────

def flats(image, ink, gap, interactive):
    """Une couleur par zone fermée de l'encrage (sélection contiguë sur le
    calque d'encrage, agrandie de « gap » px pour passer sous le trait)."""
    w, h = image.get_width(), image.get_height()
    layer = Gimp.Layer.new(image, "Aplats", w, h, Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, ink.get_parent(), image.get_item_position(ink) + 1)
    layer.fill(Gimp.FillType.TRANSPARENT)
    _, ox, oy = ink.get_offsets()
    iw, ih = ink.get_width(), ink.get_height()
    # encrage lu une seule fois (au lieu d'un pixel à la fois)
    ink_px = ink.get_buffer().get(Gegl.Rectangle.new(0, 0, iw, ih), 1.0, "Y'A u8",
                                  Gegl.AbyssPolicy.NONE)
    step = max(8, int(min(w, h) / 60))
    xs = list(range(step // 2, w, step))
    ys = list(range(step // 2, h, step))
    # points d'échantillonnage déjà couverts : par un aplat (sélection
    # agrandie remplie) ou par le fond déjà reconnu
    visited = set()
    sel_chan = image.get_selection()

    def mark_selection():
        _ok, _non_empty, x1, y1, x2, y2 = Gimp.Selection.bounds(image)
        if x2 <= x1 or y2 <= y1:
            return
        data = sel_chan.get_buffer().get(Gegl.Rectangle.new(x1, y1, x2 - x1, y2 - y1), 1.0, "Y u8",
                                         Gegl.AbyssPolicy.NONE)
        bw = x2 - x1
        for yy in ys:
            if yy < y1 or yy >= y2:
                continue
            row = (yy - y1) * bw
            for xx in xs:
                if x1 <= xx < x2 and data[row + xx - x1] > 0:
                    visited.add((xx, yy))

    rnd = random.Random(7)
    saved = None
    if not Gimp.Selection.is_empty(image):        # sélection de l'utilisateur rendue à la fin
        saved = Gimp.Selection.save(image)
    Gimp.context_push()
    Gimp.progress_init("Aplats…")
    filled = 0
    try:
        Gimp.context_set_sample_threshold(0.35)
        Gimp.context_set_sample_merged(False)
        Gimp.context_set_sample_transparent(True)
        Gimp.context_set_antialias(False)
        Gimp.context_set_feather(False)
        for y in ys:
            Gimp.progress_update(y / float(h))
            for x in xs:
                if not (0 <= x - ox < iw and 0 <= y - oy < ih):
                    continue
                i = ((y - oy) * iw + (x - ox)) * 2
                if ink_px[i + 1] > 128 and ink_px[i] < 128:      # pixel d'encre : pas une zone
                    continue
                if (x, y) in visited:
                    continue
                image.select_contiguous_color(Gimp.ChannelOps.REPLACE, ink, x, y)
                if Gimp.Selection.is_empty(image):
                    continue
                ok_, _non_empty, x1, y1, x2, y2 = Gimp.Selection.bounds(image)
                if (x2 - x1) * (y2 - y1) > 0.9 * w * h:   # le fond autour du dessin
                    mark_selection()
                    continue
                if gap > 0:
                    Gimp.Selection.grow(image, int(gap))
                hue = rnd.random()
                r, g, b = colorsys.hsv_to_rgb(hue, 0.45, 0.95)
                Gimp.context_set_foreground(color(r, g, b))
                layer.edit_fill(Gimp.FillType.FOREGROUND)
                mark_selection()
                filled += 1
    finally:
        Gimp.context_pop()
        Gimp.progress_end()
        if saved is not None:
            image.select_item(Gimp.ChannelOps.REPLACE, saved)
            image.remove_channel(saved)
        else:
            Gimp.Selection.none(image)
    if not filled:
        image.remove_layer(layer)
        return "Aucune zone fermée trouvée sur le calque d'encrage."
    if interactive:
        Gimp.message("%d aplats créés sous « %s » (Baguette magique sur « Aplats » pour sélectionner "
                     "une zone)." % (filled, ink.get_name()))
    return None


# ─── BD ─────────────────────────────────────────────────────────────────

PANELS = [("rows", "Rangées", 1, 10, 3, 1), ("cols", "Colonnes", 1, 10, 2, 1),
          ("margin", "Marge (px)", 0, 500, 60, 1), ("gutter", "Gouttière (px)", 0, 200, 24, 1),
          ("border", "Trait (px)", 1, 30, 4, 1)]


def comic_panels(image, o):
    w, h = image.get_width(), image.get_height()
    rows, cols = int(o["rows"]), int(o["cols"])
    m, g = o["margin"], o["gutter"]
    cw = (w - 2 * m - (cols - 1) * g) / cols
    ch = (h - 2 * m - (rows - 1) * g) / rows
    if cw < 10 or ch < 10:
        return "Les cases seraient trop petites."
    group = Gimp.GroupLayer.new(image, "Cases")
    insert_top(image, group)
    n = 0
    for r in range(rows):
        for c in range(cols):
            x, y = m + c * (cw + g), m + r * (ch + g)
            n += 1
            vl = vector_from_points(image, "Case %d" % n,
                                    [[(x, y), (x + cw, y), (x + cw, y + ch), (x, y + ch)]],
                                    fill=color(1, 1, 1), stroke=color(0, 0, 0), width=o["border"])
            image.insert_layer(vl, group, 0)
            vl.refresh()
    return None


def comic_balloon(image):
    w, h = image.get_width(), image.get_height()
    ok_, non_empty, x1, y1, x2, y2 = Gimp.Selection.bounds(image)
    if not (ok_ and non_empty):
        bw, bh = w * 0.35, h * 0.18
        x1, y1 = (w - bw) / 2, h * 0.15
        x2, y2 = x1 + bw, y1 + bh
    cx, cy, rx, ry = (x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) / 2, (y2 - y1) / 2
    # ellipse de Bézier et queue (triangle) en bas à gauche, réunies (union)
    ell_path = Gimp.Path.new(image, "Bulle (ellipse)")
    ell_path.bezier_stroke_new_ellipse(cx, cy, rx, ry, 0.0)
    image.insert_path(ell_path, None, -1)
    tail_path = Gimp.Path.new(image, "Bulle (queue)")
    tx, ty = cx - rx * 0.35, cy + ry * 0.8
    tail = [(tx - rx * 0.14, ty), (tx + rx * 0.14, ty), (cx - rx * 0.8, cy + ry * 1.9)]
    flat = []
    for x, y in tail:
        flat += [x, y, x, y, x, y]
    tail_path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER, flat, True)
    image.insert_path(tail_path, None, -1)
    path = path_boolean(image, [ell_path, tail_path], 0) or ell_path
    if path is not ell_path:
        image.remove_path(ell_path)
        image.remove_path(tail_path)
        path.set_name("Bulle")
    else:                               # union indisponible : ellipse seule
        image.remove_path(tail_path)
    vl = Gimp.VectorLayer.new(image, path)
    vl.set_name("Bulle")
    vl.set_enable_fill(True)
    vl.set_fill_color(color(1, 1, 1))
    vl.set_enable_stroke(True)
    vl.set_stroke_color(color(0, 0, 0))
    vl.set_stroke_width(max(2.0, min(w, h) / 300.0))
    insert_top(image, vl)
    vl.refresh()
    size = max(10.0, ry * 0.45)
    tl = Gimp.TextLayer.new(image, "Texte", Gimp.Font.get_by_name("Sans-serif"), size, Gimp.Unit.pixel())
    image.insert_layer(tl, vl.get_parent(), image.get_item_position(vl))
    tl.set_justification(Gimp.TextJustification.CENTER)
    tl.set_color(color(0, 0, 0))
    tl.set_offsets(int(cx - tl.get_width() / 2), int(cy - tl.get_height() / 2))
    Gimp.Selection.none(image)
    image.set_selected_layers([tl])
    return None


def screentone(image, drawables, o):
    for d in drawables:
        f = Gimp.DrawableFilter.new(d, "gegl:newsprint", "Trame")
        cfg = f.get_config()
        for k, v in (("period", float(o["period"])), ("angle", float(o["angle"])),
                     ("color-model", 0)):
            try:
                cfg.set_property(k, v)
            except (TypeError, ValueError):
                pass
        f.update()
        d.append_filter(f)
    return None


def speed_lines(image, o, focus):
    w, h = image.get_width(), image.get_height()
    ok_, non_empty, x1, y1, x2, y2 = Gimp.Selection.bounds(image)
    cx, cy = ((x1 + x2) / 2, (y1 + y2) / 2) if (ok_ and non_empty) else (w / 2, h / 2)
    rnd = random.Random(3)
    n, thick = int(o["count"]), o["thickness"]
    strokes = []
    if focus:
        r_out = math.hypot(w, h)
        r_in = o["inner"] * min(w, h) / 200.0
        for i in range(n):
            a = 2 * math.pi * i / n + rnd.uniform(-0.4, 0.4) * math.pi / n
            r0 = r_in * rnd.uniform(0.9, 1.5)
            da = thick / max(r_out, 1) * rnd.uniform(0.6, 1.6)
            strokes.append([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
                            (cx + r_out * math.cos(a - da * 40), cy + r_out * math.sin(a - da * 40)),
                            (cx + r_out * math.cos(a + da * 40), cy + r_out * math.sin(a + da * 40))])
        name = "Lignes concentriques"
    else:
        ang = math.radians(o["angle"])
        dx, dy = math.cos(ang), math.sin(ang)
        nx, ny = -dy, dx
        span = math.hypot(w, h)
        for i in range(n):
            t = rnd.uniform(-span / 2, span / 2)
            L = rnd.uniform(0.15, 0.6) * span
            s = rnd.uniform(-span / 2, span / 2)
            bx, by = cx + nx * t + dx * s, cy + ny * t + dy * s
            th = thick * rnd.uniform(0.4, 1.2)
            strokes.append([(bx, by), (bx + dx * L + nx * th, by + dy * L + ny * th),
                            (bx + dx * L - nx * th, by + dy * L - ny * th)])
        name = "Lignes de vitesse"
    vl = vector_from_points(image, name, strokes, fill=color(0, 0, 0))
    insert_top(image, vl)
    vl.refresh()
    return None


# ─── gomme vectorielle ──────────────────────────────────────────────────

def vector_eraser(image, layers):
    vls = [l for l in layers if isinstance(l, Gimp.VectorLayer)]
    if not vls:
        return "Sélectionnez une forme (calque vectoriel)."
    if Gimp.Selection.is_empty(image):
        return "Sélectionnez d'abord la partie à effacer."
    before = set(p.get_id() for p in image.get_paths())
    proc = Gimp.get_pdb().lookup_procedure("plug-in-sel2path")
    if proc is None:
        return "Conversion de la sélection en chemin indisponible."
    cfg = proc.create_config()
    cfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    cfg.set_property("image", image)
    proc.run(cfg)
    new = [p for p in image.get_paths() if p.get_id() not in before]
    if not new:
        return "La sélection n'a pas pu être convertie en chemin."
    sel_path = new[0]
    for vl in vls:
        cut = path_boolean(image, [vl.get_path(), sel_path], 1)
        if cut is None:
            continue
        name = vl.get_name()
        cut.set_name(name)
        nv = Gimp.VectorLayer.new(image, cut)
        image.insert_layer(nv, vl.get_parent(), image.get_item_position(vl))
        copy_vector_style(vl, nv)
        nv.refresh()
        remove_layer_and_paths(image, vl)
        nv.set_name(name)
    image.remove_path(sel_path)
    Gimp.Selection.none(image)
    return None


# ─── perspective ────────────────────────────────────────────────────────

def perspective_guides(image, o):
    w, h = image.get_width(), image.get_height()
    n = int(o["points"])
    horizon = h * o["horizon"] / 100.0
    vps = {1: [(w / 2, horizon)],
           2: [(-w * 0.2, horizon), (w * 1.2, horizon)],
           3: [(-w * 0.2, horizon), (w * 1.2, horizon), (w / 2, h * 2.2)]}[n]
    strokes = [[(0, horizon), (w, horizon)]]
    R = math.hypot(w, h) * 2
    for vx, vy in vps:
        for i in range(int(o["lines"])):
            a = 2 * math.pi * i / o["lines"]
            strokes.append([(vx, vy), (vx + R * math.cos(a), vy + R * math.sin(a))])
    vl = vector_from_points(image, "⟂ Perspective (%d point%s)" % (n, "s" if n > 1 else ""), strokes,
                            stroke=color(0.2, 0.6, 1.0), width=1.0, closed=False)
    insert_top(image, vl)
    vl.refresh()
    vl.set_opacity(50)
    vl.set_lock_content(True)
    mark_sketch(vl)
    return None


# ─── harmonies ──────────────────────────────────────────────────────────

def harmonies():
    fg = Gimp.context_get_foreground()
    r, g, b, _ = fg.get_rgba_with_space(None)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    schemes = [("Complémentaire", [0, 0.5]), ("Triade", [0, 1 / 3, 2 / 3]),
               ("Analogues", [-1 / 12, 0, 1 / 12]), ("Tétrade", [0, 0.25, 0.5, 0.75]),
               ("Complémentaires adjacentes", [0, 5 / 12, 7 / 12])]
    GimpUi.init("chopgimp_atelier")
    dlg = GimpUi.Dialog(title="Harmonies de couleurs", role="chopgimp-harmonies", modal=True)
    dlg.add_button("_Fermer", Gtk.ResponseType.CLOSE)
    dlg.add_button("Enregistrer en _palette", 1)
    grid = Gtk.Grid(column_spacing=6, row_spacing=6, margin=12)
    dlg.get_content_area().pack_start(grid, True, True, 0)
    all_colors = []
    for row, (name, offs) in enumerate(schemes):
        grid.attach(Gtk.Label(label=name, xalign=0), 0, row, 1, 1)
        for c, off in enumerate(offs):
            rr, gg, bb = colorsys.hsv_to_rgb((h + off) % 1.0, s, v)
            area = GimpUi.ColorArea.new(color(rr, gg, bb), GimpUi.ColorAreaType.FLAT, 0)
            area.set_size_request(48, 32)
            area.set_tooltip_text("#%02x%02x%02x" % (int(rr * 255), int(gg * 255), int(bb * 255)))
            grid.attach(area, c + 1, row, 1, 1)
            all_colors.append((name, rr, gg, bb))
    grid.attach(Gtk.Label(label="Couleur de base : la couleur de premier plan.", xalign=0),
                0, len(schemes), 5, 1)
    dlg.show_all()
    resp = dlg.run()
    dlg.destroy()
    if resp == 1:
        pal = Gimp.Palette.new("Harmonies — #%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255)))
        for name, rr, gg, bb in all_colors:
            pal.add_entry(name, color(rr, gg, bb))
        Gimp.message("Palette « %s » créée (panneau Palettes)." % pal.get_name())
    return None


# ─── références ─────────────────────────────────────────────────────────

def references():
    GimpUi.init("chopgimp_atelier")
    win = Gtk.Window(title="Références")
    win.set_default_size(360, 480)
    win.set_keep_above(True)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    win.add(box)
    bar = Gtk.Box(spacing=4)
    add = Gtk.Button(label="Ajouter une image…")
    bar.pack_start(add, False, False, 0)
    box.pack_start(bar, False, False, 4)
    nb = Gtk.Notebook(scrollable=True)
    box.pack_start(nb, True, True, 0)

    def add_image(path):
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file(path)
        except GLib.Error:
            return
        img = Gtk.Image()
        sw = Gtk.ScrolledWindow()
        sw.add(img)

        def fit(widget, alloc):
            k = min(alloc.width / pb.get_width(), alloc.height / pb.get_height(), 1.0)
            img.set_from_pixbuf(pb.scale_simple(max(1, int(pb.get_width() * k)),
                                                max(1, int(pb.get_height() * k)),
                                                GdkPixbuf.InterpType.BILINEAR))
        sw.connect("size-allocate", fit)
        nb.append_page(sw, Gtk.Label(label=os.path.basename(path)[:18]))
        sw.show_all()
        nb.set_current_page(nb.get_n_pages() - 1)

    def on_add(_):
        d = Gtk.FileChooserDialog(title="Image de référence", action=Gtk.FileChooserAction.OPEN,
                                  transient_for=win)
        d.add_button("_Annuler", Gtk.ResponseType.CANCEL)
        d.add_button("_Ouvrir", Gtk.ResponseType.OK)
        d.set_select_multiple(True)
        if d.run() == Gtk.ResponseType.OK:
            for p in d.get_filenames():
                add_image(p)
        d.destroy()

    add.connect("clicked", on_add)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    on_add(None)
    Gtk.main()
    return None


# ─── timelapse ──────────────────────────────────────────────────────────

def timelapse_export(image):
    folder = os.path.join(Gimp.directory(), "timelapse", "image-%d" % image.get_id())
    frames = sorted(f for f in os.listdir(folder) if f.endswith(".png")) if os.path.isdir(folder) else []
    if len(frames) < 2:
        return ("Pas d'enregistrement pour cette image : Affichage > Enregistrer en accéléré, "
                "puis dessinez.")
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    Gst.init(None)
    GimpUi.init("chopgimp_atelier")
    d = Gtk.FileChooserDialog(title="Exporter le timelapse", action=Gtk.FileChooserAction.SAVE)
    d.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    d.add_button("_Enregistrer", Gtk.ResponseType.OK)
    d.set_current_name("timelapse.webm")
    d.set_do_overwrite_confirmation(True)
    resp = d.run()
    target = d.get_filename()
    d.destroy()
    if resp != Gtk.ResponseType.OK or not target:
        return "cancel"
    # images numérotées 000000.png… → WebM (VP8), 12 images/s ; pipeline
    # construit élément par élément (chemins passés en propriétés, jamais
    # interprétés par gst-launch : guillemets, « ! »… sans danger)
    pipe = Gst.Pipeline.new("timelapse")
    chain = [("multifilesrc", {"location": os.path.join(folder, "%06d.png"), "index": 0,
                               "caps": Gst.Caps.from_string("image/png,framerate=12/1")}),
             ("pngdec", {}), ("videoconvert", {}), ("videoscale", {}),
             ("capsfilter", {"caps": Gst.Caps.from_string(
                 "video/x-raw,width=1280,pixel-aspect-ratio=1/1")}),
             ("vp8enc", {"deadline": 1}), ("webmmux", {}), ("filesink", {"location": target})]
    elements = []
    for kind, props in chain:
        e = Gst.ElementFactory.make(kind, None)
        if e is None:
            return "Encodage impossible : élément GStreamer « %s » absent." % kind
        for k, v in props.items():
            e.set_property(k, v)
        pipe.add(e)
        if elements and not elements[-1].link(e):
            return "Encodage impossible : %s → %s." % (elements[-1].get_factory().get_name(), kind)
        elements.append(e)
    pipe.set_state(Gst.State.PLAYING)
    bus = pipe.get_bus()
    msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.EOS | Gst.MessageType.ERROR)
    pipe.set_state(Gst.State.NULL)
    if msg and msg.type == Gst.MessageType.ERROR:
        err, _ = msg.parse_error()
        return "Encodage impossible : %s" % err.message
    Gimp.message("Timelapse exporté : %s (%d images)" % (target, len(frames)))
    return None


class ChopGimpAtelier(Gimp.PlugIn):
    def do_query_procedures(self):
        return list(PROCS)

    def do_create_procedure(self, name):
        label, menu = PROCS[name]
        p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        p.set_image_types("*")
        p.set_menu_label(label)
        p.add_menu_path(menu)
        p.set_documentation(label.rstrip("…"), label.rstrip("…"), name)
        p.set_attribution("ChopGimp", "ChopGimp", "2026")
        p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                               Gimp.ProcedureSensitivityMask.DRAWABLES |
                               Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
        return p

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        inter = run_mode == Gimp.RunMode.INTERACTIVE
        layers = [d for d in drawables if isinstance(d, Gimp.Layer)]
        msg = None

        def ask(title, rows):
            return spin_dialog(title, rows) if inter else defaults(rows)

        if name == "chopgimp-references":
            if inter:
                references()
            return ok(procedure)
        if name == "chopgimp-harmonies":
            if inter:
                harmonies()
            return ok(procedure)
        if name == "chopgimp-timelapse-export":
            msg = timelapse_export(image) if inter else "Fenêtre interactive."
        else:
            opts = None
            if name == "chopgimp-flats":
                opts = ask("Aplats sous l'encrage", [("gap", "Passer sous le trait (px)", 0, 20, 2, 1)])
            elif name == "chopgimp-comic-panels":
                opts = ask("Cases de BD", PANELS)
            elif name == "chopgimp-screentone":
                opts = ask("Trame", [("period", "Pas (px)", 2, 100, 8, 1), ("angle", "Angle", -90, 90, 45, 1)])
            elif name == "chopgimp-speed-lines":
                opts = ask("Lignes de vitesse", [("count", "Nombre", 5, 400, 60, 1),
                                                 ("thickness", "Épaisseur (px)", 1, 40, 4, 1),
                                                 ("angle", "Direction (°)", -180, 180, 0, 1)])
            elif name == "chopgimp-focus-lines":
                opts = ask("Lignes concentriques", [("count", "Nombre", 10, 600, 120, 1),
                                                    ("thickness", "Épaisseur (px)", 1, 40, 6, 1),
                                                    ("inner", "Zone libre au centre (%)", 0, 90, 30, 1)])
            elif name == "chopgimp-perspective-guides":
                opts = ask("Guides de perspective", [("points", "Points de fuite (1 à 3)", 1, 3, 2, 1),
                                                     ("horizon", "Horizon (% de la hauteur)", 0, 100, 40, 1),
                                                     ("lines", "Lignes par point", 8, 120, 36, 1)])
            if inter and opts is None and name not in ("chopgimp-sketch-layer", "chopgimp-sketch-toggle",
                                                      "chopgimp-comic-balloon", "chopgimp-vector-eraser"):
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            image.undo_group_start()
            try:
                if name == "chopgimp-sketch-layer":
                    msg = sketch_layer(image)
                elif name == "chopgimp-sketch-toggle":
                    msg = sketch_toggle(image)
                elif name == "chopgimp-flats":
                    if len(layers) != 1:
                        msg = "Sélectionnez le calque d'encrage."
                    else:
                        msg = flats(image, layers[0], opts["gap"], inter)
                elif name == "chopgimp-comic-panels":
                    msg = comic_panels(image, opts)
                elif name == "chopgimp-comic-balloon":
                    msg = comic_balloon(image)
                elif name == "chopgimp-screentone":
                    msg = screentone(image, drawables, opts) if drawables else "Sélectionnez un calque."
                elif name == "chopgimp-speed-lines":
                    msg = speed_lines(image, opts, False)
                elif name == "chopgimp-focus-lines":
                    msg = speed_lines(image, opts, True)
                elif name == "chopgimp-vector-eraser":
                    msg = vector_eraser(image, layers)
                elif name == "chopgimp-perspective-guides":
                    msg = perspective_guides(image, opts)
            finally:
                image.undo_group_end()
        Gimp.displays_flush()
        if msg == "cancel":
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        return fail(procedure, msg) if msg else ok(procedure)


if __name__ == "__main__":
    Gimp.main(ChopGimpAtelier.__gtype__, sys.argv)

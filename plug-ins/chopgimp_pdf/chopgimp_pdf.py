#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — import PDF / Illustrator (.ai moderne) en calques modifiables.

Prioritaire sur l'import PDF de GIMP (qui donne une image par page) :

- poppler dessine la page sur une surface « script » de cairo ; le
  module cairoscript la relit et en tire tracés, couleurs, contours et
  images ;
- chaque calque du PDF (OCG — les calques d'Illustrator) devient un
  groupe : la page est rendue une fois par calque, les objets propres à
  chaque calque sont séparés de ceux de la base ;
- tracés → 3.27.2 (lot V4) : UN calque vectoriel à plusieurs objets par
  page / calque PDF (un objet par élément dessiné, découpes en groupes de
  masque d'écrêtage, dégradés vectoriels ; module vobjects), entre deux
  images ; option « Fusionner les objets de même style (plus léger) » ;
  sans les objets (CHOPGIMP_NO_VOBJECTS=1), un calque vectoriel par suite
  d'objets de même style, comme en 3.26 ;
- images → calques d'image placés sur leurs 4 coins ;
- texte (API texte de poppler) → calques de texte modifiables, ligne par
  ligne, police / taille / couleur reprises ; ou contours vectoriels ;
- un rendu de référence de la page est ajouté, masqué, pour comparer.

SVG : lecture directe du XML (vobjects.SvgImport) : calques Inkscape,
groupes <g> avec leurs noms, transformations, découpes, dégradés.

Le mode « image (comme avant) » appelle l'import PDF de GIMP.
"""
import math
import os
import re
import shutil
import sys
import tempfile

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gegl", "0.4")
gi.require_version("Poppler", "0.18")
from gi.repository import Gimp, GimpUi, Gegl, Gio, GLib, GObject, Gtk, Poppler
import cairo
gi.require_foreign("cairo")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cairoscript  # noqa: E402
import ocg  # noqa: E402
import printer  # noqa: E402
import vobjects  # noqa: E402
from chopgimp_common import (pdb_run, pdb_call, srgb, set_parasite_text, dialog_box,  # noqa: E402
                             vbox, spin_scale, form_grid, frame, ok, fail)

PROC = "file-chopgimp-pdf-load"
PROC_THUMB = "file-chopgimp-pdf-load-thumb"
PROC_PS = "file-chopgimp-eps-load"
PROC_SVG = "file-chopgimp-svg-load"
PROC_PS_THUMB = "file-chopgimp-eps-load-thumb"
PROC_SVG_THUMB = "file-chopgimp-svg-load-thumb"
# 3.31.0 (lot 4b) : calques PDF (OCG) de l'export PDF (file-pdf-export, module ocg)
PROC_OCG = "chopgimp-pdf-ocg-layers"
# 4.2.0 : Fichier > Exporter pour l'imprimeur ; profils PSO v3 de l'ECI
PROC_PRINT = "file-chopgimp-print-export"
PROC_ECI = "plug-in-chopgimp-cmyk-download"
PROC_SVG_PASTE = "plug-in-chopgimp-svg-to-vobjects"   # 4.2.1 : coller un SVG
MAX_SIDE = 16384          # côté maximal d'un rendu en pixels (la résolution est réduite)
MAX_OBJECTS = 50000       # au-delà, la page est importée en image


# ─── outils ─────────────────────────────────────────────────────────────

def or_error(procedure, res, msg):
    """Résultat d'une procédure déléguée, ou erreur si elle est absente."""
    if res is None:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(msg))
    return res


def fit_scale(pw, ph, dpi):
    """Échelle points → pixels, réduite pour que le rendu tienne dans MAX_SIDE."""
    scale = dpi / 72.0
    side = max(pw, ph) * scale
    if side > MAX_SIDE:
        scale *= MAX_SIDE / side
    return scale


def fonts_resolver():
    """Le résolveur de polices de l'import PSD (nom PostScript → police)."""
    path = os.path.join(os.path.dirname(HERE), "chopgimp_psd")
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        import chopgimp_psd
        settings = chopgimp_psd.settings_load()
        return chopgimp_psd.Fonts(settings.get("fonts", {}))
    except Exception:
        return None


class Report:
    def __init__(self):
        self.lines = []

    def add(self, s):
        self.lines.append(s)

    def text(self):
        return "\n".join(self.lines)


# ─── rendu par calque ───────────────────────────────────────────────────

def ocg_layers(doc):
    """[(titre, Poppler.Layer)] à plat (calques imbriqués compris)."""
    out = []

    def walk(it, prefix):
        while it is not None:
            layer = it.get_layer()
            title = it.get_title() if hasattr(it, "get_title") else None
            if layer is not None:
                out.append(((prefix + (layer.get_title() or "Calque")).strip(), layer))
            child = it.get_child()
            if child is not None:
                walk(child, prefix + ((title or (layer.get_title() if layer else "")) + " / "
                                      if (title or layer) else ""))
            if not it.next():
                break

    try:
        it = Poppler.LayersIter.new(doc)
    except Exception:
        it = None
    if it is not None:
        walk(it, "")
    return out


def render_script(page, scale, w, h):
    fd, path = tempfile.mkstemp(suffix=".cs", prefix="chopgimp-pdf-")
    os.close(fd)
    try:
        dev = cairo.ScriptDevice(path)
        surf = cairo.ScriptSurface(dev, cairo.Content.COLOR_ALPHA, w, h)
        cr = cairo.Context(surf)
        cr.scale(scale, scale)
        page.render(cr)
        surf.finish()
        dev.finish()
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def render_pixels(page, scale, w, h):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)
    cr.scale(scale, scale)
    page.render(cr)
    surf.flush()
    return surf


def signature(o):
    if o.kind == "image":
        iw, ih, _, corners, _ = o.image
        return ("i", iw, ih, tuple(round(v, 1) for c in corners for v in c))
    pts = tuple(round(v, 1) for _, sub in o.path for knot in sub for p in knot for v in p)
    return ("p", pts, o.fill and tuple(round(v, 3) for v in o.fill),
            o.stroke and tuple(round(v, 3) for v in o.stroke["color"]))


def subtract(objs, base_sigs):
    left = dict(base_sigs)
    out = []
    for o in objs:
        s = signature(o)
        if left.get(s, 0) > 0:
            left[s] -= 1
        else:
            out.append(o)
    return out


# ─── construction des calques ───────────────────────────────────────────

CAPS = {"butt": Gimp.CapStyle.BUTT, "round": Gimp.CapStyle.ROUND, "square": Gimp.CapStyle.SQUARE}
JOINS = {"miter": Gimp.JoinStyle.MITER, "round": Gimp.JoinStyle.ROUND, "bevel": Gimp.JoinStyle.BEVEL}


def style_key(o):
    if o.kind != "path":
        return None
    return (o.fill and tuple(round(v, 4) for v in o.fill), o.fill_kind,
            o.stroke and (tuple(round(v, 4) for v in o.stroke["color"]), round(o.stroke["width"], 2),
                          o.stroke["cap"], o.stroke["join"], tuple(o.stroke["dash"])))


def merge_runs(objs, limit):
    """Objets consécutifs de même style → un seul objet (plusieurs sous-chemins)."""
    out = []
    for o in objs:
        if out and o.kind == "path" and out[-1].kind == "path" and style_key(o) == style_key(out[-1]) \
                and len(out[-1].path) < limit:
            out[-1].path = out[-1].path + o.path
        else:
            out.append(o)
    return out


def build_path_layer(image, o, parent, n):
    path = Gimp.Path.new(image, "Tracé %d" % n)
    for closed, knots in o.path:
        flat = []
        for cin, a, cout in knots:
            flat += [cin[0], cin[1], a[0], a[1], cout[0], cout[1]]
        if len(flat) >= 6:
            path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER, flat, closed)
    image.insert_path(path, None, -1)
    vl = Gimp.VectorLayer.new(image, path)
    what = []
    if o.fill is not None:
        vl.set_enable_fill(True)
        vl.set_fill_color(srgb(*o.fill[:3]))
        what.append("fond " + vobjects._color_name(o.fill))
    else:
        vl.set_enable_fill(False)
    st = o.stroke
    if st:
        vl.set_enable_stroke(True)
        vl.set_stroke_color(srgb(*st["color"][:3]))
        vl.set_stroke_width(max(0.1, st["width"]))
        vl.set_stroke_cap_style(CAPS[st["cap"]])
        vl.set_stroke_join_style(JOINS[st["join"]])
        if st["dash"]:
            vl.set_stroke_dash_pattern(st["dash"])
        what.append("contour " + vobjects._color_name(st["color"]))
    else:
        vl.set_enable_stroke(False)
    alpha = (o.fill or st["color"])[3] if (o.fill or st) else 1.0
    vl.set_name(("Forme %d — " % n) + ", ".join(what))
    image.insert_layer(vl, parent, 0)
    vl.set_opacity(max(0.0, min(100.0, alpha * 100.0)))
    vl.refresh()
    return vl


# ─── 3.27.2 (lot V4) : calques vectoriels à plusieurs objets ────────────

_VOBJ = [None]


def vobjects_available():
    """La procédure chopgimp-vobjects-set-xml existe et les objets sont actifs."""
    if _VOBJ[0] is None:
        env = os.environ.get("CHOPGIMP_NO_VOBJECTS", "")
        _VOBJ[0] = (not (env and env != "0") and
                    Gimp.get_pdb().lookup_procedure("chopgimp-vobjects-set-xml") is not None)
    return _VOBJ[0]


def world_leaves(nodes, m=None, out=None):
    """[(objet tracé, matrice monde)] du bas vers le haut, formes de découpe
    exclues (pour le repli sans objets)."""
    out = [] if out is None else out
    for n in nodes:
        wm = vobjects.compose(n.transform, m)
        if n.kind == "group":
            kids = n.children[:-1] if n.clip else n.children
            world_leaves(kids, wm, out)
        elif n.visible:
            out.append((n, wm))
    return out


class _Shape:
    """Objet au format de cairoscript pour build_path_layer (repli)."""
    kind = "path"
    fill_kind = "solid"

    def __init__(self, node, m):
        self.path = vobjects.tf_subpaths(node.subpaths, m)
        k = m.scale_factor() if m is not None else 1.0

        def color(p):
            # format 2 : opacité du fond / contour, fond / contour masqué
            if not p.get("visible", True):
                return None
            op = p.get("opacity", 1.0)
            if p.get("type") == "color":
                c = p["rgba"]
            elif p.get("stops"):
                c = p["stops"][0][1]
            else:
                return None
            return (c[0], c[1], c[2], c[3] * op)
        self.fill = color(node.fill)
        st = node.stroke
        c = color(st)
        self.stroke = None
        if c is not None:
            w = st.get("width", 1.0)
            self.stroke = {"color": c, "width": w * k, "cap": st.get("cap", "butt"),
                           "join": st.get("join", "miter"),
                           "dash": [v * w * k for v in st.get("dash") or []]}


def build_vector_objects(image, name, nodes, parent, report, merge=False):
    """Un calque vectoriel avec les objets (chopgimp-vobjects-set-xml) ; sans
    les objets, un calque par objet comme avant. → nombre de calques créés."""
    if merge:
        nodes = vobjects.merge_similar(nodes)
    leaves = world_leaves(nodes)
    if not leaves:
        return 0
    if vobjects_available():
        path = Gimp.Path.new(image, name)
        first, m = leaves[0]
        for closed, knots in vobjects.tf_subpaths(first.subpaths, m):
            flat = [v for cin, a, cout in knots for v in (cin[0], cin[1], a[0], a[1], cout[0], cout[1])]
            if len(flat) >= 6:
                path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER, flat, closed)
        image.insert_path(path, None, -1)
        vl = Gimp.VectorLayer.new(image, path)
        vl.set_name(name)
        image.insert_layer(vl, parent, 0)
        res = pdb_run("chopgimp-vobjects-set-xml", layer=vl, xml=vobjects.to_xml(nodes))
        if res is not None and res.index(0) == Gimp.PDBStatusType.SUCCESS and res.index(1):
            return 1
        report.add("Objets refusés par GIMP (%s) : un calque par objet." % name)
        image.remove_layer(vl)
        try:
            image.remove_path(path)
        except Exception:
            pass
        _VOBJ[0] = False
    for i, (n, m) in enumerate(leaves):
        build_path_layer(image, _Shape(n, m), parent, i + 1).set_name(n.name or "Forme %d" % (i + 1))
    return len(leaves)


def path_bounds(o):
    xs = [p[0] for _, sub in o.path for knot in sub for p in knot]
    ys = [p[1] for _, sub in o.path for knot in sub for p in knot]
    return (int(math.floor(min(xs))), int(math.floor(min(ys))),
            int(math.ceil(max(xs))), int(math.ceil(max(ys)))) if xs else None


def build_raster_part(image, o, parent, n, ref):
    """Objet non représentable en vecteur (dégradé…) : les pixels du rendu
    de poppler, recadrés sur l'objet et masqués par sa forme."""
    b = path_bounds(o)
    if b is None or ref is None:
        return None
    x1, y1 = max(0, b[0]), max(0, b[1])
    x2, y2 = min(ref.get_width(), b[2]), min(ref.get_height(), b[3])
    if x2 <= x1 or y2 <= y1:
        return None
    w, h = x2 - x1, y2 - y1
    layer = Gimp.Layer.new(image, "Dégradé %d (pixels)" % n, w, h, Gimp.ImageType.RGBA_IMAGE, 100,
                           Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, parent, 0)
    src = ref.get_buffer()
    data = src.get(Gegl.Rectangle.new(x1, y1, w, h), 1.0, "R'G'B'A u8", Gegl.AbyssPolicy.NONE)
    dst = layer.get_buffer()
    dst.set(Gegl.Rectangle.new(0, 0, w, h), "R'G'B'A u8", data)
    dst.flush()
    layer.set_offsets(x1, y1)
    # masque d'après la forme (les objets voisins du rendu restent dehors)
    path = Gimp.Path.new(image, "Forme du dégradé %d" % n)
    for closed, knots in o.path:
        flat = [v for cin, a, cout in knots for v in (cin[0], cin[1], a[0], a[1], cout[0], cout[1])]
        if len(flat) >= 6:
            path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER, flat, True)
    image.insert_path(path, None, -1)
    image.select_item(Gimp.ChannelOps.REPLACE, path)
    mask = layer.create_mask(Gimp.AddMaskType.SELECTION)
    layer.add_mask(mask)
    Gimp.Selection.none(image)
    layer.update(0, 0, w, h)
    return layer


def build_image_layer(image, o, parent, n):
    iw, ih, data, corners, alpha = o.image
    layer = Gimp.Layer.new(image, "Image %d" % n, iw, ih, Gimp.ImageType.RGBA_IMAGE,
                           alpha * 100.0, Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, parent, 0)
    buf = layer.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, iw, ih), "R'G'B'A u8", data)
    buf.flush()
    layer.update(0, 0, iw, ih)
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = corners
    if abs(y0 - y1) < 0.5 and abs(x0 - x3) < 0.5 and x1 > x0 and y3 > y0:
        nw, nh = max(1, int(round(x1 - x0))), max(1, int(round(y3 - y0)))
        if (nw, nh) != (iw, ih):
            layer.scale(nw, nh, False)
        layer.set_offsets(int(round(x0)), int(round(y0)))
    else:
        layer.transform_perspective(x0, y0, x1, y1, x3, y3, x2, y2)
    return layer


def standard_font(psname):
    """Polices standard du PDF (Helvetica, Times, Courier…) → famille générique."""
    low = psname.lower()
    if low.startswith(("helvetica", "arial")):
        base = "Sans-serif"
    elif low.startswith(("times", "georgia")):
        base = "Serif"
    elif low.startswith(("courier", "monaco")):
        base = "Monospace"
    else:
        return None
    style = []
    if "bold" in low:
        style.append("Bold")
    if "italic" in low or "oblique" in low:
        style.append("Italic")
    name = " ".join([base] + style)
    return name if Gimp.Font.get_by_name(name) else base


def add_texts(image, page, scale, parent, fonts, text_mode, report):
    text = page.get_text() or ""
    ok_, rects = page.get_text_layout()
    attrs = sorted(page.get_text_attributes() or [], key=lambda a: a.start_index)
    if not text or not ok_ or not rects:
        return 0
    if len(rects) != len(text):
        report.add("Texte : correspondance caractères / positions incomplète (%d/%d)"
                   % (len(rects), len(text)))
    n_chars = min(len(rects), len(text))

    # les lignes sont parcourues dans l'ordre : index courant dans attrs
    cursor = [0]

    def attr_at(i):
        k = cursor[0]
        while k < len(attrs) and attrs[k].end_index < i:
            k += 1
        cursor[0] = k
        if k < len(attrs) and attrs[k].start_index <= i:
            return attrs[k]
        return attrs[-1] if attrs else None

    # lignes : coupures sur « \n » ou saut de position
    lines, start = [], 0
    for i in range(n_chars):
        if text[i] == "\n":
            if i > start:
                lines.append((start, i))
            start = i + 1
    if start < n_chars:
        lines.append((start, n_chars))

    made, missing = 0, set()
    for a, b in lines:
        s = text[a:b].rstrip()
        if not s.strip():
            continue
        at = attr_at(a)
        x = min(rects[i].x1 for i in range(a, b)) * scale
        y = min(rects[i].y1 for i in range(a, b)) * scale
        size = (at.font_size if at else 12.0) * scale
        psname = (at.font_name if at else "") or ""
        psname = psname.split("+", 1)[-1]
        fname, found = (fonts.lookup(psname) if fonts else ("Sans-serif", False))
        if not found and psname:
            fname = standard_font(psname)
            if fname is None:
                missing.add(psname)
                fname = "Sans-serif"
        font = Gimp.Font.get_by_name(fname) or Gimp.Font.get_by_name("Sans-serif")
        tl = Gimp.TextLayer.new(image, s, font, max(1.0, size), Gimp.Unit.pixel())
        tl.set_name(s[:40])
        image.insert_layer(tl, parent, 0)
        if at:
            c = at.color
            tl.set_color(srgb(c.red / 65535.0, c.green / 65535.0, c.blue / 65535.0))
        tl.set_offsets(int(round(x)), int(round(y - size * 0.18)))
        if text_mode == "outline":
            path = Gimp.Path.new_from_text_layer(image, tl)
            image.insert_path(path, None, -1)
            vl = Gimp.VectorLayer.new(image, path)
            vl.set_name(tl.get_name())
            vl.set_enable_fill(True)
            vl.set_fill_color(tl.get_color())
            vl.set_enable_stroke(False)
            image.insert_layer(vl, parent, image.get_item_position(tl))
            vl.refresh()
            image.remove_layer(tl)
        made += 1
    if missing:
        report.add("Polices absentes (remplacées) : " + ", ".join(sorted(missing)))
    return made


def import_page(image, doc, page_no, opts, report, fonts):
    page = doc.get_page(page_no)
    pw, ph = page.get_size()
    scale = fit_scale(pw, ph, opts["dpi"])
    w, h = int(math.ceil(pw * scale)), int(math.ceil(ph * scale))
    if scale < opts["dpi"] / 72.0:
        report.add("Page %d : résolution réduite à %d ppp (rendu limité à %d px de côté)."
                   % (page_no + 1, int(scale * 72), MAX_SIDE))

    layers = ocg_layers(doc)
    passes = []
    if layers:
        states = [(L, L.is_visible()) for _, L in layers]
        for _, L in layers:
            L.hide()
        base_objs, stats = cairoscript.parse(render_script(page, scale, w, h))
        base_sigs = {}
        for o in base_objs:
            s = signature(o)
            base_sigs[s] = base_sigs.get(s, 0) + 1
        passes.append(("", True, base_objs))
        for title, L in layers:
            L.show()
            objs, _ = cairoscript.parse(render_script(page, scale, w, h))
            L.hide()
            passes.append((title, dict(states)[L], subtract(objs, base_sigs)))
        for L, vis in states:
            (L.show if vis else L.hide)()
    else:
        objs, stats = cairoscript.parse(render_script(page, scale, w, h))
        passes.append(("", True, objs))

    total = sum(len(p[2]) for p in passes)
    if vobjects_available():
        # 3.27.2 : un objet par élément, tout dans un calque vectoriel
        merged = passes
        n_layers = total
    else:
        merged = [(t, v, merge_runs(objs, 400)) for t, v, objs in passes]
        n_layers = sum(len(m[2]) for m in merged)
    if n_layers > opts["max_objects"]:
        report.add("Page %d : %d objets (plafond %d) : importée en image." %
                   (page_no + 1, n_layers, opts["max_objects"]))
        return False

    if image.get_width() < w or image.get_height() < h:
        image.resize(max(w, image.get_width()), max(h, image.get_height()), 0, 0)

    # en cas d'échec, la page à moitié construite est retirée
    paths_before = {pth.get_id() for pth in image.get_paths()}
    created = []
    try:
        counts, n_text = build_page(image, page, page_no, scale, w, h, merged, opts, report,
                                    fonts, created)
    except Exception:
        for item in reversed(created):
            try:
                image.remove_layer(item)
            except Exception:
                pass
        for pth in image.get_paths():
            if pth.get_id() not in paths_before:
                try:
                    image.remove_path(pth)
                except Exception:
                    pass
        raise

    if counts.get("objects"):
        report.add("Page %d : %d objets vectoriels en %d calque(s), %d images, %d lignes de texte, "
                   "%d calques PDF." % (page_no + 1, counts["objects"], counts["path"], counts["image"],
                                       n_text, len(layers)))
        if counts.get("gradients_vector"):
            report.add("  %d dégradé(s) vectoriel(s)%s." % (counts["gradients_vector"],
                       " (%d approché(s))" % counts["gradients_approx"] if counts.get("gradients_approx") else ""))
        if counts.get("clips_vector"):
            report.add("  %d masque(s) d'écrêtage." % counts["clips_vector"])
    else:
        report.add("Page %d : %d formes vectorielles (%d objets réunis), %d images, %d lignes de texte, "
                   "%d calques PDF." % (page_no + 1, counts["path"], total, counts["image"], n_text, len(layers)))
        if stats["gradients"]:
            report.add("  %d dégradé(s) repris en pixels (rendu exact, masqué par la forme)."
                       % stats["gradients"])
        if stats["clips"]:
            report.add("  %d découpe(s) non appliquée(s) aux vecteurs : voir le rendu de référence."
                       % stats["clips"])
    unknown = stats["unknown"]
    if unknown:
        report.add("  Opérations non reconnues : " + ", ".join("%s×%d" % kv for kv in sorted(unknown.items())))
    return True


def build_page(image, page, page_no, scale, w, h, merged, opts, report, fonts, created):
    """Calques d'une page ; chaque calque de premier niveau est noté dans created."""
    # rendu de référence, masqué, tout en bas
    ref = Gimp.Layer.new(image, "Page %d — rendu de référence" % (page_no + 1), w, h,
                         Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(ref, None, len(image.get_layers()))
    created.append(ref)
    surf = render_pixels(page, scale, w, h)
    data = bytes(surf.get_data())
    buf = ref.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, w, h), "cairo-ARGB32", data)
    buf.flush()
    ref.set_visible(False)

    page_group = Gimp.GroupLayer.new(image, "Page %d" % (page_no + 1))
    image.insert_layer(page_group, None, 0)
    created.append(page_group)
    counts = {"path": 0, "image": 0}
    if vobjects_available():
        build_page_objects(image, page_group, merged, opts, report, counts)
        merged = []
    for title, visible, objs in merged:
        parent = page_group
        if title:
            parent = Gimp.GroupLayer.new(image, title)
            image.insert_layer(parent, page_group, 0)
            parent.set_visible(visible)
            if not visible and not opts["hidden_layers"]:
                image.remove_layer(parent)
                continue
        for o in objs:
            counts[o.kind] += 1
            if o.kind == "path" and o.fill_kind == "gradient" and \
                    build_raster_part(image, o, parent, counts["path"], ref):
                if o.stroke:
                    o.fill = None
                    build_path_layer(image, o, parent, counts["path"])
                continue
            if o.kind == "path":
                build_path_layer(image, o, parent, counts["path"])
            else:
                build_image_layer(image, o, parent, counts["image"])
    n_text = 0
    if opts["text"] != "none":
        tg = Gimp.GroupLayer.new(image, "Textes")
        image.insert_layer(tg, page_group, 0)
        n_text = add_texts(image, page, scale, tg, fonts, opts["text"], report)
        if not n_text:
            image.remove_layer(tg)
    return counts, n_text


def build_page_objects(image, page_group, passes, opts, report, counts):
    """3.27.2 : chaque passe (la page, puis chaque calque PDF) → un calque
    vectoriel à plusieurs objets ; une image coupe la suite d'objets (ordre
    de superposition gardé) : la passe devient alors un groupe."""
    stats = counts
    n_obj = 0
    total = max(1, sum(len(p[2]) for p in passes))
    for title, visible, objs in passes:
        if title and not visible and not opts["hidden_layers"]:
            continue
        # suites d'objets entre les images
        chunks, run = [], []
        for o in objs:
            if o.kind == "image":
                if run:
                    chunks.append(("vector", run))
                    run = []
                chunks.append(("image", o))
            else:
                run.append(o)
        if run:
            chunks.append(("vector", run))
        if not chunks:
            continue
        name = title or "Formes"
        parent = page_group
        if len(chunks) > 1:
            parent = Gimp.GroupLayer.new(image, name)
            image.insert_layer(parent, page_group, 0)
            parent.set_visible(visible)
        for kind, c in chunks:
            if kind == "image":
                counts["image"] += 1
                build_image_layer(image, c, parent, counts["image"])
                continue
            nodes = vobjects.pdf_nodes(c, stats, n_obj + 1)
            n_obj += len(c)
            counts["objects"] = counts.get("objects", 0) + len(c)
            made = build_vector_objects(image, name, nodes, parent, report, opts.get("merge", False))
            counts["path"] += made
            if made and parent is page_group and not visible:
                for layer in page_group.get_children()[:made]:
                    layer.set_visible(False)
            Gimp.progress_update(min(1.0, n_obj / float(total)))


def import_page_image(image, doc, page_no, opts):
    """Page entière en un calque de pixels (rendu poppler)."""
    page = doc.get_page(page_no)
    pw, ph = page.get_size()
    scale = fit_scale(pw, ph, opts["dpi"])
    w, h = max(1, int(math.ceil(pw * scale))), max(1, int(math.ceil(ph * scale)))
    if image.get_width() < w or image.get_height() < h:
        image.resize(max(w, image.get_width()), max(h, image.get_height()), 0, 0)
    layer = Gimp.Layer.new(image, "Page %d (image)" % (page_no + 1), w, h,
                           Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, None, 0)
    surf = render_pixels(page, scale, w, h)
    buf = layer.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, w, h), "cairo-ARGB32", bytes(surf.get_data()))
    buf.flush()
    return layer


# ─── fenêtre d'options ──────────────────────────────────────────────────

def options_dialog(n_pages, n_layers):
    GimpUi.init("chopgimp_pdf")
    dialog = GimpUi.Dialog(title="Importer un PDF / Illustrator", role="chopgimp-pdf", modal=True)
    dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("_Importer", Gtk.ResponseType.OK)
    main = dialog_box(dialog, spacing=12)
    mode = Gtk.ComboBoxText()
    mode.append("layers", "Calques modifiables (vecteurs, textes, images)")
    mode.append("image", "Image (comme avant)")
    mode.set_active_id("layers")
    pages = Gtk.Entry(text="1")
    pages.set_tooltip_text("%d page(s) dans le document" % n_pages)
    text = Gtk.ComboBoxText()
    text.append("editable", "Calques de texte modifiables")
    text.append("outline", "Contours vectoriels")
    text.append("none", "Ignorer")
    text.set_active_id("editable")
    main.pack_start(frame("Contenu", form_grid([("Importer comme", mode), ("Pages (ex. 1, 3-5)", pages),
                                                ("Texte", text)])), False, False, 0)
    opt_box = vbox()
    dpi = spin_scale(Gtk.Adjustment(value=150, lower=36, upper=1200, step_increment=1, page_increment=50),
                     "Résolution (ppp)", limits=(36, 600), unit="ppp")
    opt_box.pack_start(dpi, False, False, 0)
    # 3.27.2 : tout reste dans un calque vectoriel par page / calque : le
    # plafond n'est plus qu'une garde contre les fichiers démesurés
    mx = spin_scale(Gtk.Adjustment(value=MAX_OBJECTS, lower=50, upper=500000, step_increment=100,
                                   page_increment=5000),
                    "Nombre maximal d'objets", limits=(50, 200000), gamma=2.0)
    opt_box.pack_start(mx, False, False, 0)
    merge = Gtk.CheckButton(label="Fusionner les objets de même style (plus léger)")
    merge.set_tooltip_text("Les objets voisins de même fond et contour deviennent un seul objet "
                           "à plusieurs sous-tracés : moins d'objets, mais on ne les modifie plus "
                           "séparément.")
    merge.set_active(False)
    opt_box.pack_start(merge, False, False, 0)
    hidden = Gtk.CheckButton(label="Importer aussi les calques masqués (%d calque(s) PDF)" % n_layers)
    hidden.set_active(True)
    opt_box.pack_start(hidden, False, False, 0)
    main.pack_start(frame("Options", opt_box), False, False, 0)
    dialog.show_all()
    resp = dialog.run()
    opts = None
    if resp == Gtk.ResponseType.OK:
        opts = {"mode": mode.get_active_id(), "pages": pages.get_text(), "text": text.get_active_id(),
                "dpi": dpi.get_value(), "max_objects": int(mx.get_value()),
                "hidden_layers": hidden.get_active(), "merge": merge.get_active()}
    dialog.destroy()
    return opts


def parse_pages(spec, n):
    out = []
    for part in (spec or "1").replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            a, b = int(a or 1), int(b or n)
            out += list(range(a, b + 1))
        else:
            out.append(int(part))
    return [p - 1 for p in out if 1 <= p <= n] or [0]


# ─── EPS / PostScript / ancien Illustrator : Ghostscript (libgs) → PDF ───

def ps_to_pdf(src, dst):
    """Convertit en PDF vectoriel avec la bibliothèque Ghostscript du paquet
    (pas de commande « gs »). → message d'erreur ou None."""
    import ctypes
    import ctypes.util
    lib = None
    # noms Linux puis Windows (libgs-10.dll de MSYS2, à côté de python.exe)
    for name in ("libgs.so.10", "libgs.so", "libgs-10.dll",
                 ctypes.util.find_library("gs") or ""):
        if not name:
            continue
        try:
            lib = ctypes.CDLL(name)
            break
        except OSError:
            continue
    if lib is None:
        return "Ghostscript introuvable"
    inst = ctypes.c_void_p()
    if lib.gsapi_new_instance(ctypes.byref(inst), None) < 0:
        return "Ghostscript : démarrage impossible"
    args = [b"gs", b"-dBATCH", b"-dNOPAUSE", b"-dSAFER", b"-dQUIET", b"-dEPSCrop",
            b"-sDEVICE=pdfwrite", b"-dCompatibilityLevel=1.5",
            b"-sOutputFile=" + dst.encode(), src.encode()]
    argv = (ctypes.c_char_p * len(args))(*args)
    try:
        lib.gsapi_set_arg_encoding(inst, 1)          # UTF-8
        code = lib.gsapi_init_with_args(inst, len(args), argv)
        lib.gsapi_exit(inst)
    finally:
        lib.gsapi_delete_instance(inst)
    if code < 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
        return "Ghostscript : conversion impossible (code %d)" % code
    return None


def load_ps(procedure, run_mode, file, metadata, flags, config, data):
    path = file.get_path()
    fd, pdf = tempfile.mkstemp(suffix=".pdf", prefix="chopgimp-eps-")
    os.close(fd)
    try:
        err = ps_to_pdf(path, pdf) if path else "fichier distant"
        if err:
            res = pdb_run("file-ps-load", **{"run-mode": run_mode, "file": file})
            return or_error(procedure, res, err), flags
        res, flags = load(procedure, run_mode, Gio.File.new_for_path(pdf), metadata, flags,
                          config, data, classic_file=file)
        return res, flags
    finally:
        try:
            os.unlink(pdf)
        except OSError:
            pass


# ─── SVG : lecture directe (vobjects.SvgImport), rendu librsvg de référence ─

def outline_text_layer(image, tl, parent):
    """Calque de texte → calque vectoriel de ses contours (option « Contours »)."""
    path = Gimp.Path.new_from_text_layer(image, tl)
    image.insert_path(path, None, -1)
    vl = Gimp.VectorLayer.new(image, path)
    vl.set_name(tl.get_name())
    vl.set_enable_fill(True)
    vl.set_fill_color(tl.get_color())
    vl.set_enable_stroke(False)
    image.insert_layer(vl, parent, image.get_item_position(tl))
    vl.refresh()
    image.remove_layer(tl)
    return vl


def svg_text_layer(image, it, parent, fonts, text_mode):
    name = it["family"]
    bold, italic = it["bold"], it["italic"]
    fname, found = (fonts.lookup(name.replace(" ", "") + ("-Bold" if bold else ""))
                    if fonts else (name, False))
    font = (Gimp.Font.get_by_name(fname if found else name) or Gimp.Font.get_by_name("Sans-serif"))
    size = max(1.0, it["size"])
    tl = Gimp.TextLayer.new(image, it["text"], font, size, Gimp.Unit.pixel())
    tl.set_name(it["text"][:40])
    image.insert_layer(tl, parent, 0)
    tl.set_color(srgb(*it["rgba"][:3]))
    if bold or italic:
        tl.set_markup("<markup>%s%s%s</markup>" % ("<b>" * bold + "<i>" * italic,
                                                   GLib.markup_escape_text(it["text"], -1),
                                                   "</i>" * italic + "</b>" * bold))
    tl.set_offsets(int(round(it["x"])), int(round(it["y"] - size * 0.92)))
    if text_mode == "outline":
        return outline_text_layer(image, tl, parent)
    return tl


def svg_image_layer(image, it, parent, n, base_dir, report):
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    data = vobjects.image_bytes(it["href"], base_dir)
    pb = None
    if data:
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pb = loader.get_pixbuf()
        except GLib.Error:
            pb = None
    if pb is None:
        report.add("Image illisible : %s" % it["href"][:60])
        return None
    if not pb.get_has_alpha():
        pb = pb.add_alpha(False, 0, 0, 0)
    iw, ih, rs = pb.get_width(), pb.get_height(), pb.get_rowstride()
    px = pb.get_pixels()
    raw = b"".join(px[y * rs:y * rs + iw * 4] for y in range(ih))

    class _Img:
        image = (iw, ih, raw, vobjects.image_corners(it)(iw, ih), it["opacity"])
    layer = build_image_layer(image, _Img, parent, n)
    layer.set_name(it["name"])
    return layer


def build_svg_items(image, items, parent, ctx):
    """Plan d'import (vobjects.SvgImport.plan) → calques, du bas vers le haut."""
    def children():
        return parent.get_children() if parent is not None else image.get_layers()

    for it in items:
        k = it["kind"]
        if k == "group":
            g = Gimp.GroupLayer.new(image, it["name"] or "Groupe")
            image.insert_layer(g, parent, 0)
            build_svg_items(image, it["items"], g, ctx)
            if not g.get_children():
                image.remove_layer(g)
                continue
            g.set_visible(it["visible"])
            g.set_opacity(it["opacity"] * 100.0)
            ctx["counts"]["groups"] += 1
        elif k == "vector":
            n_obj = sum(n.count() for n in it["nodes"])
            made = build_vector_objects(image, it["name"] or "Formes", it["nodes"], parent,
                                        ctx["report"], ctx["merge"])
            for layer in children()[:made]:
                layer.set_visible(it["visible"])
                if it["opacity"] < 1.0:
                    layer.set_opacity(it["opacity"] * 100.0)
            ctx["counts"]["vector"] += made
            ctx["counts"]["objects"] += n_obj
            ctx["done"] += n_obj
            Gimp.progress_update(min(1.0, ctx["done"] / float(ctx["total"])))
        elif k == "image":
            ctx["counts"]["image"] += 1
            layer = svg_image_layer(image, it, parent, ctx["counts"]["image"], ctx["dir"], ctx["report"])
            if layer is not None:
                layer.set_visible(it["visible"])
        elif k == "text":
            svg_text_layer(image, it, parent, ctx["fonts"], ctx["text"])
            ctx["counts"]["text"] += 1


def import_svg(image, path, opts, report, fonts):
    import xml.etree.ElementTree as ET
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    handle = Rsvg.Handle.new_from_file(path)
    handle.set_dpi(opts["dpi"])
    ok_, w, h = handle.get_intrinsic_size_in_pixels()
    if not ok_ or w <= 0 or h <= 0:
        dim = handle.get_dimensions()
        w, h = dim.width, dim.height
    # 400.0003 px (largeur « 4.16667in » écrite par file-svg) : 400, pas 401
    w0, h0 = vobjects.image_size(w, h)
    # rendu limité à MAX_SIDE px de côté : le document est réduit d'un facteur zoom
    zoom = min(1.0, MAX_SIDE / float(max(w0, h0, 1)))
    w, h = max(1, int(math.ceil(w0 * zoom))), max(1, int(math.ceil(h0 * zoom)))
    if zoom < 1.0:
        report.add("SVG réduit à %d × %d px (rendu limité à %d px de côté)." % (w, h, MAX_SIDE))
    vp = Rsvg.Rectangle()
    vp.x, vp.y, vp.width, vp.height = 0, 0, w0, h0
    root = ET.parse(path).getroot()

    # 3.27.2 (lot V4) : structure lue dans le XML : un calque vectoriel à
    # plusieurs objets par calque Inkscape (ou suite d'objets), groupes <g>,
    # découpes, dégradés et transformations conservés
    imp = vobjects.SvgImport(root, vobjects.svg_base_matrix(root, w0, h0, zoom),
                             os.path.basename(path), opts["hidden_layers"], opts["text"] != "none")
    items = imp.plan()
    n_objs = vobjects.count_plan(items)
    if n_objs > opts["max_objects"]:
        report.add("SVG : %d objets (plafond %d) : importé en image." % (n_objs, opts["max_objects"]))
        return False
    image.resize(max(w, image.get_width()), max(h, image.get_height()), 0, 0)

    # rendu de référence (masqué), pour comparer
    ref = Gimp.Layer.new(image, os.path.basename(path) + " — rendu de référence", w, h,
                         Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(ref, None, len(image.get_layers()))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)
    cr.scale(zoom, zoom)
    handle.render_document(cr, vp)
    surf.flush()
    rbuf = ref.get_buffer()
    rbuf.set(Gegl.Rectangle.new(0, 0, w, h), "cairo-ARGB32", bytes(surf.get_data()))
    rbuf.flush()
    ref.set_visible(False)

    ctx = {"report": report, "merge": opts.get("merge", False), "fonts": fonts, "text": opts["text"],
           "dir": os.path.dirname(path), "total": max(1, n_objs), "done": 0,
           "counts": {"vector": 0, "objects": 0, "groups": 0, "image": 0, "text": 0}}
    symbols = vobjects.collect_symbols(items) if vobjects_available() else {}
    build_svg_items(image, items, None, ctx)
    if symbols:
        par = image.get_parasite("chopgimp-symbols")
        old_text = bytes(par.get_data()).decode("utf-8", "replace") if par else ""
        text = vobjects.symbols_parasite_text(old_text, symbols)
        image.attach_parasite(Gimp.Parasite.new("chopgimp-symbols", 3, list(text.encode("utf-8"))))
        report.add("SVG : %d symbole(s) (<symbol> / <use>) repris dans le panneau Symboles."
                   % len(symbols))

    c, st = ctx["counts"], imp.stats
    report.add("SVG : %d objets vectoriels (%d groupes) en %d calque(s) vectoriel(s), %d images, "
               "%d textes, %d calques de groupe." % (c["objects"], st["groups"], c["vector"], c["image"],
                                                     c["text"], c["groups"]))
    if st["gradients"]:
        report.add("  %d dégradé(s) vectoriel(s)%s." % (st["gradients"], " (%d approché(s) : répétition "
                   "ou déformation)" % st["gradients_approx"] if st["gradients_approx"] else ""))
    if st["clips"]:
        report.add("  %d masque(s) d'écrêtage." % st["clips"])
    if st.get("masks_clip"):
        report.add("  %d masque(s) de fusion simples (formes blanches) repris en masques "
                   "d'écrêtage." % st["masks_clip"])
    if st.get("patterns_approx"):
        report.add("  %d motif(s) approché(s) par leur couleur moyenne." % st["patterns_approx"])
    lost = []
    for key, label in (("masks", "masques de fusion"), ("filters", "filtres"), ("patterns", "motifs"),
                       ("lost_clips", "découpes de calques"),
                       ("markers", "marqueurs (pointes de flèche non reconnues ou marker-mid)")):
        if st[key]:
            lost.append("%d %s" % (st[key], label))
    if lost:
        report.add("  Non repris (voir le rendu de référence) : " + ", ".join(lost) + ".")
    if st["unknown"]:
        report.add("  Éléments ignorés : " + ", ".join("%s×%d" % kv for kv in sorted(st["unknown"].items())))
    return True


def load_svg(procedure, run_mode, file, metadata, flags, config, data):
    path = file.get_path()
    opts = {"mode": "layers", "pages": "1", "text": "editable", "dpi": 96.0, "max_objects": MAX_OBJECTS,
            "hidden_layers": True, "merge": False}
    if run_mode == Gimp.RunMode.INTERACTIVE:
        chosen = options_dialog(1, 0)
        if chosen is None:
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error()), flags
        opts.update(chosen)
    def original():
        res = pdb_run("file-svg-load", **{"run-mode": run_mode, "file": file})
        return or_error(procedure, res, "Import SVG d'origine absent"), flags

    if opts["mode"] == "image" or not path:
        return original()
    image = Gimp.Image.new(1, 1, Gimp.ImageBaseType.RGB)
    image.undo_disable()
    image.set_resolution(opts["dpi"], opts["dpi"])
    report = Report()
    try:
        done = import_svg(image, path, opts, report, fonts_resolver() if opts["text"] != "none" else None)
    except Exception as e:
        image.delete()
        Gimp.message("Import SVG modifiable impossible (%s) : import d'origine." % e)
        return original()
    if not done:                      # trop d'objets : import d'origine (image)
        image.delete()
        Gimp.message(report.text())
        return original()
    image.undo_enable()
    set_parasite_text(image, "chopgimp-pdf-report", report.text(), 0)
    return Gimp.ValueArray.new_from_values([
        GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS),
        GObject.Value(Gimp.Image, image),
    ]), flags


# ─── 4.2.1 : SVG du presse-papiers (Inkscape, Illustrator) → objets ─────

def svg_paste_nodes(text):
    """Texte SVG (seul ou au milieu d'un autre texte) → objets de l'import
    SVG (un objet par forme ; calques et groupes SVG gardés en groupes),
    en pixels à 96 ppp. → [VNode]"""
    import xml.etree.ElementTree as ET
    i = text.find("<svg")
    if i < 0:
        return []
    j = text.rfind("<?xml", 0, i)
    text = text[j if j >= 0 else i:]
    k = text.rfind("</svg>")
    if k >= 0:
        text = text[:k + 6]
    root = ET.fromstring(text.encode("utf-8"))
    w0 = h0 = 0.0
    try:
        gi.require_version("Rsvg", "2.0")
        from gi.repository import Rsvg
        handle = Rsvg.Handle.new_from_data(text.encode("utf-8"))
        handle.set_dpi(96.0)
        ok_, w0, h0 = handle.get_intrinsic_size_in_pixels()
        if not ok_:
            w0 = h0 = 0.0
    except Exception:  # noqa: BLE001 — tailles lues dans le XML
        pass
    if w0 <= 0 or h0 <= 0:
        vb = vobjects._num_list(root.get("viewBox"))
        w0 = vobjects.parse_length(root.get("width"), 0.0, vb[2] if len(vb) == 4 else 100.0)
        h0 = vobjects.parse_length(root.get("height"), 0.0, vb[3] if len(vb) == 4 else 100.0)
    imp = vobjects.SvgImport(root, vobjects.svg_base_matrix(root, w0, h0), "SVG", False, False)

    def nodes_of(items):
        out = []
        for it in items:
            if not it.get("visible", True) or it["kind"] not in ("vector", "group"):
                continue
            kids = it["nodes"] if it["kind"] == "vector" else nodes_of(it["items"])
            if not kids:
                continue
            if it["kind"] == "group" or it.get("opacity", 1.0) < 1.0:
                g = vobjects.VNode("group", it.get("name") or "")
                g.opacity = it.get("opacity", 1.0)
                g.children = kids
                kids = [g]
            out.extend(kids)
        return out

    nodes = nodes_of(imp.plan())
    # un seul calque SVG (cas d'Inkscape) : ses objets, sans groupe autour
    while len(nodes) == 1 and nodes[0].kind == "group" and not nodes[0].clip and \
            nodes[0].opacity >= 1.0 and nodes[0].transform is None and nodes[0].symbol is None:
        nodes = nodes[0].children
    return nodes


def svg_paste(procedure, config, data):
    try:
        nodes = svg_paste_nodes(config.get_property("svg") or "")
        xml = vobjects.to_xml(nodes) if nodes else ""
        n = sum(x.count() for x in nodes)
    except Exception:  # noqa: BLE001 — SVG illisible : rien à coller
        xml, n = "", 0
    return Gimp.ValueArray.new_from_values([
        GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS),
        GObject.Value(GObject.TYPE_STRING, xml),
        GObject.Value(GObject.TYPE_INT, n)])


# ─── procédures ─────────────────────────────────────────────────────────

def classic(file, run_mode):
    """Import d'origine de GIMP (PDF, ou PostScript pour EPS/PS/ancien AI)."""
    name = (file.get_basename() or "").lower()
    proc = "file-pdf-load" if name.endswith((".pdf", ".ai")) else "file-ps-load"
    return pdb_run(proc, **{"run-mode": run_mode, "file": file})


def load(procedure, run_mode, file, metadata, flags, config, data, classic_file=None):
    path = file.get_path()
    classic_file = classic_file or file
    try:
        doc = Poppler.Document.new_from_file(file.get_uri(), None)
    except GLib.Error:
        doc = None
    if doc is None or not path:
        return or_error(procedure, classic(classic_file, run_mode), "Import d'origine absent"), flags

    opts = {"mode": "layers", "pages": "1", "text": "editable", "dpi": 150.0, "max_objects": MAX_OBJECTS,
            "hidden_layers": True, "merge": False}
    if os.environ.get("CHOPGIMP_PDF_PAGES"):
        opts["pages"] = os.environ["CHOPGIMP_PDF_PAGES"]
    if run_mode == Gimp.RunMode.INTERACTIVE:
        chosen = options_dialog(doc.get_n_pages(), len(ocg_layers(doc)))
        if chosen is None:
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error()), flags
        opts = chosen
    if opts["mode"] == "image":
        return or_error(procedure, classic(classic_file, run_mode), "Import d'origine absent"), flags

    pw, ph = doc.get_page(0).get_size()
    scale = fit_scale(pw, ph, opts["dpi"])
    image = Gimp.Image.new(max(1, int(math.ceil(pw * scale))), max(1, int(math.ceil(ph * scale))),
                           Gimp.ImageBaseType.RGB)
    image.undo_disable()
    image.set_resolution(opts["dpi"], opts["dpi"])
    report = Report()
    fonts = fonts_resolver() if opts["text"] != "none" else None
    for p in parse_pages(opts["pages"], doc.get_n_pages()):
        try:
            vector = import_page(image, doc, p, opts, report, fonts)
        except Exception as e:
            report.add("Page %d : import vectoriel impossible (%s) : importée en image." % (p + 1, e))
            vector = False
        if not vector:
            # trop d'objets ou échec : la page entière en calque de pixels
            try:
                import_page_image(image, doc, p, opts)
            except Exception as e:
                report.add("Page %d : import en image impossible (%s)" % (p + 1, e))
    image.undo_enable()

    if not image.get_layers():                # rien d'importé : import classique
        image.delete()
        return or_error(procedure, classic(classic_file, run_mode), "Import d'origine absent"), flags

    text = report.text()
    if text:
        set_parasite_text(image, "chopgimp-pdf-report", text, 0)
        if run_mode == Gimp.RunMode.INTERACTIVE:
            Gimp.message("Import PDF :\n" + text)
    return Gimp.ValueArray.new_from_values([
        GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS),
        GObject.Value(Gimp.Image, image),
    ]), flags


def thumbnail(procedure, file, size, config, data):
    """Vignette PDF / EPS : celle de l'import d'origine de GIMP."""
    name = procedure.get_name()
    src = "file-ps-load-thumb" if name == PROC_PS_THUMB else "file-pdf-load-thumb"
    res = pdb_run(src, **{"file": file, "thumb-size": size})
    if res is None or res.index(0) != Gimp.PDBStatusType.SUCCESS:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error("Vignette impossible"))
    return res


def thumbnail_svg(procedure, file, size, config, data):
    """Vignette SVG rendue par librsvg (l'import SVG de GIMP n'en a pas)."""
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
    try:
        handle = Rsvg.Handle.new_from_file(file.get_path())
        ok_, w, h = handle.get_intrinsic_size_in_pixels()
        if not ok_ or w <= 0 or h <= 0:
            dim = handle.get_dimensions()
            w, h = dim.width, dim.height
    except Exception:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error("SVG illisible"))
    if w <= 0 or h <= 0:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error("SVG sans dimensions"))
    k = min(1.0, float(size) / max(w, h))
    tw, th = max(1, int(w * k)), max(1, int(h * k))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, tw, th)
    vp = Rsvg.Rectangle()
    vp.x, vp.y, vp.width, vp.height = 0, 0, tw, th
    handle.render_document(cairo.Context(surf), vp)
    surf.flush()
    image = Gimp.Image.new(tw, th, Gimp.ImageBaseType.RGB)
    layer = Gimp.Layer.new(image, "SVG", tw, th, Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, None, 0)
    buf = layer.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, tw, th), "cairo-ARGB32", bytes(surf.get_data()))
    buf.flush()
    return Gimp.ValueArray.new_from_values([
        GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS),
        GObject.Value(Gimp.Image, image),
        GObject.Value(GObject.TYPE_INT, int(w)),
        GObject.Value(GObject.TYPE_INT, int(h)),
        GObject.Value(Gimp.ImageType, Gimp.ImageType.RGBA_IMAGE),
        GObject.Value(GObject.TYPE_INT, 1)])


def ocg_export_layers(procedure, config, data):
    """PDF intermédiaire de file-pdf-export (un calque par page) → PDF à calques."""
    try:
        src = config.get_property("input").get_path()
        dst = config.get_property("output").get_path()
        ocg.make_layers_file(src, dst, config.get_property("spec"))
    except Exception as e:  # noqa: BLE001 — l'export se rabat sur un PDF sans calques
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error.new_literal(GLib.quark_from_string("chopgimp"),
                                   "Calques PDF : %s" % e, 0))
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ─── 4.2.0 : exporter pour l'imprimeur ──────────────────────────────────

def cmyk_command(image, command):
    """chopgimp-cmyk-command → (fait, résultat)"""
    res = pdb_run("chopgimp-cmyk-command", image=image, command=command)
    if res is None or res.index(0) != Gimp.PDBStatusType.SUCCESS:
        return False, "chopgimp-cmyk-command indisponible"
    return bool(res.index(1)), res.index(2) or ""


PRINT_PROFILES = {"pso-coated": "PSOcoated_v3.icc", "pso-uncoated": "PSOuncoated_v3_FOGRA52.icc",
                  "iso-coated": "ISOcoated_v2_eci.icc"}


def profile_bytes(profile):
    data = profile.get_icc_profile() if profile else None
    if data is None:
        return b""
    return bytes(data.get_data()) if hasattr(data, "get_data") else bytes(data)


def print_target(image, choice, tmp):
    """(chemin du profil CMJN cible ou None = celui de l'image, octets ICC)"""
    if choice in PRINT_PROFILES:
        _ok, listing = cmyk_command(None, "list")
        for path in listing.split("\n"):
            if os.path.basename(path) == PRINT_PROFILES[choice]:
                ok, msg = cmyk_command(None, "check|" + path)
                if not ok:
                    raise RuntimeError(msg)
                return path, open(path, "rb").read()
        raise RuntimeError("Profil %s absent (Image > Gestion des couleurs > Télécharger les "
                           "profils CMJN PSO v3)" % PRINT_PROFILES[choice])
    sim = image.get_simulation_profile()
    icc = profile_bytes(sim) if sim is not None and sim.is_cmyk() else b""
    if not icc:
        return None, b""
    path = os.path.join(tmp, "cible.icc")
    with open(path, "wb") as f:
        f.write(icc)
    ok, msg = cmyk_command(None, "check|" + path)
    if not ok:
        raise RuntimeError(msg)
    return path, icc


def print_prepare(image, rect, bleed, opts):
    """Copie de l'image recadrée sur la page + fond perdu, au profil cible."""
    dup = image.duplicate()
    dup.undo_disable()
    if opts["profile"]:
        ok, msg = cmyk_command(dup, "convert|%s|%d|%d" % (opts["profile"], opts["intent"],
                                                          int(opts["bpc"])))
    else:
        ok, msg = cmyk_command(dup, "set-cmyk")
    if not ok:
        dup.delete()
        raise RuntimeError(msg)
    dup.set_simulation_intent(Gimp.ColorRenderingIntent(opts["intent"]))
    dup.set_simulation_bpc(opts["bpc"])
    x, y, w, h = rect
    dup.resize(w + 2 * bleed, h + 2 * bleed, bleed - x, bleed - y)
    return dup


def print_raster(image, rect, bleed, opts, tmp, tif):
    dup = print_prepare(image, rect, bleed, opts)
    try:
        Gimp.context_push()
        Gimp.context_set_background(srgb(1, 1, 1))
        dup.flatten()
        Gimp.context_pop()
        res = pdb_run("file-tiff-export", **{"run-mode": Gimp.RunMode.NONINTERACTIVE,
                                             "image": dup, "file": Gio.File.new_for_path(tif),
                                             "compression": "none", "cmyk": True,
                                             "include-color-profile": True,
                                             "save-transparent-pixels": False})
        if res is None or res.index(0) != Gimp.PDBStatusType.SUCCESS:
            raise RuntimeError("export TIFF CMJN impossible")
        icc = profile_bytes(dup.get_simulation_profile())
    finally:
        dup.delete()
    w, h, data, tiff_icc = printer.read_tiff_cmyk(tif)
    return w, h, data, icc or tiff_icc


def print_vector(image, rect, bleed, opts, tmp, doc, srgb_cs, w_pt, h_pt, bleed_pt):
    dup = print_prepare(image, rect, bleed, opts)
    pdf = os.path.join(tmp, "page.chopgimp-print.pdf")
    try:
        res = pdb_run("file-pdf-export", **{"run-mode": Gimp.RunMode.NONINTERACTIVE,
                                            "image": dup, "file": Gio.File.new_for_path(pdf),
                                            "artboards": "image", "pdf-layers": False})
        if res is None or res.index(0) != Gimp.PDBStatusType.SUCCESS:
            raise RuntimeError("export PDF vectoriel impossible")
        icc_path = os.path.join(tmp, "page.icc")
        with open(icc_path, "wb") as f:
            f.write(profile_bytes(dup.get_simulation_profile()))
    finally:
        dup.delete()

    def convert(colors):
        out = []
        for i in range(0, len(colors), 500):
            chunk = colors[i:i + 500]
            ok, txt = cmyk_command(None, "rgb2cmyk|%s|%d|%d|%s" % (
                icc_path, opts["intent"], int(opts["bpc"]),
                ";".join("%.5f,%.5f,%.5f" % c for c in chunk)))
            vals = [tuple(float(v) for v in t.split(",")) for t in txt.split(";")] if ok else []
            if len(vals) != len(chunk):
                raise RuntimeError("conversion CMJN des couleurs : %s" % txt)
            for c, v in zip(chunk, vals):
                out.append((0.0, 0.0, 0.0, 1.0) if opts["black_k"] and max(c) < 1e-4 else v)
        return out

    return printer.import_vector_page(doc, open(pdf, "rb").read(), convert, srgb_cs,
                                      bleed_pt, opts["marks"], w_pt, h_pt)


def print_pages(image, mode):
    """Les pages : (x, y, largeur, hauteur, nom) des plans de travail, sinon l'image."""
    pages = []
    if mode != "image":
        res = pdb_call("chopgimp-artboards-command", image=image, command="list")
        for line in ((res.index(2) if res else "") or "").splitlines():
            f = line.split(" ", 4)
            if len(f) >= 4:
                pages.append((int(f[0]), int(f[1]), int(f[2]), int(f[3]),
                              f[4] if len(f) > 4 else "Plan"))
    if not pages:
        pages = [(0, 0, image.get_width(), image.get_height(), "")]
    return pages


def export_for_printer(image, path, opts):
    """→ liste des fichiers écrits"""
    res = image.get_resolution()           # (réussite, x, y) ou (x, y)
    xres, yres = res[-2], res[-1]
    xres = xres or 300.0
    yres = yres or xres
    bleed = int(round(opts["bleed_mm"] / 25.4 * xres))
    bleed_pt = bleed * 72.0 / xres
    pages = print_pages(image, opts["artboards"])
    base, ext = os.path.splitext(path)
    fmt = opts["format"]
    if not ext:
        ext = ".tif" if fmt == "tiff" else ".pdf"
    split = fmt == "tiff" or opts["artboards"] == "files"
    title = os.path.basename(base)
    written = []
    tmp = tempfile.mkdtemp(prefix="chopgimp-print-")
    try:
        opts["profile"], target_icc = print_target(image, opts["profile_choice"], tmp)
        doc = None
        srgb_cs = None
        for n, (x, y, w, h, name) in enumerate(pages):
            target = path if not (split and len(pages) > 1) else \
                "%s-%02d-%s%s" % (base, n + 1, re.sub(r"[^\w.-]+", "-", name) or "page", ext)
            w_pt, h_pt = w * 72.0 / xres, h * 72.0 / yres
            if fmt == "tiff":
                tif = os.path.join(tmp, "page.tif")
                print_raster(image, (x, y, w, h), bleed, opts, tmp, tif)
                shutil.move(tif, target)
                written.append(target)
                continue
            raster = None
            if fmt == "pdf-x1a":
                raster = print_raster(image, (x, y, w, h), bleed, opts, tmp,
                                      os.path.join(tmp, "page.tif"))
            if doc is None:
                icc = (raster[3] if raster else b"") or target_icc
                if not icc:
                    dup = print_prepare(image, (x, y, w, h), 0, opts)
                    icc = profile_bytes(dup.get_simulation_profile())
                    dup.delete()
                doc = printer.Doc(fmt == "pdf-x4", icc, title)
                srgb_icc = profile_bytes(Gimp.ColorProfile.new_rgb_srgb())
                srgb_cs = doc.out.add([printer.Name("ICCBased"),
                                       doc.out.add({"N": 3, "Filter": printer.Name("FlateDecode")},
                                                   printer.zlib.compress(srgb_icc, 9))])
            if raster:
                pw, ph, data, _ = raster
                doc.add_raster_page(pw, ph, data, w_pt, h_pt, bleed_pt, opts["marks"])
            else:
                try:
                    print_vector(image, (x, y, w, h), bleed, opts, tmp, doc, srgb_cs,
                                 w_pt, h_pt, bleed_pt)
                except Exception as e:  # noqa: BLE001 — repli : la page en image CMJN
                    Gimp.message("PDF/X-4 vectoriel impossible pour « %s » (%s) : page "
                                 "exportée en image CMJN." % (name or title, e))
                    pw, ph, data, _ = print_raster(image, (x, y, w, h), bleed, opts, tmp,
                                                   os.path.join(tmp, "page.tif"))
                    doc.add_raster_page(pw, ph, data, w_pt, h_pt, bleed_pt, opts["marks"])
            if split and len(pages) > 1:
                doc.save(target)
                written.append(target)
                doc = None
        if doc is not None:
            doc.save(path)
            written.append(path)
    finally:
        for f in os.listdir(tmp):
            try:
                os.unlink(os.path.join(tmp, f))
            except OSError:
                pass
        os.rmdir(tmp)
    return written


def print_export(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("chopgimp-print")
        if config.get_property("file") is None:
            src = image.get_file() or image.get_imported_file()
            folder = os.path.dirname(src.get_path()) if src and src.get_path() else GLib.get_home_dir()
            base = src.get_basename() if src and src.get_basename() else (image.get_name() or "image")
            name = os.path.splitext(base)[0] + "-imprimeur.pdf"
            config.set_property("file", Gio.File.new_for_path(os.path.join(folder, name)))
        dialog = GimpUi.ProcedureDialog.new(procedure, config, "Exporter pour l'imprimeur")
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()
    f = config.get_property("file")
    if f is None or not f.get_path():
        return fail(procedure, "Aucun fichier choisi")
    fmt = config.get_property("format")
    path = f.get_path()
    want = ".tif" if fmt == "tiff" else ".pdf"
    if not path.lower().endswith((want, ".tiff") if fmt == "tiff" else want):
        path = os.path.splitext(path)[0] + want
    opts = {"format": fmt, "profile_choice": config.get_property("profile"),
            "bpc": config.get_property("bpc"),
            "bleed_mm": config.get_property("bleed"), "marks": config.get_property("crop-marks"),
            "artboards": config.get_property("artboards"),
            "black_k": config.get_property("black-k")}
    intent = {"perceptual": 0, "relative": 1, "saturation": 2, "absolute": 3}
    opts["intent"] = intent.get(str(config.get_property("intent")), 1)
    Gimp.progress_init("Export pour l'imprimeur")
    try:
        files = export_for_printer(image, path, opts)
    except Exception as e:  # noqa: BLE001 — message clair, jamais de plantage
        return fail(procedure, "Export pour l'imprimeur : %s" % e)
    if run_mode == Gimp.RunMode.INTERACTIVE:
        Gimp.message("Export pour l'imprimeur : %s" % ", ".join(os.path.basename(x) for x in files))
    return ok(procedure)


def eci_download(procedure, config, data):
    run_mode = config.get_property("run-mode")
    dest = os.path.join(Gimp.directory(), "profiles")
    Gimp.progress_init("Téléchargement des profils PSO v3 (eci.org)")
    try:
        files = printer.download_eci(dest, lambda f: Gimp.progress_update(f))
        coated = next(p for p in files if p.endswith("PSOcoated_v3.icc"))
        done, msg = cmyk_command(None, "set-preferred|" + coated)
        if not done:
            raise RuntimeError(msg)
    except Exception as e:  # noqa: BLE001
        text = ("Les profils PSO v3 n'ont pas pu être téléchargés (%s). ChopGimp garde "
                "ISO Coated v2 (FOGRA39). Ils sont aussi disponibles sur eci.org : les copier "
                "dans %s." % (e, dest))
        if run_mode == Gimp.RunMode.INTERACTIVE:
            Gimp.message(text)
        return fail(procedure, text)
    if run_mode == Gimp.RunMode.INTERACTIVE:
        Gimp.message("Profils PSO Coated v3 et PSO Uncoated v3 installés ; PSO Coated v3 "
                     "est le profil CMJN de travail.")
    return ok(procedure)


class ChopGimpPDF(Gimp.PlugIn):
    def do_query_procedures(self):
        # la vignette d'abord : GIMP refuse un chargeur de vignette pas encore déclaré
        return [PROC_THUMB, PROC_PS_THUMB, PROC_SVG_THUMB, PROC, PROC_PS, PROC_SVG, PROC_OCG,
                PROC_PRINT, PROC_ECI, PROC_SVG_PASTE]

    def do_create_procedure(self, name):
        if name == PROC_PRINT:
            p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, print_export, None)
            p.set_image_types("RGB*")
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                   Gimp.ProcedureSensitivityMask.DRAWABLES |
                                   Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
            p.set_menu_label("Exporter pour l'_imprimeur...")
            p.add_menu_path("<Image>/File/Export")
            p.set_documentation("Exporter pour l'imprimeur (PDF/X ou TIFF CMJN)",
                                "PDF/X-1a (image CMJN), PDF/X-4 (vectoriel, couleurs CMJN) ou "
                                "TIFF CMJN ; profil intégré, conversion vers le profil cible, "
                                "fond perdu, traits de coupe, plans de travail.", name)
            p.set_attribution("ChopGimp", "ChopGimp", "2026")
            fmt = Gimp.Choice.new()
            fmt.add("pdf-x4", 0, "PDF/X-4 (vectoriel, transparence)", "")
            fmt.add("pdf-x1a", 1, "PDF/X-1a (image CMJN)", "")
            fmt.add("tiff", 2, "TIFF CMJN", "")
            p.add_choice_argument("format", "_Format", "Format", fmt, "pdf-x4",
                                  GObject.ParamFlags.READWRITE)
            p.add_file_argument("file", "_Fichier", "Fichier à écrire",
                                Gimp.FileChooserAction.SAVE, True, None,
                                GObject.ParamFlags.READWRITE)
            prof = Gimp.Choice.new()
            prof.add("image", 0, "Profil CMJN de l'image", "")
            prof.add("pso-coated", 1, "PSO Coated v3 (FOGRA51)", "")
            prof.add("pso-uncoated", 2, "PSO Uncoated v3 (FOGRA52)", "")
            prof.add("iso-coated", 3, "ISO Coated v2 (FOGRA39)", "")
            p.add_choice_argument("profile", "_Profil CMJN cible",
                                  "Les couleurs sont converties vers ce profil s'il diffère "
                                  "de celui de l'image", prof, "image",
                                  GObject.ParamFlags.READWRITE)
            intent = Gimp.Choice.new()
            intent.add("perceptual", 0, "Perception", "")
            intent.add("relative", 1, "Colorimétrie relative", "")
            intent.add("saturation", 2, "Saturation", "")
            intent.add("absolute", 3, "Colorimétrie absolue", "")
            p.add_choice_argument("intent", "_Mode de rendu", "Mode de rendu", intent,
                                  "relative", GObject.ParamFlags.READWRITE)
            p.add_boolean_argument("bpc", "Compensation du _point noir",
                                   "Compensation du point noir", True,
                                   GObject.ParamFlags.READWRITE)
            p.add_double_argument("bleed", "Fond _perdu (mm)", "Fond perdu en millimètres",
                                  0.0, 20.0, 3.0, GObject.ParamFlags.READWRITE)
            p.add_boolean_argument("crop-marks", "_Traits de coupe",
                                   "Traits de coupe (PDF), en couleur de repérage", True,
                                   GObject.ParamFlags.READWRITE)
            ab = Gimp.Choice.new()
            ab.add("image", 0, "Image entière", "")
            ab.add("pages", 1, "Une page par plan de travail", "")
            ab.add("files", 2, "Un fichier par plan de travail", "")
            p.add_choice_argument("artboards", "Plans de tra_vail", "Pages", ab, "pages",
                                  GObject.ParamFlags.READWRITE)
            p.add_boolean_argument("black-k", "Noir pur en 100 % _K",
                                   "Les tracés et textes noirs (PDF/X-4) en noir seul",
                                   True, GObject.ParamFlags.READWRITE)
            return p
        if name == PROC_ECI:
            p = Gimp.Procedure.new(self, name, Gimp.PDBProcType.PLUGIN, eci_download, None)
            p.set_menu_label("Télécharger les profils CMJN PSO v3 (ECI)...")
            p.add_menu_path("<Image>/Image/Color Management")
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            p.set_documentation("Profils PSO Coated v3 et PSO Uncoated v3 de l'ECI",
                                "Leur licence interdit de les fournir avec ChopGimp : "
                                "téléchargés depuis eci.org (somme SHA-256 vérifiée), "
                                "PSO Coated v3 devient le profil CMJN de travail.", name)
            p.set_attribution("ChopGimp", "ChopGimp", "2026")
            p.add_enum_argument("run-mode", "Run mode", "Run mode", Gimp.RunMode,
                                Gimp.RunMode.INTERACTIVE, GObject.ParamFlags.READWRITE)
            return p
        if name == PROC_SVG_PASTE:
            p = Gimp.Procedure.new(self, name, Gimp.PDBProcType.PLUGIN, svg_paste, None)
            p.set_documentation("SVG collé → objets d'un calque vectoriel",
                                "Le texte SVG (presse-papiers d'Inkscape ou d'Illustrator) au format "
                                "des objets (chopgimp-vobjects-set-xml), un objet par forme", name)
            p.set_attribution("ChopGimp", "ChopGimp", "2026")
            p.add_string_argument("svg", "SVG", "Texte SVG", "", GObject.ParamFlags.READWRITE)
            p.add_string_return_value("xml", "XML", "Objets (vide : aucun)", "",
                                      GObject.ParamFlags.READWRITE)
            p.add_int_return_value("n-objects", "Objets", "Nombre d'objets", 0, 1 << 30, 0,
                                   GObject.ParamFlags.READWRITE)
            return p
        if name == PROC_OCG:
            p = Gimp.Procedure.new(self, name, Gimp.PDBProcType.PLUGIN, ocg_export_layers, None)
            p.set_documentation("Calques PDF (OCG) d'un export PDF",
                                "Compose le PDF intermédiaire de file-pdf-export (un calque par "
                                "page, PDF 1.4 de cairo) en pages à calques PDF (contenu "
                                "optionnel), d'après la description JSON des pages.", name)
            p.set_attribution("ChopGimp", "ChopGimp", "2026")
            p.add_file_argument("input", "PDF intermédiaire", "PDF intermédiaire",
                                Gimp.FileChooserAction.OPEN, False, None,
                                GObject.ParamFlags.READWRITE)
            p.add_file_argument("output", "PDF à calques", "PDF à écrire",
                                Gimp.FileChooserAction.SAVE, False, None,
                                GObject.ParamFlags.READWRITE)
            p.add_string_argument("spec", "Description", "Pages et calques (JSON)", "",
                                  GObject.ParamFlags.READWRITE)
            return p
        if name in (PROC_THUMB, PROC_PS_THUMB, PROC_SVG_THUMB):
            p = Gimp.ThumbnailProcedure.new(self, name, Gimp.PDBProcType.PLUGIN,
                                            thumbnail_svg if name == PROC_SVG_THUMB else thumbnail, None)
            p.set_documentation("Vignette d'un PDF / AI", "Délègue à file-pdf-load-thumb.", name)
            p.set_attribution("ChopGimp", "ChopGimp", "2026")
            return p
        if name == PROC_SVG:
            p = Gimp.LoadProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, load_svg, None)
            p.set_menu_label("SVG (calques modifiables)")
            p.set_documentation("Ouvre un SVG en calques modifiables",
                                "Un calque vectoriel à plusieurs objets par calque Inkscape (groupes, "
                                "découpes, dégradés conservés), textes modifiables.", name)
            p.set_attribution("ChopGimp", "ChopGimp", "2026")
            p.set_mime_types("image/svg+xml")
            p.set_extensions("svg")
            p.set_priority(-1)
            p.set_thumbnail_loader(PROC_SVG_THUMB)
            return p
        if name == PROC_PS:
            p = Gimp.LoadProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, load_ps, None)
            p.set_menu_label("EPS / PostScript / ancien Illustrator (calques modifiables)")
            p.set_documentation("Ouvre un EPS, un PS ou un ancien fichier Illustrator en calques "
                                "modifiables", "Converti en PDF par Ghostscript, puis importé "
                                "comme un PDF (tracés, textes, images).", name)
            p.set_attribution("ChopGimp", "ChopGimp", "2026")
            p.set_mime_types("application/postscript,image/x-eps")
            p.set_extensions("eps,ps,ai")
            p.set_magics("0,string,%!PS,0,long,0xc5d0d3c6")
            p.set_priority(-1)
            p.set_thumbnail_loader(PROC_PS_THUMB)
            return p
        p = Gimp.LoadProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, load, None)
        p.set_menu_label("PDF / Illustrator (calques modifiables)")
        p.set_documentation("Ouvre un PDF ou un fichier Illustrator (.ai) en calques modifiables",
                            "Tracés en calques vectoriels, textes modifiables, images, calques PDF "
                            "(OCG) en groupes.", name)
        p.set_attribution("ChopGimp", "ChopGimp", "2026")
        p.set_mime_types("application/pdf,application/illustrator")
        p.set_extensions("pdf,ai")
        p.set_magics("0,string,%PDF-")   # même longueur que file-pdf-load : la priorité départage
        p.set_priority(-1)
        p.set_thumbnail_loader(PROC_THUMB)
        return p


if __name__ == "__main__":
    Gimp.main(ChopGimpPDF.__gtype__, sys.argv)

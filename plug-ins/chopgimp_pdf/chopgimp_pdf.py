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
- tracés → calques vectoriels (fond, contour) ; les objets consécutifs
  de même style sont réunis dans un seul calque ;
- images → calques d'image placés sur leurs 4 coins ;
- texte (API texte de poppler) → calques de texte modifiables, ligne par
  ligne, police / taille / couleur reprises ; ou contours vectoriels ;
- dégradés : couleur moyenne (rapport) ; un rendu de référence de la
  page est ajouté, masqué, pour comparer.

Le mode « image (comme avant) » appelle l'import PDF de GIMP.
"""
import math
import os
import re
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

PROC = "file-chopgimp-pdf-load"
PROC_THUMB = "file-chopgimp-pdf-load-thumb"
PROC_PS = "file-chopgimp-eps-load"
PROC_SVG = "file-chopgimp-svg-load"
PROC_PS_THUMB = "file-chopgimp-eps-load-thumb"
PROC_SVG_THUMB = "file-chopgimp-svg-load-thumb"


# ─── outils ─────────────────────────────────────────────────────────────

def pdb_run(name, **kw):
    proc = Gimp.get_pdb().lookup_procedure(name)
    if proc is None:
        return None
    cfg = proc.create_config()
    for k, v in kw.items():
        cfg.set_property(k, v)
    return proc.run(cfg)


def gegl_color(rgba):
    c = Gegl.Color.new("black")
    c.set_rgba_with_space(rgba[0], rgba[1], rgba[2], rgba[3] if len(rgba) > 3 else 1.0, None)
    return c


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


def color_name(rgba):
    return "#%02x%02x%02x" % tuple(int(round(max(0, min(1, v)) * 255)) for v in rgba[:3])


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
        vl.set_fill_color(gegl_color(o.fill[:3] + (1.0,)))
        what.append("fond " + color_name(o.fill))
    else:
        vl.set_enable_fill(False)
    st = o.stroke
    if st:
        vl.set_enable_stroke(True)
        vl.set_stroke_color(gegl_color(st["color"][:3] + (1.0,)))
        vl.set_stroke_width(max(0.1, st["width"]))
        vl.set_stroke_cap_style(CAPS[st["cap"]])
        vl.set_stroke_join_style(JOINS[st["join"]])
        if st["dash"]:
            vl.set_stroke_dash_pattern(st["dash"])
        what.append("contour " + color_name(st["color"]))
    else:
        vl.set_enable_stroke(False)
    alpha = (o.fill or st["color"])[3] if (o.fill or st) else 1.0
    vl.set_name(("Forme %d — " % n) + ", ".join(what))
    image.insert_layer(vl, parent, 0)
    vl.set_opacity(max(0.0, min(100.0, alpha * 100.0)))
    vl.refresh()
    return vl


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
    attrs = page.get_text_attributes() or []
    if not text or not ok_ or not rects:
        return 0
    if len(rects) != len(text):
        report.add("Texte : correspondance caractères / positions incomplète (%d/%d)"
                   % (len(rects), len(text)))
    n_chars = min(len(rects), len(text))

    def attr_at(i):
        for a in attrs:
            if a.start_index <= i <= a.end_index:
                return a
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
            tl.set_color(gegl_color((c.red / 65535.0, c.green / 65535.0, c.blue / 65535.0, 1.0)))
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
    scale = opts["dpi"] / 72.0
    w, h = int(math.ceil(pw * scale)), int(math.ceil(ph * scale))

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
            objs, st = cairoscript.parse(render_script(page, scale, w, h))
            L.hide()
            stats["glyphs"] += st["glyphs"]
            passes.append((title, dict(states)[L], subtract(objs, base_sigs)))
        for L, vis in states:
            (L.show if vis else L.hide)()
    else:
        objs, stats = cairoscript.parse(render_script(page, scale, w, h))
        passes.append(("", True, objs))

    total = sum(len(p[2]) for p in passes)
    merged = [(t, v, merge_runs(objs, 400)) for t, v, objs in passes]
    n_layers = sum(len(m[2]) for m in merged)
    if n_layers > opts["max_objects"]:
        report.add("Page %d : %d objets (plafond %d) : importée en image." %
                   (page_no + 1, n_layers, opts["max_objects"]))
        return False

    if image.get_width() < w or image.get_height() < h:
        image.resize(max(w, image.get_width()), max(h, image.get_height()), 0, 0)

    # rendu de référence, masqué, tout en bas
    ref = Gimp.Layer.new(image, "Page %d — rendu de référence" % (page_no + 1), w, h,
                         Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(ref, None, len(image.get_layers()))
    surf = render_pixels(page, scale, w, h)
    data = bytes(surf.get_data())
    buf = ref.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, w, h), "cairo-ARGB32", data)
    buf.flush()
    ref.set_visible(False)

    page_group = Gimp.GroupLayer.new(image, "Page %d" % (page_no + 1))
    image.insert_layer(page_group, None, 0)
    counts = {"path": 0, "image": 0}
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


# ─── fenêtre d'options ──────────────────────────────────────────────────

def options_dialog(n_pages, n_layers):
    GimpUi.init("chopgimp_pdf")
    dialog = GimpUi.Dialog(title="Importer un PDF / Illustrator", role="chopgimp-pdf", modal=True)
    dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("_Importer", Gtk.ResponseType.OK)
    grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=12)
    dialog.get_content_area().pack_start(grid, True, True, 0)
    row = 0

    def label(t):
        grid.attach(Gtk.Label(label=t, xalign=0), 0, row, 1, 1)

    label("Importer comme")
    mode = Gtk.ComboBoxText()
    mode.append("layers", "Calques modifiables (vecteurs, textes, images)")
    mode.append("image", "Image (comme avant)")
    mode.set_active_id("layers")
    grid.attach(mode, 1, row, 1, 1)
    row += 1
    label("Pages (ex. 1, 3-5)")
    pages = Gtk.Entry(text="1" if n_pages > 1 else "1")
    pages.set_tooltip_text("%d page(s) dans le document" % n_pages)
    grid.attach(pages, 1, row, 1, 1)
    row += 1
    label("Texte")
    text = Gtk.ComboBoxText()
    text.append("editable", "Calques de texte modifiables")
    text.append("outline", "Contours vectoriels")
    text.append("none", "Ignorer")
    text.set_active_id("editable")
    grid.attach(text, 1, row, 1, 1)
    row += 1
    label("Résolution (ppp)")
    dpi = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=150, lower=36, upper=1200, step_increment=1))
    grid.attach(dpi, 1, row, 1, 1)
    row += 1
    label("Nombre maximal d'objets")
    mx = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=1500, lower=50, upper=50000, step_increment=50))
    grid.attach(mx, 1, row, 1, 1)
    row += 1
    hidden = Gtk.CheckButton(label="Importer aussi les calques masqués (%d calque(s) PDF)" % n_layers)
    hidden.set_active(True)
    grid.attach(hidden, 0, row, 2, 1)
    dialog.show_all()
    resp = dialog.run()
    opts = None
    if resp == Gtk.ResponseType.OK:
        opts = {"mode": mode.get_active_id(), "pages": pages.get_text(), "text": text.get_active_id(),
                "dpi": dpi.get_value(), "max_objects": int(mx.get_value()),
                "hidden_layers": hidden.get_active()}
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
    for name in ("libgs.so.10", "libgs.so", ctypes.util.find_library("gs") or ""):
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
            return res, flags
        res, flags = load(procedure, run_mode, Gio.File.new_for_path(pdf), metadata, flags,
                          config, data, classic_file=file)
        return res, flags
    finally:
        try:
            os.unlink(pdf)
        except OSError:
            pass


# ─── SVG : librsvg sur la surface « script », calques Inkscape, textes ───

SVG_NS = "{http://www.w3.org/2000/svg}"
INK_NS = "{http://www.inkscape.org/namespaces/inkscape}"


def svg_matrix(transform):
    """Attribut transform → cairoscript.Matrix (translate, scale, rotate, matrix)."""
    m = cairoscript.Matrix()
    for op, args in re.findall(r"(\w+)\s*\(([^)]*)\)", transform or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if op == "translate":
            t = cairoscript.Matrix(1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif op == "scale":
            t = cairoscript.Matrix(v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif op == "rotate":
            a = math.radians(v[0])
            t = cairoscript.Matrix(math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
        elif op == "matrix" and len(v) == 6:
            t = cairoscript.Matrix(*v)
        else:
            continue
        m = t.mul(m)
    return m


def svg_style(el):
    st = {}
    for item in (el.get("style") or "").split(";"):
        if ":" in item:
            k, v = item.split(":", 1)
            st[k.strip()] = v.strip()
    for k in ("font-size", "font-family", "font-weight", "font-style", "fill", "display"):
        if el.get(k) is not None and k not in st:
            st[k] = el.get(k)
    return st


def parse_len(v, default):
    m = re.match(r"\s*([-\d.eE]+)", v or "")
    return float(m.group(1)) if m else default


def parse_color(v):
    v = (v or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        return tuple(int(v[i:i + 2], 16) / 255.0 for i in (1, 3, 5)) + (1.0,)
    if re.fullmatch(r"#[0-9a-fA-F]{3}", v):
        return tuple(int(c * 2, 16) / 255.0 for c in v[1:]) + (1.0,)
    named = {"black": (0, 0, 0), "white": (1, 1, 1), "red": (1, 0, 0), "green": (0, 0.5, 0),
             "blue": (0, 0, 1)}
    return tuple(named.get(v, (0, 0, 0))) + (1.0,)


def svg_texts(root, base):
    """[(texte, x, y (ligne de base), taille, famille, gras, italique, couleur, id calque)]"""
    out = []

    def walk(el, m, style, layer):
        tag = el.tag
        if tag.startswith(SVG_NS):
            tag = tag[len(SVG_NS):]
        m = svg_matrix(el.get("transform")).mul(m)
        st = dict(style)
        st.update(svg_style(el))
        if st.get("display") == "none":
            return
        if el.get(INK_NS + "groupmode") == "layer":
            layer = el.get("id")
        if tag == "text":
            # une ligne par <tspan> positionné, sinon le texte entier
            spans = [c for c in el if c.tag.endswith("tspan") and c.get("y") is not None]
            items = spans or [el]
            for it in items:
                txt = "".join(it.itertext()).strip()
                if not txt:
                    continue
                ist = dict(st)
                ist.update(svg_style(it))
                x = parse_len((it.get("x") or el.get("x") or "0").split()[0], 0.0)
                y = parse_len((it.get("y") or el.get("y") or "0").split()[0], 0.0)
                px, py = m.apply(x, y)
                size = parse_len(ist.get("font-size"), 16.0) * m.scale_factor()
                out.append((txt, px, py, size, (ist.get("font-family") or "Sans").strip("'\" "),
                            ist.get("font-weight") in ("bold", "700", "800", "900"),
                            ist.get("font-style") in ("italic", "oblique"),
                            parse_color(ist.get("fill", "#000000")), layer))
            return
        for c in el:
            walk(c, m, st, layer)

    walk(root, base, {}, None)
    return out


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
    w, h = int(math.ceil(w)), int(math.ceil(h))
    vp = Rsvg.Rectangle()
    vp.x, vp.y, vp.width, vp.height = 0, 0, w, h
    root = ET.parse(path).getroot()

    # les formes sont rendues depuis une copie sans <text> : librsvg dessine
    # le texte en tracés, qui feraient doublon avec les calques de texte
    shapes = handle
    if opts["text"] != "none":
        stripped = ET.parse(path)
        for parent in stripped.getroot().iter():
            for child in list(parent):
                if child.tag in (SVG_NS + "text", "text"):
                    parent.remove(child)
        fd, tmp_svg = tempfile.mkstemp(suffix=".svg", prefix="chopgimp-svg-")
        os.close(fd)
        stripped.write(tmp_svg, encoding="utf-8", xml_declaration=True)
        try:
            shapes = Rsvg.Handle.new_from_file(tmp_svg)
            shapes.set_dpi(opts["dpi"])
        finally:
            os.unlink(tmp_svg)

    def script(layer_id=None):
        fd, tmp = tempfile.mkstemp(suffix=".cs", prefix="chopgimp-svg-")
        os.close(fd)
        try:
            dev = cairo.ScriptDevice(tmp)
            surf = cairo.ScriptSurface(dev, cairo.Content.COLOR_ALPHA, w, h)
            cr = cairo.Context(surf)
            if layer_id:
                shapes.render_layer(cr, "#" + layer_id, vp)
            else:
                shapes.render_document(cr, vp)
            surf.finish()
            dev.finish()
            with open(tmp, "rb") as f:
                return f.read()
        finally:
            os.unlink(tmp)

    layers = []
    for el in root.iter():
        if el.get(INK_NS + "groupmode") == "layer" and el.get("id"):
            st = svg_style(el)
            layers.append((el.get("id"), el.get(INK_NS + "label") or el.get("id"),
                           st.get("display") != "none"))

    image.resize(max(w, image.get_width()), max(h, image.get_height()), 0, 0)
    all_objs, stats = cairoscript.parse(script())
    passes = []
    sigs_layers = {}
    for lid, label, visible in layers:
        objs, st = cairoscript.parse(script(lid))
        passes.append((label, visible, objs))
        for o in objs:
            k = signature(o)
            sigs_layers[k] = sigs_layers.get(k, 0) + 1
    base = subtract(all_objs, sigs_layers)
    passes.insert(0, ("", True, base))

    # viewBox → pixels pour les textes
    vb = [float(v) for v in re.split(r"[\s,]+", (root.get("viewBox") or "").strip()) if v]
    base_m = cairoscript.Matrix()
    if len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
        base_m = cairoscript.Matrix(w / vb[2], 0, 0, h / vb[3], -vb[0] * w / vb[2], -vb[1] * h / vb[3])

    # rendu de référence (masqué) : comparaison et pixels des dégradés
    ref = Gimp.Layer.new(image, os.path.basename(path) + " — rendu de référence", w, h,
                         Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(ref, None, len(image.get_layers()))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    handle.render_document(cairo.Context(surf), vp)
    surf.flush()
    rbuf = ref.get_buffer()
    rbuf.set(Gegl.Rectangle.new(0, 0, w, h), "cairo-ARGB32", bytes(surf.get_data()))
    rbuf.flush()
    ref.set_visible(False)

    doc_group = Gimp.GroupLayer.new(image, os.path.basename(path))
    image.insert_layer(doc_group, None, 0)
    groups = {}
    counts = {"path": 0, "image": 0}
    for title, visible, objs in [(t, v, merge_runs(o, 400)) for t, v, o in passes]:
        parent = doc_group
        if title:
            parent = Gimp.GroupLayer.new(image, title)
            image.insert_layer(parent, doc_group, 0)
            parent.set_visible(visible)
            groups[title] = parent
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
        label_of = {lid: label for lid, label, _ in layers}
        for txt, x, y, size, family, bold, italic, color, lid in svg_texts(root, base_m):
            parent = groups.get(label_of.get(lid), doc_group)
            name = family.split(",")[0].strip()
            fname, found = (fonts.lookup(name.replace(" ", "") + ("-Bold" if bold else ""))
                            if fonts else (name, False))
            font = (Gimp.Font.get_by_name(fname if found else name) or
                    Gimp.Font.get_by_name("Sans-serif"))
            tl = Gimp.TextLayer.new(image, txt, font, max(1.0, size), Gimp.Unit.pixel())
            tl.set_name(txt[:40])
            image.insert_layer(tl, parent, 0)
            tl.set_color(gegl_color(color))
            if bold or italic:
                tl.set_markup("<markup>%s%s%s</markup>" % ("<b>" * bold + "<i>" * italic,
                                                           GLib.markup_escape_text(txt, -1),
                                                           "</i>" * italic + "</b>" * bold))
            tl.set_offsets(int(round(x)), int(round(y - size * 0.92)))
            n_text += 1

    report.add("SVG : %d formes vectorielles, %d images, %d textes, %d calques Inkscape."
               % (counts["path"], counts["image"], n_text, len(layers)))
    if stats["gradients"]:
        report.add("  %d dégradé(s) repris en pixels (rendu exact, masqué par la forme)." % stats["gradients"])
    if stats["clips"]:
        report.add("  %d découpe(s) non appliquée(s) aux vecteurs." % stats["clips"])
    return True


def load_svg(procedure, run_mode, file, metadata, flags, config, data):
    path = file.get_path()
    opts = {"mode": "layers", "pages": "1", "text": "editable", "dpi": 96.0, "max_objects": 3000,
            "hidden_layers": True}
    if run_mode == Gimp.RunMode.INTERACTIVE:
        chosen = options_dialog(1, 0)
        if chosen is None:
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error()), flags
        opts.update(chosen)
    if opts["mode"] == "image" or not path:
        return pdb_run("file-svg-load", **{"run-mode": run_mode, "file": file}), flags
    image = Gimp.Image.new(1, 1, Gimp.ImageBaseType.RGB)
    image.undo_disable()
    image.set_resolution(opts["dpi"], opts["dpi"])
    report = Report()
    try:
        import_svg(image, path, opts, report, fonts_resolver() if opts["text"] != "none" else None)
    except Exception as e:
        image.delete()
        Gimp.message("Import SVG modifiable impossible (%s) : import d'origine." % e)
        return pdb_run("file-svg-load", **{"run-mode": run_mode, "file": file}), flags
    image.undo_enable()
    raw = [b - 256 if b > 127 else b for b in report.text().encode("utf-8")]
    image.attach_parasite(Gimp.Parasite.new("chopgimp-pdf-report", 0, raw))
    return Gimp.ValueArray.new_from_values([
        GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS),
        GObject.Value(Gimp.Image, image),
    ]), flags


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
        res = classic(classic_file, run_mode)
        return res, flags

    opts = {"mode": "layers", "pages": "1", "text": "editable", "dpi": 150.0, "max_objects": 1500,
            "hidden_layers": True}
    if os.environ.get("CHOPGIMP_PDF_PAGES"):
        opts["pages"] = os.environ["CHOPGIMP_PDF_PAGES"]
    if run_mode == Gimp.RunMode.INTERACTIVE:
        chosen = options_dialog(doc.get_n_pages(), len(ocg_layers(doc)))
        if chosen is None:
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error()), flags
        opts = chosen
    if opts["mode"] == "image":
        return classic(classic_file, run_mode), flags

    pw, ph = doc.get_page(0).get_size()
    scale = opts["dpi"] / 72.0
    image = Gimp.Image.new(max(1, int(math.ceil(pw * scale))), max(1, int(math.ceil(ph * scale))),
                           Gimp.ImageBaseType.RGB)
    image.undo_disable()
    image.set_resolution(opts["dpi"], opts["dpi"])
    report = Report()
    fonts = fonts_resolver() if opts["text"] != "none" else None
    plain = []
    for p in parse_pages(opts["pages"], doc.get_n_pages()):
        try:
            if not import_page(image, doc, p, opts, report, fonts):
                plain.append(p)
        except Exception as e:
            import traceback
            traceback.print_exc()          # dans le journal de session
            report.add("Page %d : import vectoriel impossible (%s)" % (p + 1, e))
            plain.append(p)
    image.undo_enable()

    if not image.get_layers():                # rien d'importé : import classique
        image.delete()
        return classic(classic_file, run_mode), flags

    text = report.text()
    if text:
        raw = [b - 256 if b > 127 else b for b in text.encode("utf-8")]
        image.attach_parasite(Gimp.Parasite.new("chopgimp-pdf-report", 0, raw))
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


class ChopGimpPDF(Gimp.PlugIn):
    def do_query_procedures(self):
        # la vignette d'abord : GIMP refuse un chargeur de vignette pas encore déclaré
        return [PROC_THUMB, PROC_PS_THUMB, PROC_SVG_THUMB, PROC, PROC_PS, PROC_SVG]

    def do_create_procedure(self, name):
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
                                "Formes en calques vectoriels, calques Inkscape en groupes, textes "
                                "modifiables.", name)
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

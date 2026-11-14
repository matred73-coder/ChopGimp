#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — production et exports façon Photoshop (étape « Base III »).

Fichier > Exporter pour le web…
    JPEG, WebP, PNG ou AVIF ; qualité, taille ; aperçu avant / après avec
    le poids du fichier, recalculé à chaque réglage.
Fichier > Générer les ressources
    Chaque calque dont le nom est un nom de fichier (« logo.png »,
    « bannière.jpg 80% », « icône.png 200% », plusieurs séparés par des
    virgules) est exporté dans « <image>-ressources/ ». Activable pour
    chaque enregistrement (Fichier > Générer les ressources à chaque
    enregistrement), comme le Generator de Photoshop.
Fichier > Traitement par lots…
    Applique à tout un dossier : taille maximale, accentuation, sRGB,
    filigrane texte, format et qualité de sortie.
Fenêtres > Compositions de calques…
    Mémorise visibilité, position et opacité des calques sous un nom,
    les rappelle, et exporte chaque composition.
"""
import json
import os
import re
import sys
import tempfile

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gimp, GimpUi, Gio, GLib, GdkPixbuf, GObject, Gtk

PROCS = {
    "chopgimp-export-web": ("Exporter pour le web…", "<Image>/File/Export"),
    "chopgimp-generate-assets": ("Générer les ressources", "<Image>/File/Export"),
    "chopgimp-generator-toggle": ("Générer les ressources à chaque enregistrement", "<Image>/File/Export"),
    "chopgimp-batch": ("Traitement par lots…", "<Image>/File/Export"),
    "chopgimp-layer-comps": ("Compositions de calques…", "<Image>/Windows"),
}
GEN_PARASITE = "chopgimp-generator-on"
COMPS_PARASITE = "chopgimp-layer-comps"

FORMATS = {
    "jpg": ("file-jpeg-export", {"quality": lambda q: q / 100.0}),
    "webp": ("file-webp-export", {"quality": lambda q: float(q)}),
    "avif": ("file-heif-av1-export", {"quality": lambda q: int(q)}),
    "png": ("file-png-export", {"compression": lambda q: 9}),
}


def ok(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def fail(procedure, msg):
    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                       GLib.Error.new_literal(GLib.quark_from_string("chopgimp"), msg, 0))


def parasite_json(item, name, default):
    par = item.get_parasite(name)
    if not par:
        return default
    try:
        return json.loads(bytes(b & 255 for b in par.get_data()).decode("utf-8"))
    except ValueError:
        return default


def set_parasite_json(item, name, data):
    raw = [b - 256 if b > 127 else b for b in json.dumps(data).encode("utf-8")]
    item.attach_parasite(Gimp.Parasite.new(name, Gimp.PARASITE_PERSISTENT, raw))


def export_image(image, path, fmt, quality):
    """Exporte une image (aplatie) au format voulu. → taille en octets ou None."""
    proc_name, props = FORMATS[fmt]
    proc = Gimp.get_pdb().lookup_procedure(proc_name)
    if proc is None:
        return None
    flat = image.duplicate()
    if fmt == "jpg":
        flat.flatten()
    else:
        flat.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
    cfg = proc.create_config()
    cfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
    cfg.set_property("image", flat)
    cfg.set_property("file", Gio.File.new_for_path(path))
    for k, f in props.items():
        try:
            cfg.set_property(k, f(quality))
        except (TypeError, ValueError):
            pass
    res = proc.run(cfg)
    flat.delete()
    if res.index(0) != Gimp.PDBStatusType.SUCCESS or not os.path.exists(path):
        return None
    return os.path.getsize(path)


def human(n):
    return "%.0f Ko" % (n / 1024.0) if n < 1024 * 1024 else "%.2f Mo" % (n / 1048576.0)


# ─── exporter pour le web ───────────────────────────────────────────────

def export_web(image):
    GimpUi.init("chopgimp_web")
    dlg = GimpUi.Dialog(title="Exporter pour le web", role="chopgimp-export-web", modal=True)
    dlg.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dlg.add_button("_Enregistrer…", Gtk.ResponseType.OK)
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, margin=12)
    dlg.get_content_area().pack_start(box, True, True, 0)
    previews = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    box.pack_start(previews, True, True, 0)
    pics, caps = [], []
    for title in ("Original", "Exporté"):
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        img = Gtk.Image()
        img.set_size_request(320, 320)
        cap = Gtk.Label(label=title)
        col.pack_start(img, True, True, 0)
        col.pack_start(cap, False, False, 0)
        previews.pack_start(col, True, True, 0)
        pics.append(img)
        caps.append(cap)
    grid = Gtk.Grid(column_spacing=8, row_spacing=8)
    box.pack_start(grid, False, False, 0)
    grid.attach(Gtk.Label(label="Format", xalign=0), 0, 0, 1, 1)
    fmt = Gtk.ComboBoxText()
    for k, lab in (("jpg", "JPEG"), ("webp", "WebP"), ("avif", "AVIF"), ("png", "PNG")):
        fmt.append(k, lab)
    fmt.set_active_id("jpg")
    grid.attach(fmt, 1, 0, 1, 1)
    grid.attach(Gtk.Label(label="Qualité", xalign=0), 0, 1, 1, 1)
    qual = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 100, 1)
    qual.set_value(80)
    qual.set_size_request(180, -1)
    grid.attach(qual, 1, 1, 1, 1)
    grid.attach(Gtk.Label(label="Taille (%)", xalign=0), 0, 2, 1, 1)
    size = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=100, lower=5, upper=100, step_increment=5))
    grid.attach(size, 1, 2, 1, 1)
    info = Gtk.Label(xalign=0)
    grid.attach(info, 0, 3, 2, 1)

    tmpdir = tempfile.mkdtemp(prefix="chopgimp-web-")
    pending = [0]
    state = {}

    def preview_of(path):
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
        k = min(320.0 / pb.get_width(), 320.0 / pb.get_height(), 1.0)
        return pb.scale_simple(max(1, int(pb.get_width() * k)), max(1, int(pb.get_height() * k)),
                               GdkPixbuf.InterpType.BILINEAR)

    def refresh():
        pending[0] = 0
        f = fmt.get_active_id()
        work = image.duplicate()
        pct = size.get_value() / 100.0
        if pct < 1.0:
            work.scale(max(1, int(image.get_width() * pct)), max(1, int(image.get_height() * pct)))
        orig = os.path.join(tmpdir, "original.png")
        out = os.path.join(tmpdir, "export." + f)
        export_image(work, orig, "png", 100)
        n = export_image(work, out, f, qual.get_value())
        state.update(fmt=f, quality=qual.get_value(), pct=pct)
        try:
            pics[0].set_from_pixbuf(preview_of(orig))
            if n and f != "avif":
                pics[1].set_from_pixbuf(preview_of(out))
        except GLib.Error:
            pass
        caps[0].set_text("Original — %s (PNG)" % human(os.path.getsize(orig)))
        caps[1].set_text("Exporté — %s" % (human(n) if n else "format indisponible"))
        info.set_text("%d × %d px" % (work.get_width(), work.get_height()))
        work.delete()
        return False

    def changed(*_):
        if pending[0]:
            GLib.source_remove(pending[0])
        pending[0] = GLib.timeout_add(300, refresh)

    for w, sig in ((fmt, "changed"), (qual, "value-changed"), (size, "value-changed")):
        w.connect(sig, changed)
    dlg.show_all()
    refresh()
    resp = dlg.run()
    dlg.destroy()
    if resp != Gtk.ResponseType.OK:
        return "cancel"
    chooser = Gtk.FileChooserDialog(title="Enregistrer pour le web", action=Gtk.FileChooserAction.SAVE)
    chooser.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    chooser.add_button("_Enregistrer", Gtk.ResponseType.OK)
    chooser.set_do_overwrite_confirmation(True)
    base = os.path.splitext(image.get_name() or "image")[0]
    chooser.set_current_name("%s.%s" % (base, state["fmt"]))
    f = image.get_file()
    if f is not None and f.get_parent() is not None:
        chooser.set_current_folder_file(f.get_parent())
    r = chooser.run()
    target = chooser.get_filename()
    chooser.destroy()
    if r != Gtk.ResponseType.OK or not target:
        return "cancel"
    work = image.duplicate()
    if state["pct"] < 1.0:
        work.scale(max(1, int(image.get_width() * state["pct"])),
                   max(1, int(image.get_height() * state["pct"])))
    n = export_image(work, target, state["fmt"], state["quality"])
    work.delete()
    if not n:
        return "Export impossible dans ce format."
    Gimp.message("Exporté : %s (%s)" % (target, human(n)))
    return None


# ─── génération de ressources ───────────────────────────────────────────

ASSET = re.compile(r"^\s*(?:(\d+)%\s+)?([^,]+?\.(png|jpe?g|webp|gif))(?:\s+(\d+)%)?\s*$", re.I)


def walk(layers):
    for l in layers:
        yield l
        if isinstance(l, Gimp.GroupLayer):
            yield from walk(l.get_children())


def generate_assets(image, quiet=False):
    f = image.get_file()
    if f is None:
        return "Enregistrez d'abord l'image : les ressources vont à côté du fichier."
    folder = os.path.join(os.path.dirname(f.get_path()),
                          os.path.splitext(os.path.basename(f.get_path()))[0] + "-ressources")
    made = []
    for layer in walk(image.get_layers()):
        for part in layer.get_name().split(","):
            m = ASSET.match(part)
            if not m:
                continue
            scale_pre, name, ext, num = m.group(1), m.group(2), m.group(3).lower(), m.group(4)
            ext = "jpg" if ext == "jpeg" else ext
            if ext == "gif":
                continue
            scale = int(scale_pre) / 100.0 if scale_pre else 1.0
            quality = 90
            if num:
                if ext == "jpg" or ext == "webp":
                    quality = int(num)
                else:
                    scale = int(num) / 100.0
            os.makedirs(folder, exist_ok=True)
            tmp = Gimp.Image.new(image.get_width(), image.get_height(), Gimp.ImageBaseType.RGB)
            copy = Gimp.Layer.new_from_drawable(layer, tmp)
            tmp.insert_layer(copy, None, 0)
            copy.set_visible(True)
            tmp.crop(layer.get_width(), layer.get_height(), *layer.get_offsets()[1:])
            if scale != 1.0:
                tmp.scale(max(1, int(tmp.get_width() * scale)), max(1, int(tmp.get_height() * scale)))
            if export_image(tmp, os.path.join(folder, name), ext, quality):
                made.append(name)
            tmp.delete()
    if not quiet:
        Gimp.message("Ressources générées dans %s : %s" % (folder, ", ".join(made) if made else
                     "aucune (nommez des calques « logo.png », « photo.jpg 80% »…)"))
    return None


# ─── traitement par lots ────────────────────────────────────────────────

def batch_dialog():
    GimpUi.init("chopgimp_web")
    dlg = GimpUi.Dialog(title="Traitement par lots", role="chopgimp-batch", modal=True)
    dlg.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dlg.add_button("_Lancer", Gtk.ResponseType.OK)
    g = Gtk.Grid(column_spacing=10, row_spacing=8, margin=12)
    dlg.get_content_area().pack_start(g, True, True, 0)
    src = Gtk.FileChooserButton(title="Dossier source", action=Gtk.FileChooserAction.SELECT_FOLDER)
    dst = Gtk.FileChooserButton(title="Dossier de sortie", action=Gtk.FileChooserAction.SELECT_FOLDER)
    maxs = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=2000, lower=0, upper=20000, step_increment=100))
    sharpen = Gtk.CheckButton(label="Accentuer légèrement")
    srgb = Gtk.CheckButton(label="Convertir en sRGB")
    srgb.set_active(True)
    mark = Gtk.Entry(placeholder_text="Filigrane (texte, facultatif)")
    fmt = Gtk.ComboBoxText()
    for k, lab in (("jpg", "JPEG"), ("webp", "WebP"), ("png", "PNG"), ("avif", "AVIF")):
        fmt.append(k, lab)
    fmt.set_active_id("jpg")
    qual = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=85, lower=10, upper=100, step_increment=1))
    rows = [("Dossier source", src), ("Dossier de sortie", dst), ("Côté maximal (px, 0 = garder)", maxs),
            ("", sharpen), ("", srgb), ("Filigrane", mark), ("Format", fmt), ("Qualité", qual)]
    for i, (lab, w) in enumerate(rows):
        g.attach(Gtk.Label(label=lab, xalign=0), 0, i, 1, 1)
        g.attach(w, 1, i, 1, 1)
    dlg.show_all()
    resp = dlg.run()
    opts = None
    if resp == Gtk.ResponseType.OK and src.get_filename() and dst.get_filename():
        opts = {"src": src.get_filename(), "dst": dst.get_filename(), "max": int(maxs.get_value()),
                "sharpen": sharpen.get_active(), "srgb": srgb.get_active(), "mark": mark.get_text(),
                "fmt": fmt.get_active_id(), "quality": qual.get_value()}
    dlg.destroy()
    return opts


def batch_run(opts):
    exts = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".psd", ".xcf", ".heic", ".avif")
    files = sorted(f for f in os.listdir(opts["src"]) if f.lower().endswith(exts))
    done, errors = 0, []
    Gimp.progress_init("Traitement par lots…")
    for i, name in enumerate(files):
        Gimp.progress_update(i / max(1, len(files)))
        try:
            im = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE,
                                Gio.File.new_for_path(os.path.join(opts["src"], name)))
        except GLib.Error as e:
            errors.append("%s (%s)" % (name, e.message))
            continue
        w, h = im.get_width(), im.get_height()
        if opts["max"] and max(w, h) > opts["max"]:
            k = opts["max"] / float(max(w, h))
            im.scale(max(1, int(w * k)), max(1, int(h * k)))
        if opts["srgb"]:
            try:
                im.convert_color_profile(Gimp.ColorProfile.new_rgb_srgb(),
                                         Gimp.ColorRenderingIntent.PERCEPTUAL, True)
            except Exception:
                pass
        im.flatten() if opts["fmt"] == "jpg" else im.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        if opts["sharpen"]:
            d = im.get_layers()[0]
            f = Gimp.DrawableFilter.new(d, "gegl:unsharp-mask", "Accentuation")
            cfg = f.get_config()
            cfg.set_property("std-dev", 1.0)
            cfg.set_property("scale", 0.5)
            f.update()
            d.merge_filter(f)
        if opts["mark"]:
            size = max(12.0, im.get_width() / 40.0)
            tl = Gimp.TextLayer.new(im, opts["mark"], Gimp.Font.get_by_name("Sans-serif"), size,
                                    Gimp.Unit.pixel())
            im.insert_layer(tl, None, 0)
            tl.set_opacity(60)
            tl.set_offsets(int(im.get_width() - tl.get_width() - size), int(im.get_height() - tl.get_height() - size / 2))
        out = os.path.join(opts["dst"], os.path.splitext(name)[0] + "." + opts["fmt"])
        if export_image(im, out, opts["fmt"], opts["quality"]):
            done += 1
        else:
            errors.append(name)
        im.delete()
    Gimp.progress_end()
    Gimp.message("Traitement par lots : %d fichier(s) dans %s%s" %
                 (done, opts["dst"], ("\nErreurs : " + ", ".join(errors)) if errors else ""))


# ─── compositions de calques ────────────────────────────────────────────

def comp_capture(image):
    return {str(l.get_tattoo()): {"visible": l.get_visible(), "x": l.get_offsets()[1],
                                  "y": l.get_offsets()[2], "opacity": l.get_opacity()}
            for l in walk(image.get_layers())}


def comp_apply(image, state):
    for l in walk(image.get_layers()):
        s = state.get(str(l.get_tattoo()))
        if not s:
            continue
        l.set_visible(s["visible"])
        l.set_opacity(s["opacity"])
        _, x, y = l.get_offsets()
        if (x, y) != (s["x"], s["y"]):
            l.set_offsets(s["x"], s["y"])


def layer_comps(image):
    comps = parasite_json(image, COMPS_PARASITE, {})
    GimpUi.init("chopgimp_web")
    dlg = GimpUi.Dialog(title="Compositions de calques", role="chopgimp-layer-comps", modal=True)
    dlg.add_button("_Fermer", Gtk.ResponseType.CLOSE)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=12)
    dlg.get_content_area().pack_start(box, True, True, 0)
    store = Gtk.ListStore(str)
    view = Gtk.TreeView(model=store, headers_visible=False)
    view.append_column(Gtk.TreeViewColumn("Nom", Gtk.CellRendererText(), text=0))
    sw = Gtk.ScrolledWindow(min_content_height=200, min_content_width=280)
    sw.add(view)
    box.pack_start(sw, True, True, 0)
    row = Gtk.Box(spacing=4)
    box.pack_start(row, False, False, 0)

    def reload():
        store.clear()
        for name in comps:
            store.append([name])

    def selected():
        m, it = view.get_selection().get_selected()
        return m[it][0] if it else None

    def save():
        set_parasite_json(image, COMPS_PARASITE, comps)

    def on_new(_):
        n = "Composition %d" % (len(comps) + 1)
        comps[n] = comp_capture(image)
        save()
        reload()

    def on_update(_):
        n = selected()
        if n:
            comps[n] = comp_capture(image)
            save()

    def on_apply(_):
        n = selected()
        if n:
            image.undo_group_start()
            comp_apply(image, comps[n])
            image.undo_group_end()
            Gimp.displays_flush()

    def on_delete(_):
        n = selected()
        if n:
            del comps[n]
            save()
            reload()

    def on_export(_):
        f = image.get_file()
        if f is None or not comps:
            Gimp.message("Enregistrez l'image et créez au moins une composition.")
            return
        folder = os.path.splitext(f.get_path())[0] + "-compositions"
        os.makedirs(folder, exist_ok=True)
        current = comp_capture(image)
        for n, st in comps.items():
            comp_apply(image, st)
            export_image(image, os.path.join(folder, re.sub(r"[^\w.\- ]", "_", n) + ".png"), "png", 100)
        comp_apply(image, current)
        Gimp.displays_flush()
        Gimp.message("Compositions exportées dans " + folder)

    for lab, cb in (("Nouvelle", on_new), ("Mettre à jour", on_update), ("Appliquer", on_apply),
                    ("Supprimer", on_delete), ("Exporter tout", on_export)):
        b = Gtk.Button(label=lab)
        b.connect("clicked", cb)
        row.pack_start(b, True, True, 0)
    view.connect("row-activated", lambda *a: on_apply(None))
    reload()
    dlg.show_all()
    dlg.run()
    dlg.destroy()
    return None


class ChopGimpWeb(Gimp.PlugIn):
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
                               Gimp.ProcedureSensitivityMask.NO_DRAWABLES |
                               (Gimp.ProcedureSensitivityMask.NO_IMAGE if name == "chopgimp-batch" else 0))
        return p

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        interactive = run_mode == Gimp.RunMode.INTERACTIVE
        msg = None
        if name == "chopgimp-export-web":
            msg = export_web(image) if interactive else "Fenêtre interactive."
        elif name == "chopgimp-generate-assets":
            msg = generate_assets(image, quiet=not interactive)
        elif name == "chopgimp-generator-toggle":
            on = not parasite_json(image, GEN_PARASITE, False)
            set_parasite_json(image, GEN_PARASITE, on)
            Gimp.message("Génération des ressources à chaque enregistrement : %s" %
                         ("activée" if on else "désactivée"))
        elif name == "chopgimp-batch":
            opts = batch_dialog() if interactive else None
            if opts is None:
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            batch_run(opts)
        else:
            msg = layer_comps(image) if interactive else None
        if msg == "cancel":
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        return fail(procedure, msg) if msg else ok(procedure)


if __name__ == "__main__":
    Gimp.main(ChopGimpWeb.__gtype__, sys.argv)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — fonctions de base façon Photoshop (étape « Base II »).

Calque > Nouveau calque de remplissage
    Couleur unie…   calque vectoriel couvrant l'image (couleur modifiable
                    dans la barre d'options, comme une forme)
    Dégradé…        calque + incrustation de dégradé modifiable
                    (Calque > Effets > Modifier l'effet)
    Motif…          calque rempli du motif actif
Image > Instantané
    Créer un instantané   copie de l'image à cet instant (panneau Images)
    Revenir à un instantané…   ouvre la copie choisie
Filtres > Camera Raw…
    exposition, contraste, hautes lumières, ombres, clarté, vibrance,
    saturation, température, vignettage, grain : des filtres non
    destructifs (« Camera Raw : … »), réglés avec aperçu en direct et
    modifiables ensuite (icône fx).
"""
import os
import sys
import time

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, GimpUi, Gegl, Gio, GLib, Gtk

try:                        # accélère les options de fusion « Si » (facultatif)
    import numpy as np
except Exception:
    np = None

FILL = "<Image>/Layer/Nouveau calque de remplissage"
SNAP = "<Image>/Image/Instantané"
PROCS = {
    "chopgimp-fill-color": ("Couleur unie…", FILL),
    "chopgimp-fill-gradient": ("Dégradé…", FILL),
    "chopgimp-fill-pattern": ("Motif", FILL),
    "chopgimp-snapshot-new": ("Créer un instantané", SNAP),
    "chopgimp-snapshot-revert": ("Revenir à un instantané…", SNAP),
    "chopgimp-camera-raw": ("Camera Raw…", "<Image>/Filters"),
    "chopgimp-blend-if": ("Options de fusion « Si »…", "<Image>/Layer/Style de calque"),
}
BLEND_PARASITE = "chopgimp-blend-if"
CR_PREFIX = "Camera Raw : "
SNAP_PARASITE = "chopgimp-snapshot-of"


def ok(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def fail(procedure, msg):
    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                       GLib.Error.new_literal(GLib.quark_from_string("chopgimp"), msg, 0))


def insert_target(image):
    sel = image.get_selected_layers()
    if sel:
        return sel[0].get_parent(), image.get_item_position(sel[0])
    return None, 0


# ─── calques de remplissage ─────────────────────────────────────────────

def fill_color(image, interactive):
    color = Gimp.context_get_foreground()
    if interactive:
        GimpUi.init("chopgimp_studio")
        dlg = Gtk.ColorChooserDialog(title="Calque de remplissage — couleur unie")
        r, g, b, a = color.get_rgba_with_space(None)
        from gi.repository import Gdk
        dlg.set_rgba(Gdk.RGBA(r, g, b, 1.0))
        resp = dlg.run()
        rgba = dlg.get_rgba()
        dlg.destroy()
        if resp != Gtk.ResponseType.OK:
            return "cancel"
        color = Gegl.Color.new("black")
        color.set_rgba_with_space(rgba.red, rgba.green, rgba.blue, 1.0, None)
    w, h = image.get_width(), image.get_height()
    path = Gimp.Path.new(image, "Remplissage")
    path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER,
                                [0, 0, 0, 0, 0, 0, w, 0, w, 0, w, 0, w, h, w, h, w, h, 0, h, 0, h, 0, h],
                                True)
    image.insert_path(path, None, -1)
    vl = Gimp.VectorLayer.new(image, path)
    vl.set_name("Couleur unie")
    vl.set_enable_fill(True)
    vl.set_fill_color(color)
    vl.set_enable_stroke(False)
    parent, pos = insert_target(image)
    image.insert_layer(vl, parent, pos)
    vl.refresh()
    image.set_selected_layers([vl])
    return None


def new_full_layer(image, name):
    layer = Gimp.Layer.new(image, name, image.get_width(), image.get_height(),
                           Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    parent, pos = insert_target(image)
    image.insert_layer(layer, parent, pos)
    return layer


def fill_gradient(image, run_mode):
    layer = new_full_layer(image, "Dégradé")
    layer.fill(Gimp.FillType.WHITE)
    image.set_selected_layers([layer])
    proc = Gimp.get_pdb().lookup_procedure("chopgimp-fx-gradient-overlay")
    if proc is None:
        return "Le plug-in de styles est absent."
    cfg = proc.create_config()
    cfg.set_property("run-mode", run_mode)
    cfg.set_property("image", image)
    cfg.set_core_object_array("drawables", [layer])
    res = proc.run(cfg)
    if res.index(0) == Gimp.PDBStatusType.CANCEL:
        image.remove_layer(layer)
        return "cancel"
    return None


def fill_pattern(image):
    layer = new_full_layer(image, "Motif — " + Gimp.context_get_pattern().get_name())
    layer.fill(Gimp.FillType.PATTERN)
    image.set_selected_layers([layer])
    return None


# ─── instantanés ────────────────────────────────────────────────────────

def snapshot_new(image):
    copy = image.duplicate()
    stamp = time.strftime("%H:%M:%S")
    base = image.get_name() or "image"
    name = "Instantané %s — %s" % (stamp, os.path.splitext(base)[0])
    copy.set_file(Gio.File.new_for_path(os.path.join(GLib.get_tmp_dir(), name + ".xcf")))
    copy.clean_all()
    raw = [b - 256 if b > 127 else b for b in str(image.get_id()).encode()]
    copy.attach_parasite(Gimp.Parasite.new(SNAP_PARASITE, 0, raw))
    Gimp.message("%s créé (panneau Images). Image > Instantané > Revenir à un instantané… "
                 "pour l'ouvrir." % name)
    return None


def snapshots_of(image):
    out = []
    for im in Gimp.get_images():
        par = im.get_parasite(SNAP_PARASITE)
        if par and bytes(b & 255 for b in par.get_data()).decode() == str(image.get_id()):
            out.append(im)
    return out


def snapshot_revert(image):
    snaps = snapshots_of(image)
    if not snaps:
        return "Aucun instantané pour cette image (Image > Instantané > Créer un instantané)."
    GimpUi.init("chopgimp_studio")
    dlg = GimpUi.Dialog(title="Revenir à un instantané", role="chopgimp-snapshot", modal=True)
    dlg.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dlg.add_button("_Ouvrir", Gtk.ResponseType.OK)
    lb = Gtk.ListBox(margin=12)
    for im in snaps:
        lb.add(Gtk.Label(label=im.get_name(), xalign=0, margin=6))
    lb.select_row(lb.get_row_at_index(len(snaps) - 1))
    dlg.get_content_area().pack_start(lb, True, True, 0)
    dlg.show_all()
    resp = dlg.run()
    row = lb.get_selected_row()
    dlg.destroy()
    if resp != Gtk.ResponseType.OK or row is None:
        return "cancel"
    Gimp.Display.new(snaps[row.get_index()])
    return None


# ─── Camera Raw ─────────────────────────────────────────────────────────

# (clé, libellé, mini, maxi, défaut, opération, fonction valeur → propriétés)
CR = [
    ("exposure", "Exposition (IL)", -4.0, 4.0, 0.0, "gegl:exposure", lambda v: {"exposure": v}),
    ("contrast", "Contraste", -100, 100, 0, "gimp:brightness-contrast", lambda v: {"contrast": v / 100.0}),
    ("highlights", "Hautes lumières", -100, 100, 0, "gegl:shadows-highlights",
     lambda v: {"highlights": v, "shadows": 0.0}),
    ("shadows", "Ombres", -100, 100, 0, "gegl:shadows-highlights",
     lambda v: {"shadows": v, "highlights": 0.0}),
    ("clarity", "Clarté", 0, 100, 0, "gegl:unsharp-mask",
     lambda v: {"std-dev": 40.0, "scale": v / 100.0}),
    ("vibrance", "Vibrance", -100, 100, 0, "gegl:saturation", lambda v: {"scale": 1.0 + v / 200.0}),
    ("saturation", "Saturation", -100, 100, 0, "gimp:hue-saturation", lambda v: {"saturation": v / 100.0}),
    ("temperature", "Température (K)", 2000, 12000, 6500, "gegl:color-temperature",
     lambda v: {"original-temperature": 6500.0, "intended-temperature": float(v)}),
    ("vignette", "Vignettage", 0, 100, 0, "gegl:vignette",
     lambda v: {"radius": 1.2, "softness": 0.8, "gamma": 2.0, "proportion": 1.0, "squeeze": 0.0,
                "x": 0.5, "y": 0.5, "rotation": 0.0}),
    ("grain", "Grain", 0, 100, 0, "gegl:noise-rgb",
     lambda v: {"red": v / 400.0, "green": v / 400.0, "blue": v / 400.0, "independent": False,
                "gaussian": True, "linear": False}),
]


def cr_apply(layer, values, keep=None):
    """Remplace les filtres « Camera Raw : » du calque par ceux des valeurs
    non neutres. keep : identifiants de filtres à ne pas supprimer (aperçu)."""
    keep = keep or ()
    for f in list(layer.get_filters() or []):
        if f.get_name().startswith(CR_PREFIX) and f.get_id() not in keep:
            f.delete()
    for key, label, lo, hi, default, op, props in CR:
        v = values.get(key, default)
        if abs(v - default) < 1e-6:
            continue
        try:
            f = Gimp.DrawableFilter.new(layer, op, CR_PREFIX + label)
        except Exception:
            continue
        cfg = f.get_config()
        for k, val in props(v).items():
            try:
                cfg.set_property(k, val)
            except (TypeError, ValueError):
                pass
        if key == "vignette":
            f.set_opacity(v / 100.0)
        f.update()
        layer.append_filter(f)


def camera_raw(image, layer):
    GimpUi.init("chopgimp_studio")
    dlg = GimpUi.Dialog(title="Camera Raw — " + layer.get_name(), role="chopgimp-camera-raw", modal=True)
    dlg.add_button("_Réinitialiser", 1)
    dlg.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dlg.add_button("_OK", Gtk.ResponseType.OK)
    grid = Gtk.Grid(column_spacing=12, row_spacing=6, margin=12)
    dlg.get_content_area().pack_start(grid, True, True, 0)
    scales = {}
    for row, (key, label, lo, hi, default, op, props) in enumerate(CR):
        grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
        step = 0.05 if isinstance(lo, float) else 1
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
        sc.set_value(default)
        sc.set_hexpand(True)
        sc.set_size_request(260, -1)
        sc.set_digits(2 if isinstance(lo, float) else 0)
        grid.attach(sc, 1, row, 1, 1)
        scales[key] = sc

    # filtres d'origine masqués pendant l'aperçu, historique gelé
    originals = [f for f in (layer.get_filters() or []) if f.get_name().startswith(CR_PREFIX)]
    vis = {f.get_id(): f.get_visible() for f in originals}
    image.undo_freeze()
    pending = [0]

    def values():
        return {k: s.get_value() for k, s in scales.items()}

    def refresh():
        pending[0] = 0
        for f in originals:
            f.set_visible(False)
        # même rendu que le résultat final (opacité du vignettage comprise)
        cr_apply(layer, values(), keep=vis)
        Gimp.displays_flush()
        return False

    def changed(*_):
        if pending[0]:
            GLib.source_remove(pending[0])
        pending[0] = GLib.timeout_add(150, refresh)

    for s in scales.values():
        s.connect("value-changed", changed)
    resp = Gtk.ResponseType.CANCEL
    try:
        dlg.show_all()
        while True:
            resp = dlg.run()
            if resp == 1:
                for key, label, lo, hi, default, op, props in CR:
                    scales[key].set_value(default)
                continue
            break
    finally:
        if pending[0]:
            GLib.source_remove(pending[0])
        final = values()
        # retour à l'état d'origine, puis une seule étape d'annulation
        try:
            for f in list(layer.get_filters() or []):
                if f.get_name().startswith(CR_PREFIX) and f.get_id() not in vis:
                    f.delete()
            for f in originals:
                f.set_visible(vis[f.get_id()])
        finally:
            image.undo_thaw()
            dlg.destroy()
    if resp != Gtk.ResponseType.OK:
        return "cancel"
    image.undo_group_start()
    try:
        cr_apply(layer, final)
    finally:
        image.undo_group_end()
    return None


# ─── options de fusion « Si » (Blend If) ─────────────────────────────────

def ramp_lut(b0, b1, w0, w1):
    """Table 0..255 → 0..1 : invisible sous b0 et au-dessus de w1, rampes
    b0→b1 et w0→w1 (curseurs scindés de Photoshop)."""
    out = []
    for i in range(256):
        if i < b0 or i > w1:
            v = 0.0
        elif i < b1:
            v = (i - b0) / max(1.0, b1 - b0)
        elif i > w0:
            v = (w1 - i) / max(1.0, w1 - w0)
        else:
            v = 1.0
        out.append(max(0.0, min(1.0, v)))
    return out


def blend_if_apply(image, layer, this, below):
    """this / below : (noir début, noir fin, blanc début, blanc fin) en 0..255.
    Résultat : masque de calque = plage de « ce calque » × plage du dessous.
    Renvoie un message d'erreur, ou None."""
    neutral = (0, 0, 255, 255)
    active = tuple(this) != neutral or tuple(below) != neutral
    if layer.get_mask() is not None:
        # seul un masque créé par « Si » (valeurs non neutres mémorisées)
        # est remplacé : jamais le masque de l'utilisateur
        prev = blend_if_values(layer)
        if prev is None or prev == [0, 0, 255, 255, 0, 0, 255, 255]:
            if not active:
                return None
            return ("Ce calque a déjà un masque de calque : appliquez-le ou supprimez-le "
                    "avant les options de fusion « Si ».")
        layer.remove_mask(Gimp.MaskApplyMode.DISCARD)
    if active:
        mask = layer.create_mask(Gimp.AddMaskType.COPY if tuple(this) != neutral
                                 else Gimp.AddMaskType.WHITE)
        layer.add_mask(mask)
        if tuple(this) != neutral:
            mask.curves_explicit(Gimp.HistogramChannel.VALUE, ramp_lut(*this))
        if tuple(below) != neutral:
            blend_if_below(image, layer, mask, below)
    raw = [b - 256 if b > 127 else b
           for b in ("%d %d %d %d %d %d %d %d" % (tuple(this) + tuple(below))).encode()]
    layer.attach_parasite(Gimp.Parasite.new(BLEND_PARASITE, 0, raw))
    return None


def blend_if_values(layer):
    """Valeurs « Si » mémorisées sur le calque (8 entiers), ou None."""
    par = layer.get_parasite(BLEND_PARASITE)
    if not par:
        return None
    try:
        vals = [int(v) for v in bytes(b & 255 for b in par.get_data()).decode().split()]
    except (ValueError, UnicodeDecodeError):
        return None
    return vals if len(vals) == 8 else None


def blend_if_below(image, layer, mask, below):
    """Multiplie le masque par la plage de luminance de ce qui est dessous."""
    # rendu du dessous : ce calque et tout ce qui est au-dessus, masqués
    hidden = [layer] if layer.get_visible() else []
    node = layer
    while node is not None:
        parent = node.get_parent()
        sibs = list(parent.get_children() if parent else image.get_layers())
        hidden += [l for l in sibs[:sibs.index(node)] if l.get_visible()]
        node = parent
    for l in hidden:
        l.set_visible(False)
    under = Gimp.Layer.new_from_visible(image, image, "dessous")
    for l in hidden:
        l.set_visible(True)
    image.insert_layer(under, None, 0)
    try:
        under.desaturate(Gimp.DesaturateMode.LUMINANCE)
        under.curves_explicit(Gimp.HistogramChannel.VALUE, ramp_lut(*below))

        # produit des deux, lu dans le cadre du calque
        _, ox, oy = layer.get_offsets()
        w, h = layer.get_width(), layer.get_height()
        _, ux, uy = under.get_offsets()
        m = mask.get_buffer().get(Gegl.Rectangle.new(0, 0, w, h), 1.0, "Y u8", Gegl.AbyssPolicy.NONE)
        u = under.get_buffer().get(Gegl.Rectangle.new(ox - ux, oy - uy, w, h), 1.0, "Y u8",
                                   Gegl.AbyssPolicy.NONE)
    finally:
        image.remove_layer(under)
    if np is not None:
        a = np.frombuffer(m, dtype=np.uint8).astype(np.uint32)
        b = np.frombuffer(u, dtype=np.uint8).astype(np.uint32)
        out = ((a * b + 127) // 255).astype(np.uint8).tobytes()
    else:
        out = bytes((a * b + 127) // 255 for a, b in zip(m, u))
    buf = mask.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, w, h), "Y u8", out)
    buf.flush()
    mask.update(0, 0, w, h)


def blend_if_dialog(layer):
    vals = blend_if_values(layer) or [0, 0, 255, 255, 0, 0, 255, 255]
    GimpUi.init("chopgimp_studio")
    dlg = GimpUi.Dialog(title="Options de fusion « Si » — " + layer.get_name(), role="chopgimp-blend-if",
                        modal=True)
    dlg.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dlg.add_button("_OK", Gtk.ResponseType.OK)
    grid = Gtk.Grid(column_spacing=10, row_spacing=6, margin=12)
    dlg.get_content_area().pack_start(grid, True, True, 0)
    spins = []
    labels = ["Noir début", "Noir fin", "Blanc début", "Blanc fin"]
    for block, title in ((0, "Ce calque"), (1, "Calque du dessous")):
        grid.attach(Gtk.Label(label="<b>%s</b>" % title, use_markup=True, xalign=0), 0, block * 5, 4, 1)
        for i, lab in enumerate(labels):
            grid.attach(Gtk.Label(label=lab, xalign=0), 0, block * 5 + 1 + i, 1, 1)
            sp = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=vals[block * 4 + i], lower=0, upper=255,
                                                          step_increment=1))
            grid.attach(sp, 1, block * 5 + 1 + i, 1, 1)
            spins.append(sp)
    grid.attach(Gtk.Label(label="Les pixels hors de la plage deviennent transparents (masque de calque).\n"
                                "Relancez la commande pour modifier.", xalign=0), 0, 10, 4, 1)
    dlg.show_all()
    resp = dlg.run()
    v = [int(s.get_value()) for s in spins]
    dlg.destroy()
    if resp != Gtk.ResponseType.OK:
        return None
    fix = lambda q: (min(q[0], q[1]), max(q[0], q[1]), min(q[2], q[3]), max(q[2], q[3]))
    return fix(v[:4]), fix(v[4:])


class ChopGimpStudio(Gimp.PlugIn):
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
        if name in ("chopgimp-camera-raw", "chopgimp-blend-if"):
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
        else:
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                   Gimp.ProcedureSensitivityMask.DRAWABLES |
                                   Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
        return p

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        interactive = run_mode == Gimp.RunMode.INTERACTIVE
        if name == "chopgimp-blend-if":
            layers = [d for d in drawables if isinstance(d, Gimp.Layer) and not isinstance(d, Gimp.GroupLayer)]
            if len(layers) != 1:
                return fail(procedure, "Sélectionnez un seul calque de pixels.")
            chosen = blend_if_dialog(layers[0]) if interactive else ((0, 0, 255, 255), (0, 0, 255, 255))
            if chosen is None:
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            image.undo_group_start()
            try:
                msg = blend_if_apply(image, layers[0], *chosen)
            finally:
                image.undo_group_end()
            Gimp.displays_flush()
            return fail(procedure, msg) if msg else ok(procedure)
        if name == "chopgimp-camera-raw":
            layers = [d for d in drawables if isinstance(d, Gimp.Layer)]
            if len(layers) != 1:
                return fail(procedure, "Sélectionnez un seul calque.")
            if not interactive:
                return fail(procedure, "Camera Raw est une fenêtre interactive.")
            msg = camera_raw(image, layers[0])
        elif name.startswith("chopgimp-snapshot"):
            msg = snapshot_new(image) if name.endswith("new") else snapshot_revert(image)
        else:
            image.undo_group_start()
            try:
                if name == "chopgimp-fill-color":
                    msg = fill_color(image, interactive)
                elif name == "chopgimp-fill-gradient":
                    msg = fill_gradient(image, run_mode)
                else:
                    msg = fill_pattern(image)
            finally:
                image.undo_group_end()
        Gimp.displays_flush()
        if msg == "cancel":
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        return fail(procedure, msg) if msg else ok(procedure)


if __name__ == "__main__":
    Gimp.main(ChopGimpStudio.__gtype__, sys.argv)

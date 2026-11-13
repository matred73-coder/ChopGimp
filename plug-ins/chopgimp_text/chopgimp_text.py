#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — commandes de texte (façon Illustrator / Photoshop).

  Calque > Texte > Vectoriser le texte (Ctrl+Maj+O)   texte → forme vectorielle
  Calque > Texte > Vectoriser lettre par lettre       une forme par lettre
  Calque > Texte > Créer un tracé de travail          chemin, texte conservé
  Calque > Texte > Rechercher et remplacer…           dans tous les calques de texte
  Calque > Texte > Texte de remplissage               Lorem ipsum
  Calque > Texte > Déformer le texte…                 15 styles Photoshop
  Calque > Texte > Texte sur le tracé…                suit un chemin
  Calque > Texte > Texte dans la forme…               remplit une forme
  Calque > Texte > Supprimer l'effet de texte

Le texte reste modifiable : l'effet est une propriété du calque de texte
(rendu par app/text/chopgimp-textfx.c).
"""
import re
import sys

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gimp, GimpUi, GLib, GObject, Gtk

AUTHOR, YEAR = "ChopGimp", "2026"
TXT = "<Image>/Layer/Texte"
TXT_L = "<Layers>/Layers Menu/Texte"

LOREM = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor "
         "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud "
         "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure "
         "dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.")


def ok(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def fail(procedure, msg):
    return procedure.new_return_values(
        Gimp.PDBStatusType.EXECUTION_ERROR,
        GLib.Error.new_literal(GLib.quark_from_string("chopgimp"), msg, 0))


def is_live_text(d):
    """Un calque de texte encore modifiable (pas pixellisé)."""
    if not isinstance(d, Gimp.TextLayer):
        return False
    try:
        return not d.is_rasterized()
    except Exception:
        return True


def text_layers(drawables):
    return [d for d in drawables if is_live_text(d)]


def walk(layers):
    for l in layers:
        yield l
        if isinstance(l, Gimp.GroupLayer):
            yield from walk(l.get_children())


def text_path(image, layer):
    path = Gimp.Path.new_from_text_layer(image, layer)
    image.insert_path(path, None, 0)
    return path


def vector_from_path(image, path, layer, name, parent=None, position=None):
    vl = Gimp.VectorLayer.new(image, path)
    vl.set_name(name)
    vl.set_enable_fill(True)
    vl.set_fill_color(layer.get_color())
    vl.set_enable_stroke(False)
    vl.set_opacity(layer.get_opacity())
    vl.set_mode(layer.get_mode())
    if parent is None and position is None:
        parent, position = layer.get_parent(), image.get_item_position(layer)
    image.insert_layer(vl, parent, position)
    vl.refresh()
    return vl


def short_name(layer):
    t = (layer.get_text() or layer.get_name()).strip().replace("\n", " ")
    return t[:30] or "Texte"


# ─── vectoriser ─────────────────────────────────────────────────────────

def outline(image, layers):
    out = []
    for layer in layers:
        path = text_path(image, layer)
        vl = vector_from_path(image, path, layer, short_name(layer))
        image.remove_layer(layer)
        out.append(vl)
    image.set_selected_layers(out)


def stroke_bounds(path, sid):
    t, pts, closed = path.stroke_get_points(sid)
    xs, ys = pts[0::2], pts[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def outline_letters(image, layers):
    """Une forme par lettre : les contours inclus dans un autre (trous du
    « o », du « a »…) restent avec leur lettre."""
    groups_out = []
    for layer in layers:
        path = text_path(image, layer)
        strokes = list(path.get_strokes())
        bounds = {sid: stroke_bounds(path, sid) for sid in strokes}

        def inside(a, b):
            ax0, ay0, ax1, ay1 = bounds[a]
            bx0, by0, bx1, by1 = bounds[b]
            return a != b and ax0 >= bx0 and ay0 >= by0 and ax1 <= bx1 and ay1 <= by1

        outers = [s for s in strokes if not any(inside(s, o) for o in strokes)]
        outers.sort(key=lambda s: (bounds[s][0], bounds[s][1]))

        group = Gimp.GroupLayer.new(image, short_name(layer))
        image.insert_layer(group, layer.get_parent(), image.get_item_position(layer))
        for i, o in enumerate(outers):
            letter = Gimp.Path.new(image, "%s %d" % (short_name(layer), i + 1))
            for s in [o] + [h for h in strokes if inside(h, o) and
                            not any(inside(h, m) and inside(m, o) for m in strokes)]:
                t, pts, closed = path.stroke_get_points(s)
                letter.stroke_new_from_points(t, pts, closed)
            image.insert_path(letter, None, 0)
            vector_from_path(image, letter, layer, "%s %d" % (short_name(layer), i + 1),
                             parent=group, position=len(outers))
        image.remove_path(path)
        image.remove_layer(layer)
        groups_out.append(group)
    image.set_selected_layers(groups_out)


# ─── effets de texte (déformation, tracé, forme) ───────────────────────

WARP_STYLES = [
    ("none", "Sans"), ("arc", "Arc"), ("arc-lower", "Arc inférieur"),
    ("arc-upper", "Arc supérieur"), ("arch", "Arche"), ("bulge", "Renflement"),
    ("shell-lower", "Coquille inférieure"), ("shell-upper", "Coquille supérieure"),
    ("flag", "Drapeau"), ("wave", "Onde"), ("fish", "Poisson"), ("rise", "Montée"),
    ("fisheye", "Œil de poisson"), ("inflate", "Gonflement"), ("squeeze", "Compression"),
    ("twist", "Torsion"),
]


def call(name, **kw):
    p = Gimp.get_pdb().lookup_procedure(name)
    cfg = p.create_config()
    for k, v in kw.items():
        cfg.set_property(k, v)
    res = p.run(cfg)
    if res.index(0) != Gimp.PDBStatusType.SUCCESS:
        return None
    return res


def fx_get(layer):
    res = call("chopgimp-text-fx-get", layer=layer)
    return (res.index(1) if res else "") or ""


def fx_set(layer, spec, undo):
    call("chopgimp-text-fx-set", layer=layer, spec=spec or "", push_undo=undo)
    Gimp.displays_flush()


def spec_parse(spec):
    out = {}
    for item in (spec or "").split(";"):
        if "=" in item:
            k, v = item.split("=", 1)
            out[k] = v
    return out


def spec_join(d):
    return ";".join("%s=%s" % (k, v) for k, v in d.items())


def target_path(image, drawables):
    """Le chemin visé : chemin sélectionné, sinon celui d'un calque
    vectoriel sélectionné."""
    paths = image.get_selected_paths()
    if paths:
        return paths[0]
    for d in drawables:
        if isinstance(d, Gimp.VectorLayer):
            return d.get_path()
    return None


def fx_dialog(title, layer, rows, make_spec):
    """rows: [(libellé, widget)] ; make_spec() → texte de l'effet.
    Aperçu en direct sans annulation, validé avec annulation."""
    GimpUi.init("chopgimp_text")
    original = fx_get(layer)
    dialog = GimpUi.Dialog(title=title, role="chopgimp-text-fx", modal=True)
    dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("_OK", Gtk.ResponseType.OK)
    grid = Gtk.Grid(row_spacing=8, column_spacing=10, margin=12)
    dialog.get_content_area().pack_start(grid, True, True, 0)
    for r, (label, widget) in enumerate(rows):
        if label:
            grid.attach(Gtk.Label(label=label, xalign=1), 0, r, 1, 1)
            grid.attach(widget, 1, r, 1, 1)
        else:
            grid.attach(widget, 0, r, 2, 1)

    pending = [0]

    def preview(*_):
        if pending[0]:
            GLib.source_remove(pending[0])

        def run():
            pending[0] = 0
            fx_set(layer, make_spec(), False)
            return False
        pending[0] = GLib.timeout_add(120, run)

    def connect_all(widget):
        for sig in ("value-changed", "changed", "toggled"):
            if GObject.signal_lookup(sig, type(widget)):
                widget.connect(sig, preview)
        if isinstance(widget, Gtk.Box):          # ex. les boutons radio
            for child in widget.get_children():
                connect_all(child)

    for _, widget in rows:
        connect_all(widget)
    dialog.show_all()
    preview()
    resp = dialog.run()
    if pending[0]:
        GLib.source_remove(pending[0])
    spec = make_spec()
    dialog.destroy()
    fx_set(layer, original, False)          # état initial, sans annulation
    if resp == Gtk.ResponseType.OK and spec != original:
        fx_set(layer, spec, True)           # une seule étape d'annulation


def slider(lo, hi, value, step=1):
    adj = Gtk.Adjustment(value=value, lower=lo, upper=hi, step_increment=step,
                         page_increment=step * 10)
    sc = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj,
                   digits=0, hexpand=True)
    sc.set_size_request(260, -1)
    sc.set_value_pos(Gtk.PositionType.RIGHT)
    return sc


def warp_dialog(layer):
    cur = spec_parse(fx_get(layer))
    combo = Gtk.ComboBoxText()
    for key, label in WARP_STYLES:
        combo.append(key, label)
    combo.set_active_id(cur.get("warp", "arc") if "warp" in cur else "arc")
    horiz = Gtk.RadioButton(label="Horizontale")
    vert = Gtk.RadioButton(label="Verticale", group=horiz)
    vert.set_active(cur.get("vertical", "0") == "1")
    orient = Gtk.Box(spacing=12)
    orient.pack_start(horiz, False, False, 0)
    orient.pack_start(vert, False, False, 0)
    bend = slider(-100, 100, float(cur.get("bend", 50)))
    hd = slider(-100, 100, float(cur.get("hdist", 0)))
    vd = slider(-100, 100, float(cur.get("vdist", 0)))

    def make():
        style = combo.get_active_id()
        if style == "none":
            return ""
        return spec_join({"warp": style, "bend": int(bend.get_value()),
                          "hdist": int(hd.get_value()), "vdist": int(vd.get_value()),
                          "vertical": int(vert.get_active())})

    fx_dialog("Déformer le texte", layer,
              [("Style :", combo), ("", orient), ("Inflexion (%) :", bend),
               ("Distorsion horizontale (%) :", hd), ("Distorsion verticale (%) :", vd)],
              make)


def path_dialog(layer, path):
    cur = spec_parse(fx_get(layer))
    tattoo = path.get_tattoo()
    start = slider(-100, 100, float(cur.get("start", 0)) if "path" in cur else 0)
    shift = slider(-500, 500, float(cur.get("shift", 0)) if "path" in cur else 0)
    flip = Gtk.CheckButton(label="Faire passer de l'autre côté du tracé")
    flip.set_active("path" in cur and cur.get("flip") == "1")

    def make():
        return spec_join({"path": tattoo, "start": int(start.get_value()),
                          "flip": int(flip.get_active()), "shift": int(shift.get_value())})

    fx_dialog("Texte sur le tracé", layer,
              [("Départ (% du tracé) :", start), ("Décalage de la ligne de base (px) :", shift),
               ("", flip)], make)


def shape_dialog(layer, path):
    cur = spec_parse(fx_get(layer))
    tattoo = path.get_tattoo()
    inset = slider(0, 500, float(cur.get("inset", 6)) if "shape" in cur else 6)

    def make():
        return spec_join({"shape": tattoo, "inset": int(inset.get_value())})

    fx_dialog("Texte dans la forme", layer, [("Marge intérieure (px) :", inset)], make)


# ─── rechercher / remplacer ─────────────────────────────────────────────

def find_replace_dialog(image):
    GimpUi.init("chopgimp_text")
    dialog = GimpUi.Dialog(title="Rechercher et remplacer le texte", role="chopgimp-find-replace",
                           modal=True)
    dialog.add_button("_Fermer", Gtk.ResponseType.CLOSE)
    dialog.add_button("_Tout remplacer", Gtk.ResponseType.APPLY)
    grid = Gtk.Grid(row_spacing=6, column_spacing=8, margin=12)
    dialog.get_content_area().pack_start(grid, True, True, 0)
    find = Gtk.Entry(hexpand=True)
    repl = Gtk.Entry(hexpand=True)
    case = Gtk.CheckButton(label="Respecter la casse")
    whole = Gtk.CheckButton(label="Mot entier")
    status = Gtk.Label(xalign=0)
    for row, (lab, w) in enumerate([("Rechercher :", find), ("Remplacer par :", repl)]):
        grid.attach(Gtk.Label(label=lab, xalign=1), 0, row, 1, 1)
        grid.attach(w, 1, row, 1, 1)
    grid.attach(case, 1, 2, 1, 1)
    grid.attach(whole, 1, 3, 1, 1)
    grid.attach(status, 0, 4, 2, 1)
    dialog.show_all()
    while dialog.run() == Gtk.ResponseType.APPLY:
        needle = find.get_text()
        if not needle:
            continue
        pattern = re.escape(needle)
        if whole.get_active():
            pattern = r"\b" + pattern + r"\b"
        rx = re.compile(pattern, 0 if case.get_active() else re.IGNORECASE)
        count = layers = 0
        image.undo_group_start()
        for layer in walk(image.get_layers()):
            if not is_live_text(layer):
                continue
            text = layer.get_text() or ""
            new, n = rx.subn(repl.get_text().replace("\\", "\\\\"), text)
            if n:
                layer.set_text(new)      # (le style par caractère est réinitialisé)
                count += n
                layers += 1
        image.undo_group_end()
        Gimp.displays_flush()
        status.set_text("%d remplacement(s) dans %d calque(s) de texte." % (count, layers))
    dialog.destroy()


# ─── texte de remplissage ───────────────────────────────────────────────

def lorem(image, layers):
    if layers:
        for layer in layers:
            layer.set_text(LOREM)
        return
    font = Gimp.context_get_font()
    w, h = image.get_width(), image.get_height()
    layer = Gimp.TextLayer.new(image, LOREM, font, max(12.0, w / 40.0), Gimp.Unit.pixel())
    image.insert_layer(layer, None, 0)
    layer.resize(int(w * 0.6), int(h * 0.4))
    layer.set_offsets(int(w * 0.2), int(h * 0.3))
    image.set_selected_layers([layer])


# ─── déclaration ────────────────────────────────────────────────────────

PROCS = {
    "chopgimp-text-outline": ("Vectoriser le texte", [TXT, TXT_L]),
    "chopgimp-text-outline-letters": ("Vectoriser lettre par lettre", [TXT, TXT_L]),
    "chopgimp-text-work-path": ("Créer un tracé de travail", [TXT, TXT_L]),
    "chopgimp-text-find-replace": ("Rechercher et remplacer…", [TXT]),
    "chopgimp-text-lorem": ("Texte de remplissage (Lorem ipsum)", [TXT]),
    "chopgimp-text-warp": ("Déformer le texte…", [TXT, TXT_L]),
    "chopgimp-text-on-path": ("Texte sur le tracé…", [TXT, TXT_L]),
    "chopgimp-text-in-shape": ("Texte dans la forme…", [TXT, TXT_L]),
    "chopgimp-text-fx-clear": ("Supprimer l'effet de texte", [TXT, TXT_L]),
}

FX_PROCS = ("chopgimp-text-warp", "chopgimp-text-on-path", "chopgimp-text-in-shape",
            "chopgimp-text-fx-clear")


class ChopGimpText(Gimp.PlugIn):

    def do_query_procedures(self):
        return list(PROCS)

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        label, paths = PROCS[name]
        p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        p.set_image_types("*")
        p.set_attribution(AUTHOR, AUTHOR, YEAR)
        p.set_menu_label(label)
        for path in paths:
            p.add_menu_path(path)
        p.set_documentation(label.rstrip("…"), label.rstrip("…"), name)
        p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                               Gimp.ProcedureSensitivityMask.DRAWABLES |
                               Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
        return p

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        layers = text_layers(drawables)
        if name in ("chopgimp-text-outline", "chopgimp-text-outline-letters",
                    "chopgimp-text-work-path") + FX_PROCS and not layers:
            return fail(procedure, "Sélectionnez un calque de texte.")
        if name in FX_PROCS:
            layer = layers[0]
            if name == "chopgimp-text-fx-clear":
                fx_set(layer, "", True)
                return ok(procedure)
            if name == "chopgimp-text-warp":
                if run_mode == Gimp.RunMode.INTERACTIVE:
                    warp_dialog(layer)
                else:
                    fx_set(layer, "warp=arc;bend=50", True)
                return ok(procedure)
            path = target_path(image, drawables)
            if path is None:
                return fail(procedure, "Sélectionnez aussi un chemin (panneau Chemins) "
                                       "ou un calque vectoriel.")
            if run_mode != Gimp.RunMode.INTERACTIVE:
                key = "path" if name == "chopgimp-text-on-path" else "shape"
                fx_set(layer, "%s=%d" % (key, path.get_tattoo()), True)
            elif name == "chopgimp-text-on-path":
                path_dialog(layer, path)
            else:
                shape_dialog(layer, path)
            return ok(procedure)
        if name == "chopgimp-text-find-replace":
            if run_mode == Gimp.RunMode.INTERACTIVE:
                find_replace_dialog(image)
            return ok(procedure)
        image.undo_group_start()
        try:
            if name == "chopgimp-text-outline":
                outline(image, layers)
            elif name == "chopgimp-text-outline-letters":
                outline_letters(image, layers)
            elif name == "chopgimp-text-work-path":
                for layer in layers:
                    text_path(image, layer).set_name(short_name(layer))
            elif name == "chopgimp-text-lorem":
                lorem(image, layers)
        finally:
            image.undo_group_end()
            Gimp.displays_flush()
        return ok(procedure)


Gimp.main(ChopGimpText.__gtype__, sys.argv)

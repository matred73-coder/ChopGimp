#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — commandes de texte (façon Illustrator / Photoshop).

  Calque > Texte > Vectoriser le texte (Ctrl+Maj+O)   texte → forme vectorielle
  Calque > Texte > Vectoriser lettre par lettre       une forme par lettre
  Calque > Texte > Créer un tracé de travail          chemin, texte conservé
  Calque > Texte > Rechercher et remplacer…           dans tous les calques de texte
  Calque > Texte > Texte de remplissage               Lorem ipsum
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


def text_layers(drawables):
    return [d for d in drawables if isinstance(d, Gimp.TextLayer)]


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
            if not isinstance(layer, Gimp.TextLayer):
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
}


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
                    "chopgimp-text-work-path") and not layers:
            return fail(procedure, "Sélectionnez un calque de texte.")
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — objets dynamiques (façon Photoshop) sur les calques liés de GIMP 3.2.

Calque > Objet dynamique :
  Convertir en objet dynamique   les calques sélectionnés sont enregistrés
                                 dans un XCF (dossier « objets-dynamiques »)
                                 et remplacés par un calque lié à ce fichier
  Modifier le contenu            ouvre le fichier lié ; quand il est
                                 enregistré, GIMP met le calque à jour
  Remplacer le contenu…          lie le calque à un autre fichier

Fichier > Placer (lié)… / Placer (incorporé)… sont les actions de GIMP
« ouvrir comme calque lié / comme calques », renommées.
"""
import os
import re
import sys
import time

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gimp, GimpUi, Gio, GLib, Gtk

MENU = "<Image>/Layer/Objet dynamique"
MENU_L = "<Layers>/Layers Menu/Objet dynamique"

PROCS = {
    "chopgimp-smart-convert": "Convertir en objet dynamique",
    "chopgimp-smart-edit": "Modifier le contenu",
    "chopgimp-smart-replace": "Remplacer le contenu…",
}


def ok(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def fail(procedure, msg):
    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                       GLib.Error.new_literal(GLib.quark_from_string("chopgimp"), msg, 0))


def store_dir(image):
    f = image.get_file()
    base = os.path.splitext(f.get_basename())[0] if f else "sans-titre"
    d = os.path.join(Gimp.directory(), "objets-dynamiques", re.sub(r"[^\w.\- ]", "_", base))
    os.makedirs(d, exist_ok=True)
    return d


def convert(image, layers):
    layers = [l for l in layers if not isinstance(l, Gimp.LinkLayer)]
    if not layers:
        return "Sélectionnez un ou plusieurs calques (pas déjà liés)."
    x1 = y1 = 10 ** 9
    x2 = y2 = -10 ** 9
    for l in layers:
        _, x, y = l.get_offsets()
        x1, y1 = min(x1, x), min(y1, y)
        x2, y2 = max(x2, x + l.get_width()), max(y2, y + l.get_height())
    w, h = max(1, x2 - x1), max(1, y2 - y1)

    sub = Gimp.Image.new(w, h, image.get_base_type())
    sub.undo_disable()
    # du bas vers le haut, pour garder l'ordre
    order = sorted(layers, key=lambda l: image.get_item_position(l), reverse=True)
    for l in order:
        copy = Gimp.Layer.new_from_drawable(l, sub)
        sub.insert_layer(copy, None, 0)
        _, x, y = l.get_offsets()
        copy.set_offsets(x - x1, y - y1)
    name = layers[0].get_name() if len(layers) == 1 else "Objet dynamique"
    path = os.path.join(store_dir(image), "%s-%d.xcf" % (re.sub(r"[^\w.\- ]", "_", name)[:40],
                                                         int(time.time() * 1000) % 10 ** 9))
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, sub, Gio.File.new_for_path(path), None)
    sub.delete()

    top = min(layers, key=lambda l: image.get_item_position(l))
    parent, pos = top.get_parent(), image.get_item_position(top)
    link = Gimp.LinkLayer.new(image, Gio.File.new_for_path(path))
    if link is None:
        return "Le calque lié n'a pas pu être créé."
    link.set_name(name)
    image.insert_layer(link, parent, pos)
    link.set_offsets(x1, y1)
    for l in layers:
        image.remove_layer(l)
    image.set_selected_layers([link])
    return None


def edit(image, layers):
    links = [l for l in layers if isinstance(l, Gimp.LinkLayer)]
    if not links:
        return "Sélectionnez un objet dynamique (calque lié)."
    for l in links:
        f = l.get_file()
        if f is None or not f.query_exists(None):
            return "Le fichier lié est introuvable."
        img = Gimp.file_load(Gimp.RunMode.INTERACTIVE, f)
        if img is not None:
            Gimp.Display.new(img)
    Gimp.message("Modifiez puis enregistrez le fichier ouvert (Ctrl+S pour un XCF, Fichier > "
                 "Écraser pour un autre format) : l'objet dynamique se mettra à jour.")
    return None


def replace(image, layers):
    links = [l for l in layers if isinstance(l, Gimp.LinkLayer)]
    if not links:
        return "Sélectionnez un objet dynamique (calque lié)."
    GimpUi.init("chopgimp_smart")
    dialog = Gtk.FileChooserDialog(title="Remplacer le contenu", action=Gtk.FileChooserAction.OPEN)
    dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("_Remplacer", Gtk.ResponseType.OK)
    cur = links[0].get_file()
    if cur is not None and cur.get_parent() is not None:
        dialog.set_current_folder_file(cur.get_parent())
    resp = dialog.run()
    f = dialog.get_file() if resp == Gtk.ResponseType.OK else None
    dialog.destroy()
    if f is None:
        return "cancel"
    for l in links:
        l.set_file(f)
    return None


class ChopGimpSmart(Gimp.PlugIn):
    def do_query_procedures(self):
        return list(PROCS)

    def do_create_procedure(self, name):
        p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        p.set_image_types("*")
        p.set_menu_label(PROCS[name])
        p.add_menu_path(MENU)
        p.add_menu_path(MENU_L)
        p.set_documentation(PROCS[name].rstrip("…"), PROCS[name].rstrip("…"), name)
        p.set_attribution("ChopGimp", "ChopGimp", "2026")
        p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                               Gimp.ProcedureSensitivityMask.DRAWABLES)
        return p

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        layers = [d for d in drawables if isinstance(d, Gimp.Layer)]
        if name == "chopgimp-smart-convert":
            image.undo_group_start()
            try:
                msg = convert(image, layers)
            finally:
                image.undo_group_end()
        elif name == "chopgimp-smart-edit":
            msg = edit(image, layers)
        else:
            image.undo_group_start()
            try:
                msg = replace(image, layers)
            finally:
                image.undo_group_end()
        Gimp.displays_flush()
        if msg == "cancel":
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        return fail(procedure, msg) if msg else ok(procedure)


if __name__ == "__main__":
    Gimp.main(ChopGimpSmart.__gtype__, sys.argv)

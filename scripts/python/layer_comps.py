#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Compositions de calques
#   Compositions de calques façon Photoshop : enregistrer / restaurer la
#   visibilité, la position et l'opacité des calques. Stockées comme
#   parasites de l'image, donc conservées dans les fichiers XCF.
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib
import sys
import json

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

PARASITE_NAME = "photogimp-layer-comps"


def _get_all_layers_recursive(image):
    """Return a flat list of all layers including those inside groups."""
    result = []

    def _walk(layers):
        for layer in layers:
            result.append(layer)
            if hasattr(layer, 'get_children'):
                children = layer.get_children()
                if children:
                    _walk(children)

    _walk(image.get_layers())
    return result


def _capture_layer_states(image):
    """Capture current state of all layers as a serializable dict."""
    states = {}
    for layer in _get_all_layers_recursive(image):
        name = layer.get_name()
        offsets = layer.get_offsets()
        states[name] = {
            "visible": layer.get_visible(),
            "x_offset": offsets.offset_x,
            "y_offset": offsets.offset_y,
            "opacity": layer.get_opacity(),
        }
    return states


def _load_comps(image):
    """Load comps dict from the image parasite. Returns {} if none."""
    parasite = image.get_parasite(PARASITE_NAME)
    if parasite is None:
        return {}
    try:
        raw = parasite.get_data()
        # Les données peuvent revenir en gint8 signés : remettre en octets 0-255
        data_bytes = bytes((b & 0xFF) for b in raw) if not isinstance(raw, bytes) else raw
        return json.loads(data_bytes.decode('utf-8').rstrip('\x00'))
    except Exception:
        return {}


def _save_comps(image, comps):
    """Save comps dict to the image parasite (JSON ASCII : octets < 128)."""
    data = json.dumps(comps, ensure_ascii=True)
    parasite = Gimp.Parasite.new(PARASITE_NAME,
                                 Gimp.PARASITE_PERSISTENT | Gimp.PARASITE_UNDOABLE,
                                 list(data.encode('ascii')))
    image.attach_parasite(parasite)


def _error(procedure, msg):
    return procedure.new_return_values(
        Gimp.PDBStatusType.EXECUTION_ERROR,
        GLib.Error.new_literal(GLib.quark_from_string("photogimp"), msg, 0))


# ---------------------------------------------------------------------------
# Enregistrer la composition de calques
# ---------------------------------------------------------------------------
def save_comp(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-save-layer-comp')
        dialog = GimpUi.ProcedureDialog.new(procedure, config, _("Compositions de calques"))
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    comp_name = config.get_property('comp-name')
    if not comp_name or comp_name.strip() == "":
        comp_name = "Comp 1"

    Gimp.context_push()
    image.undo_group_start()

    comps = _load_comps(image)
    comps[comp_name] = _capture_layer_states(image)
    _save_comps(image, comps)

    image.undo_group_end()
    Gimp.context_pop()

    Gimp.message("Composition de calques « {} » enregistrée ({} calques capturés).".format(
        comp_name, len(comps[comp_name])))
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Restaurer la composition de calques
# ---------------------------------------------------------------------------
def restore_comp(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-restore-layer-comp')
        dialog = GimpUi.ProcedureDialog.new(procedure, config, _("Compositions de calques"))
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    comp_name = config.get_property('comp-name')

    comps = _load_comps(image)
    if comp_name not in comps:
        return _error(procedure, "Composition de calques « {} » introuvable.\nDisponibles : {}".format(
            comp_name, ", ".join(comps.keys()) if comps else "(aucune)"))

    states = comps[comp_name]

    Gimp.context_push()
    image.undo_group_start()

    restored = 0
    for layer in _get_all_layers_recursive(image):
        name = layer.get_name()
        if name in states:
            s = states[name]
            layer.set_visible(s["visible"])
            layer.set_offsets(s["x_offset"], s["y_offset"])
            layer.set_opacity(s["opacity"])
            restored += 1

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    Gimp.message("Composition de calques « {} » restaurée ({} calques mis à jour).".format(
        comp_name, restored))
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Lister les compositions de calques
# ---------------------------------------------------------------------------
def list_comps(procedure, run_mode, image, drawables, config, data):
    comps = _load_comps(image)

    if not comps:
        Gimp.message("Aucune composition de calques enregistrée dans cette image.\n"
                     "Utilisez « Enregistrer la composition de calques » pour en créer une.")
    else:
        lines = ["Compositions de calques dans cette image :", ""]
        for i, (name, states) in enumerate(comps.items(), 1):
            lines.append("  {}. « {} » ({} calques)".format(i, name, len(states)))
        lines.append("")
        lines.append("Utilisez « Restaurer la composition de calques » avec le nom exact.")
        Gimp.message("\n".join(lines))

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Supprimer la composition de calques
# ---------------------------------------------------------------------------
def delete_comp(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-delete-layer-comp')
        dialog = GimpUi.ProcedureDialog.new(procedure, config, _("Compositions de calques"))
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    comp_name = config.get_property('comp-name')
    comps = _load_comps(image)

    if comp_name not in comps:
        return _error(procedure, "Composition de calques « {} » introuvable.".format(comp_name))

    del comps[comp_name]
    if comps:
        _save_comps(image, comps)
    else:
        image.detach_parasite(PARASITE_NAME)
    Gimp.message("Composition de calques « {} » supprimée.".format(comp_name))

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class LayerComps(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-save-layer-comp',
            'python-fu-restore-layer-comp',
            'python-fu-list-layer-comps',
            'python-fu-delete-layer-comp',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        menu_base = "<Image>/Layer/Compositions de calques"

        if name == 'python-fu-save-layer-comp':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                save_comp, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Enregistrer la composition de calques"),
                _("Enregistre la visibilité, la position et l'opacité des calques sous un nom "
                  "(stockée dans l'image, conservée dans le fichier XCF)."),
                name)
            procedure.set_menu_label(_("_Enregistrer la composition de calques…"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_string_argument("comp-name", _("_Nom de la composition"),
                                          _("Nom de cette composition de calques"),
                                          "Comp 1",
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-restore-layer-comp':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                restore_comp, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Restaurer la composition de calques"),
                _("Restaurer une composition de calques enregistrée, par son nom."),
                name)
            procedure.set_menu_label(_("_Restaurer la composition de calques…"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_string_argument("comp-name", _("_Nom de la composition"),
                                          _("Nom de la composition de calques à restaurer"),
                                          "Comp 1",
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-list-layer-comps':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                list_comps, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Lister les compositions de calques"),
                _("Afficher toutes les compositions de calques enregistrées dans cette image."),
                name)
            procedure.set_menu_label(_("_Lister les compositions de calques"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-delete-layer-comp':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                delete_comp, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Supprimer la composition de calques"),
                _("Supprimer une composition de calques enregistrée dans cette image."),
                name)
            procedure.set_menu_label(_("_Supprimer la composition de calques…"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_string_argument("comp-name", _("_Nom de la composition"),
                                          _("Nom de la composition de calques à supprimer"),
                                          "Comp 1",
                                          GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(LayerComps.__gtype__, sys.argv)

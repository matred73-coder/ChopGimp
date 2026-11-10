#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Vector Mask
#   Convert paths to layer masks (Photoshop-style vector masks)
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

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


def vector_mask_from_path(procedure, run_mode, image, drawables, config, data):
    """Convert the active path to a layer mask on the active layer."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("vecmask"),
                                                                  "Aucun calque actif.", 0))

    active_layer = drawables[0]
    pdb = Gimp.get_pdb()

    # Get active path (vectors)
    active_path = image.get_active_vectors()
    if not active_path:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("vecmask"),
                                                                  "Aucun chemin actif. Créez ou sélectionnez un chemin d'abord.", 0))

    invert_mask = config.get_property("invert")

    Gimp.context_push()
    image.undo_group_start()

    # Remove existing mask if any
    existing_mask = active_layer.get_mask()
    if existing_mask:
        active_layer.remove_mask(Gimp.MaskApplyMode.DISCARD)

    # Convert path to selection
    pdb.run_procedure('gimp-image-select-item', [
        GObject.Value(Gimp.Image, image),
        GObject.Value(Gimp.ChannelOps, Gimp.ChannelOps.REPLACE),
        GObject.Value(Gimp.Item, active_path),
    ])

    # Invert selection if requested
    if invert_mask:
        pdb.run_procedure('gimp-selection-invert', [
            GObject.Value(Gimp.Image, image),
        ])

    # Add layer mask from selection
    mask = active_layer.create_mask(Gimp.AddMaskType.SELECTION)
    active_layer.add_mask(mask)
    mask.set_name("Masque vectoriel")

    # Clear selection but keep the path for future editing
    image.get_selection().none(image)

    # Re-set the active path so it remains available
    image.set_active_vectors(active_path)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class VectorMask(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-vector-mask-from-path',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-vector-mask-from-path':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                vector_mask_from_path, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Vector Mask from Path"),
                _("Convertir le chemin actif en masque de calque vectoriel sur le calque actif."),
                name)
            procedure.set_menu_label(_("Masque _vectoriel depuis chemin..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Layer")

            procedure.add_boolean_argument("invert", _("Inverser le masque"),
                                           _("Inverser la sélection avant de créer le masque"),
                                           False, GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(VectorMask.__gtype__, sys.argv)

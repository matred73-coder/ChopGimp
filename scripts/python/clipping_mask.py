#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Clipping Mask
#   Simulate Photoshop Clipping Masks using layer masks
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


def clipping_mask_apply(procedure, run_mode, image, drawables, config, data):
    """Clip the active layer to the layer below using its alpha as mask."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("clipping"),
                                                                  "Aucun calque actif.", 0))

    active_layer = drawables[0]

    # Get the parent and position of the active layer
    parent = active_layer.get_parent()
    position = image.get_item_position(active_layer)

    # Get the layer below: next in stack (position + 1)
    if parent:
        n_children = parent.get_n_children()
        children = [parent.get_child(i) for i in range(n_children)]
    else:
        children = image.get_layers()

    # Find active layer index in children list
    active_idx = None
    for i, child in enumerate(children):
        if child.get_name() == active_layer.get_name() and child == active_layer:
            active_idx = i
            break

    if active_idx is None or active_idx + 1 >= len(children):
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("clipping"),
                                                                  "Pas de calque en dessous.", 0))

    layer_below = children[active_idx + 1]

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    # Remove existing mask if any
    existing_mask = active_layer.get_mask()
    if existing_mask:
        active_layer.remove_mask(Gimp.MaskApplyMode.DISCARD)

    # Get alpha from the layer below as selection
    pdb.run_procedure('gimp-image-set-active-layer', [
        GObject.Value(Gimp.Image, image),
        GObject.Value(Gimp.Layer, layer_below),
    ])
    pdb.run_procedure('gimp-layer-alpha-to-selection', [
        GObject.Value(Gimp.Layer, layer_below),
    ])

    # Set active layer back
    pdb.run_procedure('gimp-image-set-active-layer', [
        GObject.Value(Gimp.Image, image),
        GObject.Value(Gimp.Layer, active_layer),
    ])

    # Add layer mask from selection
    mask = active_layer.create_mask(Gimp.AddMaskType.SELECTION)
    active_layer.add_mask(mask)

    # Rename the mask item
    mask.set_name("Masque d'écrêtage")

    # Remove selection
    image.get_selection().none(image)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def clipping_mask_remove(procedure, run_mode, image, drawables, config, data):
    """Remove the clipping mask (delete layer mask) from active layer."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("clipping"),
                                                                  "Aucun calque actif.", 0))

    active_layer = drawables[0]

    mask = active_layer.get_mask()
    if not mask:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("clipping"),
                                                                  "Ce calque n'a pas de masque.", 0))

    Gimp.context_push()
    image.undo_group_start()

    active_layer.remove_mask(Gimp.MaskApplyMode.DISCARD)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ClippingMask(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-clipping-mask-apply',
            'python-fu-clipping-mask-remove',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-clipping-mask-apply':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                clipping_mask_apply, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Clipping Mask — Apply"),
                _("Écrêter le calque actif sur le calque inférieur en utilisant son alpha comme masque."),
                name)
            procedure.set_menu_label(_("Masque d'_écrêtage"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Layer")

        elif name == 'python-fu-clipping-mask-remove':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                clipping_mask_remove, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Clipping Mask — Remove"),
                _("Supprimer le masque d'écrêtage (masque de calque) du calque actif."),
                name)
            procedure.set_menu_label(_("_Supprimer masque d'écrêtage"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Layer")

        else:
            return None

        return procedure


Gimp.main(ClippingMask.__gtype__, sys.argv)

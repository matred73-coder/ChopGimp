#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Vector Align & Distribute
#   Illustrator-style alignment and distribution tools for layers.
#   Aligner a gauche/Center/Right/Top/Middle/Bottom relative to canvas.
#   Distribuer horizontalement/Vertically with equal spacing.
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


def _get_all_layers(image):
    """Return all top-level layers in the image."""
    return image.get_layers()


def _get_layer_bounds(layer):
    """Return (x, y, w, h) for a layer."""
    offsets = layer.get_offsets()
    return offsets.offset_x, offsets.offset_y, layer.get_width(), layer.get_height()


# ---------------------------------------------------------------------------
# Aligner a gauche
# ---------------------------------------------------------------------------
def align_left(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-align-left')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    ref = config.get_property('reference')

    Gimp.context_push()
    image.undo_group_start()

    layers = drawables if len(drawables) > 1 else _get_all_layers(image)

    if ref == "canvas":
        target_x = 0.0
    elif ref == "selection":
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure('gimp-selection-bounds')
        pc = proc.create_config()
        pc.set_property('image', image)
        result = proc.run(pc)
        target_x = float(result.index(2))  # x1
    else:
        target_x = 0.0

    for layer in layers:
        layer.set_offsets(int(target_x), layer.get_offsets().offset_y)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Centrer horizontalement
# ---------------------------------------------------------------------------
def align_center_h(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-align-center-h')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    ref = config.get_property('reference')

    Gimp.context_push()
    image.undo_group_start()

    layers = drawables if len(drawables) > 1 else _get_all_layers(image)

    if ref == "canvas":
        center_x = image.get_width() / 2.0
    elif ref == "selection":
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure('gimp-selection-bounds')
        pc = proc.create_config()
        pc.set_property('image', image)
        result = proc.run(pc)
        x1, x2 = float(result.index(2)), float(result.index(4))
        center_x = (x1 + x2) / 2.0
    else:
        center_x = image.get_width() / 2.0

    for layer in layers:
        new_x = int(center_x - layer.get_width() / 2.0)
        layer.set_offsets(new_x, layer.get_offsets().offset_y)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Aligner a droite
# ---------------------------------------------------------------------------
def align_right(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-align-right')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    ref = config.get_property('reference')

    Gimp.context_push()
    image.undo_group_start()

    layers = drawables if len(drawables) > 1 else _get_all_layers(image)

    if ref == "canvas":
        right_edge = float(image.get_width())
    elif ref == "selection":
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure('gimp-selection-bounds')
        pc = proc.create_config()
        pc.set_property('image', image)
        result = proc.run(pc)
        right_edge = float(result.index(4))  # x2
    else:
        right_edge = float(image.get_width())

    for layer in layers:
        new_x = int(right_edge - layer.get_width())
        layer.set_offsets(new_x, layer.get_offsets().offset_y)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Aligner en haut
# ---------------------------------------------------------------------------
def align_top(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-align-top')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    ref = config.get_property('reference')

    Gimp.context_push()
    image.undo_group_start()

    layers = drawables if len(drawables) > 1 else _get_all_layers(image)

    if ref == "canvas":
        target_y = 0.0
    elif ref == "selection":
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure('gimp-selection-bounds')
        pc = proc.create_config()
        pc.set_property('image', image)
        result = proc.run(pc)
        target_y = float(result.index(3))  # y1
    else:
        target_y = 0.0

    for layer in layers:
        layer.set_offsets(layer.get_offsets().offset_x, int(target_y))

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Align Middle (Vertical center)
# ---------------------------------------------------------------------------
def align_middle(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-align-middle')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    ref = config.get_property('reference')

    Gimp.context_push()
    image.undo_group_start()

    layers = drawables if len(drawables) > 1 else _get_all_layers(image)

    if ref == "canvas":
        center_y = image.get_height() / 2.0
    elif ref == "selection":
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure('gimp-selection-bounds')
        pc = proc.create_config()
        pc.set_property('image', image)
        result = proc.run(pc)
        y1, y2 = float(result.index(3)), float(result.index(5))
        center_y = (y1 + y2) / 2.0
    else:
        center_y = image.get_height() / 2.0

    for layer in layers:
        new_y = int(center_y - layer.get_height() / 2.0)
        layer.set_offsets(layer.get_offsets().offset_x, new_y)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Aligner en bas
# ---------------------------------------------------------------------------
def align_bottom(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-align-bottom')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    ref = config.get_property('reference')

    Gimp.context_push()
    image.undo_group_start()

    layers = drawables if len(drawables) > 1 else _get_all_layers(image)

    if ref == "canvas":
        bottom_edge = float(image.get_height())
    elif ref == "selection":
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure('gimp-selection-bounds')
        pc = proc.create_config()
        pc.set_property('image', image)
        result = proc.run(pc)
        bottom_edge = float(result.index(5))  # y2
    else:
        bottom_edge = float(image.get_height())

    for layer in layers:
        new_y = int(bottom_edge - layer.get_height())
        layer.set_offsets(layer.get_offsets().offset_x, new_y)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Distribuer horizontalement
# ---------------------------------------------------------------------------
def distribute_h(procedure, run_mode, image, drawables, config, data):
    Gimp.context_push()
    image.undo_group_start()

    layers = drawables if len(drawables) > 1 else _get_all_layers(image)

    if len(layers) < 3:
        # Need at least 3 layers to distribute meaningfully
        # With 2, just leave them as-is
        image.undo_group_end()
        Gimp.context_pop()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    # Sort layers by their current X position
    layer_info = []
    for layer in layers:
        x, y, w, h = _get_layer_bounds(layer)
        layer_info.append((x, layer, w))

    layer_info.sort(key=lambda item: item[0])

    # First and last stay in place; distribute others evenly between them
    first_x = layer_info[0][0]
    last_x = layer_info[-1][0]

    # Total span from first layer left edge to last layer left edge
    total_span = last_x - first_x
    step = total_span / (len(layer_info) - 1)

    for i, (orig_x, layer, w) in enumerate(layer_info):
        new_x = int(first_x + step * i)
        layer.set_offsets(new_x, layer.get_offsets().offset_y)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Distribuer verticalement
# ---------------------------------------------------------------------------
def distribute_v(procedure, run_mode, image, drawables, config, data):
    Gimp.context_push()
    image.undo_group_start()

    layers = drawables if len(drawables) > 1 else _get_all_layers(image)

    if len(layers) < 3:
        image.undo_group_end()
        Gimp.context_pop()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    # Sort layers by their current Y position
    layer_info = []
    for layer in layers:
        x, y, w, h = _get_layer_bounds(layer)
        layer_info.append((y, layer, h))

    layer_info.sort(key=lambda item: item[0])

    first_y = layer_info[0][0]
    last_y = layer_info[-1][0]

    total_span = last_y - first_y
    step = total_span / (len(layer_info) - 1)

    for i, (orig_y, layer, h) in enumerate(layer_info):
        new_y = int(first_y + step * i)
        layer.set_offsets(layer.get_offsets().offset_x, new_y)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class VectorAlign(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-align-left',
            'python-fu-align-center-h',
            'python-fu-align-right',
            'python-fu-align-top',
            'python-fu-align-middle',
            'python-fu-align-bottom',
            'python-fu-distribute-h',
            'python-fu-distribute-v',
        ]

    def _make_reference_choice(self):
        choice = Gimp.Choice.new()
        choice.add("canvas", 0, _("Canevas"), "")
        choice.add("selection", 1, _("Selection"), "")
        return choice

    def do_create_procedure(self, name):
        Gegl.init(None)
        menu_base = "<Image>/Filters/Vector/Align"

        if name == 'python-fu-align-left':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                align_left, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Aligner a gauche"),
                _("Aligner les calques selectionnes au bord gauche du canevas ou de la selection."),
                name)
            procedure.set_menu_label(_("Aligner a _gauche..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_choice_argument("reference", _("_Reference"),
                                          _("Aligner par rapport au canevas ou a la selection"),
                                          self._make_reference_choice(),
                                          "canvas", GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-align-center-h':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                align_center_h, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Centrer horizontalement"),
                _("Centrer les calques horizontalement sur le canevas ou la selection."),
                name)
            procedure.set_menu_label(_("Aligner au _centre (H)..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_choice_argument("reference", _("_Reference"),
                                          _("Aligner par rapport au canevas ou a la selection"),
                                          self._make_reference_choice(),
                                          "canvas", GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-align-right':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                align_right, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Aligner a droite"),
                _("Aligner les calques selectionnes au bord droit du canevas ou de la selection."),
                name)
            procedure.set_menu_label(_("Aligner a _droite..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_choice_argument("reference", _("_Reference"),
                                          _("Aligner par rapport au canevas ou a la selection"),
                                          self._make_reference_choice(),
                                          "canvas", GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-align-top':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                align_top, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Aligner en haut"),
                _("Aligner les calques selectionnes au bord superieur du canevas ou de la selection."),
                name)
            procedure.set_menu_label(_("Aligner en _haut..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_choice_argument("reference", _("_Reference"),
                                          _("Aligner par rapport au canevas ou a la selection"),
                                          self._make_reference_choice(),
                                          "canvas", GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-align-middle':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                align_middle, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Centrer verticalement"),
                _("Centrer les calques verticalement sur le canevas ou la selection."),
                name)
            procedure.set_menu_label(_("Aligner au _milieu (V)..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_choice_argument("reference", _("_Reference"),
                                          _("Aligner par rapport au canevas ou a la selection"),
                                          self._make_reference_choice(),
                                          "canvas", GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-align-bottom':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                align_bottom, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Aligner en bas"),
                _("Aligner les calques selectionnes au bord inferieur du canevas ou de la selection."),
                name)
            procedure.set_menu_label(_("Aligner en _bas..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_choice_argument("reference", _("_Reference"),
                                          _("Aligner par rapport au canevas ou a la selection"),
                                          self._make_reference_choice(),
                                          "canvas", GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-distribute-h':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                distribute_h, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Distribuer horizontalement"),
                _("Distribute layers with equal horizontal spacing between "
                  "the leftmost and rightmost layers."),
                name)
            procedure.set_menu_label(_("Distribuer _horizontalement"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-distribute-v':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                distribute_v, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Distribuer verticalement"),
                _("Distribute layers with equal vertical spacing between "
                  "the topmost and bottommost layers."),
                name)
            procedure.set_menu_label(_("Distribuer _verticalement"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        else:
            return None

        return procedure


Gimp.main(VectorAlign.__gtype__, sys.argv)

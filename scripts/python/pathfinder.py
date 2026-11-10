#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Pathfinder
#   Illustrator-style boolean operations on vector paths:
#   Union, Soustraction, Intersection, Division
#
#   Strategy: convert paths to selections, apply channel operations,
#   then convert result back to a path.
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


def _get_top_two_paths(image):
    """Return the two topmost paths in the image, or (None, None)."""
    vectors_list = image.get_vectors()
    if len(vectors_list) < 2:
        return None, None
    return vectors_list[0], vectors_list[1]


def _path_to_selection(image, vectors, pdb, operation=Gimp.ChannelOps.REPLACE):
    """Convert a path to selection using the given channel operation."""
    proc = pdb.lookup_procedure('gimp-image-select-item')
    pc = proc.create_config()
    pc.set_property('image', image)
    pc.set_property('operation', operation)
    pc.set_property('item', vectors)
    proc.run(pc)


def _selection_to_path(image, pdb):
    """Convert the current selection to a new path and return it."""
    proc = pdb.lookup_procedure('gimp-selection-to-path')
    pc = proc.create_config()
    proc.run(pc)
    # The new path is added at the top of the vectors stack
    vectors_list = image.get_vectors()
    if vectors_list:
        return vectors_list[0]
    return None


def _check_paths(image, procedure):
    """Validate that at least 2 paths exist. Return error or None."""
    vectors_list = image.get_vectors()
    if len(vectors_list) < 2:
        error = GLib.Error.new_literal(
            GLib.quark_from_string("pathfinder"),
            "Pathfinder requires at least two paths in the image. "
            "Please create two vector paths first.",
            0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)
    return None


# ---------------------------------------------------------------------------
# Union (A + B)
# ---------------------------------------------------------------------------
def pathfinder_union(procedure, run_mode, image, drawables, config, data):
    err = _check_paths(image, procedure)
    if err:
        return err

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    path_a, path_b = _get_top_two_paths(image)

    # A to selection, then add B
    _path_to_selection(image, path_a, pdb, Gimp.ChannelOps.REPLACE)
    _path_to_selection(image, path_b, pdb, Gimp.ChannelOps.ADD)

    # Convert result to path
    result = _selection_to_path(image, pdb)
    if result:
        result.set_name("Union")

    Gimp.Selection.none(image)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Soustraction (A - B)
# ---------------------------------------------------------------------------
def pathfinder_subtract(procedure, run_mode, image, drawables, config, data):
    err = _check_paths(image, procedure)
    if err:
        return err

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    path_a, path_b = _get_top_two_paths(image)

    # A to selection, then subtract B
    _path_to_selection(image, path_a, pdb, Gimp.ChannelOps.REPLACE)
    _path_to_selection(image, path_b, pdb, Gimp.ChannelOps.SUBTRACT)

    result = _selection_to_path(image, pdb)
    if result:
        result.set_name("Soustraction")

    Gimp.Selection.none(image)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Intersectionion (A & B)
# ---------------------------------------------------------------------------
def pathfinder_intersect(procedure, run_mode, image, drawables, config, data):
    err = _check_paths(image, procedure)
    if err:
        return err

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    path_a, path_b = _get_top_two_paths(image)

    # A to selection, then intersect with B
    _path_to_selection(image, path_a, pdb, Gimp.ChannelOps.REPLACE)
    _path_to_selection(image, path_b, pdb, Gimp.ChannelOps.INTERSECT)

    result = _selection_to_path(image, pdb)
    if result:
        result.set_name("Intersection")

    Gimp.Selection.none(image)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Division (split at intersections — A-B and B-A as separate paths)
# ---------------------------------------------------------------------------
def pathfinder_divide(procedure, run_mode, image, drawables, config, data):
    err = _check_paths(image, procedure)
    if err:
        return err

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    path_a, path_b = _get_top_two_paths(image)

    # Part 1: A minus B
    _path_to_selection(image, path_a, pdb, Gimp.ChannelOps.REPLACE)
    _path_to_selection(image, path_b, pdb, Gimp.ChannelOps.SUBTRACT)

    has_sel_proc = pdb.lookup_procedure('gimp-selection-bounds')
    sel_config = has_sel_proc.create_config()
    sel_config.set_property('image', image)
    sel_result = has_sel_proc.run(sel_config)

    result_a = None
    if sel_result.index(1):  # non-empty selection
        result_a = _selection_to_path(image, pdb)
        if result_a:
            result_a.set_name("Division (A-B)")

    # Part 2: B minus A
    _path_to_selection(image, path_b, pdb, Gimp.ChannelOps.REPLACE)
    _path_to_selection(image, path_a, pdb, Gimp.ChannelOps.SUBTRACT)

    sel_config2 = has_sel_proc.create_config()
    sel_config2.set_property('image', image)
    sel_result2 = has_sel_proc.run(sel_config2)

    result_b = None
    if sel_result2.index(1):
        result_b = _selection_to_path(image, pdb)
        if result_b:
            result_b.set_name("Division (B-A)")

    # Part 3: Intersectionion (A & B)
    _path_to_selection(image, path_a, pdb, Gimp.ChannelOps.REPLACE)
    _path_to_selection(image, path_b, pdb, Gimp.ChannelOps.INTERSECT)

    sel_config3 = has_sel_proc.create_config()
    sel_config3.set_property('image', image)
    sel_result3 = has_sel_proc.run(sel_config3)

    if sel_result3.index(1):
        result_c = _selection_to_path(image, pdb)
        if result_c:
            result_c.set_name("Division (A&B)")

    Gimp.Selection.none(image)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class Pathfinder(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-pathfinder-union',
            'python-fu-pathfinder-subtract',
            'python-fu-pathfinder-intersect',
            'python-fu-pathfinder-divide',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)
        menu_base = "<Image>/Filters/Vector/Pathfinder"

        if name == 'python-fu-pathfinder-union':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                pathfinder_union, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Union (A + B)"),
                _("Combine the two topmost paths into a single path "
                  "(logical OR / union of both shapes)."),
                name)
            procedure.set_menu_label(_("_Union"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-pathfinder-subtract':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                pathfinder_subtract, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Soustraction (A - B)"),
                _("Soustraction the second path from the first path "
                  "(remove overlapping area of B from A)."),
                name)
            procedure.set_menu_label(_("_Soustraction"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-pathfinder-intersect':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                pathfinder_intersect, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Intersectionion (A & B)"),
                _("Ne conserver que la zone de chevauchement des deux chemins superieurs."),
                name)
            procedure.set_menu_label(_("_Intersectionionion"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-pathfinder-divide':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                pathfinder_divide, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Division"),
                _("Split the two topmost paths at their intersections, "
                  "creating separate paths for A-B, B-A, and A&B."),
                name)
            procedure.set_menu_label(_("_Division"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        else:
            return None

        return procedure


Gimp.main(Pathfinder.__gtype__, sys.argv)

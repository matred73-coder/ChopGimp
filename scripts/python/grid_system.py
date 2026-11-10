#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Grid System
#   Guide-based grid systems for design and layout:
#   Columns, Rows, Bootstrap, Nombre d'or, Regle des tiers, Clear All
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
import math

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


# ---------------------------------------------------------------------------
# Grille de colonnes
# ---------------------------------------------------------------------------
def columns_grid(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-grid-columns')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    num_columns = config.get_property('num-columns')
    gutter = config.get_property('gutter-width')
    margin = config.get_property('margin')

    Gimp.context_push()
    image.undo_group_start()

    w = image.get_width()
    usable = w - 2 * margin
    total_gutters = (num_columns - 1) * gutter
    col_width = (usable - total_gutters) / num_columns

    # Left margin guide
    if margin > 0:
        image.add_vguide(margin)

    x = margin
    for i in range(num_columns):
        # Left edge of column (skip first, already have margin guide)
        if i > 0:
            image.add_vguide(int(round(x)))
        # Right edge of column
        x += col_width
        image.add_vguide(int(round(x)))
        # Skip gutter
        if i < num_columns - 1:
            x += gutter

    # Right margin guide
    if margin > 0:
        image.add_vguide(w - margin)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Grille de lignes
# ---------------------------------------------------------------------------
def rows_grid(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-grid-rows')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    num_rows = config.get_property('num-rows')
    gutter = config.get_property('gutter-height')
    margin = config.get_property('margin')

    Gimp.context_push()
    image.undo_group_start()

    h = image.get_height()
    usable = h - 2 * margin
    total_gutters = (num_rows - 1) * gutter
    row_height = (usable - total_gutters) / num_rows

    if margin > 0:
        image.add_hguide(margin)

    y = margin
    for i in range(num_rows):
        if i > 0:
            image.add_hguide(int(round(y)))
        y += row_height
        image.add_hguide(int(round(y)))
        if i < num_rows - 1:
            y += gutter

    if margin > 0:
        image.add_hguide(h - margin)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Grille Bootstrap 12 colonnes
# ---------------------------------------------------------------------------
def bootstrap_grid(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-grid-bootstrap')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    gutter = config.get_property('gutter-width')
    container_margin = config.get_property('container-margin')

    Gimp.context_push()
    image.undo_group_start()

    w = image.get_width()
    num_columns = 12
    usable = w - 2 * container_margin
    total_gutters = (num_columns - 1) * gutter
    col_width = (usable - total_gutters) / num_columns

    # Marge du conteneurs
    if container_margin > 0:
        image.add_vguide(container_margin)
        image.add_vguide(w - container_margin)

    x = container_margin
    for i in range(num_columns):
        if i > 0:
            image.add_vguide(int(round(x)))
        x += col_width
        image.add_vguide(int(round(x)))
        if i < num_columns - 1:
            x += gutter

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Nombre d'or
# ---------------------------------------------------------------------------
def golden_ratio(procedure, run_mode, image, drawables, config, data):
    Gimp.context_push()
    image.undo_group_start()

    w = image.get_width()
    h = image.get_height()
    phi = (1.0 + math.sqrt(5.0)) / 2.0  # ~1.618

    # Vertical golden section lines
    image.add_vguide(int(round(w / phi)))
    image.add_vguide(int(round(w - w / phi)))

    # Horizontal golden section lines
    image.add_hguide(int(round(h / phi)))
    image.add_hguide(int(round(h - h / phi)))

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Regle des tiers
# ---------------------------------------------------------------------------
def rule_of_thirds(procedure, run_mode, image, drawables, config, data):
    Gimp.context_push()
    image.undo_group_start()

    w = image.get_width()
    h = image.get_height()

    # Two vertical lines at 1/3 and 2/3
    image.add_vguide(int(round(w / 3.0)))
    image.add_vguide(int(round(2.0 * w / 3.0)))

    # Two horizontal lines at 1/3 and 2/3
    image.add_hguide(int(round(h / 3.0)))
    image.add_hguide(int(round(2.0 * h / 3.0)))

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Effacer tous les guides
# ---------------------------------------------------------------------------
def clear_guides(procedure, run_mode, image, drawables, config, data):
    Gimp.context_push()
    image.undo_group_start()

    # Remove all guides by iterating
    # image.find_next_guide(0) returns the first guide ID, 0 means no more
    guide_id = image.find_next_guide(0)
    while guide_id != 0:
        next_id = image.find_next_guide(guide_id)
        image.delete_guide(guide_id)
        guide_id = next_id

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class GridSystem(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-grid-columns',
            'python-fu-grid-rows',
            'python-fu-grid-bootstrap',
            'python-fu-grid-golden-ratio',
            'python-fu-grid-rule-of-thirds',
            'python-fu-grid-clear-guides',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        menu_base = "<Image>/Filters/Design/Systeme de grille"

        if name == 'python-fu-grid-columns':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                columns_grid, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Grille de colonnes"),
                _("Creer des guides verticaux pour une mise en page en colonnes."),
                name)
            procedure.set_menu_label(_("Grille de _colonnes..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_int_argument("num-columns", _("_Colonnes"),
                                       _("Nombre de colonnes"), 1, 48, 12,
                                       GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("gutter-width", _("Largeur de _gouttiere"),
                                       _("Space between columns (px)"), 0, 200, 20,
                                       GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("margin", _("_Marge"),
                                       _("Marge gauche et droite (px)"), 0, 1000, 0,
                                       GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-grid-rows':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                rows_grid, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Grille de lignes"),
                _("Creer des guides horizontaux pour une mise en page en lignes."),
                name)
            procedure.set_menu_label(_("Grille de _lignes..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_int_argument("num-rows", _("_Lignes"),
                                       _("Nombre de lignes"), 1, 48, 6,
                                       GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("gutter-height", _("Hauteur de _gouttiere"),
                                       _("Space between rows (px)"), 0, 200, 20,
                                       GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("margin", _("_Marge"),
                                       _("Marge haut et bas (px)"), 0, 1000, 0,
                                       GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-grid-bootstrap':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                bootstrap_grid, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Grille Bootstrap 12 colonnes"),
                _("Creer une grille Bootstrap de 12 colonnes avec gouttiere configurable."),
                name)
            procedure.set_menu_label(_("Grille _Bootstrap..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_int_argument("gutter-width", _("Largeur de _gouttiere"),
                                       _("Space between columns (px)"), 0, 200, 30,
                                       GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("container-margin", _("_Marge du conteneur"),
                                       _("Container side margin (px)"), 0, 1000, 15,
                                       GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-grid-golden-ratio':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                golden_ratio, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Guides du nombre d'or"),
                _("Placer des guides aux divisions de la section doree (phi)."),
                name)
            procedure.set_menu_label(_("_Nombre d'or"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-grid-rule-of-thirds':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                rule_of_thirds, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Regle des tiers"),
                _("Placer des guides a 1/3 et 2/3 pour la composition photographique."),
                name)
            procedure.set_menu_label(_("Regle des _tiers"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-grid-clear-guides':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                clear_guides, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Effacer tous les guides"),
                _("Supprimer tous les guides de l'image."),
                name)
            procedure.set_menu_label(_("_Effacer tous les guides"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        else:
            return None

        return procedure


Gimp.main(GridSystem.__gtype__, sys.argv)

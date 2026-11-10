#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Plage de couleurs
#   Photoshop-style "Select > Color Range" selection by color with
#   tolerance, fuzziness, and add/subtract modes.
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


def color_range_select(procedure, run_mode, image, drawables, config, data):
    """Select pixels matching the foreground color within a tolerance range."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-color-range-select')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    tolerance    = config.get_property('tolerance')
    fuzziness    = config.get_property('fuzziness')
    select_mode  = config.get_property('select-mode')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    drawable = drawables[0] if drawables else image.get_active_drawable()

    if drawable is None:
        image.undo_group_end()
        Gimp.context_pop()
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error())

    # Get the current foreground color as sample color
    fg_color = Gimp.context_get_foreground()

    # Set select-by-color threshold
    Gimp.context_set_sample_threshold(tolerance / 255.0)
    Gimp.context_set_sample_merged(True)
    Gimp.context_set_sample_transparent(False)

    # Determine GIMP channel operation based on select mode:
    # 0 = Remplacer, 1 = Ajouter, 2 = Soustraire
    if select_mode == 0:
        channel_op = Gimp.ChannelOps.REPLACE
    elif select_mode == 1:
        channel_op = Gimp.ChannelOps.ADD
    elif select_mode == 2:
        channel_op = Gimp.ChannelOps.SUBTRACT
    else:
        channel_op = Gimp.ChannelOps.REPLACE

    # Execute select-by-color on the drawable
    pdb.run_procedure('gimp-by-color-select', [
        GObject.Value(Gimp.Drawable.__gtype__, drawable),
        GObject.Value(Gimp.RGB.__gtype__, fg_color),
        GObject.Value(GObject.TYPE_DOUBLE, tolerance / 255.0),
        GObject.Value(GObject.TYPE_INT, int(channel_op)),      # operation
        GObject.Value(GObject.TYPE_BOOLEAN, True),              # sample-merged
        GObject.Value(GObject.TYPE_BOOLEAN, False),             # select-transparent
        GObject.Value(GObject.TYPE_INT, 0),                     # select-criterion: COMPOSITE
        GObject.Value(GObject.TYPE_BOOLEAN, False),             # antialias — we feather later
    ])

    # Apply fuzziness as feathering to soften the selection edges
    if fuzziness > 0.0:
        pdb.run_procedure('gimp-selection-feather',
                          [GObject.Value(GObject.TYPE_DOUBLE, fuzziness)])

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ColorRangeSelect(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-color-range-select']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            color_range_select, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Plage de couleurs"),
            _("Selectionner les pixels correspondant a la couleur de premier plan "
              "avec tolerance et flou reglables. Equivalent de 'Plage de couleurs' "
              "de Photoshop. Definissez la couleur de premier plan avant d'executer."),
            name)
        procedure.set_menu_label(_("_Plage de couleurs..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Selection")

        procedure.add_double_argument("tolerance",
                                      _("_Tolerance"),
                                      _("Tolerance de correspondance de couleur (0-255). "
                                        "Plus la valeur est elevee, plus de couleurs sont selectionnees."),
                                      0.0, 255.0, 30.0,
                                      GObject.ParamFlags.READWRITE)

        procedure.add_double_argument("fuzziness",
                                      _("_Flou (contour progressif)"),
                                      _("Rayon de contour progressif applique a la selection (0 = bords nets)"),
                                      0.0, 100.0, 5.0,
                                      GObject.ParamFlags.READWRITE)

        procedure.add_int_argument("select-mode",
                                   _("_Mode de selection"),
                                   _("0 = Remplacer, 1 = Ajouter a la selection, 2 = Soustraire"),
                                   0, 2, 0,
                                   GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(ColorRangeSelect.__gtype__, sys.argv)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Affiner le masque
#   Improve existing layer masks with levels, feather, expand/contract, smooth.
#   Works directly on the active layer's mask channel.
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


def refine_mask(procedure, run_mode, image, drawables, config, data):
    """Refine the active layer's mask: levels, feather, expand/contract, smooth."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-refine-mask')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    black_point   = config.get_property('black-point')
    white_point   = config.get_property('white-point')
    feather       = config.get_property('feather-radius')
    expand_contract = config.get_property('expand-contract')
    smooth_radius = config.get_property('smooth-radius')

    drawable = drawables[0] if drawables else image.get_active_drawable()
    if drawable is None:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error())

    # Get the layer mask
    mask = drawable.get_mask()
    if mask is None:
        Gimp.message("Ce calque n'a pas de masque. Ajoutez un masque de calque d'abord.")
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error())

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    # Step 1: Adjust levels on the mask (increase contrast = cleaner edges)
    if black_point > 0.0 or white_point < 1.0:
        levels_filter = Gimp.DrawableFilter.new(mask, "gegl:levels", "")
        levels_config = levels_filter.get_config()
        levels_config.set_property("in-low", black_point)
        levels_config.set_property("in-high", white_point)
        mask.merge_filter(levels_filter)

    # Step 2: Expand or contract the mask
    # To expand/contract a mask, we convert it to selection, modify, then back
    if expand_contract != 0:
        # Load mask as selection
        pdb.run_procedure('gimp-image-select-item',
                          [GObject.Value(Gimp.Image.__gtype__, image),
                           GObject.Value(GObject.TYPE_INT, int(Gimp.ChannelOps.REPLACE)),
                           GObject.Value(Gimp.Item.__gtype__, mask)])

        if expand_contract > 0:
            pdb.run_procedure('gimp-selection-grow',
                              [GObject.Value(GObject.TYPE_INT, expand_contract)])
        else:
            pdb.run_procedure('gimp-selection-shrink',
                              [GObject.Value(GObject.TYPE_INT, abs(expand_contract))])

        # Fill mask from modified selection
        # First fill mask with black (clear), then fill selection with white
        Gimp.context_set_foreground(Gimp.RGB())  # black
        black = Gimp.RGB()
        black.set(0.0, 0.0, 0.0)
        Gimp.context_set_foreground(black)
        Gimp.Selection.none(image)

        # Reload modified selection
        pdb.run_procedure('gimp-image-select-item',
                          [GObject.Value(Gimp.Image.__gtype__, image),
                           GObject.Value(GObject.TYPE_INT, int(Gimp.ChannelOps.REPLACE)),
                           GObject.Value(Gimp.Item.__gtype__, mask)])

        if expand_contract > 0:
            pdb.run_procedure('gimp-selection-grow',
                              [GObject.Value(GObject.TYPE_INT, expand_contract)])
        else:
            pdb.run_procedure('gimp-selection-shrink',
                              [GObject.Value(GObject.TYPE_INT, abs(expand_contract))])

        # Apply the modified selection back to the mask
        # Clear mask to black
        Gimp.Selection.all(image)
        Gimp.context_set_foreground(black)
        mask.edit_fill(Gimp.FillType.FOREGROUND)

        # Restore the modified selection and fill with white
        pdb.run_procedure('gimp-image-select-item',
                          [GObject.Value(Gimp.Image.__gtype__, image),
                           GObject.Value(GObject.TYPE_INT, int(Gimp.ChannelOps.REPLACE)),
                           GObject.Value(Gimp.Item.__gtype__, mask)])

        if expand_contract > 0:
            pdb.run_procedure('gimp-selection-grow',
                              [GObject.Value(GObject.TYPE_INT, expand_contract)])
        else:
            pdb.run_procedure('gimp-selection-shrink',
                              [GObject.Value(GObject.TYPE_INT, abs(expand_contract))])

        white = Gimp.RGB()
        white.set(1.0, 1.0, 1.0)
        Gimp.context_set_foreground(white)
        mask.edit_fill(Gimp.FillType.FOREGROUND)

        Gimp.Selection.none(image)

    # Step 3: Smooth the mask (gaussian blur at low radius to remove jaggies)
    if smooth_radius > 0.0:
        blur_filter = Gimp.DrawableFilter.new(mask, "gegl:gaussian-blur", "")
        blur_config = blur_filter.get_config()
        blur_config.set_property("std-dev-x", smooth_radius)
        blur_config.set_property("std-dev-y", smooth_radius)
        mask.merge_filter(blur_filter)

        # Re-apply levels to restore edge crispness after blur
        if black_point > 0.0 or white_point < 1.0:
            levels_filter = Gimp.DrawableFilter.new(mask, "gegl:levels", "")
            levels_config = levels_filter.get_config()
            levels_config.set_property("in-low", black_point)
            levels_config.set_property("in-high", white_point)
            mask.merge_filter(levels_filter)

    # Step 4: Feather the mask edges (gaussian blur for soft transitions)
    if feather > 0.0:
        feather_filter = Gimp.DrawableFilter.new(mask, "gegl:gaussian-blur", "")
        feather_config = feather_filter.get_config()
        feather_config.set_property("std-dev-x", feather)
        feather_config.set_property("std-dev-y", feather)
        mask.merge_filter(feather_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class RefineMask(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-refine-mask']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            refine_mask, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Affiner le masque"),
            _("Ameliorer un masque de calque existant : ajuster les niveaux "
              "(point noir/blanc), adoucir, dilater/contracter et lisser. "
              "Travaille directement sur le masque du calque actif."),
            name)
        procedure.set_menu_label(_("_Affiner le masque..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Selection")

        procedure.add_double_argument("black-point",
                                      _("Point _noir"),
                                      _("Point noir du masque (0.0-1.0). Augmenter pour "
                                        "assombrir les zones sombres du masque (plus opaque)."),
                                      0.0, 0.99, 0.1,
                                      GObject.ParamFlags.READWRITE)

        procedure.add_double_argument("white-point",
                                      _("Point _blanc"),
                                      _("Point blanc du masque (0.01-1.0). Diminuer pour "
                                        "eclaircir les zones claires du masque (plus transparent)."),
                                      0.01, 1.0, 0.9,
                                      GObject.ParamFlags.READWRITE)

        procedure.add_double_argument("feather-radius",
                                      _("Contour _progressif"),
                                      _("Rayon de contour progressif sur le masque (0 = desactive)"),
                                      0.0, 200.0, 0.0,
                                      GObject.ParamFlags.READWRITE)

        procedure.add_int_argument("expand-contract",
                                   _("_Dilater/Contracter"),
                                   _("Positif = dilater le masque, negatif = contracter (pixels)"),
                                   -100, 100, 0,
                                   GObject.ParamFlags.READWRITE)

        procedure.add_double_argument("smooth-radius",
                                      _("_Lissage"),
                                      _("Rayon de lissage des bords du masque (0 = desactive)"),
                                      0.0, 50.0, 1.0,
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(RefineMask.__gtype__, sys.argv)

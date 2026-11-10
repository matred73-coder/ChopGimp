#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Selection et masque
#   Photoshop-style "Select and Mask" refinement in a single dialog.
#   Smooth, feather, contract/expand, and shift edges of the current selection.
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


def select_and_mask(procedure, run_mode, image, drawables, config, data):
    """Refine current selection: smooth, feather, contract/expand, shift edge."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-select-and-mask')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    smooth_radius    = config.get_property('smooth-radius')
    feather_radius   = config.get_property('feather-radius')
    contract_expand  = config.get_property('contract-expand')
    shift_edge       = config.get_property('shift-edge')

    # Check that there is a selection
    non_empty = image.get_selection().bounds().non_empty if hasattr(image.get_selection().bounds(), 'non_empty') else True

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    # Step 1: Smooth (remove jagged edges)
    if smooth_radius > 0:
        # Smooth = shrink then grow by same amount, which rounds corners
        pdb.run_procedure('gimp-selection-sharpen', [])
        # Use gimp-selection-flood to smooth
        # Alternative: shrink+grow for rounding
        half = max(1, int(smooth_radius / 2))
        pdb.run_procedure('gimp-selection-shrink', [GObject.Value(GObject.TYPE_INT, half)])
        pdb.run_procedure('gimp-selection-grow', [GObject.Value(GObject.TYPE_INT, half)])
        # Additional smoothing pass in reverse direction
        pdb.run_procedure('gimp-selection-grow', [GObject.Value(GObject.TYPE_INT, half)])
        pdb.run_procedure('gimp-selection-shrink', [GObject.Value(GObject.TYPE_INT, half)])

    # Step 2: Contract or Expand
    if contract_expand != 0:
        if contract_expand < 0:
            # Negative = contract (shrink)
            pdb.run_procedure('gimp-selection-shrink',
                              [GObject.Value(GObject.TYPE_INT, abs(contract_expand))])
        else:
            # Positive = expand (grow)
            pdb.run_procedure('gimp-selection-grow',
                              [GObject.Value(GObject.TYPE_INT, contract_expand)])

    # Step 3: Shift Edge (additional expand/contract for fine-tuning)
    if shift_edge != 0:
        if shift_edge < 0:
            pdb.run_procedure('gimp-selection-shrink',
                              [GObject.Value(GObject.TYPE_INT, abs(shift_edge))])
        else:
            pdb.run_procedure('gimp-selection-grow',
                              [GObject.Value(GObject.TYPE_INT, shift_edge)])

    # Step 4: Feather (must be last to get soft edges on final shape)
    if feather_radius > 0.0:
        pdb.run_procedure('gimp-selection-feather',
                          [GObject.Value(GObject.TYPE_DOUBLE, feather_radius)])

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class SelectAndMask(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-select-and-mask']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            select_and_mask, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Selection et masque"),
            _("Affiner la selection courante en une seule etape : lissage, "
              "contour progressif, contraction/dilatation et decalage du contour. "
              "Equivalent du 'Selection et masque' de Photoshop."),
            name)
        procedure.set_menu_label(_("_Selection et masque..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Selection")

        procedure.add_int_argument("smooth-radius",
                                   _("_Lissage (rayon)"),
                                   _("Rayon de lissage des bords de la selection (0 = desactive)"),
                                   0, 100, 2,
                                   GObject.ParamFlags.READWRITE)

        procedure.add_double_argument("feather-radius",
                                      _("Contour _progressif (rayon)"),
                                      _("Rayon du contour progressif en pixels (0 = desactive)"),
                                      0.0, 500.0, 3.0,
                                      GObject.ParamFlags.READWRITE)

        procedure.add_int_argument("contract-expand",
                                   _("_Contracter/Dilater"),
                                   _("Negatif = contracter, positif = dilater la selection (pixels)"),
                                   -200, 200, 0,
                                   GObject.ParamFlags.READWRITE)

        procedure.add_int_argument("shift-edge",
                                   _("_Decalage du contour"),
                                   _("Decaler le contour vers l'interieur (negatif) ou l'exterieur (positif)"),
                                   -100, 100, 0,
                                   GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(SelectAndMask.__gtype__, sys.argv)

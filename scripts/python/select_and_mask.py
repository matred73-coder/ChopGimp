#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Sélection et masque
#   Affinage de la sélection façon Photoshop en une seule boîte de dialogue :
#   lissage, contour progressif, contraction/dilatation, décalage du contour.
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


def _shift(image, pixels):
    """Dilate (positif) ou contracte (négatif) la sélection."""
    if pixels > 0:
        Gimp.Selection.grow(image, int(pixels))
    elif pixels < 0:
        Gimp.Selection.shrink(image, int(-pixels))


def select_and_mask(procedure, run_mode, image, drawables, config, data):
    """Affine la sélection : lissage, contraction/dilatation, décalage, progressif."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-select-and-mask')
        dialog = GimpUi.ProcedureDialog.new(procedure, config, _("Sélection et masque"))
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    smooth_radius    = config.get_property('smooth-radius')
    feather_radius   = config.get_property('feather-radius')
    contract_expand  = config.get_property('contract-expand')
    shift_edge       = config.get_property('shift-edge')

    if Gimp.Selection.is_empty(image):
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error.new_literal(GLib.quark_from_string("photogimp"),
                                   _("Aucune sélection : créez d'abord une sélection."), 0))

    image.undo_group_start()
    try:
        # 1. Lissage : ouverture puis fermeture morphologique (arrondit les angles,
        #    supprime les petites irrégularités du contour)
        if smooth_radius > 0:
            half = max(1, int(smooth_radius / 2))
            Gimp.Selection.shrink(image, half)
            Gimp.Selection.grow(image, half)
            Gimp.Selection.grow(image, half)
            Gimp.Selection.shrink(image, half)

        # 2. Contracter / dilater, puis 3. décalage fin du contour
        _shift(image, contract_expand)
        _shift(image, shift_edge)

        # 4. Contour progressif en dernier pour adoucir la forme finale
        if feather_radius > 0.0:
            Gimp.Selection.feather(image, float(feather_radius))
    finally:
        image.undo_group_end()
    Gimp.displays_flush()

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
            _("Sélection et masque"),
            _("Affine la sélection courante en une seule étape : lissage, "
              "contour progressif, contraction/dilatation et décalage du contour. "
              "Équivalent de « Sélectionner et masquer » de Photoshop."),
            name)
        procedure.set_menu_label(_("_Sélection et masque…"))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Select")

        procedure.add_int_argument("smooth-radius",
                                   _("_Lissage (rayon)"),
                                   _("Rayon de lissage des bords de la sélection (0 = désactivé)"),
                                   0, 100, 2,
                                   GObject.ParamFlags.READWRITE)

        procedure.add_double_argument("feather-radius",
                                      _("Contour _progressif (rayon)"),
                                      _("Rayon du contour progressif en pixels (0 = désactivé)"),
                                      0.0, 500.0, 3.0,
                                      GObject.ParamFlags.READWRITE)

        procedure.add_int_argument("contract-expand",
                                   _("_Contracter/Dilater"),
                                   _("Négatif = contracter, positif = dilater la sélection (pixels)"),
                                   -200, 200, 0,
                                   GObject.ParamFlags.READWRITE)

        procedure.add_int_argument("shift-edge",
                                   _("_Décalage du contour"),
                                   _("Décaler le contour vers l'intérieur (négatif) ou l'extérieur (positif)"),
                                   -100, 100, 0,
                                   GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(SelectAndMask.__gtype__, sys.argv)

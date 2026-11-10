#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Correcteur localise (Spot Healing)
#   Simplified spot healing brush: select blemish area, run to heal
#   using gegl:heal-selection without needing a source point.
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


def spot_healing(procedure, run_mode, image, drawables, config, data):
    """Heal selected area by sampling surrounding pixels.

    Works on the current selection: user selects the blemish with any
    selection tool (ellipse recommended for small spots), then runs this
    to fill the selected area with texture synthesized from nearby pixels.
    Optimized for small spots and blemishes.
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi

        GimpUi.init('python-fu-spot-healing')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    sampling_radius = config.get_property('sampling-radius')
    num_iterations = config.get_property('num-iterations')

    # Verify we have a selection
    if Gimp.Selection.is_empty(image):
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("Aucune selection trouvee. Selectionnez la zone a corriger "
                       "avec l'outil de selection elliptique ou un autre outil de selection."))

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        for i in range(num_iterations):
            # Apply GEGL heal-selection for each iteration
            # Multiple passes improve quality for larger blemishes
            heal_filter = Gimp.DrawableFilter.new(
                drawable, "gegl:heal-selection", "")
            heal_config = heal_filter.get_config()
            heal_config.set_property("sampling-radius", sampling_radius)
            drawable.merge_filter(heal_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class SpotHealing(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-spot-healing']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            spot_healing, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Spot Healing — Correcteur localise"),
            _("Corriger la zone selectionnee en synthetisant la texture "
              "depuis les pixels environnants. Ideal pour les petites "
              "imperfections : selectionnez avec l'ellipse, puis lancez."),
            name)
        procedure.set_menu_label(_("_Correcteur localise..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Retouching")

        procedure.add_int_argument("sampling-radius",
                                   _("_Rayon d'echantillonnage"),
                                   _("Distance d'echantillonnage depuis le bord de la selection (pixels)"),
                                   1, 500, 30,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("num-iterations",
                                   _("Nombre d'_iterations"),
                                   _("Nombre de passes de correction (plus = meilleur pour les grandes zones)"),
                                   1, 10, 1,
                                   GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(SpotHealing.__gtype__, sys.argv)

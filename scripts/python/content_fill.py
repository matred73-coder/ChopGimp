#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Remplissage selon le contenu
#   Fill selected areas by sampling from surroundings
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


def content_fill(procedure, run_mode, image, drawables, config, data):
    """Content-aware fill using GIMP's heal selection approach.

    Strategy:
    1. Grow the selection slightly to get good sampling overlap
    2. Use the GEGL heal-selection operation which synthesizes texture
       from surrounding pixels to fill the selected area
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi

        GimpUi.init('python-fu-content-fill')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    sample_radius = config.get_property('sample-radius')

    # Verify we have a selection
    if Gimp.Selection.is_empty(image):
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("No selection found. Please select an area to fill."))

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        # Apply GEGL heal-selection (content-aware fill)
        # This operation fills the selected area by synthesizing texture
        # from surrounding pixels, similar to Photoshop's content-aware fill
        heal_filter = Gimp.DrawableFilter.new(drawable, "gegl:heal-selection", "")
        heal_config = heal_filter.get_config()
        heal_config.set_property("sampling-radius", sample_radius)
        drawable.merge_filter(heal_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ContentFill(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-content-fill']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            content_fill, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Remplissage selon le contenu"),
            _("Fill the selected area by synthesizing texture from surrounding "
              "pixels, similar to Photoshop's Remplissage selon le contenu."),
            name)
        procedure.set_menu_label(_("Remplissage selon le _contenu..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Edit")

        procedure.add_int_argument("sample-radius",
                                   _("Sampling _Rayon"),
                                   _("Distance d'echantillonnage depuis le bord de la selection (pixels)"),
                                   1, 500, 50,
                                   GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(ContentFill.__gtype__, sys.argv)

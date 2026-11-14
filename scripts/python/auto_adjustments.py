#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Auto Adjustments
#   Photoshop-style Auto Levels, Auto Contrast, Couleur auto
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GLib
import sys

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


def auto_levels(procedure, run_mode, image, drawables, config, data):
    """Stretch histogram per channel to full range (like Photoshop Auto Levels)."""
    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    for drawable in drawables:
        # Stretch each channel independently using levels-stretch (GEGL)
        levels_filter = Gimp.DrawableFilter.new(drawable, "gegl:stretch-contrast", "")
        levels_config = levels_filter.get_config()
        levels_config.set_property("keep-colors", False)
        drawable.merge_filter(levels_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def auto_contrast(procedure, run_mode, image, drawables, config, data):
    """Normalize contrast without color shift (stretch value/luminosity only)."""
    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        # stretch-contrast with keep-colors=True preserves hue, only adjusts luminosity
        contrast_filter = Gimp.DrawableFilter.new(drawable, "gegl:stretch-contrast", "")
        contrast_config = contrast_filter.get_config()
        contrast_config.set_property("keep-colors", True)
        drawable.merge_filter(contrast_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def auto_color(procedure, run_mode, image, drawables, config, data):
    """Remove color cast automatically (like Photoshop Couleur auto).

    Strategy: Convert to LAB-like decomposition via GEGL, neutralize the
    color channels by centering them, then recombine.  Simplified approach:
    use per-channel curves to push each channel mean towards midpoint.
    We achieve this with stretch-contrast per-channel then a grey-world
    color balance via gegl:gray-world.
    """
    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        # First normalize per-channel
        stretch_filter = Gimp.DrawableFilter.new(drawable, "gegl:stretch-contrast", "")
        stretch_config = stretch_filter.get_config()
        stretch_config.set_property("keep-colors", False)
        drawable.merge_filter(stretch_filter)

        # Then apply grey-world white balance to remove remaining cast
        # gegl:gray-world adjusts colors so average becomes neutral grey
        try:
            wb_filter = Gimp.DrawableFilter.new(drawable, "gegl:gray-world", "")
            drawable.merge_filter(wb_filter)
        except Exception:
            # Fallback: if gegl:gray-world is not available, the stretch
            # alone provides a reasonable auto-color correction
            pass

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class AutoAdjustments(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-auto-levels',
            'python-fu-auto-contrast',
            'python-fu-auto-color',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-auto-levels':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                auto_levels, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Auto Levels (Photoshop-style)"),
                _("Etirer l'histogramme sur toute la plage par couche, comme les Niveaux auto de Photoshop."),
                name)
            procedure.set_menu_label(_("_Niveaux auto"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Image/Reglages auto")

        elif name == 'python-fu-auto-contrast':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                auto_contrast, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Auto Contrast"),
                _("Normaliser le contraste sans decalage de couleur — etire uniquement la luminosite."),
                name)
            procedure.set_menu_label(_("_Contrastee auto"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Image/Reglages auto")

        elif name == 'python-fu-auto-color':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                auto_color, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Couleur auto"),
                _("Supprimer automatiquement les dominantes de couleur, comme la Couleur auto de Photoshop."),
                name)
            procedure.set_menu_label(_("Cou_leur auto"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Image/Reglages auto")

        else:
            return None

        return procedure


Gimp.main(AutoAdjustments.__gtype__, sys.argv)

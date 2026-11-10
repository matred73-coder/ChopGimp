#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Nettete intelligente
#   Photoshop-like Nettete intelligente with luminosity-only option
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


def smart_sharpen(procedure, run_mode, image, drawables, config, data):
    """Nettete intelligente with optional luminosity-only sharpening.

    When 'luminosity-only' is enabled:
    1. Decompose to LAB (or use desaturate trick)
    2. Sharpen only the lightness channel
    3. Recompose — this avoids color fringing artifacts
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-smart-sharpen')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    amount    = config.get_property('amount')
    radius    = config.get_property('radius')
    threshold = config.get_property('threshold')
    lum_only  = config.get_property('luminosity-only')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    for drawable in drawables:
        if lum_only and image.get_base_type() == Gimp.ImageBaseType.RGB:
            # Luminosity-only sharpening strategy:
            # 1. Duplicate the layer
            # 2. Desaturate the duplicate (lightness mode)
            # 3. Apply unsharp mask to it
            # 4. Set layer mode to Luminosity (Value)
            # 5. Flatten down to merge

            w = drawable.get_width()
            h = drawable.get_height()
            dx = drawable.get_offsets().offset_x
            dy = drawable.get_offsets().offset_y

            # Duplicate the drawable as a new layer
            dup_layer = drawable.copy()
            image.insert_layer(dup_layer, drawable.get_parent(),
                               image.get_item_position(drawable))
            dup_layer.set_name("Nettete intelligente (Luminosite)")
            dup_layer.set_mode(Gimp.LayerMode.HSL_VALUE)  # Luminosity blend
            dup_layer.set_opacity(100.0)

            # Apply unsharp mask to the duplicate
            usm_filter = Gimp.DrawableFilter.new(dup_layer, "gegl:unsharp-mask", "")
            usm_config = usm_filter.get_config()
            usm_config.set_property("std-dev", radius)
            usm_config.set_property("scale", amount)
            usm_config.set_property("threshold", threshold)
            dup_layer.merge_filter(usm_filter)

            # Merge down to combine with original
            merged = image.merge_down(dup_layer, Gimp.MergeType.CLIP_TO_BOTTOM_LAYER)
            image.set_active_layer(merged)
        else:
            # Standard unsharp mask on the drawable directly
            usm_filter = Gimp.DrawableFilter.new(drawable, "gegl:unsharp-mask", "")
            usm_config = usm_filter.get_config()
            usm_config.set_property("std-dev", radius)
            usm_config.set_property("scale", amount)
            usm_config.set_property("threshold", threshold)
            drawable.merge_filter(usm_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class SmartSharpen(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-smart-sharpen']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            smart_sharpen, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Nettete intelligente"),
            _("Nettete intelligente style Photoshop avec intensite, rayon, seuil, "
              "et option d'accentuer la luminosite uniquement pour eviter les artefacts de couleur."),
            name)
        procedure.set_menu_label(_("_Nettete intelligente..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Nettete")

        procedure.add_double_argument("amount", _("_Intensite"),
                                      _("Intensite de la nettete (facteur d'echelle)"),
                                      0.0, 10.0, 1.5,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("radius", _("_Rayon"),
                                      _("Rayon de flou en pixels (ecart type)"),
                                      0.1, 100.0, 2.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("threshold", _("_Seuil"),
                                      _("Difference minimale pour accentuer (evite le bruit)"),
                                      0.0, 1.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("luminosity-only",
                                       _("_Luminosite uniquement"),
                                       _("Accentuer uniquement le canal de luminosite pour eviter "
                                         "les artefacts de frange de couleur"),
                                       True, GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(SmartSharpen.__gtype__, sys.argv)

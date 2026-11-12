#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Netteté intelligente
#   Netteté façon Photoshop, avec option luminosité uniquement
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


def _unsharp(drawable, radius, amount, threshold):
    f = Gimp.DrawableFilter.new(drawable, "gegl:unsharp-mask", _("Netteté intelligente"))
    cfg = f.get_config()
    cfg.set_property("std-dev", float(radius))
    cfg.set_property("scale", float(amount))
    cfg.set_property("threshold", float(threshold))
    f.update()
    drawable.merge_filter(f)


def smart_sharpen(procedure, run_mode, image, drawables, config, data):
    """Netteté intelligente, avec option « luminosité uniquement » : la copie
    accentuée est fusionnée en mode Luminosité LCH pour éviter les franges
    colorées.
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-smart-sharpen')
        dialog = GimpUi.ProcedureDialog.new(procedure, config, _("Netteté intelligente"))
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    amount    = config.get_property('amount')
    radius    = config.get_property('radius')
    threshold = config.get_property('threshold')
    lum_only  = config.get_property('luminosity-only')

    targets = [d for d in drawables if not d.is_group()]
    if not targets:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error.new_literal(GLib.quark_from_string("photogimp"),
                                   _("Sélectionnez un calque (pas un groupe)."), 0))

    Gimp.context_push()
    image.undo_group_start()
    try:
        result = []
        for drawable in targets:
            if (lum_only and isinstance(drawable, Gimp.Layer)
                    and image.get_base_type() == Gimp.ImageBaseType.RGB):
                # Copie accentuée en mode Luminosité LCH, fusionnée vers le bas
                dup = drawable.copy()
                image.insert_layer(dup, drawable.get_parent(),
                                   image.get_item_position(drawable))
                dup.set_mode(Gimp.LayerMode.LCH_LIGHTNESS)
                dup.set_opacity(100.0)
                dup.set_visible(True)
                _unsharp(dup, radius, amount, threshold)
                merged = image.merge_down(dup, Gimp.MergeType.CLIP_TO_BOTTOM_LAYER)
                result.append(merged)
            else:
                _unsharp(drawable, radius, amount, threshold)
                if isinstance(drawable, Gimp.Layer):
                    result.append(drawable)
        if result:
            image.set_selected_layers(result)
    finally:
        image.undo_group_end()
        Gimp.context_pop()
    Gimp.displays_flush()
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
            _("Netteté intelligente"),
            _("Netteté façon Photoshop (intensité, rayon, seuil) avec option pour "
              "n'accentuer que la luminosité et éviter les franges colorées."),
            name)
        procedure.set_menu_label(_("_Netteté intelligente…"))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Enhance")

        procedure.add_double_argument("amount", _("_Intensité"),
                                      _("Intensité de la netteté (facteur)"),
                                      0.0, 10.0, 1.5,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("radius", _("_Rayon"),
                                      _("Rayon du flou en pixels (écart type)"),
                                      0.1, 100.0, 2.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("threshold", _("_Seuil"),
                                      _("Différence minimale à accentuer (évite le bruit)"),
                                      0.0, 1.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("luminosity-only",
                                       _("_Luminosité uniquement"),
                                       _("N'accentuer que la luminosité pour éviter "
                                         "les franges colorées"),
                                       True, GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(SmartSharpen.__gtype__, sys.argv)

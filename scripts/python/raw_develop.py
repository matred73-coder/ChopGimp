#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Developpement photo (RAW Develop)
#   Lightroom/Camera Raw style basic development panel
#   Applies exposure, temperature, tint, contrast, highlights,
#   shadows, whites, blacks, clarity, and vibrance in one dialog.
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


def raw_develop_run(procedure, run_mode, image, drawables, config, data):
    """Apply a sequence of GEGL operations simulating a Camera Raw panel."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-raw-develop')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    exposure    = config.get_property('exposure')
    temperature = config.get_property('temperature')
    tint        = config.get_property('tint')
    contrast    = config.get_property('contrast')
    highlights  = config.get_property('highlights')
    shadows     = config.get_property('shadows')
    whites      = config.get_property('whites')
    blacks      = config.get_property('blacks')
    clarity     = config.get_property('clarity')
    vibrance    = config.get_property('vibrance')

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        # 1. Exposure  (gegl:exposure)
        if abs(exposure) > 0.001:
            f = Gimp.DrawableFilter.new(drawable, "gegl:exposure", "")
            c = f.get_config()
            c.set_property("exposure", exposure)
            drawable.merge_filter(f)

        # 2. Color temperature  (gegl:color-temperature)
        if abs(temperature - 6500) > 10:
            f = Gimp.DrawableFilter.new(drawable, "gegl:color-temperature", "")
            c = f.get_config()
            c.set_property("intended-temperature", 6500.0)
            c.set_property("original-temperature", temperature)
            drawable.merge_filter(f)

        # 3. Tint via hue-chroma rotation
        if abs(tint) > 0.1:
            f = Gimp.DrawableFilter.new(drawable, "gegl:hue-chroma", "")
            c = f.get_config()
            c.set_property("hue", tint)
            drawable.merge_filter(f)

        # 4. Contrast  (gegl:brightness-contrast)
        if abs(contrast) > 0.001:
            f = Gimp.DrawableFilter.new(drawable, "gegl:brightness-contrast", "")
            c = f.get_config()
            c.set_property("contrast", contrast)
            drawable.merge_filter(f)

        # 5. Highlights & Shadows  (gegl:shadows-highlights)
        if abs(highlights) > 0.1 or abs(shadows) > 0.1:
            f = Gimp.DrawableFilter.new(drawable, "gegl:shadows-highlights", "")
            c = f.get_config()
            c.set_property("highlights", highlights)
            c.set_property("shadows", shadows)
            drawable.merge_filter(f)

        # 6. Whites — push the high end via levels
        #    whites > 0 compresses highlight output, < 0 expands
        if abs(whites) > 0.1:
            f = Gimp.DrawableFilter.new(drawable, "gegl:levels", "")
            c = f.get_config()
            # Map whites (-100..100) to out-high (0.7..1.0..1.3 range)
            out_high = 1.0 + whites / 200.0
            out_high = max(0.5, min(1.5, out_high))
            c.set_property("out-high", out_high)
            drawable.merge_filter(f)

        # 7. Blacks — push the low end via levels
        if abs(blacks) > 0.1:
            f = Gimp.DrawableFilter.new(drawable, "gegl:levels", "")
            c = f.get_config()
            # Map blacks (-100..100): positive lifts blacks, negative crushes
            in_low = max(0.0, -blacks / 200.0)
            c.set_property("in-low", in_low)
            drawable.merge_filter(f)

        # 8. Clarity — large-radius unsharp mask (local contrast)
        if abs(clarity) > 0.01:
            f = Gimp.DrawableFilter.new(drawable, "gegl:unsharp-mask", "")
            c = f.get_config()
            c.set_property("std-dev", 40.0)           # large radius
            c.set_property("scale", abs(clarity))      # amount
            c.set_property("threshold", 0.0)
            drawable.merge_filter(f)

        # 9. Vibrance — selective saturation boost
        #    Vibrance boosts less-saturated colors more than already-saturated ones.
        #    Approximate: moderate saturation scale (< full saturation effect).
        if abs(vibrance) > 0.01:
            f = Gimp.DrawableFilter.new(drawable, "gegl:saturation", "")
            c = f.get_config()
            # vibrance 0..100 maps to scale 1.0..1.5  (gentle boost)
            # vibrance -100..0 maps to scale 0.5..1.0
            scale = 1.0 + vibrance / 200.0
            scale = max(0.0, min(2.0, scale))
            c.set_property("scale", scale)
            drawable.merge_filter(f)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class RawDevelop(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-raw-develop']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            raw_develop_run, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Developpement photo"),
            _("Panneau de developpement photo style Lightroom/Camera Raw : exposition, "
              "temperature, teinte, contraste, hautes lumieres, ombres, blancs, noirs, "
              "clarte et vibrance."),
            name)
        procedure.set_menu_label(_("_Developpement photo..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Photo")

        procedure.add_double_argument("exposure", _("_Exposition (EV)"),
                                      _("Correction d'exposition en EV"),
                                      -5.0, 5.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("temperature", _("_Temperature (K)"),
                                      _("Temperature de couleur en Kelvin"),
                                      2000.0, 12000.0, 6500.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("tint", _("Tein_te"),
                                      _("Rotation de teinte pour corriger la dominante vert/magenta"),
                                      -180.0, 180.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("contrast", _("_Contraste"),
                                      _("Ajustement du contraste global"),
                                      -1.0, 1.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("highlights", _("_Hautes lumieres"),
                                      _("Recuperation des hautes lumieres (negatif = assombrir)"),
                                      -100.0, 100.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("shadows", _("_Ombres"),
                                      _("Debouchage des ombres (positif = eclaircir)"),
                                      -100.0, 100.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("whites", _("_Blancs"),
                                      _("Point blanc de sortie"),
                                      -100.0, 100.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("blacks", _("_Noirs"),
                                      _("Point noir d'entree"),
                                      -100.0, 100.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("clarity", _("C_larte"),
                                      _("Contraste local (clarte) via masque flou a grand rayon"),
                                      -1.0, 2.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("vibrance", _("_Vibrance"),
                                      _("Saturation selective — accentue les couleurs peu saturees"),
                                      -100.0, 100.0, 0.0,
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(RawDevelop.__gtype__, sys.argv)

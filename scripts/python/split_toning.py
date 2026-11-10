#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#   PhotoGIMP Pro — Split Toning
#   Lightroom-style shadow/highlight color toning
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import GObject, GLib, Gegl
import sys


def split_toning_run(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("split_toning")
        dialog = GimpUi.ProcedureDialog.new(procedure, config, "Split Toning")
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    shadow_hue = config.get_property("shadow-hue")
    shadow_sat = config.get_property("shadow-saturation")
    highlight_hue = config.get_property("highlight-hue")
    highlight_sat = config.get_property("highlight-saturation")
    balance = config.get_property("balance")

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        # Shadow toning layer
        shadow_layer = Gimp.Layer.new(image, "Split Tone: Shadows",
                                       drawable.get_width(), drawable.get_height(),
                                       Gimp.ImageType.RGBA_IMAGE, shadow_sat, Gimp.LayerMode.MULTIPLY)
        image.insert_layer(shadow_layer, None, -1)

        # Fill shadow layer with shadow color
        color = Gimp.RGB()
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(shadow_hue / 360.0, 1.0, 1.0)
        color.set(r, g, b)
        Gimp.context_set_foreground(color)
        shadow_layer.edit_fill(Gimp.FillType.FOREGROUND)

        # Create luminosity mask for shadows (dark areas)
        image.set_active_layer(drawable)
        Gimp.context_push()
        threshold_val = balance / 100.0 * 255
        # Select shadows via threshold on a copy
        Gimp.image_select_item(image, Gimp.ChannelOps.REPLACE, drawable)
        sel_filter = Gimp.DrawableFilter.new(shadow_layer, "gegl:opacity", "")
        shadow_layer.merge_filter(sel_filter)

        # Highlight toning layer
        hl_layer = Gimp.Layer.new(image, "Split Tone: Highlights",
                                   drawable.get_width(), drawable.get_height(),
                                   Gimp.ImageType.RGBA_IMAGE, highlight_sat, Gimp.LayerMode.SCREEN)
        image.insert_layer(hl_layer, None, -1)

        r2, g2, b2 = colorsys.hsv_to_rgb(highlight_hue / 360.0, 1.0, 1.0)
        color2 = Gimp.RGB()
        color2.set(r2, g2, b2)
        Gimp.context_set_foreground(color2)
        hl_layer.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.context_pop()

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class SplitToning(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["photogimp-split-toning"]

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, split_toning_run, None)
        procedure.set_menu_label("Virage partiel...")
        procedure.set_icon_name("gimp-tool-color-balance")
        procedure.add_menu_path("<Image>/Filters/Color/")
        procedure.set_documentation("Split Toning", "Apply Lightroom-style split toning", name)
        procedure.set_attribution("PhotoGIMP Pro", "PhotoGIMP Pro", "2026")
        procedure.add_double_argument("shadow-hue", "Teinte ombres", "Shadow hue (0-360)", 0.0, 360.0, 30.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("shadow-saturation", "Force ombres", "Shadow opacity 0-100", 0.0, 100.0, 30.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("highlight-hue", "Teinte hautes lumières", "Highlight hue (0-360)", 0.0, 360.0, 210.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("highlight-saturation", "Force hautes lumières", "Highlight opacity 0-100", 0.0, 100.0, 25.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("balance", "Équilibre", "Shadow/Highlight balance (0=all shadow, 100=all highlight)", 0.0, 100.0, 50.0, GObject.ParamFlags.READWRITE)
        return procedure

Gimp.main(SplitToning.__gtype__, sys.argv)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#   PhotoGIMP Pro — Virage partiel (Split Toning)
#   Teinte des ombres et des hautes lumières façon Lightroom
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import GObject, GLib, Gegl
import colorsys
import sys


def _color_from_hue(hue):
    r, g, b = colorsys.hsv_to_rgb((hue % 360.0) / 360.0, 1.0, 1.0)
    return Gegl.Color.new("#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255)))


def _select_luminosity(image, layer):
    """Remplace la sélection par la luminosité du calque (blanc = sélectionné)."""
    temp = layer.copy()
    image.insert_layer(temp, layer.get_parent(), image.get_item_position(layer))
    if temp.get_mask() is not None:
        temp.remove_mask(Gimp.MaskApplyMode.DISCARD)
    mask = temp.create_mask(Gimp.AddMaskType.COPY)
    temp.add_mask(mask)
    image.select_item(Gimp.ChannelOps.REPLACE, mask)
    image.remove_layer(temp)


def _tone_layer(image, group, name, hue, opacity, ltype):
    w, h = image.get_width(), image.get_height()
    layer = Gimp.Layer.new(image, name, w, h, ltype, opacity, Gimp.LayerMode.SOFTLIGHT)
    image.insert_layer(layer, group, 0)
    Gimp.context_set_foreground(_color_from_hue(hue))
    layer.fill(Gimp.FillType.FOREGROUND)
    # Masque = sélection courante (luminosité ou son inverse)
    layer.add_mask(layer.create_mask(Gimp.AddMaskType.SELECTION))
    return layer


def split_toning_run(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init("photogimp-split-toning")
        dialog = GimpUi.ProcedureDialog.new(procedure, config, "Virage partiel")
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

    layers = [d for d in drawables if isinstance(d, Gimp.Layer)]
    if not layers:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error.new_literal(GLib.quark_from_string("photogimp"),
                                   "Sélectionnez un calque.", 0))
    if image.get_base_type() != Gimp.ImageBaseType.RGB:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error.new_literal(GLib.quark_from_string("photogimp"),
                                   "Le virage partiel nécessite une image RVB.", 0))

    # Équilibre : 50 = neutre ; < 50 renforce les ombres, > 50 les hautes lumières
    shadow_opacity = max(0.0, min(100.0, shadow_sat * (100.0 - balance) / 50.0))
    highlight_opacity = max(0.0, min(100.0, highlight_sat * balance / 50.0))

    Gimp.context_push()
    image.undo_group_start()
    try:
        saved = None if Gimp.Selection.is_empty(image) else Gimp.Selection.save(image)
        created = []
        for layer in layers:
            parent = layer.get_parent()
            group = Gimp.GroupLayer.new(image, "Virage partiel")
            image.insert_layer(group, parent, image.get_item_position(layer))
            group.set_mode(Gimp.LayerMode.PASS_THROUGH)

            if layer.is_group():
                src = Gimp.Layer.new_from_visible(image, image, "_lum")
                image.insert_layer(src, None, 0)
                _select_luminosity(image, src)
                image.remove_layer(src)
            else:
                _select_luminosity(image, layer)

            # Hautes lumières : masque = luminosité
            _tone_layer(image, group, "Virage : hautes lumières", highlight_hue,
                        highlight_opacity, Gimp.ImageType.RGBA_IMAGE)
            # Ombres : masque = luminosité inversée
            Gimp.Selection.invert(image)
            _tone_layer(image, group, "Virage : ombres", shadow_hue,
                        shadow_opacity, Gimp.ImageType.RGBA_IMAGE)
            created.append(group)

        if saved is not None:
            image.select_item(Gimp.ChannelOps.REPLACE, saved)
            image.remove_channel(saved)
        else:
            Gimp.Selection.none(image)
        image.set_selected_layers(created)
    finally:
        image.undo_group_end()
        Gimp.context_pop()
    Gimp.displays_flush()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class SplitToning(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["photogimp-split-toning"]

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, split_toning_run, None)
        procedure.set_image_types("RGB*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_menu_label("Virage partiel…")
        procedure.set_icon_name("gimp-tool-color-balance")
        procedure.add_menu_path("<Image>/Colors")
        procedure.set_documentation(
            "Virage partiel",
            "Teinte les ombres et les hautes lumières (façon Lightroom) avec deux calques "
            "de couleur en Lumière douce masqués par la luminosité, regroupés et modifiables.",
            name)
        procedure.set_attribution("PhotoGIMP Pro", "PhotoGIMP Pro", "2026")
        procedure.add_double_argument("shadow-hue", "Teinte des ombres", "Teinte des ombres (0-360°)",
                                      0.0, 360.0, 30.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("shadow-saturation", "Intensité des ombres",
                                      "Opacité du virage des ombres (0-100)",
                                      0.0, 100.0, 30.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("highlight-hue", "Teinte des hautes lumières",
                                      "Teinte des hautes lumières (0-360°)",
                                      0.0, 360.0, 210.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("highlight-saturation", "Intensité des hautes lumières",
                                      "Opacité du virage des hautes lumières (0-100)",
                                      0.0, 100.0, 25.0, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("balance", "Équilibre",
                                      "Équilibre ombres / hautes lumières (0 = ombres, 100 = hautes lumières)",
                                      0.0, 100.0, 50.0, GObject.ParamFlags.READWRITE)
        return procedure


Gimp.main(SplitToning.__gtype__, sys.argv)

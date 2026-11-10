#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Flou de profondeur (Depth Blur)
#   Photoshop Lens Blur / Tilt-Shift simulation
#   Creates a gradient-based depth map and applies variable blur.
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
import math

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


def depth_blur_run(procedure, run_mode, image, drawables, config, data):
    """Apply variable gaussian blur using a gradient depth map."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-depth-blur')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    blur_amount = config.get_property('blur-amount')
    focus_point = config.get_property('focus-point')
    focus_range = config.get_property('focus-range')
    mode        = config.get_property('mode')

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        w = drawable.get_width()
        h = drawable.get_height()

        # --- Build a gradient mask layer as the depth map ---
        # White = full blur, Black = no blur (sharp)
        mask_layer = Gimp.Layer.new(image, "Depth Map",
                                    w, h,
                                    Gimp.ImageType.GRAY_IMAGE,
                                    100.0, Gimp.LayerMode.NORMAL)
        mask_layer.fill(Gimp.FillType.WHITE)
        image.insert_layer(mask_layer, drawable.get_parent(),
                           image.get_item_position(drawable))

        # Calculate focus band in pixel coordinates
        if mode == "linear":
            # Linear top-to-bottom: focus_point is % of image height
            focus_y = int(h * focus_point / 100.0)
            half_range = int(h * focus_range / 200.0)
            top_sharp = max(0, focus_y - half_range)
            bot_sharp = min(h, focus_y + half_range)

            # Paint the mask: black in focus zone, gradient to white outside
            # Use GEGL gradient operations on the mask layer

            # Fill entire mask white first (already done)
            # Then paint the sharp band black
            black_color = Gegl.Color.new("black")
            white_color = Gegl.Color.new("white")

            Gimp.context_set_foreground(black_color)
            Gimp.context_set_background(white_color)

            # Select the focus band and fill with black
            image.select_rectangle(Gimp.ChannelOps.REPLACE,
                                   0, top_sharp, w, bot_sharp - top_sharp)
            mask_layer.edit_fill(Gimp.FillType.FOREGROUND)
            Gimp.Selection.none(image)

            # Blur the mask to create smooth gradient transitions
            transition_radius = max(10.0, h * 0.15)
            blur_mask = Gimp.DrawableFilter.new(mask_layer, "gegl:gaussian-blur", "")
            blur_mask_cfg = blur_mask.get_config()
            blur_mask_cfg.set_property("std-dev-x", transition_radius)
            blur_mask_cfg.set_property("std-dev-y", transition_radius)
            mask_layer.merge_filter(blur_mask)

        else:
            # Radial: center-out — focus in the center, blur at edges
            cx = w / 2.0
            cy = h * focus_point / 100.0
            # Create radial gradient via vignette on the mask
            black_color = Gegl.Color.new("black")
            Gimp.context_set_foreground(black_color)
            mask_layer.edit_fill(Gimp.FillType.FOREGROUND)

            # Use vignette GEGL to create a radial white→black from center
            # Then invert: center=black (sharp), edges=white (blur)
            vig = Gimp.DrawableFilter.new(mask_layer, "gegl:vignette", "")
            vig_cfg = vig.get_config()
            vig_cfg.set_property("softness", max(0.5, focus_range / 30.0))
            vig_cfg.set_property("strength", 1.0)
            mask_layer.merge_filter(vig)

            # Invert so center is black (sharp) and edges are white (blur)
            inv = Gimp.DrawableFilter.new(mask_layer, "gegl:invert-linear", "")
            mask_layer.merge_filter(inv)

        # --- Apply variable blur using the mask ---
        # Strategy: apply multiple blur passes at different radii,
        # using the mask to control blending.
        # We use a simpler approach: apply gaussian blur to the drawable,
        # then use the mask as a layer mask to blend with original.

        # Duplicate the drawable for the blurred version
        blur_layer = drawable.copy()
        image.insert_layer(blur_layer, drawable.get_parent(),
                           image.get_item_position(drawable))
        blur_layer.set_name("Flou de profondeur")

        # Apply gaussian blur to the blurred copy
        gb = Gimp.DrawableFilter.new(blur_layer, "gegl:gaussian-blur", "")
        gb_cfg = gb.get_config()
        gb_cfg.set_property("std-dev-x", blur_amount)
        gb_cfg.set_property("std-dev-y", blur_amount)
        blur_layer.merge_filter(gb)

        # Copy the mask_layer content as a layer mask on blur_layer
        # Add a white mask first, then copy the depth map into it
        layer_mask = blur_layer.create_mask(Gimp.AddMaskType.WHITE)
        blur_layer.add_mask(layer_mask)

        # Copy depth map contents to clipboard, paste into mask
        image.set_active_layer(mask_layer)
        Gimp.Selection.all(image)
        mask_layer.edit_copy()

        # Paste into the layer mask
        floating = layer_mask.edit_paste(False)
        Gimp.floating_sel_anchor(floating)

        Gimp.Selection.none(image)

        # Remove the temporary depth map layer
        image.remove_layer(mask_layer)

        # Flatten down: merge the blur layer onto the original
        image.set_active_layer(blur_layer)
        merged = image.merge_down(blur_layer, Gimp.MergeType.CLIP_TO_BOTTOM_LAYER)
        image.set_active_layer(merged)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class DepthBlur(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-depth-blur']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            depth_blur_run, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Flou de profondeur / Tilt-Shift"),
            _("Simuler un flou de profondeur de champ avec une carte de profondeur "
              "en degrade. Mode lineaire (tilt-shift haut/bas) ou radial (centre vers bords)."),
            name)
        procedure.set_menu_label(_("_Flou de profondeur..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Blur")

        procedure.add_double_argument("blur-amount", _("_Intensite du flou"),
                                      _("Rayon du flou gaussien en pixels"),
                                      1.0, 200.0, 25.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("focus-point", _("_Point de mise au point (%)"),
                                      _("Position verticale du point net (0=haut, 100=bas)"),
                                      0.0, 100.0, 50.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("focus-range", _("_Zone nette (%)"),
                                      _("Largeur de la bande nette en pourcentage de l'image"),
                                      1.0, 100.0, 30.0,
                                      GObject.ParamFlags.READWRITE)

        mode_choice = Gimp.Choice.new()
        mode_choice.add("linear", 0, _("Lineaire (haut/bas)"), "")
        mode_choice.add("radial", 1, _("Radial (centre vers bords)"), "")
        procedure.add_choice_argument("mode", _("_Mode"),
                                      _("Type de carte de profondeur"),
                                      mode_choice, "linear",
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(DepthBlur.__gtype__, sys.argv)

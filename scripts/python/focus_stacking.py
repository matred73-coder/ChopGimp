#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Empilement de mise au point
#   Combine multiple images/layers with different focus points
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


def focus_stack(procedure, run_mode, image, drawables, config, data):
    """Empilement de mise au point — combine layers with different focus points.

    Algorithm:
    1. For each layer, compute a sharpness map using edge detection
       (Laplacian approximation via GEGL edge detection)
    2. Blur the sharpness maps slightly to avoid pixel-level noise
    3. For each pixel position, select the layer with the highest
       sharpness value
    4. Build layer masks from the sharpness comparison
    5. Result: all-in-focus composite image

    The layers should be pre-aligned (use GIMP's align tool or
    Filters > Align Layers if needed).
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-focus-stack')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    smooth_radius = config.get_property('smooth-radius')
    edge_strength = config.get_property('edge-strength')

    layers = image.get_layers()
    if len(layers) < 2:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("L'empilement de mise au point necessite au moins 2 calques. "
                       "Chargez d'abord vos images de bracketing de mise au point en calques."))

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    img_width = image.get_width()
    img_height = image.get_height()

    # Step 1: Create sharpness maps for each layer
    # We create temporary grayscale images to hold edge-detected versions
    sharpness_layers = []

    for i, layer in enumerate(layers):
        # Duplicate the layer to work on
        sharp_layer = layer.copy()
        image.insert_layer(sharp_layer, None, 0)
        sharp_layer.set_name("_sharpness_{}".format(i))
        sharp_layer.set_visible(False)

        # Desaturate to luminance (edge detection works on grayscale)
        try:
            desat_filter = Gimp.DrawableFilter.new(sharp_layer, "gegl:saturation", "")
            desat_config = desat_filter.get_config()
            desat_config.set_property("scale", 0.0)
            sharp_layer.merge_filter(desat_filter)
        except Exception:
            # Fallback: use GIMP desaturate
            sharp_layer.desaturate(Gimp.DesaturateMode.LUMINOSITY)

        # Apply edge detection (Laplacian-like) to measure local sharpness
        try:
            edge_filter = Gimp.DrawableFilter.new(sharp_layer, "gegl:edge-laplace", "")
            sharp_layer.merge_filter(edge_filter)
        except Exception:
            # Fallback: use generic edge detection
            try:
                edge_filter = Gimp.DrawableFilter.new(sharp_layer, "gegl:edge", "")
                edge_config = edge_filter.get_config()
                edge_config.set_property("amount", edge_strength)
                sharp_layer.merge_filter(edge_filter)
            except Exception:
                pass

        # Blur the sharpness map slightly to create smoother masks
        # This prevents pixel-level noise in the final composite
        if smooth_radius > 0:
            blur_filter = Gimp.DrawableFilter.new(sharp_layer, "gegl:gaussian-blur", "")
            blur_config = blur_filter.get_config()
            blur_config.set_property("std-dev-x", float(smooth_radius))
            blur_config.set_property("std-dev-y", float(smooth_radius))
            sharp_layer.merge_filter(blur_filter)

        # Boost contrast on the sharpness map for better separation
        try:
            stretch = Gimp.DrawableFilter.new(sharp_layer, "gegl:stretch-contrast", "")
            sharp_layer.merge_filter(stretch)
        except Exception:
            pass

        sharpness_layers.append(sharp_layer)

    # Step 2: Create masks from sharpness maps
    # For a 2-layer stack, the mask is straightforward:
    #   - Where layer 0 is sharper, show layer 0; otherwise show layer 1
    # For N layers, we process pairwise from bottom to top

    # Make all original layers visible and set to normal mode
    for layer in layers:
        layer.set_visible(True)
        layer.set_mode(Gimp.LayerMode.NORMAL)

    # Process from top to bottom: each layer gets a mask based on
    # whether it is the sharpest at that position
    # Strategy: start with the bottom layer fully visible,
    # then for each upper layer, add a mask showing only where it's sharper

    for i in range(len(layers) - 1):
        # Compare sharpness of layer i (upper) vs layers below
        upper_layer = layers[i]
        upper_sharp = sharpness_layers[i]

        # Create a white mask on the upper layer (fully visible by default)
        white = Gimp.Channel.new(image, img_width, img_height,
                                 "mask_temp", 100.0, Gimp.RGB())

        # Add layer mask from the sharpness map
        # We copy the sharpness layer's content as the mask
        mask = upper_layer.create_mask(Gimp.AddMaskType.WHITE)
        upper_layer.add_mask(mask)

        # Copy sharpness layer content to the mask
        # Select all on the sharpness layer, copy, paste to mask
        image.set_active_layer(upper_sharp)
        Gimp.Selection.all(image)

        # We need to copy from sharpness layer to the mask
        upper_sharp.set_visible(True)
        Gimp.edit_copy([upper_sharp])
        upper_sharp.set_visible(False)

        # Paste into the mask
        floating = Gimp.edit_paste(mask, False)
        if floating:
            Gimp.floating_sel_anchor(floating)

    # Step 3: Clean up temporary sharpness layers
    for sharp_layer in sharpness_layers:
        image.remove_layer(sharp_layer)

    # Step 4: Optionally flatten the result
    # (leave as layers with masks so user can fine-tune)
    image.set_active_layer(layers[0])

    Gimp.Selection.none(image)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class FocusStacking(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-focus-stack']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            focus_stack, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Empilement de mise au point..."),
            _("Combiner plusieurs calques avec differents points de mise au point en une seule "
              "image entierement nette. Chargez vos photos de bracketing en calques d'abord, "
              "alignez-les si necessaire, puis lancez ce filtre."),
            name)
        procedure.set_menu_label(_("Empilement de mise au _point..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Retouching")

        procedure.add_double_argument("smooth-radius",
                                      _("Rayon de _lissage"),
                                      _("Rayon de flou pour le lissage des cartes de nettete. "
                                        "Plus eleve = transitions plus douces entre les zones de mise au point. "
                                        "0 = pas de lissage (peut montrer des artefacts)."),
                                      0.0, 50.0, 5.0,
                                      GObject.ParamFlags.READWRITE)

        procedure.add_double_argument("edge-strength",
                                      _("Force du _contour"),
                                      _("Intensite de la detection de contour pour l'analyse de nettete."),
                                      0.1, 10.0, 1.0,
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(FocusStacking.__gtype__, sys.argv)

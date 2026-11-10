#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Fusion HDR
#   Merge exposure brackets into a single HDR-like image
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


def hdr_merge(procedure, run_mode, image, drawables, config, data):
    """Fusion HDR — combine exposure brackets into an HDR result.

    Strategy:
    1. Take all layers as different exposures (bottom = darkest, top = brightest,
       or any order)
    2. Create luminosity masks for each layer to extract well-exposed regions
    3. Blend layers using luminosity-weighted opacity
    4. Apply tone mapping to compress the dynamic range
    5. Result: single layer with expanded dynamic range and natural look
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-hdr-merge')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    tone_strength = config.get_property('tone-mapping-strength')
    detail_boost = config.get_property('detail-boost')

    layers = image.get_layers()
    if len(layers) < 2:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("HDR merge requires at least 2 layers (exposure brackets). "
                       "Load your bracketed exposures as layers first."))

    Gimp.context_push()
    image.undo_group_start()

    img_width = image.get_width()
    img_height = image.get_height()
    n_layers = len(layers)

    # Step 1: Create luminosity masks for each layer
    # A luminosity mask reveals well-exposed areas (midtones) and hides
    # under/overexposed areas
    for i, layer in enumerate(layers):
        layer.set_mode(Gimp.LayerMode.NORMAL)
        layer.set_visible(True)

        # Create a mask from the layer's own luminosity
        # This naturally selects the well-exposed regions of each bracket
        mask = layer.create_mask(Gimp.AddMaskType.WHITE)
        layer.add_mask(mask)

        # Copy the layer's luminance into its own mask
        # First, create a desaturated copy to get luminance
        desat_copy = layer.copy()
        image.insert_layer(desat_copy, None, 0)
        desat_copy.set_visible(True)

        # Desaturate to get luminance values
        try:
            desat_filter = Gimp.DrawableFilter.new(desat_copy, "gegl:saturation", "")
            desat_config = desat_filter.get_config()
            desat_config.set_property("scale", 0.0)
            desat_copy.merge_filter(desat_filter)
        except Exception:
            desat_copy.desaturate(Gimp.DesaturateMode.LUMINOSITY)

        # Apply a curves-like adjustment to boost midtones in the mask
        # This makes the luminosity mask prefer well-exposed areas
        # Using stretch-contrast to normalize the range
        try:
            stretch = Gimp.DrawableFilter.new(desat_copy, "gegl:stretch-contrast", "")
            stretch_config = stretch.get_config()
            stretch_config.set_property("keep-colors", True)
            desat_copy.merge_filter(stretch)
        except Exception:
            pass

        # Copy luminance data to the mask
        Gimp.Selection.all(image)
        Gimp.edit_copy([desat_copy])
        floating = Gimp.edit_paste(mask, False)
        if floating:
            Gimp.floating_sel_anchor(floating)

        # Remove the temporary desaturated copy
        image.remove_layer(desat_copy)

    # Step 2: Set layer opacities for equal blending
    # Each layer contributes proportionally
    base_opacity = 100.0 / n_layers
    for i, layer in enumerate(layers):
        # Bottom layer at full opacity, others at proportional amounts
        if i == n_layers - 1:
            layer.set_opacity(100.0)
        else:
            # Upper layers use SCREEN mode for additive exposure blending
            layer.set_opacity(min(100.0, base_opacity * 2.0))
            layer.set_mode(Gimp.LayerMode.SCREEN)

    # Step 3: Flatten to merge all exposure layers
    Gimp.Selection.none(image)
    merged = image.flatten()

    # Step 4: Apply tone mapping to compress dynamic range
    if tone_strength > 0:
        # Use GEGL stress (Spatio Temporal Retinex-like Envelope with Stochastic
        # Sampling) for local tone mapping, or mantiuk/fattal if available
        try:
            # Try GEGL stress for tone mapping (local contrast enhancement)
            stress_filter = Gimp.DrawableFilter.new(merged, "gegl:stress", "")
            stress_config = stress_filter.get_config()
            # Adjust radius and samples based on strength
            stress_config.set_property("radius", int(100 * tone_strength))
            stress_config.set_property("samples", 5)
            stress_config.set_property("iterations", 3)
            merged.merge_filter(stress_filter)
        except Exception:
            # Fallback: use curves/levels for basic tone mapping
            try:
                # Apply a gentle S-curve via brightness-contrast
                bc_filter = Gimp.DrawableFilter.new(merged, "gegl:brightness-contrast", "")
                bc_config = bc_filter.get_config()
                bc_config.set_property("contrast", 0.15 * tone_strength)
                merged.merge_filter(bc_filter)
            except Exception:
                pass

    # Step 5: Boost local detail/microcontrast if requested
    if detail_boost > 0:
        try:
            # Unsharp mask with large radius = local contrast enhancement
            usm_filter = Gimp.DrawableFilter.new(merged, "gegl:unsharp-mask", "")
            usm_config = usm_filter.get_config()
            usm_config.set_property("std-dev", 20.0)  # Large radius
            usm_config.set_property("scale", detail_boost * 0.5)
            usm_config.set_property("threshold", 0.0)
            merged.merge_filter(usm_filter)
        except Exception:
            pass

    # Final normalization
    try:
        norm_filter = Gimp.DrawableFilter.new(merged, "gegl:stretch-contrast", "")
        norm_config = norm_filter.get_config()
        norm_config.set_property("keep-colors", True)
        merged.merge_filter(norm_filter)
    except Exception:
        pass

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class HDRMerge(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-hdr-merge']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            hdr_merge, None)
        procedure.set_image_types("RGB*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Fusion HDR..."),
            _("Fusionner des calques a expositions bracketees en une seule image de type HDR "
              "par masques de luminosite et tone mapping. Chargez vos expositions bracketees "
              "en calques, alignez-les, puis lancez ce filtre."),
            name)
        procedure.set_menu_label(_("Fusion _HDR..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Retouching")

        procedure.add_double_argument("tone-mapping-strength",
                                      _("Intensite du _Tone Mapping"),
                                      _("Intensite du tone mapping pour compresser la plage dynamique. "
                                        "0 = pas de tone mapping, 1 = intensite maximale."),
                                      0.0, 2.0, 0.8,
                                      GObject.ParamFlags.READWRITE)

        procedure.add_double_argument("detail-boost",
                                      _("Renforcement du _detail"),
                                      _("Ameliorer le micro-contraste local et le detail. "
                                        "0 = aucun, plus eleve = plus de punch dans le detail."),
                                      0.0, 3.0, 0.5,
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(HDRMerge.__gtype__, sys.argv)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Separation de frequence
#   Professional beauty retouching: split image into low/high frequency layers
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


def frequency_separation(procedure, run_mode, image, drawables, config, data):
    """Separation de frequence — split into low frequency (color/tone) and
    high frequency (texture/detail) layers for professional retouching.

    Workflow after running:
    - Paint/clone on "Low Frequency" to smooth skin color and tone
    - Paint/clone on "High Frequency" to fix texture without affecting color
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-frequency-separation')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    blur_radius = config.get_property('blur-radius')

    Gimp.context_push()
    image.undo_group_start()

    source_drawable = drawables[0] if drawables else image.get_active_drawable()
    if source_drawable is None:
        image.undo_group_end()
        Gimp.context_pop()
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("No active drawable found."))

    parent = source_drawable.get_parent()
    position = image.get_item_position(source_drawable)

    # Create a layer group to hold both frequency layers
    group = Gimp.Layer.group_new(image)
    group.set_name("Separation de frequence")
    image.insert_layer(group, parent, position)

    # --- Low Frequency layer (color/tone) ---
    low_layer = source_drawable.copy()
    image.insert_layer(low_layer, group, 0)
    low_layer.set_name("Low Frequency")
    low_layer.set_mode(Gimp.LayerMode.NORMAL)

    # Apply Gaussian blur to the low frequency layer
    blur_filter = Gimp.DrawableFilter.new(low_layer, "gegl:gaussian-blur", "")
    blur_config = blur_filter.get_config()
    blur_config.set_property("std-dev-x", float(blur_radius))
    blur_config.set_property("std-dev-y", float(blur_radius))
    low_layer.merge_filter(blur_filter)

    # --- High Frequency layer (texture/detail) ---
    high_layer = source_drawable.copy()
    image.insert_layer(high_layer, group, 0)
    high_layer.set_name("High Frequency")

    # Set to Grain Extract mode: High = Original - Low
    # This extracts the detail/texture that was removed by the blur
    high_layer.set_mode(Gimp.LayerMode.GRAIN_EXTRACT)

    # Flatten the group content to bake the grain extract result,
    # then re-separate. Instead, we use a different approach:
    # We merge the high layer down onto a copy of the low layer to get
    # the actual high-frequency data, then set it to Grain Merge mode.

    # Actually the standard workflow is simpler:
    # 1. Low layer = blurred copy (Normal mode)
    # 2. High layer = original copy set to Grain Extract
    #    -> visually shows the difference
    # But for proper non-destructive editing, we flatten the high freq:

    # Merge high onto low to compute the actual grain-extracted pixels
    # Then undo and use Grain Merge for recombination
    # Simpler approach: keep high as a copy, apply the grain extract
    # by computing it pixel-wise via GEGL

    # Reset high layer to normal, apply grain-extract computation via GEGL
    high_layer.set_mode(Gimp.LayerMode.NORMAL)

    # Use GEGL grain-extract: result = (high - low + 0.5)
    # We achieve this by using the low layer as aux input is not trivial,
    # so we use the standard Photoshop technique:
    # 1. Apply Image with the blurred layer in Soustraction mode + offset 128

    # Simplest reliable approach for GIMP 3.0:
    # Make high_layer a real grain-extracted version by:
    # - Temporarily flatten: put blur on high, invert blend
    # Actually, the cleanest GIMP approach:

    # Apply gaussian blur to high_layer too, then use grain-extract math
    # No — let's use the proven GIMP method:

    # Copy low_layer pixels onto a temp layer, set temp to grain-extract
    # over high_layer, flatten them together

    # The most reliable method in GIMP 3.0:
    # High layer stays as unmodified copy, set to Grain Extract.
    # When both layers are in the group:
    #   Group output = Low + (High GRAIN_EXTRACT)
    #   = Low + (Original - Low) = Original (lossless reconstruction)

    # Set the correct blend mode for recombination
    high_layer.set_mode(Gimp.LayerMode.GRAIN_EXTRACT)

    # For the retouching workflow, the user should:
    # - Flatten high into real pixels, then set to Grain Merge
    # Let's do that for a proper editable setup:

    # Flatten the high frequency to actual pixel values
    # by merging it temporarily with the low layer
    temp_low = low_layer.copy()
    image.insert_layer(temp_low, group, image.get_item_position(high_layer) + 1)

    # Merge high_layer (grain extract) down onto temp_low
    merged = image.merge_down(high_layer, Gimp.MergeType.CLIP_TO_BOTTOM_LAYER)
    merged.set_name("High Frequency")
    merged.set_mode(Gimp.LayerMode.GRAIN_MERGE)

    # Now the group contains:
    #   Top: "High Frequency" (grain merge) — actual texture data at 50% gray base
    #   Bottom: "Low Frequency" (normal) — blurred color/tone
    # Combined they reconstruct the original image perfectly.

    # Hide the original source layer
    source_drawable.set_visible(False)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class FrequencySeparation(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-frequency-separation']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            frequency_separation, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Separation de frequence"),
            _("Separer l'image en calques Basse Frequence (couleur/tonalite) et Haute Frequence "
              "(texture/detail) pour la retouche beaute professionnelle. "
              "Peignez sur le calque bas pour lisser la couleur, sur le haut pour corriger la texture."),
            name)
        procedure.set_menu_label(_("Separation de _frequence..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Retouching")

        procedure.add_double_argument("blur-radius",
                                      _("Rayon de _flou"),
                                      _("Rayon de flou gaussien pour la separation basse frequence. "
                                        "Valeurs plus elevees = plus de details dans la haute frequence. "
                                        "Typique : 5-15 pour portraits, 2-5 pour photos produit."),
                                      1.0, 100.0, 10.0,
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(FrequencySeparation.__gtype__, sys.argv)

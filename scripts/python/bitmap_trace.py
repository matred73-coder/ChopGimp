#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Bitmap Trace
#   Convert bitmap images to vector paths:
#   Vectorisation par seuil, Vectorisation par couleur, Vectorisation par contour
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


def _selection_to_path_named(image, pdb, name):
    """Convert current selection to a named path. Returns the path or None."""
    # Check if there is a non-empty selection
    proc = pdb.lookup_procedure('gimp-selection-bounds')
    pc = proc.create_config()
    pc.set_property('image', image)
    result = proc.run(pc)
    has_selection = result.index(1)

    if not has_selection:
        return None

    proc = pdb.lookup_procedure('gimp-selection-to-path')
    pc = proc.create_config()
    proc.run(pc)

    vectors_list = image.get_vectors()
    if vectors_list:
        new_path = vectors_list[0]
        new_path.set_name(name)
        return new_path
    return None


# ---------------------------------------------------------------------------
# Vectorisation par seuil
# ---------------------------------------------------------------------------
def threshold_trace(procedure, run_mode, image, drawables, config, data):
    """Convert a high-contrast image to vector path via threshold and
    selection-to-path.  Works best on images with clear foreground/background
    separation (logos, line art, text)."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-threshold-trace')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    threshold_val = config.get_property('threshold')
    invert = config.get_property('invert')
    smooth = config.get_property('smooth')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    drawable = drawables[0] if drawables else image.get_active_drawable()

    if drawable is None:
        image.undo_group_end()
        Gimp.context_pop()
        error = GLib.Error.new_literal(
            GLib.quark_from_string("bitmap-trace"),
            "No active drawable.", 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

    # Work on a copy to avoid destroying the original
    work_layer = drawable.copy()
    image.insert_layer(work_layer, drawable.get_parent(),
                       image.get_item_position(drawable))
    work_layer.set_name("Trace (temp)")

    # Desaturate if RGB
    if image.get_base_type() == Gimp.ImageBaseType.RGB:
        proc = pdb.lookup_procedure('gimp-drawable-desaturate')
        pc = proc.create_config()
        pc.set_property('drawable', work_layer)
        pc.set_property('desaturate-mode', Gimp.DesaturateMode.LUMINOSITY)
        proc.run(pc)

    # Apply threshold using GEGL
    thresh_filter = Gimp.DrawableFilter.new(work_layer, "gegl:threshold", "")
    thresh_config = thresh_filter.get_config()
    thresh_config.set_property("value", threshold_val)
    work_layer.merge_filter(thresh_filter)

    # Optionally invert
    if invert:
        proc = pdb.lookup_procedure('gimp-drawable-invert')
        pc = proc.create_config()
        pc.set_property('drawable', work_layer)
        pc.set_property('linear', False)
        proc.run(pc)

    # Optional smoothing to reduce jagged edges before tracing
    if smooth > 0:
        blur_filter = Gimp.DrawableFilter.new(work_layer, "gegl:gaussian-blur", "")
        blur_config = blur_filter.get_config()
        blur_config.set_property("std-dev-x", float(smooth))
        blur_config.set_property("std-dev-y", float(smooth))
        work_layer.merge_filter(blur_filter)

        # Re-threshold after blur to get clean edges
        thresh2 = Gimp.DrawableFilter.new(work_layer, "gegl:threshold", "")
        thresh2_config = thresh2.get_config()
        thresh2_config.set_property("value", 0.5)
        work_layer.merge_filter(thresh2)

    # Select by color (black areas = the shapes to trace)
    proc = pdb.lookup_procedure('gimp-by-color-select')
    pc = proc.create_config()
    pc.set_property('drawable', work_layer)
    black = Gegl.Color.new("black")
    pc.set_property('color', black)
    pc.set_property('threshold', 15.0)
    pc.set_property('operation', Gimp.ChannelOps.REPLACE)
    pc.set_property('antialias', True)
    pc.set_property('feather', False)
    pc.set_property('feather-radius-x', 0.0)
    pc.set_property('feather-radius-y', 0.0)
    pc.set_property('sample-merged', False)
    proc.run(pc)

    # Convert selection to path
    result_path = _selection_to_path_named(image, pdb, "Vectorisation par seuil")

    # Clean up: remove work layer, clear selection
    Gimp.Selection.none(image)
    image.remove_layer(work_layer)

    # Set the traced path as active
    if result_path:
        image.set_active_vectors(result_path)

    image.set_active_layer(drawable)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Vectorisation par couleur
# ---------------------------------------------------------------------------
def color_trace(procedure, run_mode, image, drawables, config, data):
    """Separate image by color ranges and create a path for each color.
    Useful for tracing flat-color artwork into separate vector shapes."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-color-trace')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    num_colors = config.get_property('num-colors')
    color_threshold = config.get_property('color-threshold')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    drawable = drawables[0] if drawables else image.get_active_drawable()

    if drawable is None:
        image.undo_group_end()
        Gimp.context_pop()
        error = GLib.Error.new_literal(
            GLib.quark_from_string("bitmap-trace"),
            "No active drawable.", 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

    # Work on a copy with reduced colors (posterize)
    work_layer = drawable.copy()
    image.insert_layer(work_layer, drawable.get_parent(),
                       image.get_item_position(drawable))
    work_layer.set_name("Vectorisation par couleur (temp)")

    # Posterize to reduce to N colors
    posterize_filter = Gimp.DrawableFilter.new(work_layer, "gegl:posterize", "")
    posterize_config = posterize_filter.get_config()
    posterize_config.set_property("levels", num_colors)
    work_layer.merge_filter(posterize_filter)

    # Now we need to find the distinct colors and trace each one.
    # Strategy: Use the histogram/color picker approach.
    # We'll sample colors from the posterized image by scanning
    # a grid of points and collecting unique colors.

    w = work_layer.get_width()
    h = work_layer.get_height()

    # Sample colors on a grid
    found_colors = []
    sample_step = max(1, min(w, h) // 20)  # ~20x20 grid

    for sy in range(0, h, sample_step):
        for sx in range(0, w, sample_step):
            proc = pdb.lookup_procedure('gimp-drawable-get-pixel')
            pc = proc.create_config()
            pc.set_property('drawable', work_layer)
            pc.set_property('x-coord', sx)
            pc.set_property('y-coord', sy)
            result = proc.run(pc)
            pixel_color = result.index(1)

            # Check if this color is already known (within threshold)
            is_new = True
            for existing in found_colors:
                if _colors_similar(pixel_color, existing, color_threshold):
                    is_new = False
                    break
            if is_new:
                found_colors.append(pixel_color)

            # Safety limit
            if len(found_colors) >= num_colors * 2:
                break
        if len(found_colors) >= num_colors * 2:
            break

    # For each found color, select it and convert to path
    path_count = 0
    for i, color in enumerate(found_colors):
        if path_count >= num_colors:
            break

        proc = pdb.lookup_procedure('gimp-by-color-select')
        pc = proc.create_config()
        pc.set_property('drawable', work_layer)
        pc.set_property('color', color)
        pc.set_property('threshold', float(color_threshold))
        pc.set_property('operation', Gimp.ChannelOps.REPLACE)
        pc.set_property('antialias', True)
        pc.set_property('feather', False)
        pc.set_property('feather-radius-x', 0.0)
        pc.set_property('feather-radius-y', 0.0)
        pc.set_property('sample-merged', False)
        proc.run(pc)

        result_path = _selection_to_path_named(
            image, pdb, "Vectorisation par couleur #%d" % (i + 1))
        if result_path:
            path_count += 1

    # Clean up
    Gimp.Selection.none(image)
    image.remove_layer(work_layer)
    image.set_active_layer(drawable)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def _colors_similar(c1, c2, threshold):
    """Check if two Gegl.Color objects are similar within threshold.
    Uses a simple RGB distance comparison."""
    try:
        r1, g1, b1, a1 = c1.get_rgba()
        r2, g2, b2, a2 = c2.get_rgba()
        dist = abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
        return dist * 255.0 < threshold * 3.0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Vectorisation par contour
# ---------------------------------------------------------------------------
def edge_trace(procedure, run_mode, image, drawables, config, data):
    """Detecter les contours de l'image et les convertir en chemins vectoriels.
    Uses edge detection filter, then threshold, then selection-to-path."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-edge-trace')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    edge_amount = config.get_property('edge-amount')
    threshold_val = config.get_property('threshold')
    smooth = config.get_property('smooth')
    algorithm = config.get_property('algorithm')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    drawable = drawables[0] if drawables else image.get_active_drawable()

    if drawable is None:
        image.undo_group_end()
        Gimp.context_pop()
        error = GLib.Error.new_literal(
            GLib.quark_from_string("bitmap-trace"),
            "No active drawable.", 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

    # Work on a copy
    work_layer = drawable.copy()
    image.insert_layer(work_layer, drawable.get_parent(),
                       image.get_item_position(drawable))
    work_layer.set_name("Vectorisation par contour (temp)")

    # Desaturate first for cleaner edges
    if image.get_base_type() == Gimp.ImageBaseType.RGB:
        proc = pdb.lookup_procedure('gimp-drawable-desaturate')
        pc = proc.create_config()
        pc.set_property('drawable', work_layer)
        pc.set_property('desaturate-mode', Gimp.DesaturateMode.LUMINOSITY)
        proc.run(pc)

    # Apply edge detection
    if algorithm == "sobel":
        edge_filter = Gimp.DrawableFilter.new(work_layer, "gegl:edge-sobel", "")
        edge_config = edge_filter.get_config()
        edge_config.set_property("horizontal", True)
        edge_config.set_property("vertical", True)
        edge_config.set_property("keep-sign", False)
        work_layer.merge_filter(edge_filter)
    elif algorithm == "laplace":
        edge_filter = Gimp.DrawableFilter.new(work_layer, "gegl:edge-laplace", "")
        work_layer.merge_filter(edge_filter)
    elif algorithm == "neon":
        # Use edge-neon (Neon glow edge detection)
        edge_filter = Gimp.DrawableFilter.new(work_layer, "gegl:edge-neon", "")
        edge_config = edge_filter.get_config()
        edge_config.set_property("radius", edge_amount)
        edge_config.set_property("amount", edge_amount)
        work_layer.merge_filter(edge_filter)
    else:
        # Default: difference-of-gaussians for edge detection
        edge_filter = Gimp.DrawableFilter.new(work_layer, "gegl:difference-of-gaussians", "")
        edge_config = edge_filter.get_config()
        edge_config.set_property("radius1", edge_amount)
        edge_config.set_property("radius2", edge_amount * 0.5)
        work_layer.merge_filter(edge_filter)

    # Boost contrast of edge result
    levels_filter = Gimp.DrawableFilter.new(work_layer, "gegl:stretch-contrast", "")
    levels_config = levels_filter.get_config()
    levels_config.set_property("keep-colors", False)
    work_layer.merge_filter(levels_filter)

    # Apply threshold to get clean black/white edges
    thresh_filter = Gimp.DrawableFilter.new(work_layer, "gegl:threshold", "")
    thresh_config = thresh_filter.get_config()
    thresh_config.set_property("value", threshold_val)
    work_layer.merge_filter(thresh_filter)

    # Optional smoothing before tracing
    if smooth > 0:
        blur_filter = Gimp.DrawableFilter.new(work_layer, "gegl:gaussian-blur", "")
        blur_config = blur_filter.get_config()
        blur_config.set_property("std-dev-x", float(smooth))
        blur_config.set_property("std-dev-y", float(smooth))
        work_layer.merge_filter(blur_filter)

        # Re-threshold after smoothing
        thresh2 = Gimp.DrawableFilter.new(work_layer, "gegl:threshold", "")
        thresh2_config = thresh2.get_config()
        thresh2_config.set_property("value", 0.5)
        work_layer.merge_filter(thresh2)

    # Invert so edges become the selected region (edges are white after detection)
    proc = pdb.lookup_procedure('gimp-drawable-invert')
    pc = proc.create_config()
    pc.set_property('drawable', work_layer)
    pc.set_property('linear', False)
    proc.run(pc)

    # Select the edge regions
    proc = pdb.lookup_procedure('gimp-by-color-select')
    pc = proc.create_config()
    pc.set_property('drawable', work_layer)
    black = Gegl.Color.new("black")
    pc.set_property('color', black)
    pc.set_property('threshold', 15.0)
    pc.set_property('operation', Gimp.ChannelOps.REPLACE)
    pc.set_property('antialias', True)
    pc.set_property('feather', False)
    pc.set_property('feather-radius-x', 0.0)
    pc.set_property('feather-radius-y', 0.0)
    pc.set_property('sample-merged', False)
    proc.run(pc)

    # Convert to path
    result_path = _selection_to_path_named(image, pdb, "Vectorisation par contour")

    # Clean up
    Gimp.Selection.none(image)
    image.remove_layer(work_layer)
    image.set_active_layer(drawable)

    if result_path:
        image.set_active_vectors(result_path)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class BitmapTrace(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-threshold-trace',
            'python-fu-color-trace',
            'python-fu-edge-trace',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)
        menu_base = "<Image>/Filters/Vector/Trace"

        if name == 'python-fu-threshold-trace':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                threshold_trace, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Vectorisation par seuil"),
                _("Convert a high-contrast image to a vector path using threshold. "
                  "Ideal for logos, line art, and text."),
                name)
            procedure.set_menu_label(_("_Vectorisation par seuil..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("threshold", _("_Seuil"),
                                          _("Threshold value (0.0=all black, 1.0=all white)"),
                                          0.0, 1.0, 0.5,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_boolean_argument("invert", _("_Inverser"),
                                           _("Inverser le seuil (vectoriser les zones blanches au lieu des noires)"),
                                           False, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("smooth", _("_Lisser"),
                                          _("Pre-smooth radius to reduce jagged edges (0=none)"),
                                          0.0, 20.0, 1.0,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-color-trace':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                color_trace, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Vectorisation par couleur"),
                _("Separate image by color regions and create a path for each. "
                  "Best for flat-color artwork, icons, and illustrations."),
                name)
            procedure.set_menu_label(_("Vectorisation par _couleur..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_int_argument("num-colors", _("Nombre de _couleurs"),
                                       _("Nombre maximum de regions de couleur a vectoriser"),
                                       2, 32, 6,
                                       GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("color-threshold", _("_Seuil de couleur"),
                                          _("Tolerance pour le regroupement de couleurs similaires"),
                                          1.0, 128.0, 30.0,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-edge-trace':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                edge_trace, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Vectorisation par contour"),
                _("Detecter les contours de l'image et les convertir en chemins vectoriels."),
                name)
            procedure.set_menu_label(_("Vectorisation par _contour..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("edge-amount", _("Intensite du _contour"),
                                          _("Strength/radius of edge detection"),
                                          0.5, 50.0, 2.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("threshold", _("_Seuil"),
                                          _("Seuil pour la classification contour/non-contour"),
                                          0.0, 1.0, 0.3,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("smooth", _("_Lisser"),
                                          _("Post-smooth radius before tracing (0=none)"),
                                          0.0, 20.0, 1.0,
                                          GObject.ParamFlags.READWRITE)

            algo_choice = Gimp.Choice.new()
            algo_choice.add("sobel", 0, _("Sobel"), "")
            algo_choice.add("laplace", 1, _("Laplace"), "")
            algo_choice.add("neon", 2, _("Neon"), "")
            algo_choice.add("dog", 3, _("Difference of Gaussians"), "")
            procedure.add_choice_argument("algorithm", _("_Algorithmee"),
                                          _("Algorithme de detection de contour to use"),
                                          algo_choice, "sobel",
                                          GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(BitmapTrace.__gtype__, sys.argv)

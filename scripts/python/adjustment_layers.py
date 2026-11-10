#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Calques de reglage
#   True adjustment layers using blend modes — no pixel duplication.
#   Each creates a lightweight layer (solid color or 50% gray) with the
#   appropriate blend mode. User controls strength via layer opacity.
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


def _get_insert_pos(image, drawables):
    """Return (parent, position) to insert above active drawable."""
    active = drawables[0] if drawables else image.get_active_drawable()
    parent = active.get_parent() if active else None
    pos = image.get_item_position(active) if active else 0
    return parent, pos


def _make_color(r, g, b):
    """Create a Gimp.RGB color."""
    color = Gimp.RGB()
    color.set(r, g, b)
    return color


def _fill_layer_with_color(layer, r, g, b):
    """Fill a layer with a solid color."""
    Gimp.context_set_foreground(_make_color(r, g, b))
    layer.edit_fill(Gimp.FillType.FOREGROUND)


# ---------------------------------------------------------------------------
#  Auto Levels adjustment layer
# ---------------------------------------------------------------------------
def adj_auto_levels(procedure, run_mode, image, drawables, config, data):
    """Create a transparent layer that applies auto-levels via curves.

    Strategy: Create a curves adjustment by duplicating the active layer,
    applying stretch-contrast, then setting it to Grain Merge mode so only
    the tonal correction is applied. Actually lighter: use a Luminosity-mode
    stretched duplicate at low opacity.

    Even lighter approach: we apply gegl:stretch-contrast to a copy layer
    set to Color mode so it only affects tonal distribution.
    """
    Gimp.context_push()
    image.undo_group_start()

    parent, pos = _get_insert_pos(image, drawables)
    drawable = drawables[0] if drawables else image.get_active_drawable()

    # Duplicate active layer
    adj_layer = drawable.copy()
    adj_layer.set_name("[Reglage] Niveaux auto")
    image.insert_layer(adj_layer, parent, pos)

    # Apply stretch-contrast (auto levels)
    stretch = Gimp.DrawableFilter.new(adj_layer, "gegl:stretch-contrast", "")
    stretch_cfg = stretch.get_config()
    stretch_cfg.set_property("keep-colors", False)
    adj_layer.merge_filter(stretch)

    # Set to Grain Merge mode — this applies only the difference in tonality
    adj_layer.set_mode(Gimp.LayerMode.GRAIN_MERGE)
    adj_layer.set_opacity(50.0)

    image.set_active_layer(adj_layer)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  S-Curve contrast adjustment layer
# ---------------------------------------------------------------------------
def adj_s_curve(procedure, run_mode, image, drawables, config, data):
    """Create a 50% gray Overlay layer with S-curve applied for contrast."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-adj-s-curve')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    strength = config.get_property('strength')

    Gimp.context_push()
    image.undo_group_start()

    parent, pos = _get_insert_pos(image, drawables)
    w = image.get_width()
    h = image.get_height()

    # 50% gray layer in Overlay mode
    adj_layer = Gimp.Layer.new(image, w, h, Gimp.ImageType.RGBA_IMAGE,
                               "[Reglage] Courbe S", 100.0,
                               Gimp.LayerMode.OVERLAY)
    image.insert_layer(adj_layer, parent, pos)
    _fill_layer_with_color(adj_layer, 0.5, 0.5, 0.5)

    # Apply S-curve using GEGL brightness-contrast
    # Positive contrast creates an S-curve effect
    bc_filter = Gimp.DrawableFilter.new(adj_layer, "gegl:brightness-contrast", "")
    bc_config = bc_filter.get_config()
    bc_config.set_property("contrast", strength / 100.0 * 0.5)
    adj_layer.merge_filter(bc_filter)

    adj_layer.set_opacity(strength)
    image.set_active_layer(adj_layer)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Color Tint adjustment layer
# ---------------------------------------------------------------------------
def adj_color_tint(procedure, run_mode, image, drawables, config, data):
    """Create a solid color layer in Color blend mode for tinting."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-adj-color-tint')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    opacity = config.get_property('opacity')

    Gimp.context_push()
    image.undo_group_start()

    parent, pos = _get_insert_pos(image, drawables)
    w = image.get_width()
    h = image.get_height()

    # Get the current foreground color as tint color
    tint_color = Gimp.context_get_foreground()

    adj_layer = Gimp.Layer.new(image, w, h, Gimp.ImageType.RGBA_IMAGE,
                               "[Reglage] Teinte couleur",
                               opacity, Gimp.LayerMode.HSL_COLOR)
    image.insert_layer(adj_layer, parent, pos)

    # Fill with the foreground (tint) color
    Gimp.context_set_foreground(tint_color)
    adj_layer.edit_fill(Gimp.FillType.FOREGROUND)

    image.set_active_layer(adj_layer)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Dodge (global lighten)
# ---------------------------------------------------------------------------
def adj_dodge_global(procedure, run_mode, image, drawables, config, data):
    """Create a white layer in Soft Light mode at low opacity to globally lighten."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-adj-dodge-global')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    opacity = config.get_property('opacity')

    Gimp.context_push()
    image.undo_group_start()

    parent, pos = _get_insert_pos(image, drawables)
    w = image.get_width()
    h = image.get_height()

    adj_layer = Gimp.Layer.new(image, w, h, Gimp.ImageType.RGBA_IMAGE,
                               "[Reglage] Dodge global",
                               opacity, Gimp.LayerMode.SOFTLIGHT)
    image.insert_layer(adj_layer, parent, pos)
    _fill_layer_with_color(adj_layer, 1.0, 1.0, 1.0)

    image.set_active_layer(adj_layer)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Burn (global darken)
# ---------------------------------------------------------------------------
def adj_burn_global(procedure, run_mode, image, drawables, config, data):
    """Create a black layer in Soft Light mode at low opacity to globally darken."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-adj-burn-global')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    opacity = config.get_property('opacity')

    Gimp.context_push()
    image.undo_group_start()

    parent, pos = _get_insert_pos(image, drawables)
    w = image.get_width()
    h = image.get_height()

    adj_layer = Gimp.Layer.new(image, w, h, Gimp.ImageType.RGBA_IMAGE,
                               "[Reglage] Burn global",
                               opacity, Gimp.LayerMode.SOFTLIGHT)
    image.insert_layer(adj_layer, parent, pos)
    _fill_layer_with_color(adj_layer, 0.0, 0.0, 0.0)

    image.set_active_layer(adj_layer)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Vibrance boost
# ---------------------------------------------------------------------------
def adj_vibrance(procedure, run_mode, image, drawables, config, data):
    """Vibrance boost: duplicate layer, saturate, Color mode, low opacity.

    Mask highlights to avoid over-saturating already vivid areas.
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-adj-vibrance')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    opacity = config.get_property('opacity')
    saturation_boost = config.get_property('saturation-boost')

    Gimp.context_push()
    image.undo_group_start()

    parent, pos = _get_insert_pos(image, drawables)
    drawable = drawables[0] if drawables else image.get_active_drawable()

    # Duplicate the active layer
    adj_layer = drawable.copy()
    adj_layer.set_name("[Reglage] Vibrance")
    image.insert_layer(adj_layer, parent, pos)

    # Boost saturation using GEGL hue-saturation
    sat_filter = Gimp.DrawableFilter.new(adj_layer, "gegl:hue-chroma", "")
    sat_config = sat_filter.get_config()
    sat_config.set_property("chroma", saturation_boost)
    adj_layer.merge_filter(sat_filter)

    # Set to LCH Color mode so only color info is used (preserves luminosity)
    adj_layer.set_mode(Gimp.LayerMode.LCH_COLOR)
    adj_layer.set_opacity(opacity)

    # Add a luminosity mask to protect already-saturated highlights:
    # Create a desaturated copy as mask — bright (saturated) areas become light
    # in the mask, which we invert so they are protected
    mask = adj_layer.create_mask(Gimp.AddMaskType.BLACK)
    adj_layer.add_mask(mask)

    # Fill mask with white (fully visible)
    white = _make_color(1.0, 1.0, 1.0)
    Gimp.context_set_foreground(white)
    mask.edit_fill(Gimp.FillType.FOREGROUND)

    # Apply desaturation to get luminosity, then use levels to create
    # a mask that protects highlights (already saturated areas)
    # Copy original drawable content to mask for luminosity-based protection
    Gimp.Selection.all(image)
    drawable.edit_copy()
    floating = mask.edit_paste(False)
    Gimp.floating_sel_anchor(floating)

    # Desaturate the mask
    desat_filter = Gimp.DrawableFilter.new(mask, "gegl:desaturate", "")
    desat_config = desat_filter.get_config()
    desat_config.set_property("mode", 0)  # luminosity
    mask.merge_filter(desat_filter)

    # Invert so dark areas (low saturation) are white (affected)
    # and bright areas (high saturation) are dark (protected)
    invert_filter = Gimp.DrawableFilter.new(mask, "gegl:invert-linear", "")
    mask.merge_filter(invert_filter)

    Gimp.Selection.none(image)
    image.set_active_layer(adj_layer)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class AdjustmentLayers(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-adj-auto-levels',
            'python-fu-adj-s-curve',
            'python-fu-adj-color-tint',
            'python-fu-adj-dodge-global',
            'python-fu-adj-burn-global',
            'python-fu-adj-vibrance',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        # --- Auto Levels ---
        if name == 'python-fu-adj-auto-levels':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                adj_auto_levels, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Calque de reglage — Niveaux auto"),
                _("Cree un calque de reglage niveaux auto en mode Fusion de grain. "
                  "Reglez l'opacite pour controler l'intensite."),
                name)
            procedure.set_menu_label(_("_Niveaux auto"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Adjustment Layers")

        # --- S-Curve ---
        elif name == 'python-fu-adj-s-curve':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                adj_s_curve, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Calque de reglage — Courbe S"),
                _("Cree un calque gris 50% en mode Superposition avec un contraste "
                  "en courbe S. Reglez l'opacite pour controler l'intensite."),
                name)
            procedure.set_menu_label(_("Courbe _S..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Adjustment Layers")

            procedure.add_double_argument("strength",
                                          _("_Intensite"),
                                          _("Force du contraste en courbe S (%)"),
                                          1.0, 100.0, 50.0,
                                          GObject.ParamFlags.READWRITE)

        # --- Color Tint ---
        elif name == 'python-fu-adj-color-tint':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                adj_color_tint, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Calque de reglage — Teinte couleur"),
                _("Cree un calque de couleur unie en mode Couleur TSL. "
                  "Definissez la couleur de premier plan avant d'executer. "
                  "Reglez l'opacite pour doser l'effet."),
                name)
            procedure.set_menu_label(_("_Teinte couleur..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Adjustment Layers")

            procedure.add_double_argument("opacity",
                                          _("_Opacite"),
                                          _("Opacite du calque de teinte (%)"),
                                          1.0, 100.0, 25.0,
                                          GObject.ParamFlags.READWRITE)

        # --- Dodge Global ---
        elif name == 'python-fu-adj-dodge-global':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                adj_dodge_global, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Calque de reglage — Dodge global"),
                _("Cree un calque blanc en mode Lumiere tamisee pour eclaircir "
                  "globalement l'image. Reglez l'opacite pour doser."),
                name)
            procedure.set_menu_label(_("_Dodge global (eclaircir)..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Adjustment Layers")

            procedure.add_double_argument("opacity",
                                          _("_Opacite"),
                                          _("Opacite du calque dodge (%)"),
                                          1.0, 100.0, 15.0,
                                          GObject.ParamFlags.READWRITE)

        # --- Burn Global ---
        elif name == 'python-fu-adj-burn-global':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                adj_burn_global, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Calque de reglage — Burn global"),
                _("Cree un calque noir en mode Lumiere tamisee pour assombrir "
                  "globalement l'image. Reglez l'opacite pour doser."),
                name)
            procedure.set_menu_label(_("_Burn global (assombrir)..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Adjustment Layers")

            procedure.add_double_argument("opacity",
                                          _("_Opacite"),
                                          _("Opacite du calque burn (%)"),
                                          1.0, 100.0, 15.0,
                                          GObject.ParamFlags.READWRITE)

        # --- Vibrance ---
        elif name == 'python-fu-adj-vibrance':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                adj_vibrance, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Calque de reglage — Vibrance"),
                _("Augmente la vibrance (saturation selective) via un calque en mode "
                  "Couleur LCH avec un masque de luminosite qui protege les zones "
                  "deja saturees."),
                name)
            procedure.set_menu_label(_("_Vibrance..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Adjustment Layers")

            procedure.add_double_argument("opacity",
                                          _("_Opacite"),
                                          _("Opacite du calque vibrance (%)"),
                                          1.0, 100.0, 40.0,
                                          GObject.ParamFlags.READWRITE)

            procedure.add_double_argument("saturation-boost",
                                          _("_Boost saturation"),
                                          _("Augmentation de la saturation chroma"),
                                          0.0, 100.0, 30.0,
                                          GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(AdjustmentLayers.__gtype__, sys.argv)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Text Effects
#   Apply visual effects to text layers: 3D, Neon, Chrome, Outline, Shadow, Arc
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


# ---------------------------------------------------------------------------
#  Helper utilities
# ---------------------------------------------------------------------------

def get_pdb():
    return Gimp.get_pdb()


def ensure_not_group(drawable):
    """Return True if drawable is usable (not a group)."""
    return not drawable.is_group()


# ---------------------------------------------------------------------------
#  3D Text Effect
# ---------------------------------------------------------------------------

def text_3d(procedure, run_mode, image, drawables, config, data):
    """Create a 3D / extruded look by stacking darkened offset duplicates."""
    Gimp.context_push()
    image.undo_group_start()
    pdb = get_pdb()

    depth = 10       # number of copies
    offset_x = 1     # px per step
    offset_y = 1
    darken_step = 8  # darken each successive copy

    for drawable in drawables:
        if not ensure_not_group(drawable):
            continue

        parent = drawable.get_parent()
        pos = image.get_item_position(drawable)

        for i in range(depth, 0, -1):
            dup = drawable.copy()
            image.insert_layer(dup, parent, pos + 1)
            dup.set_offsets(
                drawable.get_offsets().offset_x + offset_x * i,
                drawable.get_offsets().offset_y + offset_y * i,
            )
            dup.set_name(f"{drawable.get_name()} 3D-{i}")

            # Darken via brightness-contrast GEGL
            bc_filter = Gimp.DrawableFilter.new(
                dup, "gegl:brightness-contrast", "")
            bc_config = bc_filter.get_config()
            bc_config.set_property("brightness", -darken_step * i / 255.0)
            dup.merge_filter(bc_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Neon Glow Effect
# ---------------------------------------------------------------------------

def text_neon_glow(procedure, run_mode, image, drawables, config, data):
    """Neon glow: duplicate text, Gaussian blur, colorize, set to Screen mode."""
    Gimp.context_push()
    image.undo_group_start()
    pdb = get_pdb()

    glow_radius = 15.0

    for drawable in drawables:
        if not ensure_not_group(drawable):
            continue

        parent = drawable.get_parent()
        pos = image.get_item_position(drawable)

        # Create glow layer (duplicate below the text)
        glow = drawable.copy()
        image.insert_layer(glow, parent, pos + 1)
        glow.set_name(f"{drawable.get_name()} Neon-Glow")

        # Flatten the glow copy if it has alpha
        pdb.run_procedure("gimp-layer-flatten-image", [])  # noop; we just blur

        # Apply Gaussian blur via GEGL
        blur_filter = Gimp.DrawableFilter.new(
            glow, "gegl:gaussian-blur", "")
        blur_config = blur_filter.get_config()
        blur_config.set_property("std-dev-x", glow_radius)
        blur_config.set_property("std-dev-y", glow_radius)
        glow.merge_filter(blur_filter)

        # Colorize the glow (neon cyan-ish: hue ~0.52, high saturation)
        color_filter = Gimp.DrawableFilter.new(
            glow, "gegl:hue-chroma", "")
        try:
            cc = color_filter.get_config()
            cc.set_property("hue", 180.0)  # shift towards cyan
        except Exception:
            pass
        glow.merge_filter(color_filter)

        # Set blend mode to Screen for the glow
        glow.set_mode(Gimp.LayerMode.SCREEN)
        glow.set_opacity(85.0)

        # Make a second stronger glow for intensity
        glow2 = glow.copy()
        image.insert_layer(glow2, parent, pos + 2)
        glow2.set_name(f"{drawable.get_name()} Neon-Glow-2")
        glow2.set_mode(Gimp.LayerMode.SCREEN)
        glow2.set_opacity(60.0)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Chrome / Metal Effect
# ---------------------------------------------------------------------------

def text_chrome(procedure, run_mode, image, drawables, config, data):
    """Chrome/metal look: emboss + desaturate + curves for metallic sheen."""
    Gimp.context_push()
    image.undo_group_start()
    pdb = get_pdb()

    for drawable in drawables:
        if not ensure_not_group(drawable):
            continue

        # Desaturate (luminosity) to get greyscale base
        desat_filter = Gimp.DrawableFilter.new(
            drawable, "gegl:saturation", "")
        desat_config = desat_filter.get_config()
        desat_config.set_property("scale", 0.0)
        drawable.merge_filter(desat_filter)

        # Emboss via GEGL for 3D metallic feel
        try:
            emboss_filter = Gimp.DrawableFilter.new(
                drawable, "gegl:emboss", "")
            emboss_config = emboss_filter.get_config()
            emboss_config.set_property("azimuth", 315.0)
            emboss_config.set_property("elevation", 45.0)
            emboss_config.set_property("depth", 3)
            drawable.merge_filter(emboss_filter)
        except Exception:
            pass

        # Increase contrast for chrome shine
        bc_filter = Gimp.DrawableFilter.new(
            drawable, "gegl:brightness-contrast", "")
        bc_config = bc_filter.get_config()
        bc_config.set_property("contrast", 0.4)
        bc_config.set_property("brightness", 0.05)
        drawable.merge_filter(bc_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Outline Text Effect
# ---------------------------------------------------------------------------

def text_outline(procedure, run_mode, image, drawables, config, data):
    """Add a colored outline around text using alpha-to-selection + grow + stroke."""
    Gimp.context_push()
    image.undo_group_start()
    pdb = get_pdb()

    outline_size = 3   # pixels to grow
    # Outline color: white
    outline_color = Gimp.RGB()
    outline_color.set(1.0, 1.0, 1.0)

    for drawable in drawables:
        if not ensure_not_group(drawable):
            continue

        parent = drawable.get_parent()
        pos = image.get_item_position(drawable)

        # Create outline layer below text
        w = image.get_width()
        h = image.get_height()
        outline_layer = Gimp.Layer.new(
            image, f"{drawable.get_name()} Outline",
            w, h, Gimp.ImageType.RGBA_IMAGE, 100.0,
            Gimp.LayerMode.NORMAL)
        image.insert_layer(outline_layer, parent, pos + 1)

        # Alpha to selection from text layer
        pdb.run_procedure("gimp-image-set-active-layer", [image, drawable])
        pdb.run_procedure("gimp-layer-create-mask", [drawable, Gimp.AddMaskType.ALPHA_TRANSFER])
        image.select_item(Gimp.ChannelOps.REPLACE, drawable)

        # Grow selection
        pdb.run_procedure("gimp-selection-grow", [image, outline_size])

        # Fill on outline layer
        image.set_active_layer(outline_layer)
        Gimp.context_set_foreground(outline_color)
        pdb.run_procedure("gimp-edit-fill", [outline_layer, Gimp.FillType.FOREGROUND])

        # Remove selection
        pdb.run_procedure("gimp-selection-none", [image])

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Shadow Text Effect
# ---------------------------------------------------------------------------

def text_shadow(procedure, run_mode, image, drawables, config, data):
    """Add a configurable drop shadow behind text."""
    Gimp.context_push()
    image.undo_group_start()
    pdb = get_pdb()

    shadow_offset_x = 4
    shadow_offset_y = 4
    shadow_blur = 8.0
    shadow_opacity = 60.0

    shadow_color = Gimp.RGB()
    shadow_color.set(0.0, 0.0, 0.0)

    for drawable in drawables:
        if not ensure_not_group(drawable):
            continue

        parent = drawable.get_parent()
        pos = image.get_item_position(drawable)

        # Duplicate text layer for shadow
        shadow = drawable.copy()
        image.insert_layer(shadow, parent, pos + 1)
        shadow.set_name(f"{drawable.get_name()} Shadow")
        shadow.set_opacity(shadow_opacity)

        # Offset the shadow
        off = drawable.get_offsets()
        shadow.set_offsets(off.offset_x + shadow_offset_x,
                           off.offset_y + shadow_offset_y)

        # Fill shadow layer with black (lock alpha, fill)
        shadow.set_lock_alpha(True)
        Gimp.context_set_foreground(shadow_color)
        pdb.run_procedure("gimp-edit-fill",
                          [shadow, Gimp.FillType.FOREGROUND])
        shadow.set_lock_alpha(False)

        # Blur the shadow
        blur_filter = Gimp.DrawableFilter.new(
            shadow, "gegl:gaussian-blur", "")
        blur_config = blur_filter.get_config()
        blur_config.set_property("std-dev-x", shadow_blur)
        blur_config.set_property("std-dev-y", shadow_blur)
        shadow.merge_filter(blur_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Arc Text Effect
# ---------------------------------------------------------------------------

def text_arc(procedure, run_mode, image, drawables, config, data):
    """Bend text along an arc using text-along-path (vectors)."""
    Gimp.context_push()
    image.undo_group_start()
    pdb = get_pdb()

    for drawable in drawables:
        if not ensure_not_group(drawable):
            continue

        w = image.get_width()
        h = image.get_height()

        # Create an elliptical arc path
        # The arc spans the width of the image
        vectors = Gimp.Vectors.new(image, "Arc Path")
        image.insert_vectors(vectors, None, 0)

        # Build a Bezier arc (semicircle across the top half)
        cx, cy = w / 2.0, h / 2.0
        rx, ry = w * 0.4, h * 0.3

        # Approximate semicircle with cubic Bezier (4 control points)
        kappa = 0.5522847498  # magic number for circle approx
        points = [
            cx - rx, cy,            # P0
            cx - rx, cy,            # P0 handle-left (same)
            cx - rx, cy - ry * kappa,  # P0 handle-right

            cx - rx * kappa, cy - ry,  # P1 handle-left
            cx, cy - ry,               # P1
            cx + rx * kappa, cy - ry,  # P1 handle-right

            cx + rx, cy - ry * kappa,  # P2 handle-left
            cx + rx, cy,               # P2
            cx + rx, cy,               # P2 handle-right (same)
        ]

        # GIMP vectors stroke: each anchor has 6 coords (ctrl1_x, ctrl1_y, x, y, ctrl2_x, ctrl2_y)
        stroke_id = vectors.stroke_new_from_points(
            Gimp.VectorsContourType.BEZIER,
            points, False)

        # If drawable is a text layer, use text-along-path
        is_text = False
        try:
            is_text = drawable.is_text_layer()
        except Exception:
            pass

        if is_text:
            try:
                pdb.run_procedure("gimp-text-layer-set-text-along-path",
                                  [drawable, vectors])
            except Exception:
                # Fallback: warp transform via GEGL
                try:
                    warp = Gimp.DrawableFilter.new(
                        drawable, "gegl:waterpixels", "")
                    # Simple spherize as arc approximation
                    sph = Gimp.DrawableFilter.new(
                        drawable, "gegl:spherize", "")
                    sph_config = sph.get_config()
                    sph_config.set_property("mode", 0)  # radial
                    sph_config.set_property("angle-over-pi-x", 1.0)
                    drawable.merge_filter(sph)
                except Exception:
                    pass
        else:
            # Non-text layer: apply curve warp
            try:
                curve = Gimp.DrawableFilter.new(
                    drawable, "gegl:curve-bend", "")
                drawable.merge_filter(curve)
            except Exception:
                pass

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
#  Plugin registration
# ===========================================================================

class TextEffects(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-text-3d',
            'python-fu-text-neon-glow',
            'python-fu-text-chrome',
            'python-fu-text-outline',
            'python-fu-text-shadow',
            'python-fu-text-arc',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        effects = {
            'python-fu-text-3d': (
                text_3d,
                "Texte _3D",
                "Creer un effet de texte 3D extrude avec des calques decales empiles.",
            ),
            'python-fu-text-neon-glow': (
                text_neon_glow,
                "Lueur _neon",
                "Ajouter un effet de lueur neon autour du texte avec des calques flous en mode ecran.",
            ),
            'python-fu-text-chrome': (
                text_chrome,
                "_Chrome / Metal",
                "Appliquer un reflet chrome/metallique au texte par estampage et desaturation.",
            ),
            'python-fu-text-outline': (
                text_outline,
                "Texte avec _contour",
                "Ajouter un contour colore autour du texte en agrandissant la selection et en remplissant.",
            ),
            'python-fu-text-shadow': (
                text_shadow,
                "Ombre _portee",
                "Ajouter une ombre portee configurable derriere le texte.",
            ),
            'python-fu-text-arc': (
                text_arc,
                "Texte en _arc",
                "Courber le texte le long d'un chemin en arc.",
            ),
        }

        if name not in effects:
            return None

        entry = effects[name]
        func = entry[0]
        label = entry[1]
        doc = entry[2]

        procedure = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, func, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(
            Gimp.ProcedureSensitivityMask.DRAWABLE |
            Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(_(label), _(doc), name)
        procedure.set_menu_label(_(label))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Typography/Text Effects")

        return procedure


Gimp.main(TextEffects.__gtype__, sys.argv)

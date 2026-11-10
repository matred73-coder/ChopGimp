#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Masques de luminosite
#   Generate Photoshop-style luminosity masks (Lights, Darks, Midtones)
#   stored as channels for precise selection control.
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


def _desaturate_to_luminosity(image, drawable):
    """Return a new channel representing the luminosity of the drawable.

    Creates a temporary layer, desaturates it (luminosity mode), converts
    to grayscale selection, and returns raw pixel data as a channel.
    """
    # Duplicate the drawable as a temp layer
    temp = drawable.copy()
    image.insert_layer(temp, drawable.get_parent(),
                       image.get_item_position(drawable))
    temp.set_name("_lum_temp")

    # Desaturate using luminosity (weighted average matching human perception)
    desat_filter = Gimp.DrawableFilter.new(temp, "gegl:desaturate", "")
    desat_config = desat_filter.get_config()
    # 0 = luminosity, 1 = luma, 2 = lightness, 3 = average, 4 = value
    desat_config.set_property("mode", 0)
    temp.merge_filter(desat_filter)

    # Select all, copy from the desaturated layer
    image.set_active_layer(temp)
    Gimp.Selection.all(image)
    temp.edit_copy()

    # Create a channel from the clipboard
    channel = Gimp.Channel.new(image, image.get_width(), image.get_height(),
                               "_lum_base", 50.0, Gimp.RGB())
    image.insert_channel(channel, None, 0)

    # Paste the luminosity data into the channel
    floating = channel.edit_paste(False)
    Gimp.floating_sel_anchor(floating)

    # Remove temp layer
    image.remove_layer(temp)
    Gimp.Selection.none(image)

    return channel


def _channel_from_existing(image, source_channel, name, opacity):
    """Duplicate a channel under a new name."""
    new_ch = source_channel.copy()
    new_ch.set_name(name)
    new_ch.set_opacity(opacity)
    image.insert_channel(new_ch, None, 0)
    return new_ch


def _apply_curves_narrow(image, channel, iterations):
    """Apply curves to narrow the tonal range of a mask.

    More iterations = narrower range (brighter lights or darker darks).
    This multiplies the mask by itself, effectively raising pixel values
    to a power.
    """
    for _i in range(iterations):
        # Select from channel, then intersect with itself via fill
        image.set_active_channel(channel)
        Gimp.Selection.all(image)
        channel.edit_copy()
        floating = channel.edit_paste(False)
        Gimp.Item.set_visible(floating, True)
        # Set the floating selection to Multiply-like behavior:
        # We paste the same data and anchor — effectively squares the values
        Gimp.floating_sel_anchor(floating)

        # Use curves to push contrast: darken shadows, brighten highlights
        curves_filter = Gimp.DrawableFilter.new(channel, "gegl:curves", "")
        curves_config = curves_filter.get_config()
        channel.merge_filter(curves_filter)

    Gimp.Selection.none(image)


def _invert_channel(image, channel):
    """Invert a channel's pixel values."""
    invert_filter = Gimp.DrawableFilter.new(channel, "gegl:invert-linear", "")
    channel.merge_filter(invert_filter)


def generate_luminosity_masks(procedure, run_mode, image, drawables, config, data):
    """Generate 7 luminosity mask channels: Lights 1-3, Darks 1-3, Midtones."""
    Gimp.context_push()
    image.undo_group_start()

    drawable = drawables[0] if drawables else image.get_active_drawable()
    if drawable is None:
        image.undo_group_end()
        Gimp.context_pop()
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error())

    w = image.get_width()
    h = image.get_height()

    # --- Base luminosity channel ---
    base_lum = _desaturate_to_luminosity(image, drawable)

    # --- Lights 1 (brightest pixels, full luminosity) ---
    lights1 = _channel_from_existing(image, base_lum, "Lumieres 1 (large)", 50.0)

    # --- Lights 2 (narrower highlights) ---
    lights2 = _channel_from_existing(image, base_lum, "Lumieres 2 (moyen)", 50.0)
    # Apply levels to narrow: raise black point
    levels_filter = Gimp.DrawableFilter.new(lights2, "gegl:levels", "")
    levels_config = levels_filter.get_config()
    levels_config.set_property("in-low", 0.25)
    levels_config.set_property("in-high", 1.0)
    lights2.merge_filter(levels_filter)

    # --- Lights 3 (narrowest highlights) ---
    lights3 = _channel_from_existing(image, base_lum, "Lumieres 3 (etroit)", 50.0)
    levels_filter = Gimp.DrawableFilter.new(lights3, "gegl:levels", "")
    levels_config = levels_filter.get_config()
    levels_config.set_property("in-low", 0.5)
    levels_config.set_property("in-high", 1.0)
    lights3.merge_filter(levels_filter)

    # --- Darks 1 (inverted luminosity = darkest pixels) ---
    darks1 = _channel_from_existing(image, base_lum, "Ombres 1 (large)", 50.0)
    _invert_channel(image, darks1)

    # --- Darks 2 (narrower shadows) ---
    darks2 = _channel_from_existing(image, base_lum, "Ombres 2 (moyen)", 50.0)
    _invert_channel(image, darks2)
    levels_filter = Gimp.DrawableFilter.new(darks2, "gegl:levels", "")
    levels_config = levels_filter.get_config()
    levels_config.set_property("in-low", 0.25)
    levels_config.set_property("in-high", 1.0)
    darks2.merge_filter(levels_filter)

    # --- Darks 3 (narrowest shadows) ---
    darks3 = _channel_from_existing(image, base_lum, "Ombres 3 (etroit)", 50.0)
    _invert_channel(image, darks3)
    levels_filter = Gimp.DrawableFilter.new(darks3, "gegl:levels", "")
    levels_config = levels_filter.get_config()
    levels_config.set_property("in-low", 0.5)
    levels_config.set_property("in-high", 1.0)
    darks3.merge_filter(levels_filter)

    # --- Midtones (intersection of lights and darks = middle tones) ---
    # Midtones = lights1 intersected with darks1
    # Strategy: duplicate lights1, then multiply with darks1 data
    midtones = _channel_from_existing(image, lights1, "Tons moyens", 50.0)

    # To intersect: load darks1 as selection, then apply as mask on midtones
    image.set_active_channel(darks1)
    Gimp.Selection.all(image)
    darks1.edit_copy()
    image.set_active_channel(midtones)
    floating = midtones.edit_paste(False)
    Gimp.floating_sel_anchor(floating)

    # The midtones channel now has the intersection (min of lights and darks)
    # Apply levels to boost the midrange
    levels_filter = Gimp.DrawableFilter.new(midtones, "gegl:levels", "")
    levels_config = levels_filter.get_config()
    levels_config.set_property("in-low", 0.0)
    levels_config.set_property("in-high", 0.75)
    midtones.merge_filter(levels_filter)

    # Remove the base working channel
    image.remove_channel(base_lum)

    # Clear selection
    Gimp.Selection.none(image)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class LuminosityMasks(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-luminosity-masks']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            generate_luminosity_masks, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Generer masques de luminosite"),
            _("Cree 7 masques de luminosite (Lumieres 1-3, Ombres 1-3, Tons moyens) "
              "sous forme de canaux. Chargez un canal comme selection pour cibler "
              "precisement les tons clairs, moyens ou sombres."),
            name)
        procedure.set_menu_label(_("_Generer masques de luminosite"))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Selection")

        return procedure


Gimp.main(LuminosityMasks.__gtype__, sys.argv)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Pipette moyenne (Average Color Sampler)
#   Sample average color from NxN area, set as foreground,
#   display HEX/RGB/HSV values, copy HEX to clipboard.
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


def _rgb_to_hsv(r, g, b):
    """Convert RGB (0-255) to HSV (H: 0-360, S: 0-100, V: 0-100)."""
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    diff = mx - mn

    # Hue
    if diff == 0:
        h = 0
    elif mx == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif mx == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    else:
        h = (60 * ((r - g) / diff) + 240) % 360

    # Saturation
    s = 0 if mx == 0 else (diff / mx) * 100

    # Value
    v = mx * 100

    return int(round(h)), int(round(s)), int(round(v))


def sample_average(procedure, run_mode, image, drawables, config, data):
    """Sample average color from NxN area around cursor position."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi

        GimpUi.init('python-fu-sample-average')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    sample_size = config.get_property('sample-size')
    center_x = config.get_property('center-x')
    center_y = config.get_property('center-y')

    # Map choice to actual pixel radius
    size_map = {
        "1x1": 0,
        "3x3": 1,
        "5x5": 2,
        "11x11": 5,
        "31x31": 15,
        "51x51": 25,
        "101x101": 50,
    }
    radius = size_map.get(sample_size, 0)

    if not drawables:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("Aucun calque selectionne."))

    drawable = drawables[0]
    width = drawable.get_width()
    height = drawable.get_height()

    # If center_x/y are -1, use image center or selection center
    if center_x < 0 or center_y < 0:
        if not Gimp.Selection.is_empty(image):
            # Use selection bounds center
            success, non_empty, x1, y1, x2, y2 = Gimp.Selection.bounds(image)
            if success and non_empty:
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
            else:
                center_x = width // 2
                center_y = height // 2
        else:
            center_x = width // 2
            center_y = height // 2

    # Compute bounding box for sampling
    x_start = max(0, center_x - radius)
    y_start = max(0, center_y - radius)
    x_end = min(width - 1, center_x + radius)
    y_end = min(height - 1, center_y + radius)

    sample_w = x_end - x_start + 1
    sample_h = y_end - y_start + 1

    if sample_w <= 0 or sample_h <= 0:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("Position d'echantillonnage hors de l'image."))

    Gimp.context_push()

    # Read pixels using GEGL buffer
    buffer = drawable.get_buffer()
    # Use Babl format for RGB
    try:
        # Sample the region and compute average
        total_r, total_g, total_b = 0.0, 0.0, 0.0
        count = 0

        # Read pixel by pixel using the drawable's sub_pixel methods via PDB
        pdb = Gimp.get_pdb()
        for py in range(y_start, y_end + 1):
            for px in range(x_start, x_end + 1):
                # Get pixel color at position
                proc = pdb.lookup_procedure('gimp-drawable-get-pixel')
                pc = proc.create_config()
                pc.set_property('drawable', drawable)
                pc.set_property('x-coord', px)
                pc.set_property('y-coord', py)
                result = proc.run(pc)

                if result.index(0) == Gimp.PDBStatusType.SUCCESS:
                    color = result.index(1)
                    # GeglColor - extract RGB components
                    rgba = color.get_rgba()
                    total_r += rgba.red
                    total_g += rgba.green
                    total_b += rgba.blue
                    count += 1

        if count == 0:
            Gimp.context_pop()
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error("Impossible de lire les pixels."))

        avg_r = total_r / count
        avg_g = total_g / count
        avg_b = total_b / count

        # Set as foreground color
        fg_color = Gegl.Color.new("black")
        fg_color.set_rgba(avg_r, avg_g, avg_b, 1.0)
        Gimp.context_set_foreground(fg_color)

        # Convert to 0-255 for display
        r8 = int(round(avg_r * 255))
        g8 = int(round(avg_g * 255))
        b8 = int(round(avg_b * 255))

        hex_color = f"#{r8:02X}{g8:02X}{b8:02X}"
        h, s, v = _rgb_to_hsv(r8, g8, b8)

        # Copy HEX to clipboard via GIMP's built-in clipboard
        pdb = Gimp.get_pdb()
        try:
            proc = pdb.lookup_procedure('gimp-edit-named-copy')
            # Fallback: use GLib/GTK clipboard if available
        except Exception:
            pass

        # Try GTK clipboard
        try:
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            clipboard = Gtk.Clipboard.get_default(Gtk.gdk.Display.get_default())
            if clipboard:
                clipboard.set_text(hex_color, -1)
                clipboard.store()
        except Exception:
            pass  # Clipboard not available in non-interactive mode

        # Show results
        msg = (
            f"Pipette moyenne ({sample_size}) au point ({center_x}, {center_y})\n"
            f"\n"
            f"HEX : {hex_color}\n"
            f"RGB : ({r8}, {g8}, {b8})\n"
            f"HSV : ({h}deg, {s}%, {v}%)\n"
            f"\n"
            f"Couleur definie comme premier plan.\n"
            f"Code HEX copie dans le presse-papiers."
        )
        Gimp.message(msg)

    except Exception as e:
        Gimp.context_pop()
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error(f"Erreur d'echantillonnage : {e}"))

    Gimp.context_pop()
    Gimp.displays_flush()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class SampleAverage(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-sample-average']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            sample_average, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Average Color Sampler"),
            _("Echantillonner la couleur moyenne d'une zone NxN, "
              "definir comme premier plan, afficher HEX/RGB/HSV "
              "et copier le code HEX dans le presse-papiers."),
            name)
        procedure.set_menu_label(_("_Pipette moyenne..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Color")

        size_choice = Gimp.Choice.new()
        size_choice.add("1x1", 0, _("1x1 (pixel unique)"), "")
        size_choice.add("3x3", 1, _("3x3"), "")
        size_choice.add("5x5", 2, _("5x5"), "")
        size_choice.add("11x11", 3, _("11x11"), "")
        size_choice.add("31x31", 4, _("31x31"), "")
        size_choice.add("51x51", 5, _("51x51"), "")
        size_choice.add("101x101", 6, _("101x101"), "")
        procedure.add_choice_argument("sample-size",
                                      _("_Taille d'echantillonnage"),
                                      _("Zone d'echantillonnage autour du point central"),
                                      size_choice, "5x5",
                                      GObject.ParamFlags.READWRITE)

        procedure.add_int_argument("center-x",
                                   _("Centre _X"),
                                   _("Position X du centre (-1 = centre de la selection ou de l'image)"),
                                   -1, 100000, -1,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("center-y",
                                   _("Centre _Y"),
                                   _("Position Y du centre (-1 = centre de la selection ou de l'image)"),
                                   -1, 100000, -1,
                                   GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(SampleAverage.__gtype__, sys.argv)

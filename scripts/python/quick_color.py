#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Pipette de couleur rapide
#   Enhanced color info display: shows HEX, RGB, HSV for the
#   current foreground color. Maintains a recent colors list.
#   Copy HEX to clipboard via xclip/xsel.
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GLib
import sys
import os
import json
import subprocess
import colorsys

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

RECENT_COLORS_PATH = os.path.join(
    GLib.get_user_config_dir(), "GIMP", "3.0", "photogimp-recent-colors.json")
MAX_RECENT = 30


def _load_recent_colors():
    """Load recent colors list from config file."""
    if os.path.exists(RECENT_COLORS_PATH):
        try:
            with open(RECENT_COLORS_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_recent_colors(colors):
    """Save recent colors list to config file."""
    os.makedirs(os.path.dirname(RECENT_COLORS_PATH), exist_ok=True)
    try:
        with open(RECENT_COLORS_PATH, 'w') as f:
            json.dump(colors[-MAX_RECENT:], f, indent=2)
    except Exception:
        pass


def _copy_to_clipboard(text):
    """Copy text to system clipboard using xclip or xsel."""
    for cmd in [['xclip', '-selection', 'clipboard'],
                ['xsel', '--clipboard', '--input']]:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            proc.communicate(input=text.encode('utf-8'))
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            continue
    return False


def _rgba_to_hex(r, g, b):
    """Convert float RGB (0-1) to HEX string."""
    return "#{:02X}{:02X}{:02X}".format(
        int(round(r * 255)),
        int(round(g * 255)),
        int(round(b * 255)))


# ---------------------------------------------------------------------------
# Pipette de couleur rapide
# ---------------------------------------------------------------------------
def quick_color(procedure, run_mode, image, drawables, config, data):
    # Get the current foreground color
    fg_color = Gimp.context_get_foreground()

    # Extract RGBA components (float 0-1)
    # In GIMP 3.0, GeglColor provides get_rgba()
    rgba = fg_color.get_rgba()
    r, g, b, a = rgba.red, rgba.green, rgba.blue, rgba.alpha

    # Compute values
    r8 = int(round(r * 255))
    g8 = int(round(g * 255))
    b8 = int(round(b * 255))
    hex_val = _rgba_to_hex(r, g, b)

    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h_deg = int(round(h * 360))
    s_pct = int(round(s * 100))
    v_pct = int(round(v * 100))

    # Add to recent colors
    recent = _load_recent_colors()
    entry = {"hex": hex_val, "rgb": [r8, g8, b8], "hsv": [h_deg, s_pct, v_pct]}
    # Avoid duplicates at the end
    if not recent or recent[-1].get("hex") != hex_val:
        recent.append(entry)
        _save_recent_colors(recent)

    # Copy HEX to clipboard
    copied = _copy_to_clipboard(hex_val)
    clipboard_msg = "Copied to clipboard!" if copied else "(Install xclip or xsel to copy)"

    # Build info message
    lines = [
        "Pipette de couleur rapide",
        "=" * 30,
        "",
        "HEX:  {}  {}".format(hex_val, clipboard_msg),
        "RGB:  {}, {}, {}".format(r8, g8, b8),
        "HSV:  {}deg, {}%, {}%".format(h_deg, s_pct, v_pct),
        "",
        "Recent colors ({} saved):".format(len(recent)),
    ]
    # Show last 8 recent colors
    for c in recent[-8:]:
        lines.append("  {} - RGB({},{},{})".format(
            c["hex"], c["rgb"][0], c["rgb"][1], c["rgb"][2]))

    Gimp.message("\n".join(lines))

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Afficher les couleurs recentes
# ---------------------------------------------------------------------------
def show_recent_colors(procedure, run_mode, image, drawables, config, data):
    recent = _load_recent_colors()

    if not recent:
        Gimp.message("Aucune couleur recente enregistree.\n"
                      "Utilisez 'Pipette de couleur rapide' pour commencer a collecter des couleurs.")
    else:
        lines = [
            "Recent Colors ({} total)".format(len(recent)),
            "=" * 35,
            "",
        ]
        for i, c in enumerate(reversed(recent[-MAX_RECENT:]), 1):
            lines.append("  {:>2}. {} - RGB({},{},{}) - HSV({}deg,{}%,{}%)".format(
                i, c["hex"],
                c["rgb"][0], c["rgb"][1], c["rgb"][2],
                c["hsv"][0], c["hsv"][1], c["hsv"][2]))
        lines.append("")
        lines.append("Stored in: {}".format(RECENT_COLORS_PATH))
        Gimp.message("\n".join(lines))

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Effacer les couleurs recentes
# ---------------------------------------------------------------------------
def clear_recent_colors(procedure, run_mode, image, drawables, config, data):
    _save_recent_colors([])
    Gimp.message("Liste des couleurs recentes effacee.")
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class QuickColor(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-quick-color',
            'python-fu-show-recent-colors',
            'python-fu-clear-recent-colors',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        menu_base = "<Image>/Filters/Color"

        if name == 'python-fu-quick-color':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                quick_color, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Pipette de couleur rapide"),
                _("Show HEX, RGB, HSV of the foreground color, copy HEX to clipboard, "
                  "and add to recent colors list."),
                name)
            procedure.set_menu_label(_("Pipette de couleur _rapide..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-show-recent-colors':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                show_recent_colors, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Afficher les couleurs recentes"),
                _("Afficher la liste des couleurs recemment prelevees."),
                name)
            procedure.set_menu_label(_("Afficher les couleurs _recentes"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-clear-recent-colors':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                clear_recent_colors, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Effacer les couleurs recentes"),
                _("Effacer la liste des couleurs recentes."),
                name)
            procedure.set_menu_label(_("_Effacer les couleurs recentes"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        else:
            return None

        return procedure


Gimp.main(QuickColor.__gtype__, sys.argv)

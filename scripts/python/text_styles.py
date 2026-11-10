#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Styles de texte
#   Save, apply, and manage text style presets (font, size, color,
#   letter-spacing, line-spacing) as JSON files.
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib
import json
import os
import sys

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

STYLES_DIR = os.path.join(GLib.get_user_config_dir(), "GIMP", "3.0", "text-styles")


def _ensure_styles_dir():
    """Create styles directory if it doesn't exist."""
    os.makedirs(STYLES_DIR, exist_ok=True)


def _list_styles():
    """Return list of (name, filepath) for all saved styles."""
    _ensure_styles_dir()
    styles = []
    for fname in sorted(os.listdir(STYLES_DIR)):
        if fname.endswith('.json'):
            name = fname[:-5]
            styles.append((name, os.path.join(STYLES_DIR, fname)))
    return styles


def _read_style(filepath):
    """Read a style JSON file and return the dict."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def _get_text_layer_style(layer):
    """Extract text style properties from a text layer."""
    font = layer.get_font()
    font_name = font.get_name() if font else "Sans"
    size = layer.get_font_size()
    size_val = size.size if hasattr(size, 'size') else size

    # Get color via PDB
    pdb = Gimp.get_pdb()
    color = layer.get_color()

    # Try to get letter and line spacing
    letter_spacing = layer.get_letter_spacing()
    line_spacing = layer.get_line_spacing()

    style = {
        "font": font_name,
        "size": size_val,
        "color": {
            "r": color.r() if hasattr(color, 'r') else 0.0,
            "g": color.g() if hasattr(color, 'g') else 0.0,
            "b": color.b() if hasattr(color, 'b') else 0.0,
        },
        "letter_spacing": letter_spacing,
        "line_spacing": line_spacing,
    }
    return style


def _apply_style_to_layer(layer, style):
    """Apply a style dict to a text layer."""
    pdb = Gimp.get_pdb()

    # Font
    if "font" in style:
        font = Gimp.Font.get_by_name(style["font"])
        if font:
            layer.set_font(font)

    # Size
    if "size" in style:
        layer.set_font_size(style["size"], Gimp.Unit.px())

    # Color
    if "color" in style:
        c = style["color"]
        color = Gimp.RGB()
        color.set(c.get("r", 0.0), c.get("g", 0.0), c.get("b", 0.0))
        layer.set_color(color)

    # Letter spacing
    if "letter_spacing" in style:
        layer.set_letter_spacing(style["letter_spacing"])

    # Line spacing
    if "line_spacing" in style:
        layer.set_line_spacing(style["line_spacing"])


# ---------------------------------------------------------------------------
#  Save Text Style
# ---------------------------------------------------------------------------
def save_text_style(procedure, run_mode, image, drawables, config, data):
    """Save current text layer's style as a named preset."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-save-text-style')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    style_name = config.get_property('style-name')
    if not style_name or not style_name.strip():
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR,
            GLib.Error("Veuillez saisir un nom de style."))

    # Find the first text layer among selected drawables
    text_layer = None
    for d in drawables:
        if d.is_text_layer():
            text_layer = d
            break

    if text_layer is None:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("Veuillez selectionner un calque texte."))

    style = _get_text_layer_style(text_layer)
    _ensure_styles_dir()

    safe_name = "".join(c if c.isalnum() or c in '-_ ' else '_' for c in style_name.strip())
    filepath = os.path.join(STYLES_DIR, f"{safe_name}.json")

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(style, f, indent=2, ensure_ascii=False)

    Gimp.message(f"Style '{style_name}' enregistre dans {filepath}")
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Apply Text Style
# ---------------------------------------------------------------------------
def apply_text_style(procedure, run_mode, image, drawables, config, data):
    """Apply a saved text style to the current text layer."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-apply-text-style')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    style_name = config.get_property('style-name')
    styles = _list_styles()

    if not styles:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("Aucun style enregistre. Utilisez 'Enregistrer style de texte' d'abord."))

    # Find the matching style
    style_path = None
    for name, path in styles:
        if name == style_name:
            style_path = path
            break

    if style_path is None:
        available = ", ".join(n for n, _ in styles)
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error(f"Style '{style_name}' introuvable. Styles disponibles : {available}"))

    style = _read_style(style_path)

    text_layer = None
    for d in drawables:
        if d.is_text_layer():
            text_layer = d
            break

    if text_layer is None:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("Veuillez selectionner un calque texte."))

    Gimp.context_push()
    image.undo_group_start()

    _apply_style_to_layer(text_layer, style)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    Gimp.message(f"Style '{style_name}' applique.")
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
#  Manage Text Styles
# ---------------------------------------------------------------------------
def manage_text_styles(procedure, run_mode, image, drawables, config, data):
    """List and optionally delete saved text styles."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-manage-text-styles')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    delete_name = config.get_property('delete-style')
    styles = _list_styles()

    if not styles:
        Gimp.message("Aucun style de texte enregistre.")
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    # If a delete name is specified, delete it
    if delete_name and delete_name.strip():
        deleted = False
        for name, path in styles:
            if name == delete_name.strip():
                os.remove(path)
                Gimp.message(f"Style '{name}' supprime.")
                deleted = True
                break
        if not deleted:
            Gimp.message(f"Style '{delete_name}' introuvable.")
    else:
        # Just list all styles
        lines = ["Styles de texte enregistres :\n"]
        for name, path in styles:
            try:
                style = _read_style(path)
                lines.append(
                    f"  - {name} : {style.get('font', '?')}, "
                    f"{style.get('size', '?')}px, "
                    f"espacement lettres={style.get('letter_spacing', 0)}, "
                    f"espacement lignes={style.get('line_spacing', 0)}")
            except Exception:
                lines.append(f"  - {name} : (erreur de lecture)")
        Gimp.message("\n".join(lines))

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class TextStyles(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-save-text-style',
            'python-fu-apply-text-style',
            'python-fu-manage-text-styles',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-save-text-style':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                save_text_style, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Save Text Style Preset"),
                _("Lire les proprietes du calque texte actif (police, taille, couleur, "
                  "espacement) et les enregistrer comme preset JSON."),
                name)
            procedure.set_menu_label(_("_Enregistrer style de texte"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Typography")

            procedure.add_string_argument("style-name",
                                          _("_Nom du style"),
                                          _("Nom pour identifier ce style de texte"),
                                          "Mon style",
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-apply-text-style':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                apply_text_style, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Apply Text Style Preset"),
                _("Appliquer un style de texte enregistre au calque texte actif."),
                name)
            procedure.set_menu_label(_("_Appliquer style de texte..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Typography")

            procedure.add_string_argument("style-name",
                                          _("_Nom du style"),
                                          _("Nom du style a appliquer"),
                                          "",
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-manage-text-styles':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                manage_text_styles, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Manage Text Styles"),
                _("Lister et supprimer les styles de texte enregistres."),
                name)
            procedure.set_menu_label(_("_Gerer les styles de texte"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Typography")

            procedure.add_string_argument("delete-style",
                                          _("_Supprimer le style"),
                                          _("Nom du style a supprimer (laisser vide pour lister)"),
                                          "",
                                          GObject.ParamFlags.READWRITE)
        else:
            return None

        return procedure


Gimp.main(TextStyles.__gtype__, sys.argv)

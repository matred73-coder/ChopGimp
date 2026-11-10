#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Raccourcis clavier
#   Creates a reference image with all PhotoGIMP Pro custom shortcuts,
#   organized by category with color-coded sections.
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


# ---------------------------------------------------------------------------
# Shortcut data — PhotoGIMP Pro mappings
# Each section: (title, bg_color_rgba, [(key, action), ...])
# ---------------------------------------------------------------------------
SHORTCUT_SECTIONS = [
    ("Tools", (0.18, 0.35, 0.58, 1.0), [
        ("V", "Move Tool"),
        ("M", "Rectangular Select"),
        ("L", "Free Select (Lasso)"),
        ("W", "Fuzzy Select (Magic Wand)"),
        ("C", "Crop Tool"),
        ("I", "Color Picker (Eyedropper)"),
        ("B", "Paintbrush"),
        ("E", "Eraser"),
        ("G", "Gradient / Bucket Fill"),
        ("S", "Clone / Stamp"),
        ("T", "Text Tool"),
        ("O", "Measure Tool"),
        ("Z", "Zoom"),
        ("Space", "Pan / Hand Tool"),
    ]),
    ("File", (0.22, 0.50, 0.22, 1.0), [
        ("Ctrl+N", "New Image"),
        ("Ctrl+O", "Open"),
        ("Ctrl+S", "Save (XCF)"),
        ("Ctrl+Shift+S", "Save As"),
        ("Ctrl+Shift+E", "Export As"),
        ("Ctrl+Alt+E", "Overwrite Export"),
        ("Ctrl+W", "Close Image"),
        ("Ctrl+Q", "Quit"),
    ]),
    ("Edit", (0.55, 0.27, 0.07, 1.0), [
        ("Ctrl+Z", "Undo"),
        ("Ctrl+Y", "Redo"),
        ("Ctrl+X", "Cut"),
        ("Ctrl+C", "Copy"),
        ("Ctrl+V", "Paste"),
        ("Ctrl+Shift+V", "Paste as New Image"),
        ("Delete", "Clear Selection"),
        ("Ctrl+Shift+C", "Copy Visible"),
    ]),
    ("Selection", (0.50, 0.20, 0.50, 1.0), [
        ("Ctrl+A", "Select All"),
        ("Ctrl+D", "Select None"),
        ("Ctrl+Shift+A", "Invert Selection"),
        ("Ctrl+Shift+L", "Select by Color"),
        ("Q", "Toggle Quick Mask"),
        ("Shift+Click", "Add to Selection"),
        ("Ctrl+Click", "Soustraction from Selection"),
    ]),
    ("Layers", (0.50, 0.50, 0.15, 1.0), [
        ("Ctrl+Shift+N", "New Layer"),
        ("Ctrl+J", "Duplicate Layer"),
        ("Ctrl+Shift+J", "Layer from Selection"),
        ("Ctrl+E", "Merge Down"),
        ("Ctrl+Shift+E", "Flatten Image"),
        ("PgUp / PgDn", "Select Layer Above/Below"),
        ("Ctrl+[", "Lower Layer"),
        ("Ctrl+]", "Raise Layer"),
    ]),
    ("View", (0.15, 0.45, 0.45, 1.0), [
        ("Ctrl+Shift+J", "Fit Image in Window"),
        ("Ctrl+Shift+E", "Fit Image in Window"),
        ("+ / -", "Zoom In / Out"),
        ("1 / 2 / 3", "Zoom 100% / 50% / 25%"),
        ("Ctrl+Shift+R", "Toggle Rulers"),
        ("Ctrl+'", "Toggle Grid"),
        ("Ctrl+T", "Show/Hide Guides"),
        ("Tab", "Toggle Docks"),
        ("F11", "Fullscreen"),
    ]),
    ("Filters & Effects", (0.45, 0.15, 0.15, 1.0), [
        ("Ctrl+Shift+U", "Desaturate"),
        ("Ctrl+L", "Levels"),
        ("Ctrl+M", "Curves"),
        ("Ctrl+B", "Color Balance"),
        ("Ctrl+U", "Hue/Saturation"),
        ("Ctrl+F", "Repeat Last Filter"),
        ("Ctrl+Shift+F", "Re-show Last Filter"),
    ]),
]


def _draw_text_layer(image, text, font_size, x, y, color, bold=False):
    """Create a text layer at position (x, y) with given color."""
    # Create text layer
    text_layer = Gimp.TextLayer.new(image, text, font_size, Gimp.Unit.pixel())
    image.insert_layer(text_layer, None, -1)
    text_layer.set_offsets(x, y)

    # Set text color
    Gimp.context_set_foreground(color)

    return text_layer


def shortcut_overlay(procedure, run_mode, image_arg, drawables, config, data):
    """Create a new image with the formatted shortcut reference."""
    Gimp.context_push()

    # Image dimensions
    img_width = 1200
    col_width = 580
    section_padding = 15
    line_height = 22
    header_height = 35
    margin_top = 60
    margin_left = 30

    # Calculate required height
    total_lines = 0
    max_col_lines = [0, 0]  # track lines per column
    col_idx = 0
    col_lines = 0
    for title, color, shortcuts in SHORTCUT_SECTIONS:
        needed = 2 + len(shortcuts) + 1  # header + items + spacing
        col_lines += needed
        if col_lines > max_col_lines[col_idx]:
            max_col_lines[col_idx] = col_lines
        total_lines += needed
        # Switch to second column after ~half the sections
        if col_idx == 0 and total_lines > len(SHORTCUT_SECTIONS) * 5 // 2:
            col_idx = 1
            col_lines = 0

    img_height = max(max_col_lines[0], max_col_lines[1] + 5) * line_height + margin_top + 100
    img_height = max(img_height, 900)

    # Create image
    image = Gimp.Image.new(img_width, img_height, Gimp.ImageBaseType.RGB)
    image.undo_group_start()

    # Background layer
    bg_layer = Gimp.Layer.new(image, "Background",
                               img_width, img_height,
                               Gimp.ImageType.RGB_IMAGE,
                               100.0, Gimp.LayerMode.NORMAL)
    image.insert_layer(bg_layer, None, -1)

    # Fill with dark background
    bg_color = Gegl.Color.new("black")
    bg_color.set_rgba(0.12, 0.12, 0.14, 1.0)
    Gimp.context_set_foreground(bg_color)
    bg_layer.edit_fill(Gimp.FillType.FOREGROUND)

    # Title text
    title_color = Gegl.Color.new("white")
    title_color.set_rgba(0.95, 0.95, 0.95, 1.0)
    title_layer = Gimp.TextLayer.new(image,
                                      "PhotoGIMP Pro - Raccourcis clavier Reference",
                                      28, Gimp.Unit.pixel())
    image.insert_layer(title_layer, None, -1)
    title_layer.set_offsets(margin_left, 15)
    Gimp.context_set_foreground(title_color)

    # Render sections in two columns
    x = margin_left
    y = margin_top
    col_count = 0
    sections_per_col = (len(SHORTCUT_SECTIONS) + 1) // 2

    white = Gegl.Color.new("white")
    white.set_rgba(0.92, 0.92, 0.92, 1.0)
    key_color = Gegl.Color.new("black")
    key_color.set_rgba(1.0, 0.85, 0.40, 1.0)  # gold for keys

    for sec_idx, (title, bg_rgba, shortcuts) in enumerate(SHORTCUT_SECTIONS):
        if sec_idx == sections_per_col:
            # Move to second column
            x = margin_left + col_width + 20
            y = margin_top

        # Section header background
        sec_bg = Gimp.Layer.new(image, "sec_bg_" + title,
                                 col_width - 10, header_height,
                                 Gimp.ImageType.RGBA_IMAGE,
                                 85.0, Gimp.LayerMode.NORMAL)
        sec_bg.fill(Gimp.FillType.TRANSPARENT)
        image.insert_layer(sec_bg, None, -1)
        sec_bg.set_offsets(x, y)
        sec_color = Gegl.Color.new("black")
        sec_color.set_rgba(bg_rgba[0], bg_rgba[1], bg_rgba[2], bg_rgba[3])
        Gimp.context_set_foreground(sec_color)
        sec_bg.edit_fill(Gimp.FillType.FOREGROUND)

        # Section title text
        sec_title = Gimp.TextLayer.new(image, title, 18, Gimp.Unit.pixel())
        image.insert_layer(sec_title, None, -1)
        sec_title.set_offsets(x + 10, y + 8)

        y += header_height + 5

        # Shortcut entries
        for key, action in shortcuts:
            # Key label
            entry_text = "{:<22s} {}".format(key, action)
            entry_layer = Gimp.TextLayer.new(image, entry_text, 14, Gimp.Unit.pixel())
            image.insert_layer(entry_layer, None, -1)
            entry_layer.set_offsets(x + 15, y)
            y += line_height

        y += section_padding

    # Footer
    footer_color = Gegl.Color.new("black")
    footer_color.set_rgba(0.5, 0.5, 0.5, 1.0)
    footer = Gimp.TextLayer.new(image,
                                 "PhotoGIMP Pro | Gardez cette image ouverte comme reference ou imprimez-la.",
                                 12, Gimp.Unit.pixel())
    image.insert_layer(footer, None, -1)
    footer.set_offsets(margin_left, img_height - 30)

    image.undo_group_end()

    # Display the new image
    Gimp.Display.new(image)
    Gimp.displays_flush()

    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class ShortcutOverlay(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-shortcut-overlay']

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-shortcut-overlay':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                shortcut_overlay, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Raccourcis clavier"),
                _("Creer une image de reference visuelle de tous les raccourcis clavier PhotoGIMP Pro, "
                  "organisee par categorie avec des sections codees par couleur."),
                name)
            procedure.set_menu_label(_("_Raccourcis clavier..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Help")

        else:
            return None

        return procedure


Gimp.main(ShortcutOverlay.__gtype__, sys.argv)

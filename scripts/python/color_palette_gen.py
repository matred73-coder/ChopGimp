#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#   PhotoGIMP Pro — Color Palette Generator
#   Generate palettes from image or color theory
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import GObject, GLib, Gegl
import sys, os, math, random, colorsys


def sample_image_colors(image, drawable, num_colors=8):
    """Sample dominant colors from image by random sampling + grouping."""
    w = drawable.get_width()
    h = drawable.get_height()
    samples = []
    for _ in range(min(2000, w * h)):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        c = drawable.get_pixel(x, y)
        if c is not None:
            pixel = c.get_pixel()
            r = int(pixel.get_value(0) * 255) if pixel.get_format().get_bytes_per_pixel() > 0 else 0
            g = int(pixel.get_value(1) * 255) if pixel.get_format().get_bytes_per_pixel() > 1 else 0
            b = int(pixel.get_value(2) * 255) if pixel.get_format().get_bytes_per_pixel() > 2 else 0
            samples.append((r, g, b))

    if not samples:
        return [(128, 128, 128)] * num_colors

    # Simple k-means-like clustering
    centers = [samples[i * len(samples) // num_colors] for i in range(num_colors)]
    for _ in range(10):
        clusters = [[] for _ in range(num_colors)]
        for s in samples:
            dists = [sum((a - b) ** 2 for a, b in zip(s, c)) for c in centers]
            clusters[dists.index(min(dists))].append(s)
        for i, cluster in enumerate(clusters):
            if cluster:
                centers[i] = tuple(sum(c[j] for c in cluster) // len(cluster) for j in range(3))
    return centers


def hue_to_rgb(h, s=0.7, v=0.85):
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def generate_harmony(base_hue, harmony_type):
    """Generate color harmony from base hue."""
    colors = []
    if harmony_type == 0:  # Complementary
        colors = [base_hue, (base_hue + 180) % 360]
    elif harmony_type == 1:  # Analogous
        colors = [(base_hue - 30) % 360, base_hue, (base_hue + 30) % 360]
    elif harmony_type == 2:  # Triadic
        colors = [base_hue, (base_hue + 120) % 360, (base_hue + 240) % 360]
    elif harmony_type == 3:  # Split Complementary
        colors = [base_hue, (base_hue + 150) % 360, (base_hue + 210) % 360]
    elif harmony_type == 4:  # Tetradic
        colors = [base_hue, (base_hue + 90) % 360, (base_hue + 180) % 360, (base_hue + 270) % 360]

    result = []
    for h in colors:
        for s in [0.3, 0.6, 0.9]:
            for v in [0.5, 0.75, 1.0]:
                result.append(hue_to_rgb(h, s, v))
    return result


def save_palette(name, colors, path):
    """Save a .gpl palette file."""
    with open(path, 'w') as f:
        f.write("GIMP Palette\n")
        f.write(f"Name: {name}\n")
        f.write("Columns: 8\n#\n")
        for i, (r, g, b) in enumerate(colors):
            f.write(f"{r:3d} {g:3d} {b:3d}\tColor {i + 1}\n")


def palette_from_image(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("color_palette_gen")
        dialog = GimpUi.ProcedureDialog.new(procedure, config, "Palette from Image")
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    num_colors = int(config.get_property("num-colors"))
    palette_name = config.get_property("palette-name")
    if not palette_name:
        palette_name = "Image Palette"

    Gimp.context_push()
    image.undo_group_start()

    drawable = drawables[0] if drawables else image.get_active_drawable()
    colors = sample_image_colors(image, drawable, num_colors)

    pal_dir = os.path.expanduser("~/.config/GIMP/3.0/palettes")
    os.makedirs(pal_dir, exist_ok=True)
    safe_name = palette_name.replace(" ", "-").replace("/", "_")
    save_palette(palette_name, colors, os.path.join(pal_dir, f"{safe_name}.gpl"))
    # Also for 3.2
    pal_dir2 = os.path.expanduser("~/.config/GIMP/3.2/palettes")
    os.makedirs(pal_dir2, exist_ok=True)
    save_palette(palette_name, colors, os.path.join(pal_dir2, f"{safe_name}.gpl"))

    Gimp.context_refresh()
    image.undo_group_end()
    Gimp.context_pop()
    Gimp.message(f"Palette '{palette_name}' saved with {len(colors)} colors.\nRefresh palettes to see it.")
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def palette_harmony(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("color_palette_gen")
        dialog = GimpUi.ProcedureDialog.new(procedure, config, "Color Harmony")
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    base_hue = int(config.get_property("base-hue"))
    harmony = int(config.get_property("harmony-type"))
    palette_name = config.get_property("harmony-name")
    if not palette_name:
        palette_name = "Harmony Palette"

    colors = generate_harmony(base_hue, harmony)

    pal_dir = os.path.expanduser("~/.config/GIMP/3.0/palettes")
    os.makedirs(pal_dir, exist_ok=True)
    safe_name = palette_name.replace(" ", "-")
    save_palette(palette_name, colors, os.path.join(pal_dir, f"{safe_name}.gpl"))
    pal_dir2 = os.path.expanduser("~/.config/GIMP/3.2/palettes")
    os.makedirs(pal_dir2, exist_ok=True)
    save_palette(palette_name, colors, os.path.join(pal_dir2, f"{safe_name}.gpl"))

    Gimp.message(f"Harmony palette '{palette_name}' saved with {len(colors)} colors.")
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ColorPaletteGen(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["photogimp-palette-from-image", "photogimp-palette-harmony"]

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        if name == "photogimp-palette-from-image":
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, palette_from_image, None)
            procedure.set_menu_label("Palette depuis l'image...")
            procedure.add_menu_path("<Image>/Filters/Color/")
            procedure.set_documentation("Extract palette from image", "Samples dominant colors", name)
            procedure.set_attribution("PhotoGIMP Pro", "PhotoGIMP Pro", "2026")
            procedure.add_int_argument("num-colors", "Couleurs", "Number of colors to extract", 2, 32, 8, GObject.ParamFlags.READWRITE)
            procedure.add_string_argument("palette-name", "Nom", "Palette name", "Image Palette", GObject.ParamFlags.READWRITE)
            return procedure

        elif name == "photogimp-palette-harmony":
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, palette_harmony, None)
            procedure.set_menu_label("Harmonie des couleurs...")
            procedure.add_menu_path("<Image>/Filters/Color/")
            procedure.set_documentation("Generate harmony palette", "Create palette from color theory", name)
            procedure.set_attribution("PhotoGIMP Pro", "PhotoGIMP Pro", "2026")
            procedure.add_int_argument("base-hue", "Teinte de base", "Base hue (0-360)", 0, 360, 200, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("harmony-type", "Harmonie", "0=Complementary 1=Analogous 2=Triadic 3=Split 4=Tetradic", 0, 4, 0, GObject.ParamFlags.READWRITE)
            procedure.add_string_argument("harmony-name", "Nom", "Palette name", "Harmony Palette", GObject.ParamFlags.READWRITE)
            return procedure

Gimp.main(ColorPaletteGen.__gtype__, sys.argv)

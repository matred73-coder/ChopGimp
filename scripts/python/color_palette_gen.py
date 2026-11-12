#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#   PhotoGIMP Pro — Générateur de palettes
#   Palettes à partir de l'image ou de la théorie des couleurs
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import GObject, GLib, Gegl
import sys, random, colorsys


def _to_srgb8(v):
    """Composante linéaire (0-1) -> sRGB 8 bits."""
    v = max(0.0, min(1.0, v))
    v = v * 12.92 if v <= 0.0031308 else 1.055 * (v ** (1.0 / 2.4)) - 0.055
    return int(round(v * 255))


def sample_image_colors(drawable, num_colors=8, samples_count=1500):
    """Couleurs dominantes : échantillonnage aléatoire + k-moyennes (sRGB 8 bits)."""
    w = drawable.get_width()
    h = drawable.get_height()
    rng = random.Random(0)
    samples = []
    for _i in range(min(samples_count, w * h)):
        c = drawable.get_pixel(rng.randrange(w), rng.randrange(h))
        if c is None:
            continue
        r, g, b, a = c.get_rgba()
        if a < 0.5:
            continue   # ignorer les zones transparentes
        samples.append((_to_srgb8(r), _to_srgb8(g), _to_srgb8(b)))

    if not samples:
        return [(128, 128, 128)] * num_colors

    # Centres initiaux répartis sur les échantillons triés par luminosité
    ordered = sorted(samples, key=lambda s: 0.299 * s[0] + 0.587 * s[1] + 0.114 * s[2])
    centers = [ordered[(2 * i + 1) * len(ordered) // (2 * num_colors)] for i in range(num_colors)]
    for _i in range(10):
        clusters = [[] for _j in range(num_colors)]
        for s in samples:
            dists = [sum((a - b) ** 2 for a, b in zip(s, c)) for c in centers]
            clusters[dists.index(min(dists))].append(s)
        for i, cluster in enumerate(clusters):
            if cluster:
                centers[i] = tuple(sum(c[j] for c in cluster) // len(cluster) for j in range(3))
    # Couleurs uniques, de la plus sombre à la plus claire
    unique = sorted(set(centers), key=lambda s: 0.299 * s[0] + 0.587 * s[1] + 0.114 * s[2])
    return unique


def hue_to_rgb(h, s=0.7, v=0.85):
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, s, v)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def generate_harmony(base_hue, harmony_type):
    """Palette d'harmonie à partir d'une teinte de base."""
    colors = []
    if harmony_type == 0:  # Complémentaire
        colors = [base_hue, (base_hue + 180) % 360]
    elif harmony_type == 1:  # Analogue
        colors = [(base_hue - 30) % 360, base_hue, (base_hue + 30) % 360]
    elif harmony_type == 2:  # Triadique
        colors = [base_hue, (base_hue + 120) % 360, (base_hue + 240) % 360]
    elif harmony_type == 3:  # Complémentaire adjacente
        colors = [base_hue, (base_hue + 150) % 360, (base_hue + 210) % 360]
    elif harmony_type == 4:  # Tétradique
        colors = [base_hue, (base_hue + 90) % 360, (base_hue + 180) % 360, (base_hue + 270) % 360]

    result = []
    for h in colors:
        for s in [0.3, 0.6, 0.9]:
            for v in [0.5, 0.75, 1.0]:
                result.append(hue_to_rgb(h, s, v))
    return result


def create_palette(name, colors, columns=8):
    """Crée la palette dans GIMP (dossier palettes de l'utilisateur) et l'active."""
    palette = Gimp.Palette.new(name)
    palette.set_columns(columns)
    for r, g, b in colors:
        palette.add_entry("#%02x%02x%02x" % (r, g, b),
                          Gegl.Color.new("#%02x%02x%02x" % (r, g, b)))
    Gimp.context_set_palette(palette)
    return palette


def _dialog(procedure, config, title):
    GimpUi.init("color_palette_gen")
    dialog = GimpUi.ProcedureDialog.new(procedure, config, title)
    dialog.fill(None)
    ok = dialog.run()
    dialog.destroy()
    return ok


def palette_from_image(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and \
            not _dialog(procedure, config, "Palette depuis l'image"):
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())

    num_colors = int(config.get_property("num-colors"))
    palette_name = config.get_property("palette-name") or "Palette de l'image"

    if drawables:
        drawable = drawables[0]
    else:
        layers = image.get_layers()
        if not layers:
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error.new_literal(GLib.quark_from_string("photogimp"),
                                       "L'image ne contient aucun calque.", 0))
        drawable = layers[0]

    colors = sample_image_colors(drawable, num_colors)
    palette = create_palette(palette_name, colors)

    Gimp.message("Palette « %s » créée avec %d couleurs (fenêtre Palettes)."
                 % (palette.get_name(), len(colors)))
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def palette_harmony(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and \
            not _dialog(procedure, config, "Harmonie des couleurs"):
        return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())

    base_hue = int(config.get_property("base-hue"))
    harmony = int(config.get_property("harmony-type"))
    palette_name = config.get_property("harmony-name") or "Palette harmonie"

    colors = generate_harmony(base_hue, harmony)
    palette = create_palette(palette_name, colors, columns=9)

    Gimp.message("Palette d'harmonie « %s » créée avec %d couleurs (fenêtre Palettes)."
                 % (palette.get_name(), len(colors)))
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ColorPaletteGen(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["photogimp-palette-from-image", "photogimp-palette-harmony"]

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        if name == "photogimp-palette-from-image":
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, palette_from_image, None)
            procedure.set_menu_label("Palette depuis l'image…")
            procedure.add_menu_path("<Image>/Colors/Info")
            procedure.set_image_types("*")
            procedure.set_documentation("Palette depuis l'image",
                                        "Crée une palette avec les couleurs dominantes du calque actif",
                                        name)
            procedure.set_attribution("PhotoGIMP Pro", "PhotoGIMP Pro", "2026")
            procedure.add_int_argument("num-colors", "Couleurs", "Nombre de couleurs à extraire", 2, 32, 8, GObject.ParamFlags.READWRITE)
            procedure.add_string_argument("palette-name", "Nom", "Nom de la palette", "Palette de l'image", GObject.ParamFlags.READWRITE)
            return procedure

        elif name == "photogimp-palette-harmony":
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, palette_harmony, None)
            procedure.set_menu_label("Harmonie des couleurs…")
            procedure.add_menu_path("<Image>/Colors/Info")
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation("Harmonie des couleurs",
                                        "Crée une palette selon la théorie des couleurs",
                                        name)
            procedure.set_attribution("PhotoGIMP Pro", "PhotoGIMP Pro", "2026")
            procedure.add_int_argument("base-hue", "Teinte de base", "Teinte de base (0-360°)", 0, 360, 200, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("harmony-type", "Harmonie",
                                       "0 = complémentaire, 1 = analogue, 2 = triadique, "
                                       "3 = complémentaire adjacente, 4 = tétradique", 0, 4, 0, GObject.ParamFlags.READWRITE)
            procedure.add_string_argument("harmony-name", "Nom", "Nom de la palette", "Palette harmonie", GObject.ParamFlags.READWRITE)
            return procedure

Gimp.main(ColorPaletteGen.__gtype__, sys.argv)

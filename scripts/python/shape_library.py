#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Bibliotheque de formes (Shape Library)
#   Custom shape library with hardcoded SVG path data for common shapes.
#   Creates GIMP vector paths scaled to desired size.
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
import re

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


# ---------------------------------------------------------------------------
#  SVG Path Data for each shape (normalized to ~100x100 viewBox)
#  Format: list of (command, points) tuples parsed from SVG "d" attribute
# ---------------------------------------------------------------------------

# Raw SVG path "d" strings, viewBox 0 0 100 100
SHAPES = {
    "heart": "M50,30 C50,20 40,0 20,0 C0,0 0,20 0,35 C0,55 20,65 50,100 C80,65 100,55 100,35 C100,20 100,0 80,0 C60,0 50,20 50,30 Z",
    "cloud": "M25,60 C10,60 0,50 0,40 C0,28 12,20 25,20 C28,8 42,0 55,0 C70,0 82,10 85,25 C95,25 100,35 100,45 C100,55 92,60 80,60 Z",
    "speech_bubble": "M10,5 L90,5 C95,5 95,10 95,10 L95,55 C95,60 90,60 90,60 L55,60 L40,80 L45,60 L10,60 C5,60 5,55 5,55 L5,10 C5,5 10,5 10,5 Z",
    "checkmark": "M15,55 L35,75 L85,25 L78,18 L35,61 L22,48 Z",
    "cross": "M20,10 L50,40 L80,10 L90,20 L60,50 L90,80 L80,90 L50,60 L20,90 L10,80 L40,50 L10,20 Z",
    "music_note": "M70,5 L70,70 C70,85 55,90 45,85 C35,80 35,65 45,60 C55,55 65,58 70,65 L70,25 L90,20 L90,5 Z",
    "lightning": "M55,0 L25,45 L45,45 L35,100 L80,40 L55,40 Z",
    "gear": "M43,2 L57,2 L60,15 L70,20 L82,12 L90,22 L78,32 L80,42 L95,45 L95,58 L80,60 L78,70 L90,80 L82,90 L70,82 L60,85 L57,98 L43,98 L40,85 L30,82 L18,90 L10,80 L22,70 L20,60 L5,58 L5,45 L20,42 L22,32 L10,22 L18,12 L30,20 L40,15 Z",
    "house": "M50,5 L95,45 L80,45 L80,95 L60,95 L60,60 L40,60 L40,95 L20,95 L20,45 L5,45 Z",
    "phone": "M30,5 L70,5 C75,5 75,10 75,10 L75,90 C75,95 70,95 70,95 L30,95 C25,95 25,90 25,90 L25,10 C25,5 30,5 30,5 Z M45,88 L55,88 C57,88 57,85 55,85 L45,85 C43,85 43,88 45,88 Z",
    "email": "M5,20 L50,55 L95,20 L95,80 L5,80 Z M5,20 L5,80 M95,20 L95,80",
    "wifi": "M50,85 C55,85 55,75 50,75 C45,75 45,85 50,85 Z M30,65 C35,55 45,50 50,50 C55,50 65,55 70,65 M15,50 C22,35 35,25 50,25 C65,25 78,35 85,50 M2,38 C12,18 28,5 50,5 C72,5 88,18 98,38",
    "lock": "M25,45 L25,30 C25,15 35,5 50,5 C65,5 75,15 75,30 L75,45 L80,45 L80,95 L20,95 L20,45 Z M45,65 L45,80 L55,80 L55,65 C60,62 62,58 60,53 C57,48 53,47 50,47 C47,47 43,48 40,53 C38,58 40,62 45,65 Z",
    "camera": "M15,30 L35,30 L40,20 L60,20 L65,30 L85,30 C90,30 95,35 95,40 L95,80 C95,85 90,90 85,90 L15,90 C10,90 5,85 5,80 L5,40 C5,35 10,30 15,30 Z M50,40 C35,40 25,50 25,62 C25,74 35,84 50,84 C65,84 75,74 75,62 C75,50 65,40 50,40 Z M50,48 C60,48 67,55 67,62 C67,69 60,76 50,76 C40,76 33,69 33,62 C33,55 40,48 50,48 Z",
    "play": "M20,10 L85,50 L20,90 Z",
    "pause": "M20,10 L40,10 L40,90 L20,90 Z M60,10 L80,10 L80,90 L60,90 Z",
    "stop": "M15,15 L85,15 L85,85 L15,85 Z",
    "forward": "M5,10 L50,50 L5,90 Z M50,10 L95,50 L50,90 Z",
    "backward": "M50,10 L5,50 L50,90 Z M95,10 L50,50 L95,90 Z",
    "arrow_up": "M50,5 L85,45 L65,45 L65,95 L35,95 L35,45 L15,45 Z",
    "arrow_down": "M50,95 L85,55 L65,55 L65,5 L35,5 L35,55 L15,55 Z",
    "arrow_left": "M5,50 L45,15 L45,35 L95,35 L95,65 L45,65 L45,85 Z",
    "arrow_right": "M95,50 L55,15 L55,35 L5,35 L5,65 L55,65 L55,85 Z",
    "plus": "M35,5 L65,5 L65,35 L95,35 L95,65 L65,65 L65,95 L35,95 L35,65 L5,65 L5,35 L35,35 Z",
    "minus": "M5,35 L95,35 L95,65 L5,65 Z",
    "star_5": "M50,5 L61,38 L97,38 L68,58 L79,92 L50,72 L21,92 L32,58 L3,38 L39,38 Z",
    "star_6": "M50,5 L62,30 L93,15 L78,42 L100,58 L70,58 L50,95 L30,58 L0,58 L22,42 L7,15 L38,30 Z",
    "hexagon": "M50,3 L93,27 L93,73 L50,97 L7,73 L7,27 Z",
    "octagon": "M30,3 L70,3 L97,30 L97,70 L70,97 L30,97 L3,70 L3,30 Z",
    "diamond": "M50,2 L98,50 L50,98 L2,50 Z",
    "triangle": "M50,5 L95,90 L5,90 Z",
}

SHAPE_LABELS = {
    "heart": "Coeur",
    "cloud": "Nuage",
    "speech_bubble": "Bulle de dialogue",
    "checkmark": "Coche",
    "cross": "Croix",
    "music_note": "Note de musique",
    "lightning": "Eclair",
    "gear": "Engrenage",
    "house": "Maison",
    "phone": "Telephone",
    "email": "Email",
    "wifi": "WiFi",
    "lock": "Cadenas",
    "camera": "Appareil photo",
    "play": "Lecture",
    "pause": "Pause",
    "stop": "Arret",
    "forward": "Avance",
    "backward": "Retour",
    "arrow_up": "Fleche haut",
    "arrow_down": "Fleche bas",
    "arrow_left": "Fleche gauche",
    "arrow_right": "Fleche droite",
    "plus": "Plus",
    "minus": "Moins",
    "star_5": "Etoile 5 branches",
    "star_6": "Etoile 6 branches",
    "hexagon": "Hexagone",
    "octagon": "Octogone",
    "diamond": "Losange",
    "triangle": "Triangle",
}


def _parse_svg_path(d_string):
    """Parse an SVG path 'd' attribute into a list of (command, [args...]) tuples."""
    # Tokenize: split on command letters, keeping the letter
    tokens = re.findall(r'[MmLlCcSsQqTtAaHhVvZz][^MmLlCcSsQqTtAaHhVvZz]*', d_string)
    commands = []
    for token in tokens:
        cmd = token[0]
        # Extract numbers (supports negative and decimal)
        nums = [float(n) for n in re.findall(r'-?[\d.]+', token[1:])]
        commands.append((cmd, nums))
    return commands


def _svg_path_to_bezier_points(commands, target_w, target_h, off_x, off_y):
    """Convert parsed SVG path commands into GIMP bezier control points.

    Returns a list of (controlpoints, closed) tuples for each sub-path/stroke.
    Each controlpoint is [handle_left_x, handle_left_y, anchor_x, anchor_y,
                          handle_right_x, handle_right_y, ...]
    Scales from 0-100 viewBox to target_w x target_h at offset (off_x, off_y).
    """
    sx = target_w / 100.0
    sy = target_h / 100.0

    def tx(x):
        return x * sx + off_x

    def ty(y):
        return y * sy + off_y

    strokes = []
    current_points = []
    cx, cy = 0, 0  # Current position
    start_x, start_y = 0, 0  # Start of current sub-path

    for cmd, nums in commands:
        if cmd == 'M':
            # Start new sub-path
            if current_points:
                strokes.append((current_points, False))
                current_points = []
            i = 0
            while i < len(nums):
                cx, cy = nums[i], nums[i + 1]
                if i == 0:
                    start_x, start_y = cx, cy
                # For MoveTo, anchor = handle_left = handle_right (straight)
                ax, ay = tx(cx), ty(cy)
                current_points.extend([ax, ay, ax, ay, ax, ay])
                i += 2
                # Subsequent coordinate pairs after M are treated as L
                if i < len(nums):
                    cmd = 'L'  # implicit lineto

        elif cmd == 'L':
            i = 0
            while i < len(nums):
                cx, cy = nums[i], nums[i + 1]
                ax, ay = tx(cx), ty(cy)
                current_points.extend([ax, ay, ax, ay, ax, ay])
                i += 2

        elif cmd == 'C':
            # Cubic bezier: C x1 y1 x2 y2 x y
            i = 0
            while i + 5 < len(nums):
                x1, y1 = nums[i], nums[i + 1]
                x2, y2 = nums[i + 2], nums[i + 3]
                ex, ey = nums[i + 4], nums[i + 5]

                # Adjust the right handle of the previous anchor
                if len(current_points) >= 6:
                    current_points[-2] = tx(x1)
                    current_points[-1] = ty(y1)

                # New anchor with left handle = control point 2, right handle = anchor
                ax, ay = tx(ex), ty(ey)
                current_points.extend([tx(x2), ty(y2), ax, ay, ax, ay])

                cx, cy = ex, ey
                i += 6

        elif cmd == 'Z' or cmd == 'z':
            # Close path
            if current_points:
                strokes.append((current_points, True))
                current_points = []
            cx, cy = start_x, start_y

        # For simplicity, treat other commands as line approximations
        elif cmd == 'H':
            for val in nums:
                cx = val
                ax, ay = tx(cx), ty(cy)
                current_points.extend([ax, ay, ax, ay, ax, ay])

        elif cmd == 'V':
            for val in nums:
                cy = val
                ax, ay = tx(cx), ty(cy)
                current_points.extend([ax, ay, ax, ay, ax, ay])

    if current_points:
        strokes.append((current_points, False))

    return strokes


def shape_library(procedure, run_mode, image, drawables, config, data):
    """Create a GIMP vector path from the selected shape."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-shape-library')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    shape_key = config.get_property('shape')
    w = config.get_property('width')
    h = config.get_property('height')
    x = config.get_property('x')
    y = config.get_property('y')
    do_stroke = config.get_property('stroke-path')

    if shape_key not in SHAPES:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error(f"Forme inconnue : {shape_key}"))

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    # Parse SVG path and convert to bezier points
    svg_d = SHAPES[shape_key]
    commands = _parse_svg_path(svg_d)
    strokes_data = _svg_path_to_bezier_points(commands, w, h, x, y)

    label = SHAPE_LABELS.get(shape_key, shape_key)
    vectors = Gimp.Vectors.new(image, f"Forme: {label}")
    image.insert_vectors(vectors, None, -1)

    for controlpoints, closed in strokes_data:
        if len(controlpoints) < 6:
            continue
        proc = pdb.lookup_procedure('gimp-vectors-bezier-stroke-new')
        pc = proc.create_config()
        pc.set_property('vectors', vectors)
        fa = Gimp.FloatArray.new(controlpoints)
        pc.set_property('controlpoints', fa)
        pc.set_property('closed', closed)
        proc.run(pc)

    # Optionally stroke the path
    if do_stroke and drawables:
        Gimp.context_set_stroke_method(Gimp.StrokeMethod.LINE)
        Gimp.context_set_line_width(2.0)
        for drawable in drawables:
            drawable.edit_stroke_item(vectors)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    Gimp.message(f"Forme '{label}' creee comme chemin vectoriel ({w}x{h} a {x},{y}).")
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ShapeLibrary(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-shape-library']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            shape_library, None)
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.set_documentation(
            _("Shape Library — Custom Shapes"),
            _("Bibliotheque de formes vectorielles : coeur, nuage, bulle, "
              "etoile, fleches, icones et plus. Cree un chemin GIMP "
              "a la taille et position souhaitees."),
            name)
        procedure.set_menu_label(_("_Bibliotheque de formes..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Vector")

        # Shape choice
        shape_choice = Gimp.Choice.new()
        idx = 0
        for key in SHAPES:
            label = SHAPE_LABELS.get(key, key)
            shape_choice.add(key, idx, _(label), "")
            idx += 1
        procedure.add_choice_argument("shape",
                                      _("_Forme"),
                                      _("Forme a creer"),
                                      shape_choice, "heart",
                                      GObject.ParamFlags.READWRITE)

        procedure.add_int_argument("width",
                                   _("_Largeur"),
                                   _("Largeur de la forme en pixels"),
                                   10, 10000, 200,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("height",
                                   _("_Hauteur"),
                                   _("Hauteur de la forme en pixels"),
                                   10, 10000, 200,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("x",
                                   _("Position _X"),
                                   _("Position X du coin superieur gauche"),
                                   0, 100000, 50,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("y",
                                   _("Position _Y"),
                                   _("Position Y du coin superieur gauche"),
                                   0, 100000, 50,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("stroke-path",
                                       _("_Tracer le chemin"),
                                       _("Tracer le chemin sur le calque actif apres creation"),
                                       False,
                                       GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(ShapeLibrary.__gtype__, sys.argv)

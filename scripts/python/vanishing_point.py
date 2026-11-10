#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Vanishing Point
#   Create perspective grid from a vanishing point
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


def vanishing_point(procedure, run_mode, image, drawables, config, data):
    """Create perspective guide lines radiating from a vanishing point."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("vanish"),
                                                                  "Aucun calque actif.", 0))

    pdb = Gimp.get_pdb()

    vp_x = config.get_property("vanishing_point_x")
    vp_y = config.get_property("vanishing_point_y")
    num_lines = int(config.get_property("num_lines"))
    spread_angle = config.get_property("spread_angle")

    img_w = image.get_width()
    img_h = image.get_height()

    # Default to image center if -1
    if vp_x < 0:
        vp_x = img_w / 2.0
    if vp_y < 0:
        vp_y = img_h / 2.0

    Gimp.context_push()
    image.undo_group_start()

    # Create a new layer for the perspective grid
    grid_layer = Gimp.Layer.new(image, "Point de fuite - grille",
                                img_w, img_h,
                                Gimp.ImageType.RGBA_IMAGE, 80.0,
                                Gimp.LayerMode.NORMAL)
    image.insert_layer(grid_layer, None, 0)

    # Set drawing color (cyan for visibility)
    color_line = Gimp.RGB()
    color_line.set(0.0, 0.8, 1.0)
    Gimp.context_set_foreground(color_line)
    Gimp.context_set_brush_size(1.5)
    Gimp.context_set_opacity(80.0)

    # Maximum line length (diagonal of the image)
    max_length = math.sqrt(img_w ** 2 + img_h ** 2) * 1.5

    # Calculate angular spread
    # spread_angle is the total spread, lines are evenly distributed within it
    half_spread = spread_angle / 2.0
    if num_lines < 2:
        angles = [0.0]
    else:
        angles = []
        for i in range(num_lines):
            angle_deg = -half_spread + (spread_angle * i / (num_lines - 1))
            angles.append(angle_deg)

    # Draw radiating lines from the vanishing point
    for angle_deg in angles:
        angle_rad = math.radians(angle_deg)

        # Calculate endpoint far from VP
        end_x = vp_x + max_length * math.cos(angle_rad)
        end_y = vp_y + max_length * math.sin(angle_rad)

        # Also draw in opposite direction for full coverage
        end_x2 = vp_x - max_length * math.cos(angle_rad)
        end_y2 = vp_y - max_length * math.sin(angle_rad)

        strokes = [float(end_x2), float(end_y2), float(vp_x), float(vp_y),
                    float(vp_x), float(vp_y), float(end_x), float(end_y)]

        pdb.run_procedure('gimp-pencil', [
            GObject.Value(Gimp.Drawable, grid_layer),
            GObject.Value(Gimp.ObjectArray, Gimp.ObjectArray.new(GObject.TYPE_DOUBLE, strokes, False)),
        ])

    # Draw a small cross at the vanishing point
    color_vp = Gimp.RGB()
    color_vp.set(1.0, 0.3, 0.0)
    Gimp.context_set_foreground(color_vp)
    Gimp.context_set_brush_size(2.0)

    cross_size = 10.0
    cross_strokes_h = [float(vp_x - cross_size), float(vp_y),
                       float(vp_x + cross_size), float(vp_y)]
    cross_strokes_v = [float(vp_x), float(vp_y - cross_size),
                       float(vp_x), float(vp_y + cross_size)]

    pdb.run_procedure('gimp-pencil', [
        GObject.Value(Gimp.Drawable, grid_layer),
        GObject.Value(Gimp.ObjectArray, Gimp.ObjectArray.new(GObject.TYPE_DOUBLE, cross_strokes_h, False)),
    ])
    pdb.run_procedure('gimp-pencil', [
        GObject.Value(Gimp.Drawable, grid_layer),
        GObject.Value(Gimp.ObjectArray, Gimp.ObjectArray.new(GObject.TYPE_DOUBLE, cross_strokes_v, False)),
    ])

    # Also add GIMP guides at the vanishing point for precision
    image.add_hguide(int(vp_y))
    image.add_vguide(int(vp_x))

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class VanishingPoint(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-vanishing-point',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-vanishing-point':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                vanishing_point, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Vanishing Point"),
                _("Créer une grille perspective avec des lignes de fuite irradiant depuis un point de fuite."),
                name)
            procedure.set_menu_label(_("_Point de fuite..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters")

            procedure.add_double_argument("vanishing_point_x", _("Point de fuite X"),
                                          _("Position X du point de fuite (-1 = centre)"),
                                          -1.0, 100000.0, -1.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("vanishing_point_y", _("Point de fuite Y"),
                                          _("Position Y du point de fuite (-1 = centre)"),
                                          -1.0, 100000.0, -1.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("num_lines", _("Nombre de lignes"),
                                          _("Nombre de lignes de fuite à tracer"),
                                          2.0, 100.0, 12.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("spread_angle", _("Angle d'ouverture (°)"),
                                          _("Angle total de répartition des lignes en degrés"),
                                          10.0, 360.0, 180.0,
                                          GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(VanishingPoint.__gtype__, sys.argv)

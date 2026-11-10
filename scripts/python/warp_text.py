#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Deformer le texte (Warp Text)
#   Photoshop-style text warp: Arc, Flag, Wave, Bulge, Perspective
#   Converts text to path, applies mathematical warp, renders to layer.
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


def _warp_point(x, y, warp_type, bend, h_dist, v_dist,
                cx, cy, width, height):
    """Apply a warp transformation to a single point.

    All coordinates are normalized to [-1, 1] range relative to the
    bounding box center (cx, cy) and dimensions (width, height).
    """
    # Normalize to [-1, 1]
    nx = (x - cx) / (width / 2.0) if width > 0 else 0
    ny = (y - cy) / (height / 2.0) if height > 0 else 0
    bend_f = bend / 100.0
    h_f = h_dist / 100.0
    v_f = v_dist / 100.0

    dx = 0.0
    dy = 0.0

    if warp_type == "arc":
        # Arc: bend along a circular arc
        dy = bend_f * (1.0 - nx * nx) * (height / 2.0)
        dx = h_f * ny * (width / 4.0)
        dy += v_f * nx * (height / 4.0)

    elif warp_type == "flag":
        # Flag: wave with increasing amplitude
        phase = nx * math.pi
        amp = bend_f * (0.5 + 0.5 * abs(nx))
        dy = amp * math.sin(phase) * (height / 2.0)
        dx = h_f * ny * (width / 4.0)
        dy += v_f * nx * (height / 4.0)

    elif warp_type == "wave":
        # Wave: sinusoidal distortion
        dy = bend_f * math.sin(nx * math.pi * 2) * (height / 3.0)
        dx = h_f * math.sin(ny * math.pi * 2) * (width / 4.0)
        dy += v_f * math.cos(nx * math.pi) * (height / 4.0)

    elif warp_type == "bulge":
        # Bulge/inflate: radial displacement from center
        dist = math.sqrt(nx * nx + ny * ny)
        if dist > 0.001:
            factor = bend_f * (1.0 - dist) * 0.5
            dx = factor * nx * (width / 2.0)
            dy = factor * ny * (height / 2.0)
        dx += h_f * ny * (width / 4.0)
        dy += v_f * nx * (height / 4.0)

    elif warp_type == "perspective":
        # Perspective: converging lines (trapezoid)
        scale = 1.0 + bend_f * ny * 0.5
        dx = nx * (scale - 1.0) * (width / 2.0)
        dx += h_f * ny * (width / 4.0)
        dy += v_f * nx * (height / 4.0)

    return (x + dx, y + dy)


def warp_text_run(procedure, run_mode, image, drawables, config, data):
    """Warp the active text layer or any drawable using path manipulation."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-warp-text')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    warp_type = config.get_property('warp-type')
    bend      = config.get_property('bend')
    h_dist    = config.get_property('horizontal-distortion')
    v_dist    = config.get_property('vertical-distortion')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    for drawable in drawables:
        w = drawable.get_width()
        h = drawable.get_height()
        off_x = drawable.get_offsets().offset_x
        off_y = drawable.get_offsets().offset_y

        # Bounding box center
        cx = off_x + w / 2.0
        cy = off_y + h / 2.0

        is_text = drawable.is_text_layer() if hasattr(drawable, 'is_text_layer') else False

        if is_text:
            # Strategy for text layers:
            # 1. Convert text to path
            # 2. Warp the path control points
            # 3. Create a new layer, stroke or fill the warped path

            # Get text-to-path
            try:
                text_path = drawable.text_to_path()
            except Exception:
                # Fallback: use distort filter approach
                text_path = None

            if text_path is not None:
                # Warp each stroke's control points
                num_strokes = text_path.get_n_strokes()
                for stroke_id_idx in range(num_strokes):
                    stroke_ids = text_path.get_stroke_ids()
                    if stroke_id_idx >= len(stroke_ids):
                        break
                    sid = stroke_ids[stroke_id_idx]

                    # Get bezier points
                    cp_type, points, closed = text_path.stroke_get_points(sid)
                    if points is None or len(points) < 2:
                        continue

                    # points is a flat array: x0, y0, x1, y1, ...
                    new_points = list(points)
                    for i in range(0, len(new_points), 2):
                        px = new_points[i]
                        py = new_points[i + 1]
                        nx, ny = _warp_point(px, py, warp_type, bend,
                                             h_dist, v_dist, cx, cy, w, h)
                        new_points[i] = nx
                        new_points[i + 1] = ny

                    # Remove old stroke and add warped one
                    text_path.stroke_remove(sid)
                    text_path.stroke_new_from_points(cp_type, new_points, closed)

                # Create a new layer from the warped text path
                warp_layer = Gimp.Layer.new(image, "Texte deforme",
                                            image.get_width(), image.get_height(),
                                            Gimp.ImageType.RGBA_IMAGE,
                                            100.0, Gimp.LayerMode.NORMAL)
                warp_layer.fill(Gimp.FillType.TRANSPARENT)
                image.insert_layer(warp_layer, drawable.get_parent(),
                                   image.get_item_position(drawable))

                # Fill the path with the text foreground color
                image.set_active_layer(warp_layer)
                Gimp.context_set_antialias(True)
                image.select_item(Gimp.ChannelOps.REPLACE, text_path)
                warp_layer.edit_fill(Gimp.FillType.FOREGROUND)
                Gimp.Selection.none(image)

                # Hide original text layer
                drawable.set_visible(False)
            else:
                # Fallback for text: use curve-bend or shift filter
                _apply_gegl_warp_fallback(drawable, warp_type, bend, h_dist, v_dist, w, h)
        else:
            # Non-text drawable: use GEGL distortion filters as approximation
            _apply_gegl_warp_fallback(drawable, warp_type, bend, h_dist, v_dist, w, h)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def _apply_gegl_warp_fallback(drawable, warp_type, bend, h_dist, v_dist, w, h):
    """Apply GEGL-based distortion as a fallback when path manipulation is not possible."""
    bend_f = bend / 100.0

    if warp_type == "arc":
        # Spherize simulates arc bending
        try:
            f = Gimp.DrawableFilter.new(drawable, "gegl:spherize", "")
            c = f.get_config()
            c.set_property("amount", bend_f)
            drawable.merge_filter(f)
        except Exception:
            pass

    elif warp_type == "flag" or warp_type == "wave":
        # Use shift filter for wave-like distortion
        try:
            f = Gimp.DrawableFilter.new(drawable, "gegl:shift", "")
            c = f.get_config()
            c.set_property("shift", abs(bend_f) * min(w, h) * 0.15)
            drawable.merge_filter(f)
        except Exception:
            pass

    elif warp_type == "bulge":
        # Spherize for bulge
        try:
            f = Gimp.DrawableFilter.new(drawable, "gegl:spherize", "")
            c = f.get_config()
            c.set_property("amount", bend_f)
            drawable.merge_filter(f)
        except Exception:
            pass

    elif warp_type == "perspective":
        # Use waterpixels or just a slight spherize as approximation
        try:
            f = Gimp.DrawableFilter.new(drawable, "gegl:spherize", "")
            c = f.get_config()
            c.set_property("amount", bend_f * 0.5)
            drawable.merge_filter(f)
        except Exception:
            pass

    # Apply additional horizontal/vertical distortion
    if abs(h_dist) > 0.5 or abs(v_dist) > 0.5:
        try:
            f = Gimp.DrawableFilter.new(drawable, "gegl:shift", "")
            c = f.get_config()
            shift_amount = max(abs(h_dist), abs(v_dist)) / 100.0 * min(w, h) * 0.1
            c.set_property("shift", shift_amount)
            drawable.merge_filter(f)
        except Exception:
            pass


class WarpText(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-warp-text']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            warp_text_run, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Deformer le texte"),
            _("Deformation de texte style Photoshop : arc, drapeau, vague, "
              "gonflement, perspective. Fonctionne sur les calques de texte "
              "(conversion en chemin) ou sur tout calque (filtres GEGL)."),
            name)
        procedure.set_menu_label(_("_Deformer le texte..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Typography")

        warp_choice = Gimp.Choice.new()
        warp_choice.add("arc", 0, _("Arc"), "")
        warp_choice.add("flag", 1, _("Drapeau"), "")
        warp_choice.add("wave", 2, _("Vague"), "")
        warp_choice.add("bulge", 3, _("Gonflement"), "")
        warp_choice.add("perspective", 4, _("Perspective"), "")
        procedure.add_choice_argument("warp-type", _("_Type de deformation"),
                                      _("Style de deformation a appliquer"),
                                      warp_choice, "arc",
                                      GObject.ParamFlags.READWRITE)

        procedure.add_double_argument("bend", _("_Courbure"),
                                      _("Intensite de la deformation (-100 a 100)"),
                                      -100.0, 100.0, 50.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("horizontal-distortion",
                                      _("Distorsion _horizontale"),
                                      _("Distorsion horizontale supplementaire"),
                                      -100.0, 100.0, 0.0,
                                      GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("vertical-distortion",
                                      _("Distorsion _verticale"),
                                      _("Distorsion verticale supplementaire"),
                                      -100.0, 100.0, 0.0,
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(WarpText.__gtype__, sys.argv)

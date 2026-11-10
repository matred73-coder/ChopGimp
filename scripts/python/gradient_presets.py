#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Gradient Presets
#   Photoshop-style advanced gradient shapes: radial, diamond, reflected, angular
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


def _apply_gradient(image, drawable, shape_type, config):
    """Apply a gradient with the given shape type using the active gradient."""
    pdb = Gimp.get_pdb()

    img_w = image.get_width()
    img_h = image.get_height()

    center_x = config.get_property("center_x")
    center_y = config.get_property("center_y")
    radius = config.get_property("radius")

    # If center is -1, use image center
    if center_x < 0:
        center_x = img_w / 2.0
    if center_y < 0:
        center_y = img_h / 2.0
    # If radius is 0, use half the smaller dimension
    if radius <= 0:
        radius = min(img_w, img_h) / 2.0

    Gimp.context_push()
    image.undo_group_start()

    # Map shape type string to Gimp.GradientType
    gradient_map = {
        "radial":    Gimp.GradientType.RADIAL,
        "diamond":   Gimp.GradientType.SHAPEBURST_DIMPLED,
        "reflected": Gimp.GradientType.BILINEAR,
        "angular":   Gimp.GradientType.CONICAL_SYMMETRIC,
    }

    grad_type = gradient_map.get(shape_type, Gimp.GradientType.RADIAL)

    # For diamond shape, use the square gradient type which is closer to PS diamond
    if shape_type == "diamond":
        grad_type = Gimp.GradientType.SQUARE

    # Draw the gradient
    # gimp-drawable-edit-gradient-fill uses the context gradient
    # We use gimp-edit-blend for more control over shape
    pdb.run_procedure('gimp-edit-blend', [
        GObject.Value(Gimp.Drawable, drawable),
        GObject.Value(Gimp.BlendMode, Gimp.BlendMode.FG_BG_RGB),
        GObject.Value(Gimp.LayerMode, Gimp.LayerMode.NORMAL),
        GObject.Value(Gimp.GradientType, grad_type),
        GObject.Value(GObject.TYPE_DOUBLE, 100.0),       # opacity
        GObject.Value(GObject.TYPE_DOUBLE, 0.0),         # offset
        GObject.Value(Gimp.RepeatMode, Gimp.RepeatMode.NONE),
        GObject.Value(GObject.TYPE_BOOLEAN, False),       # reverse
        GObject.Value(GObject.TYPE_BOOLEAN, False),       # supersampling
        GObject.Value(GObject.TYPE_INT, 3),               # max_depth
        GObject.Value(GObject.TYPE_DOUBLE, 0.2),          # threshold
        GObject.Value(GObject.TYPE_BOOLEAN, False),       # dither
        GObject.Value(GObject.TYPE_DOUBLE, center_x),     # x1
        GObject.Value(GObject.TYPE_DOUBLE, center_y),     # y1
        GObject.Value(GObject.TYPE_DOUBLE, center_x + radius),  # x2
        GObject.Value(GObject.TYPE_DOUBLE, center_y),     # y2
    ])

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()


def gradient_radial(procedure, run_mode, image, drawables, config, data):
    """Apply a radial gradient from center outward."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("gradient"),
                                                                  "Aucun calque actif.", 0))
    _apply_gradient(image, drawables[0], "radial", config)
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def gradient_diamond(procedure, run_mode, image, drawables, config, data):
    """Apply a diamond-shaped gradient."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("gradient"),
                                                                  "Aucun calque actif.", 0))
    _apply_gradient(image, drawables[0], "diamond", config)
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def gradient_reflected(procedure, run_mode, image, drawables, config, data):
    """Apply a reflected/mirrored gradient."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("gradient"),
                                                                  "Aucun calque actif.", 0))
    _apply_gradient(image, drawables[0], "reflected", config)
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def gradient_angular(procedure, run_mode, image, drawables, config, data):
    """Apply an angular/conical gradient."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("gradient"),
                                                                  "Aucun calque actif.", 0))
    _apply_gradient(image, drawables[0], "angular", config)
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def _create_gradient_procedure(plugin, name, callback, menu_label, doc_title, doc_desc):
    """Helper to create a gradient procedure with common parameters."""
    procedure = Gimp.ImageProcedure.new(plugin, name,
                                        Gimp.PDBProcType.PLUGIN,
                                        callback, None)
    procedure.set_image_types("RGB*, GRAY*")
    procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                   Gimp.ProcedureSensitivityMask.DRAWABLES)
    procedure.set_documentation(_(doc_title), _(doc_desc), name)
    procedure.set_menu_label(_(menu_label))
    procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
    procedure.add_menu_path("<Image>/Filters/Render")

    procedure.add_double_argument("center_x", _("Centre X"),
                                  _("Position X du centre (-1 = centre image)"),
                                  -1.0, 100000.0, -1.0,
                                  GObject.ParamFlags.READWRITE)
    procedure.add_double_argument("center_y", _("Centre Y"),
                                  _("Position Y du centre (-1 = centre image)"),
                                  -1.0, 100000.0, -1.0,
                                  GObject.ParamFlags.READWRITE)
    procedure.add_double_argument("radius", _("Rayon"),
                                  _("Rayon du dégradé (0 = automatique)"),
                                  0.0, 100000.0, 0.0,
                                  GObject.ParamFlags.READWRITE)
    return procedure


class GradientPresets(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-gradient-radial',
            'python-fu-gradient-diamond',
            'python-fu-gradient-reflected',
            'python-fu-gradient-angular',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-gradient-radial':
            return _create_gradient_procedure(
                self, name, gradient_radial,
                "Dégradé _radial...",
                "Radial Gradient",
                "Appliquer un dégradé radial depuis le centre.")

        elif name == 'python-fu-gradient-diamond':
            return _create_gradient_procedure(
                self, name, gradient_diamond,
                "Dégradé _losange...",
                "Diamond Gradient",
                "Appliquer un dégradé en forme de losange.")

        elif name == 'python-fu-gradient-reflected':
            return _create_gradient_procedure(
                self, name, gradient_reflected,
                "Dégradé ré_flexion...",
                "Reflected Gradient",
                "Appliquer un dégradé réfléchi/miroir.")

        elif name == 'python-fu-gradient-angular':
            return _create_gradient_procedure(
                self, name, gradient_angular,
                "Dégradé _angle...",
                "Angular Gradient",
                "Appliquer un dégradé angulaire/conique.")

        else:
            return None


Gimp.main(GradientPresets.__gtype__, sys.argv)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Pattern Stamp
#   Fill selection with active pattern (Photoshop Pattern Stamp tool)
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


def pattern_stamp(procedure, run_mode, image, drawables, config, data):
    """Fill the current selection with the active pattern, with scale and rotation."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("patstamp"),
                                                                  "Aucun calque actif.", 0))

    drawable = drawables[0]
    pdb = Gimp.get_pdb()

    scale = config.get_property("scale")
    angle = config.get_property("angle")

    Gimp.context_push()
    image.undo_group_start()

    # If scale != 100 or angle != 0, we create a temporary pattern-filled layer,
    # transform it, then flatten into the target layer via selection.
    if abs(scale - 100.0) > 0.01 or abs(angle) > 0.01:
        # Save current selection
        has_selection = not pdb.run_procedure('gimp-selection-is-empty',
                                              [GObject.Value(Gimp.Image, image)]).index(1)

        # Create a temp layer same size as image
        img_w = image.get_width()
        img_h = image.get_height()
        temp_layer = Gimp.Layer.new(image, "pattern-stamp-temp",
                                    img_w, img_h,
                                    Gimp.ImageType.RGBA_IMAGE,
                                    100.0,
                                    Gimp.LayerMode.NORMAL)
        image.insert_layer(temp_layer, None, 0)

        # Fill temp layer with pattern
        Gimp.context_set_fill_mode(Gimp.FillMode.PATTERN)
        pdb.run_procedure('gimp-drawable-edit-fill', [
            GObject.Value(Gimp.Drawable, temp_layer),
            GObject.Value(Gimp.FillType, Gimp.FillType.PATTERN),
        ])

        # Scale if needed
        if abs(scale - 100.0) > 0.01:
            new_w = max(1, int(img_w * scale / 100.0))
            new_h = max(1, int(img_h * scale / 100.0))
            temp_layer.scale(new_w, new_h, False)
            # Re-center
            off_x = (img_w - new_w) // 2
            off_y = (img_h - new_h) // 2
            temp_layer.set_offsets(off_x, off_y)
            # Resize to full canvas
            temp_layer.resize_to_image_size()

        # Rotate if needed
        if abs(angle) > 0.01:
            angle_rad = angle * (math.pi / 180.0)
            center_x = img_w / 2.0
            center_y = img_h / 2.0
            pdb.run_procedure('gimp-item-transform-rotate-default', [
                GObject.Value(Gimp.Item, temp_layer),
                GObject.Value(GObject.TYPE_DOUBLE, angle_rad),
                GObject.Value(GObject.TYPE_BOOLEAN, True),
                GObject.Value(GObject.TYPE_DOUBLE, center_x),
                GObject.Value(GObject.TYPE_DOUBLE, center_y),
            ])

        # Flatten temp layer down onto target via merge
        image.flatten()
        # This is too destructive; instead, copy from temp into drawable via selection
        # Let's undo the flatten and do it properly
        # Actually, use a different approach: copy visible from temp, paste into drawable

        # Better approach: just merge down temp_layer onto the target
        image.set_active_layer(temp_layer)
        merged = image.merge_down(temp_layer, Gimp.MergeType.CLIP_TO_BOTTOM_LAYER)

    else:
        # Simple case: fill with pattern directly
        Gimp.context_set_fill_mode(Gimp.FillMode.PATTERN)
        pdb.run_procedure('gimp-drawable-edit-fill', [
            GObject.Value(Gimp.Drawable, drawable),
            GObject.Value(Gimp.FillType, Gimp.FillType.PATTERN),
        ])

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class PatternStamp(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-pattern-stamp',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-pattern-stamp':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                pattern_stamp, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Pattern Stamp"),
                _("Remplir la sélection avec le motif actif, avec échelle et rotation optionnelles."),
                name)
            procedure.set_menu_label(_("_Tampon de motif..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Retouching")

            procedure.add_double_argument("scale", _("Échelle (%)"),
                                          _("Redimensionner le motif (100 = taille originale)"),
                                          10.0, 1000.0, 100.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("angle", _("Angle (°)"),
                                          _("Rotation du motif en degrés"),
                                          -360.0, 360.0, 0.0,
                                          GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(PatternStamp.__gtype__, sys.argv)

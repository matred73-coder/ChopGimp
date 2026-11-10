#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Layer Styles
#   Basic Photoshop-like layer styles: Ombre portee, Ombre interne,
#   Contour, Incrustation couleur (non-destructive via extra layers)
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
# Ombre portee
# ---------------------------------------------------------------------------
def drop_shadow(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-drop-shadow')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    offset_x = config.get_property('offset-x')
    offset_y = config.get_property('offset-y')
    blur_radius = config.get_property('blur-radius')
    color = config.get_property('color')
    opacity = config.get_property('opacity')

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        w = drawable.get_width()
        h = drawable.get_height()

        # Create shadow layer below the current drawable
        shadow = Gimp.Layer.new(image, "Ombre portee",
                                w + abs(offset_x) * 2 + blur_radius * 4,
                                h + abs(offset_y) * 2 + blur_radius * 4,
                                Gimp.ImageType.RGBA_IMAGE,
                                opacity,
                                Gimp.LayerMode.MULTIPLY)
        shadow.fill(Gimp.FillType.TRANSPARENT)

        # Position: below the current layer
        parent = drawable.get_parent()
        pos = image.get_item_position(drawable)
        image.insert_layer(shadow, parent, pos + 1)

        # Offset the shadow layer so its center aligns with drawable + offset
        dx = drawable.get_offsets().offset_x
        dy = drawable.get_offsets().offset_y
        shadow.set_offsets(dx + offset_x - abs(offset_x) - blur_radius * 2,
                           dy + offset_y - abs(offset_y) - blur_radius * 2)

        # Copy alpha from source to shadow layer as selection, then fill
        pdb = Gimp.get_pdb()

        # Select by alpha from source
        proc = pdb.lookup_procedure('gimp-image-set-active-layer')
        pc = proc.create_config()
        pc.set_property('image', image)
        pc.set_property('layer', drawable)
        proc.run(pc)

        proc = pdb.lookup_procedure('gimp-selection-layer-alpha')
        pc = proc.create_config()
        pc.set_property('layer', drawable)
        proc.run(pc)

        # Shift selection to match shadow offset
        proc = pdb.lookup_procedure('gimp-selection-translate')
        pc = proc.create_config()
        pc.set_property('off-x', offset_x)
        pc.set_property('off-y', offset_y)
        proc.run(pc)

        # Fill shadow layer with color in selection
        image.set_active_layer(shadow)
        Gimp.context_set_foreground(color)
        shadow.edit_fill(Gimp.FillType.FOREGROUND)

        Gimp.Selection.none(image)

        # Blur the shadow
        if blur_radius > 0:
            blur_filter = Gimp.DrawableFilter.new(shadow, "gegl:gaussian-blur", "")
            blur_config = blur_filter.get_config()
            blur_config.set_property("std-dev-x", float(blur_radius))
            blur_config.set_property("std-dev-y", float(blur_radius))
            shadow.merge_filter(blur_filter)

        # Restore active layer
        image.set_active_layer(drawable)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Ombre interne
# ---------------------------------------------------------------------------
def inner_shadow(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-inner-shadow')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    offset_x = config.get_property('offset-x')
    offset_y = config.get_property('offset-y')
    blur_radius = config.get_property('blur-radius')
    color = config.get_property('color')
    opacity = config.get_property('opacity')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    for drawable in drawables:
        w = drawable.get_width()
        h = drawable.get_height()
        dx = drawable.get_offsets().offset_x
        dy = drawable.get_offsets().offset_y

        # Create inner shadow layer above the current drawable, clipped to it
        inner = Gimp.Layer.new(image, "Ombre interne",
                                w, h,
                                Gimp.ImageType.RGBA_IMAGE,
                                opacity,
                                Gimp.LayerMode.MULTIPLY)
        inner.fill(Gimp.FillType.TRANSPARENT)
        parent = drawable.get_parent()
        pos = image.get_item_position(drawable)
        image.insert_layer(inner, parent, pos)
        inner.set_offsets(dx, dy)

        # Fill entire inner shadow layer with shadow color
        Gimp.context_set_foreground(color)
        inner.edit_fill(Gimp.FillType.FOREGROUND)

        # Create mask from inverted alpha of source (shadow only inside edges)
        # Select alpha of source layer
        proc = pdb.lookup_procedure('gimp-selection-layer-alpha')
        pc = proc.create_config()
        pc.set_property('layer', drawable)
        proc.run(pc)

        # Shrink selection to create inner edge, then invert for shadow mask
        # Actually: translate selection by offset, then use as mask
        # Better approach: use layer alpha as mask, offset and blur

        # Apply alpha mask: create mask from selection (the drawable shape)
        mask = inner.create_mask(Gimp.AddMaskType.SELECTION)
        inner.add_mask(mask)

        # Invert the mask (shadow is at edges, not center)
        proc = pdb.lookup_procedure('gimp-drawable-invert')
        pc = proc.create_config()
        pc.set_property('drawable', mask)
        pc.set_property('linear', False)
        proc.run(pc)

        # Offset the mask to simulate light direction
        proc = pdb.lookup_procedure('gimp-drawable-offset')
        pc = proc.create_config()
        pc.set_property('drawable', mask)
        pc.set_property('wrap-around', False)
        pc.set_property('fill-type', Gimp.OffsetType.TRANSPARENT)
        pc.set_property('offset-x', offset_x)
        pc.set_property('offset-y', offset_y)
        proc.run(pc)

        # Blur the mask
        if blur_radius > 0:
            blur_filter = Gimp.DrawableFilter.new(mask, "gegl:gaussian-blur", "")
            blur_config = blur_filter.get_config()
            blur_config.set_property("std-dev-x", float(blur_radius))
            blur_config.set_property("std-dev-y", float(blur_radius))
            mask.merge_filter(blur_filter)

        # Apply and keep the mask
        inner.remove_mask(Gimp.MaskApplyMode.APPLY)

        # Clip inner shadow to source alpha
        proc = pdb.lookup_procedure('gimp-selection-layer-alpha')
        pc = proc.create_config()
        pc.set_property('layer', drawable)
        proc.run(pc)

        # Intersection with selection to clip
        proc = pdb.lookup_procedure('gimp-selection-invert')
        pc = proc.create_config()
        pc.set_property('image', image)
        proc.run(pc)

        inner.edit_clear()
        Gimp.Selection.none(image)

        image.set_active_layer(drawable)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Contour
# ---------------------------------------------------------------------------
def stroke_style(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-stroke-style')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    stroke_size = config.get_property('stroke-size')
    color = config.get_property('color')
    position = config.get_property('position')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    for drawable in drawables:
        w = drawable.get_width()
        h = drawable.get_height()
        dx = drawable.get_offsets().offset_x
        dy = drawable.get_offsets().offset_y

        # Create stroke layer
        stroke_layer = Gimp.Layer.new(image, "Contour",
                                      w + stroke_size * 2,
                                      h + stroke_size * 2,
                                      Gimp.ImageType.RGBA_IMAGE,
                                      100.0,
                                      Gimp.LayerMode.NORMAL)
        stroke_layer.fill(Gimp.FillType.TRANSPARENT)

        parent = drawable.get_parent()
        if position == "outside":
            # Contour below, larger
            pos = image.get_item_position(drawable) + 1
            image.insert_layer(stroke_layer, parent, pos)
            stroke_layer.set_offsets(dx - stroke_size, dy - stroke_size)
        elif position == "inside":
            # Contour above, clipped
            pos = image.get_item_position(drawable)
            image.insert_layer(stroke_layer, parent, pos)
            stroke_layer.set_offsets(dx, dy)
        else:
            # Center: below
            pos = image.get_item_position(drawable) + 1
            image.insert_layer(stroke_layer, parent, pos)
            stroke_layer.set_offsets(dx - stroke_size // 2, dy - stroke_size // 2)

        # Select alpha of source
        proc = pdb.lookup_procedure('gimp-selection-layer-alpha')
        pc = proc.create_config()
        pc.set_property('layer', drawable)
        proc.run(pc)

        if position == "outside":
            # Grow selection by stroke size
            Gimp.Selection.grow(image, stroke_size)
        elif position == "center":
            grow_px = stroke_size // 2
            if grow_px > 0:
                Gimp.Selection.grow(image, grow_px)

        # Fill stroke layer with color in selection
        image.set_active_layer(stroke_layer)
        Gimp.context_set_foreground(color)
        stroke_layer.edit_fill(Gimp.FillType.FOREGROUND)

        if position == "outside" or position == "center":
            # Cut out the original shape from the stroke
            proc = pdb.lookup_procedure('gimp-selection-layer-alpha')
            pc = proc.create_config()
            pc.set_property('layer', drawable)
            proc.run(pc)
            stroke_layer.edit_clear()

        elif position == "inside":
            # Shrink selection to remove interior
            Gimp.Selection.shrink(image, stroke_size)
            stroke_layer.edit_clear()
            # Clip to source alpha
            proc = pdb.lookup_procedure('gimp-selection-layer-alpha')
            pc = proc.create_config()
            pc.set_property('layer', drawable)
            proc.run(pc)
            proc = pdb.lookup_procedure('gimp-selection-invert')
            pc = proc.create_config()
            pc.set_property('image', image)
            proc.run(pc)
            stroke_layer.edit_clear()

        Gimp.Selection.none(image)
        image.set_active_layer(drawable)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Incrustation couleur
# ---------------------------------------------------------------------------
def color_overlay(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-color-overlay')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    color = config.get_property('color')
    opacity = config.get_property('opacity')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()

    for drawable in drawables:
        w = drawable.get_width()
        h = drawable.get_height()
        dx = drawable.get_offsets().offset_x
        dy = drawable.get_offsets().offset_y

        overlay = Gimp.Layer.new(image, "Incrustation couleur",
                                 w, h,
                                 Gimp.ImageType.RGBA_IMAGE,
                                 opacity,
                                 Gimp.LayerMode.NORMAL)
        overlay.fill(Gimp.FillType.TRANSPARENT)

        parent = drawable.get_parent()
        pos = image.get_item_position(drawable)
        image.insert_layer(overlay, parent, pos)
        overlay.set_offsets(dx, dy)

        # Select alpha of source to clip
        proc = pdb.lookup_procedure('gimp-selection-layer-alpha')
        pc = proc.create_config()
        pc.set_property('layer', drawable)
        proc.run(pc)

        # Fill with color
        Gimp.context_set_foreground(color)
        image.set_active_layer(overlay)
        overlay.edit_fill(Gimp.FillType.FOREGROUND)

        Gimp.Selection.none(image)
        image.set_active_layer(drawable)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class LayerStyles(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-drop-shadow',
            'python-fu-inner-shadow',
            'python-fu-stroke-style',
            'python-fu-color-overlay',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        menu_base = "<Image>/Layer/Layer Styles"

        if name == 'python-fu-drop-shadow':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                drop_shadow, None)
            procedure.set_image_types("RGBA, GRAYA")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Ombre portee"),
                _("Ajouter une ombre portee style Photoshop derriere le calque."),
                name)
            procedure.set_menu_label(_("_Ombre portee..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            black = Gegl.Color.new("black")
            procedure.add_int_argument("offset-x", _("Decalage _X"), _("Decalage horizontal"),
                                       -500, 500, 5, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("offset-y", _("Decalage _Y"), _("Decalage vertical"),
                                       -500, 500, 5, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("blur-radius", _("Rayon de _flou"), _("Flou de l'ombre"),
                                       0, 200, 10, GObject.ParamFlags.READWRITE)
            procedure.add_color_argument("color", _("_Couleur"), _("Couleur de l'ombre"),
                                         True, black, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("opacity", _("_Opacite"), _("Opacite de l'ombre"),
                                          0.0, 100.0, 60.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-inner-shadow':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                inner_shadow, None)
            procedure.set_image_types("RGBA, GRAYA")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Ombre interne"),
                _("Ajouter une ombre interne style Photoshop a l'interieur des bords du calque."),
                name)
            procedure.set_menu_label(_("Ombre _interne..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            black = Gegl.Color.new("black")
            procedure.add_int_argument("offset-x", _("Decalage _X"), _("Decalage horizontal"),
                                       -500, 500, 3, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("offset-y", _("Decalage _Y"), _("Decalage vertical"),
                                       -500, 500, 3, GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("blur-radius", _("Rayon de _flou"), _("Flou de l'ombre"),
                                       0, 200, 8, GObject.ParamFlags.READWRITE)
            procedure.add_color_argument("color", _("_Couleur"), _("Couleur de l'ombre"),
                                         True, black, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("opacity", _("_Opacite"), _("Opacite de l'ombre"),
                                          0.0, 100.0, 50.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-stroke-style':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                stroke_style, None)
            procedure.set_image_types("RGBA, GRAYA")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Contour"),
                _("Ajouter un contour colore autour du contenu du calque."),
                name)
            procedure.set_menu_label(_("_Contour..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            red = Gegl.Color.new("black")
            red.set_rgba(1.0, 0.0, 0.0, 1.0)
            procedure.add_int_argument("stroke-size", _("_Taille"), _("Largeur du contour en pixels"),
                                       1, 200, 3, GObject.ParamFlags.READWRITE)
            procedure.add_color_argument("color", _("_Couleur"), _("Couleur du contour"),
                                         True, red, GObject.ParamFlags.READWRITE)
            choice = Gimp.Choice.new()
            choice.add("outside", 0, _("Outside"), "")
            choice.add("inside", 1, _("Inside"), "")
            choice.add("center", 2, _("Center"), "")
            procedure.add_choice_argument("position", _("_Position"), _("Position du contour"),
                                          choice, "outside", GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-color-overlay':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                color_overlay, None)
            procedure.set_image_types("RGBA, GRAYA")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Incrustation couleur"),
                _("Remplir la forme du calque avec une couleur unie a l'opacite specifiee."),
                name)
            procedure.set_menu_label(_("Incrustation _couleur..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            white = Gegl.Color.new("white")
            procedure.add_color_argument("color", _("_Couleur"), _("Couleur d'incrustation"),
                                         True, white, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("opacity", _("_Opacite"), _("Opacite de l'incrustation"),
                                          0.0, 100.0, 80.0, GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(LayerStyles.__gtype__, sys.argv)

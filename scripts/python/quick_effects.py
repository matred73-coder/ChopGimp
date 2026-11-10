#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Quick Effects
#   One-click Photoshop-style effects: Vignette, Tons HDR, Vintage,
#   High Key, Low Key, Bichromie
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
# Vignette
# ---------------------------------------------------------------------------
def vignette(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-vignette')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    softness = config.get_property('softness')
    strength = config.get_property('strength')

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        vig_filter = Gimp.DrawableFilter.new(drawable, "gegl:vignette", "")
        vig_config = vig_filter.get_config()
        vig_config.set_property("softness", softness)
        vig_config.set_property("strength", strength)
        drawable.merge_filter(vig_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Tons HDR — local contrast enhancement
# ---------------------------------------------------------------------------
def hdr_toning(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-hdr-toning')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    strength = config.get_property('strength')

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        # Unsharp mask with large radius = local contrast enhancement (HDR look)
        usm_filter = Gimp.DrawableFilter.new(drawable, "gegl:unsharp-mask", "")
        usm_config = usm_filter.get_config()
        usm_config.set_property("std-dev", 30.0)       # Large radius
        usm_config.set_property("scale", strength)      # Amount
        usm_config.set_property("threshold", 0.0)
        drawable.merge_filter(usm_filter)

        # Slight stretch to enhance dynamic range
        stretch_filter = Gimp.DrawableFilter.new(drawable, "gegl:stretch-contrast", "")
        stretch_config = stretch_filter.get_config()
        stretch_config.set_property("keep-colors", True)
        drawable.merge_filter(stretch_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Vintage / Retro — desaturate + warm tone + grain
# ---------------------------------------------------------------------------
def vintage(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-vintage')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    grain_amount = config.get_property('grain-amount')

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        w = drawable.get_width()
        h = drawable.get_height()

        # 1. Partial desaturation
        desat_filter = Gimp.DrawableFilter.new(drawable, "gegl:saturation", "")
        desat_config = desat_filter.get_config()
        desat_config.set_property("scale", 0.4)  # 40% of original saturation
        drawable.merge_filter(desat_filter)

        # 2. Warm color overlay — create a new layer with warm tone
        if image.get_base_type() is Gimp.ImageBaseType.RGB:
            warm_layer = Gimp.Layer.new(image, "Vintage Warm",
                                        w, h,
                                        Gimp.ImageType.RGBA_IMAGE,
                                        25.0,  # opacity
                                        Gimp.LayerMode.MULTIPLY)
            warm_layer.fill(Gimp.FillType.TRANSPARENT)
            image.insert_layer(warm_layer, drawable.get_parent(),
                               image.get_item_position(drawable))

            warm_color = Gegl.Color.new("black")
            warm_color.set_rgba(0.85, 0.65, 0.30, 1.0)
            Gimp.context_set_foreground(warm_color)
            warm_layer.edit_fill(Gimp.FillType.FOREGROUND)

        # 3. Film grain via noise
        if grain_amount > 0:
            grain_filter = Gimp.DrawableFilter.new(drawable, "gegl:noise-hsv", "")
            grain_config = grain_filter.get_config()
            grain_config.set_property("dulling", 4)
            grain_config.set_property("value-distance", grain_amount)
            drawable.merge_filter(grain_filter)

        # 4. Slight vignette
        vig_filter = Gimp.DrawableFilter.new(drawable, "gegl:vignette", "")
        vig_config = vig_filter.get_config()
        vig_config.set_property("softness", 2.0)
        vig_config.set_property("strength", 0.6)
        drawable.merge_filter(vig_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# High Key
# ---------------------------------------------------------------------------
def high_key(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-high-key')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    amount = config.get_property('amount')

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        # Brightness-Contrast push for high-key look
        bc_filter = Gimp.DrawableFilter.new(drawable, "gegl:brightness-contrast", "")
        bc_config = bc_filter.get_config()
        bc_config.set_property("brightness", amount)
        bc_config.set_property("contrast", -0.1)  # slightly lower contrast
        drawable.merge_filter(bc_filter)

        # Slight desaturation for airy feel
        desat_filter = Gimp.DrawableFilter.new(drawable, "gegl:saturation", "")
        desat_config = desat_filter.get_config()
        desat_config.set_property("scale", 0.8)
        drawable.merge_filter(desat_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Low Key
# ---------------------------------------------------------------------------
def low_key(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-low-key')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    amount = config.get_property('amount')

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        bc_filter = Gimp.DrawableFilter.new(drawable, "gegl:brightness-contrast", "")
        bc_config = bc_filter.get_config()
        bc_config.set_property("brightness", -amount)
        bc_config.set_property("contrast", 0.15)  # boost contrast for drama
        drawable.merge_filter(bc_filter)

        # Boost saturation slightly for deep colors
        sat_filter = Gimp.DrawableFilter.new(drawable, "gegl:saturation", "")
        sat_config = sat_filter.get_config()
        sat_config.set_property("scale", 1.2)
        drawable.merge_filter(sat_filter)

        # Vignette for mood
        vig_filter = Gimp.DrawableFilter.new(drawable, "gegl:vignette", "")
        vig_config = vig_filter.get_config()
        vig_config.set_property("softness", 1.5)
        vig_config.set_property("strength", 0.8)
        drawable.merge_filter(vig_filter)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Bichromie
# ---------------------------------------------------------------------------
def duotone(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-duotone')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    shadow_color    = config.get_property('shadow-color')
    highlight_color = config.get_property('highlight-color')

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        w = drawable.get_width()
        h = drawable.get_height()

        # 1. Desaturate the drawable
        desat_filter = Gimp.DrawableFilter.new(drawable, "gegl:saturation", "")
        desat_config = desat_filter.get_config()
        desat_config.set_property("scale", 0.0)
        drawable.merge_filter(desat_filter)

        # 2. Create shadow tone layer (Multiply mode)
        shadow_layer = Gimp.Layer.new(image, "Bichromie Shadows",
                                      w, h,
                                      Gimp.ImageType.RGBA_IMAGE,
                                      100.0,
                                      Gimp.LayerMode.MULTIPLY)
        shadow_layer.fill(Gimp.FillType.TRANSPARENT)
        image.insert_layer(shadow_layer, drawable.get_parent(),
                           image.get_item_position(drawable))
        Gimp.context_set_foreground(shadow_color)
        shadow_layer.edit_fill(Gimp.FillType.FOREGROUND)

        # 3. Create highlight tone layer (Screen mode)
        highlight_layer = Gimp.Layer.new(image, "Bichromie Highlights",
                                         w, h,
                                         Gimp.ImageType.RGBA_IMAGE,
                                         50.0,
                                         Gimp.LayerMode.SCREEN)
        highlight_layer.fill(Gimp.FillType.TRANSPARENT)
        image.insert_layer(highlight_layer, drawable.get_parent(),
                           image.get_item_position(drawable))
        Gimp.context_set_foreground(highlight_color)
        highlight_layer.edit_fill(Gimp.FillType.FOREGROUND)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class QuickEffects(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-vignette',
            'python-fu-hdr-toning',
            'python-fu-vintage',
            'python-fu-high-key',
            'python-fu-low-key',
            'python-fu-duotone',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        menu_base = "<Image>/Filters/Quick Effects"

        if name == 'python-fu-vignette':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                vignette, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Effet Vignette"),
                _("Ajouter des bords sombres avec rayon et intensite personnalisables."),
                name)
            procedure.set_menu_label(_("_Vignette..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("softness", _("_Douceur"),
                                          _("Edge softness"), 0.0, 10.0, 3.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("strength", _("_Intensite"),
                                          _("Intensite de la vignette"), 0.0, 5.0, 1.0,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-hdr-toning':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                hdr_toning, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Tons HDR"),
                _("Amelioration du contraste local pour un aspect HDR."),
                name)
            procedure.set_menu_label(_("Tons _HDR..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("strength", _("_Intensite"),
                                          _("Intensite de l'effet"), 0.1, 5.0, 1.5,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-vintage':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                vintage, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Effet Vintage / Retro"),
                _("Desaturer + ton chaud + grain de film + vignette pour un aspect retro."),
                name)
            procedure.set_menu_label(_("V_intage / Retro..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("grain-amount", _("Grain de _film"),
                                          _("Amount of film grain noise"),
                                          0.0, 1.0, 0.15,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-high-key':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                high_key, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("High Key"),
                _("Aspect lumineux et aere avec exposition augmentee et contraste doux."),
                name)
            procedure.set_menu_label(_("High _Key..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("amount", _("_Intensite"),
                                          _("Brightness boost amount"),
                                          0.0, 1.0, 0.3,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-low-key':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                low_key, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Low Key"),
                _("Aspect sombre et dramatique avec des ombres profondes et un contraste riche."),
                name)
            procedure.set_menu_label(_("_Low Key..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("amount", _("_Intensite"),
                                          _("Darkness amount"),
                                          0.0, 1.0, 0.25,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-duotone':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                duotone, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Bichromie"),
                _("Effet de bichromie avec couleurs d'ombre et de haute lumiere personnalisables."),
                name)
            procedure.set_menu_label(_("_Bichromie..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            shadow_default = Gegl.Color.new("black")
            shadow_default.set_rgba(0.1, 0.05, 0.2, 1.0)  # Deep purple
            highlight_default = Gegl.Color.new("black")
            highlight_default.set_rgba(1.0, 0.85, 0.5, 1.0)  # Warm gold

            procedure.add_color_argument("shadow-color", _("Couleur des _ombres"),
                                         _("Couleur pour les tons sombres"),
                                         True, shadow_default,
                                         GObject.ParamFlags.READWRITE)
            procedure.add_color_argument("highlight-color", _("Couleur des _hautes lumieres"),
                                         _("Couleur pour les tons clairs"),
                                         True, highlight_default,
                                         GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(QuickEffects.__gtype__, sys.argv)

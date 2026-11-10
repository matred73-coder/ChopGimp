#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Non-Destructive Effects (NDE) avec prévisualisation live
#   Simulates Photoshop Smart Filters via layer-group approach.
#   Each effect uses DrawableFilter.update() for real-time canvas preview
#   before committing with merge_filter().
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib
import sys

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

NDE_PREFIX = "NDE: "


def _get_or_create_nde_group(image, drawable):
    """Ensure the drawable lives inside an NDE group. Return (group, base_layer)."""
    parent = drawable.get_parent()
    if parent is not None and parent.get_name().startswith(NDE_PREFIX):
        return parent, drawable

    group_name = NDE_PREFIX + drawable.get_name()
    group = Gimp.GroupLayer.new(image, group_name)
    old_parent = drawable.get_parent()
    pos = image.get_item_position(drawable)
    image.insert_layer(group, old_parent, pos)
    image.reorder_item(drawable, group, 0)
    return group, drawable


def _add_fx_layer(image, group, base_drawable, fx_name):
    """Duplicate the base layer inside the group and place on top."""
    children = group.get_children()
    if not children:
        return None
    base_layer = children[-1]
    fx_layer = base_layer.copy()
    fx_layer.set_name(fx_name)
    image.insert_layer(fx_layer, group, 0)
    return fx_layer


def _apply_with_preview(procedure, run_mode, image, drawables, config,
                        gegl_op, build_config_fn, build_name_fn):
    """Generic NDE effect with live preview.

    1. Create FX layer in NDE group
    2. Create DrawableFilter on FX layer
    3. Apply config → filter.update() → live preview on canvas
    4. Show dialog → user adjusts params → preview updates
    5. OK → merge_filter() / Cancel → remove FX layer
    """
    Gimp.context_push()
    image.undo_group_start()

    results = []
    for drawable in drawables:
        group, base = _get_or_create_nde_group(image, drawable)
        fx_name = build_name_fn(config)
        fx_layer = _add_fx_layer(image, group, base, fx_name)
        if not fx_layer:
            continue

        # Create the GEGL filter on the FX layer
        filt = Gimp.DrawableFilter.new(fx_layer, gegl_op, "")
        filt_config = filt.get_config()

        # Set initial params and show preview
        build_config_fn(config, filt_config)
        filt.update(fx_layer)
        fx_layer.append_filter(filt)
        Gimp.displays_flush()

        results.append((fx_layer, filt, group))

    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("nde-effects")
        dialog = GimpUi.ProcedureDialog.new(procedure, config, None)
        dialog.fill(None)

        # Connect config changes to live preview update
        def on_config_changed(*args):
            for fx_layer, filt, group in results:
                filt_config = filt.get_config()
                build_config_fn(config, filt_config)
                filt.update(fx_layer)
                Gimp.displays_flush()

        config.connect("notify", on_config_changed)

        accepted = dialog.run()
        dialog.destroy()

        if not accepted:
            # Cancel: remove filter and FX layer
            for fx_layer, filt, group in results:
                fx_layer.remove_filter(filt)
                image.remove_layer(fx_layer)
                # If group has only 1 child, dissolve the group
                children = group.get_children()
                if children and len(children) == 1:
                    child = children[0]
                    image.merge_layer_group(group)
            Gimp.displays_flush()
            image.undo_group_end()
            Gimp.context_pop()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())

    # OK: apply final params and merge
    for fx_layer, filt, group in results:
        build_config_fn(config, filt.get_config())
        fx_layer.merge_filter(filt)
        fx_layer.set_name(build_name_fn(config))
        image.set_active_layer(fx_layer)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ═══════════════════════════════════════════════════════════════
# NDE Flou gaussien
# ═══════════════════════════════════════════════════════════════
def nde_blur(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("std-dev-x", float(cfg.get_property("radius")))
        fc.set_property("std-dev-y", float(cfg.get_property("radius")))

    def name(cfg):
        return "FX: Flou gaussien (r={})".format(round(cfg.get_property("radius"), 1))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:gaussian-blur", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Luminosité/Contraste
# ═══════════════════════════════════════════════════════════════
def nde_brightness_contrast(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("brightness", cfg.get_property("brightness"))
        fc.set_property("contrast", cfg.get_property("contrast"))

    def name(cfg):
        return "FX: Luminosité/Contraste (b={}, c={})".format(
            round(cfg.get_property("brightness"), 2),
            round(cfg.get_property("contrast"), 2))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:brightness-contrast", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Teinte/Saturation
# ═══════════════════════════════════════════════════════════════
def nde_hue_saturation(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("hue", cfg.get_property("hue-shift"))
        fc.set_property("chroma", cfg.get_property("saturation"))
        fc.set_property("lightness", cfg.get_property("lightness"))

    def name(cfg):
        return "FX: Teinte/Saturation (h={}, s={}, l={})".format(
            round(cfg.get_property("hue-shift"), 1),
            round(cfg.get_property("saturation"), 2),
            round(cfg.get_property("lightness"), 2))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:hue-chroma", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Balance des couleurs
# ═══════════════════════════════════════════════════════════════
def nde_color_balance(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("cyan-red", cfg.get_property("cyan-red"))
        fc.set_property("magenta-green", cfg.get_property("magenta-green"))
        fc.set_property("yellow-blue", cfg.get_property("yellow-blue"))

    def name(cfg):
        return "FX: Balance couleurs (cr={}, mg={}, yb={})".format(
            round(cfg.get_property("cyan-red"), 2),
            round(cfg.get_property("magenta-green"), 2),
            round(cfg.get_property("yellow-blue"), 2))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:color-balance", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Courbes (stretch-contrast)
# ═══════════════════════════════════════════════════════════════
def nde_curves(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("keep-colors", cfg.get_property("keep-colors"))

    def name(cfg):
        mode = "luminosité" if cfg.get_property("keep-colors") else "par canal"
        return "FX: Courbes ({})".format(mode)

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:stretch-contrast", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Niveaux
# ═══════════════════════════════════════════════════════════════
def nde_levels(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("in-low", cfg.get_property("in-low"))
        fc.set_property("in-high", cfg.get_property("in-high"))
        fc.set_property("gamma", cfg.get_property("gamma"))

    def name(cfg):
        return "FX: Niveaux (in={}-{}, g={})".format(
            round(cfg.get_property("in-low"), 2),
            round(cfg.get_property("in-high"), 2),
            round(cfg.get_property("gamma"), 2))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:levels", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Netteté (Unsharp Mask)
# ═══════════════════════════════════════════════════════════════
def nde_sharpen(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("std-dev", cfg.get_property("radius"))
        fc.set_property("scale", cfg.get_property("amount"))
        fc.set_property("threshold", cfg.get_property("threshold"))

    def name(cfg):
        return "FX: Netteté (a={}, r={})".format(
            round(cfg.get_property("amount"), 1),
            round(cfg.get_property("radius"), 1))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:unsharp-mask", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Vignette
# ═══════════════════════════════════════════════════════════════
def nde_vignette(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("softness", cfg.get_property("softness"))
        fc.set_property("strength", cfg.get_property("strength"))

    def name(cfg):
        return "FX: Vignette (douceur={}, force={})".format(
            round(cfg.get_property("softness"), 1),
            round(cfg.get_property("strength"), 1))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:vignette", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Exposition
# ═══════════════════════════════════════════════════════════════
def nde_exposure(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("exposure", cfg.get_property("exposure"))
        fc.set_property("offset", cfg.get_property("offset"))

    def name(cfg):
        return "FX: Exposition (ev={}, offset={})".format(
            round(cfg.get_property("exposure"), 2),
            round(cfg.get_property("offset"), 3))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:exposure", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Température de couleur
# ═══════════════════════════════════════════════════════════════
def nde_color_temperature(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("intended-temperature", cfg.get_property("temperature"))

    def name(cfg):
        return "FX: Température ({}K)".format(int(cfg.get_property("temperature")))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:color-temperature", build, name)


# ═══════════════════════════════════════════════════════════════
# NDE Ombres/Hautes lumières
# ═══════════════════════════════════════════════════════════════
def nde_shadows_highlights(procedure, run_mode, image, drawables, config, data):
    def build(cfg, fc):
        fc.set_property("shadows", cfg.get_property("shadows"))
        fc.set_property("highlights", cfg.get_property("highlights"))

    def name(cfg):
        return "FX: Ombres/HL (s={}, h={})".format(
            round(cfg.get_property("shadows"), 1),
            round(cfg.get_property("highlights"), 1))

    return _apply_with_preview(procedure, run_mode, image, drawables, config,
                               "gegl:shadows-highlights", build, name)


# ═══════════════════════════════════════════════════════════════
# Supprimer tous les effets NDE
# ═══════════════════════════════════════════════════════════════
def nde_remove_all(procedure, run_mode, image, drawables, config, data):
    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        parent = drawable.get_parent()
        target_group = None
        if hasattr(drawable, 'get_children') and drawable.get_name().startswith(NDE_PREFIX):
            target_group = drawable
        elif parent is not None and parent.get_name().startswith(NDE_PREFIX):
            target_group = parent

        if target_group is not None:
            merged = image.merge_layer_group(target_group)
            old_name = merged.get_name()
            if old_name.startswith(NDE_PREFIX):
                merged.set_name(old_name[len(NDE_PREFIX):])
            image.set_active_layer(merged)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ═══════════════════════════════════════════════════════════════
# Plugin registration
# ═══════════════════════════════════════════════════════════════
class NDEEffects(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-nde-blur',
            'python-fu-nde-brightness-contrast',
            'python-fu-nde-hue-saturation',
            'python-fu-nde-color-balance',
            'python-fu-nde-curves',
            'python-fu-nde-levels',
            'python-fu-nde-sharpen',
            'python-fu-nde-vignette',
            'python-fu-nde-exposure',
            'python-fu-nde-color-temperature',
            'python-fu-nde-shadows-highlights',
            'python-fu-nde-remove-all',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)
        menu_base = "<Image>/Filters/Non-Destructive Effects"

        if name == 'python-fu-nde-blur':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_blur, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Flou gaussien", "Flou gaussien non-destructif avec prévisualisation live", name)
            procedure.set_menu_label("NDE Flou _gaussien...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("radius", "Rayon", "Rayon de flou en pixels", 0.1, 500.0, 10.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-brightness-contrast':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_brightness_contrast, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Luminosité/Contraste", "Réglage luminosité et contraste avec prévisualisation live", name)
            procedure.set_menu_label("NDE _Luminosité/Contraste...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("brightness", "Luminosité", "Réglage de luminosité", -1.0, 1.0, 0.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("contrast", "Contraste", "Réglage de contraste", -1.0, 1.0, 0.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-hue-saturation':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_hue_saturation, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Teinte/Saturation", "Réglage teinte, saturation, luminosité avec prévisualisation live", name)
            procedure.set_menu_label("NDE _Teinte/Saturation...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("hue-shift", "Décalage teinte", "Rotation de teinte en degrés", -180.0, 180.0, 0.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("saturation", "Saturation", "Réglage de saturation", -100.0, 100.0, 0.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("lightness", "Luminosité", "Réglage de luminosité", -100.0, 100.0, 0.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-color-balance':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_color_balance, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Balance des couleurs", "Balance des couleurs avec prévisualisation live", name)
            procedure.set_menu_label("NDE Balance des _couleurs...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("cyan-red", "Cyan-Rouge", "Balance Cyan-Rouge", -1.0, 1.0, 0.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("magenta-green", "Magenta-Vert", "Balance Magenta-Vert", -1.0, 1.0, 0.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("yellow-blue", "Jaune-Bleu", "Balance Jaune-Bleu", -1.0, 1.0, 0.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-curves':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_curves, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Courbes", "Étirement de contraste avec prévisualisation live", name)
            procedure.set_menu_label("NDE _Courbes...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_boolean_argument("keep-colors", "Conserver les couleurs", "Préserver les teintes (luminosité uniquement)", True, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-levels':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_levels, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Niveaux", "Réglage niveaux avec prévisualisation live", name)
            procedure.set_menu_label("NDE _Niveaux...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("in-low", "Entrée bas", "Point noir d'entrée", 0.0, 1.0, 0.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("in-high", "Entrée haut", "Point blanc d'entrée", 0.0, 1.0, 1.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("gamma", "Gamma", "Réglage Gamma / tons moyens", 0.1, 10.0, 1.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-sharpen':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_sharpen, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Netteté", "Accentuation par masque flou avec prévisualisation live", name)
            procedure.set_menu_label("NDE _Netteté...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("amount", "Intensité", "Intensité de la netteté", 0.0, 10.0, 1.5, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("radius", "Rayon", "Rayon de netteté", 0.1, 100.0, 3.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("threshold", "Seuil", "Seuil pour les contours", 0.0, 1.0, 0.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-vignette':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_vignette, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Vignette", "Effet vignette avec prévisualisation live", name)
            procedure.set_menu_label("NDE _Vignette...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("softness", "Douceur", "Douceur du bord", 0.0, 10.0, 3.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("strength", "Intensité", "Intensité de la vignette", 0.0, 5.0, 1.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-exposure':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_exposure, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Exposition", "Réglage d'exposition avec prévisualisation live", name)
            procedure.set_menu_label("NDE _Exposition...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("exposure", "Exposition", "Exposition en EV", -10.0, 10.0, 0.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("offset", "Décalage", "Décalage noir", -0.5, 0.5, 0.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-color-temperature':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_color_temperature, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Température", "Température de couleur avec prévisualisation live", name)
            procedure.set_menu_label("NDE _Température couleur...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("temperature", "Température", "Température en Kelvin", 1000.0, 12000.0, 6500.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-shadows-highlights':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_shadows_highlights, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("NDE Ombres/Hautes lumières", "Récupération ombres et hautes lumières avec prévisualisation live", name)
            procedure.set_menu_label("NDE _Ombres/Hautes lumières...")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)
            procedure.add_double_argument("shadows", "Ombres", "Récupération des ombres", -100.0, 100.0, 0.0, GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("highlights", "Hautes lumières", "Récupération des hautes lumières", -100.0, 100.0, 0.0, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-nde-remove-all':
            procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, nde_remove_all, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE | Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation("Supprimer tous les effets NDE", "Aplatir le groupe NDE en un seul calque", name)
            procedure.set_menu_label("_Supprimer tous les effets NDE")
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        else:
            return None

        return procedure


Gimp.main(NDEEffects.__gtype__, sys.argv)

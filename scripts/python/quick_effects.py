#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Effets rapides
#   Effets en un clic façon Photoshop : Vignette, Tons HDR, Vintage,
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


SHADOW_DEFAULT = "#33194d"      # violet profond
HIGHLIGHT_DEFAULT = "#ffd98c"   # or chaud


def _color_or_default(color, default):
    """Couleur d'argument, ou la valeur par défaut si elle n'est pas définie
    (couleur entièrement transparente : défaut non transmis par la config)."""
    if color is None or color.get_rgba()[3] == 0.0:
        return Gegl.Color.new(default)
    return color


def _dialog(procedure, config, name, title):
    gi.require_version('GimpUi', '3.0')
    from gi.repository import GimpUi
    GimpUi.init(name)
    dialog = GimpUi.ProcedureDialog.new(procedure, config, title)
    dialog.fill(None)
    ok = dialog.run()
    dialog.destroy()
    return ok


def _cancel(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())


def _success(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def _apply(drawable, op, props, opacity=None):
    """Applique (fusionne) un filtre GEGL sur le calque."""
    f = Gimp.DrawableFilter.new(drawable, op, "")
    cfg = f.get_config()
    for k, v in props.items():
        cfg.set_property(k, v)
    if opacity is not None:
        f.set_opacity(float(opacity))
    f.update()
    drawable.merge_filter(f)


def _targets(drawables):
    return [d for d in drawables if not d.is_group()]


def _color_layer(image, drawable, name, color, opacity, mode):
    """Calque uni de la taille du calque cible, inséré juste au-dessus."""
    layer = Gimp.Layer.new(image, name, drawable.get_width(), drawable.get_height(),
                           Gimp.ImageType.RGBA_IMAGE, opacity, mode)
    image.insert_layer(layer, drawable.get_parent(), image.get_item_position(drawable))
    off = drawable.get_offsets()
    layer.set_offsets(off.offset_x, off.offset_y)
    Gimp.context_set_foreground(color)
    layer.fill(Gimp.FillType.FOREGROUND)
    return layer


def _vignette(drawable, softness, strength):
    _apply(drawable, "gegl:vignette",
           {"color": Gegl.Color.new("black"), "radius": 1.2, "softness": float(softness)},
           opacity=strength)


# ---------------------------------------------------------------------------
# Vignette
# ---------------------------------------------------------------------------
def vignette(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and \
            not _dialog(procedure, config, 'python-fu-vignette', _("Vignette")):
        return _cancel(procedure)

    softness = config.get_property('softness')
    strength = config.get_property('strength')

    Gimp.context_push()
    image.undo_group_start()
    try:
        for drawable in _targets(drawables):
            _vignette(drawable, softness, strength)
    finally:
        image.undo_group_end()
        Gimp.context_pop()
    Gimp.displays_flush()
    return _success(procedure)


# ---------------------------------------------------------------------------
# Tons HDR — amélioration du contraste local
# ---------------------------------------------------------------------------
def hdr_toning(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and \
            not _dialog(procedure, config, 'python-fu-hdr-toning', _("Tons HDR")):
        return _cancel(procedure)

    strength = config.get_property('strength')

    Gimp.context_push()
    image.undo_group_start()
    try:
        for drawable in _targets(drawables):
            # Masque flou à grand rayon = contraste local (aspect HDR)
            _apply(drawable, "gegl:unsharp-mask",
                   {"std-dev": 30.0, "scale": float(strength), "threshold": 0.0})
            # Étirement de la plage dynamique
            _apply(drawable, "gegl:stretch-contrast", {"keep-colors": True})
    finally:
        image.undo_group_end()
        Gimp.context_pop()
    Gimp.displays_flush()
    return _success(procedure)


# ---------------------------------------------------------------------------
# Vintage / Rétro — désaturation + ton chaud + grain + vignette
# ---------------------------------------------------------------------------
def vintage(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and \
            not _dialog(procedure, config, 'python-fu-vintage', _("Vintage / Rétro")):
        return _cancel(procedure)

    grain_amount = config.get_property('grain-amount')

    Gimp.context_push()
    image.undo_group_start()
    try:
        for drawable in _targets(drawables):
            # 1. Désaturation partielle
            _apply(drawable, "gegl:saturation", {"scale": 0.4})

            # 2. Grain de film
            if grain_amount > 0:
                _apply(drawable, "gegl:noise-hsv",
                       {"holdness": 4, "hue-distance": 0.0, "saturation-distance": 0.0,
                        "value-distance": float(grain_amount)})

            # 3. Légère vignette
            _vignette(drawable, 0.8, 0.6)

            # 4. Calque de ton chaud (Produit, 25 %)
            if image.get_base_type() == Gimp.ImageBaseType.RGB:
                _color_layer(image, drawable, _("Vintage : ton chaud"),
                             Gegl.Color.new("#d9a64d"), 25.0, Gimp.LayerMode.MULTIPLY)
    finally:
        image.undo_group_end()
        Gimp.context_pop()
    Gimp.displays_flush()
    return _success(procedure)


# ---------------------------------------------------------------------------
# High Key
# ---------------------------------------------------------------------------
def high_key(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and \
            not _dialog(procedure, config, 'python-fu-high-key', _("High Key")):
        return _cancel(procedure)

    amount = config.get_property('amount')

    Gimp.context_push()
    image.undo_group_start()
    try:
        for drawable in _targets(drawables):
            # Exposition augmentée, contraste légèrement réduit
            _apply(drawable, "gegl:exposure", {"exposure": 3.0 * float(amount)})
            _apply(drawable, "gegl:brightness-contrast",
                   {"brightness": 0.0, "contrast": 0.9})
            # Légère désaturation pour un rendu aérien
            _apply(drawable, "gegl:saturation", {"scale": 0.8})
    finally:
        image.undo_group_end()
        Gimp.context_pop()
    Gimp.displays_flush()
    return _success(procedure)


# ---------------------------------------------------------------------------
# Low Key
# ---------------------------------------------------------------------------
def low_key(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and \
            not _dialog(procedure, config, 'python-fu-low-key', _("Low Key")):
        return _cancel(procedure)

    amount = config.get_property('amount')

    Gimp.context_push()
    image.undo_group_start()
    try:
        for drawable in _targets(drawables):
            # Exposition réduite, contraste renforcé
            _apply(drawable, "gegl:exposure", {"exposure": -3.0 * float(amount)})
            _apply(drawable, "gegl:brightness-contrast",
                   {"brightness": 0.0, "contrast": 1.15})
            # Couleurs plus profondes
            _apply(drawable, "gegl:saturation", {"scale": 1.2})
            # Vignette pour l'ambiance
            _vignette(drawable, 0.7, 0.8)
    finally:
        image.undo_group_end()
        Gimp.context_pop()
    Gimp.displays_flush()
    return _success(procedure)


# ---------------------------------------------------------------------------
# Bichromie
# ---------------------------------------------------------------------------
def duotone(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE and \
            not _dialog(procedure, config, 'python-fu-duotone', _("Bichromie")):
        return _cancel(procedure)

    shadow_color    = _color_or_default(config.get_property('shadow-color'), SHADOW_DEFAULT)
    highlight_color = _color_or_default(config.get_property('highlight-color'), HIGHLIGHT_DEFAULT)

    Gimp.context_push()
    image.undo_group_start()
    try:
        for drawable in _targets(drawables):
            # 1. Niveaux de gris
            _apply(drawable, "gegl:saturation", {"scale": 0.0})
            # 2. Hautes lumières : gris x couleur claire (Produit)
            _color_layer(image, drawable, _("Bichromie : hautes lumières"),
                         highlight_color, 100.0, Gimp.LayerMode.MULTIPLY)
            # 3. Ombres : la couleur sombre remplace le noir (Écran)
            _color_layer(image, drawable, _("Bichromie : ombres"),
                         shadow_color, 100.0, Gimp.LayerMode.SCREEN)
    finally:
        image.undo_group_end()
        Gimp.context_pop()
    Gimp.displays_flush()
    return _success(procedure)


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

        menu_base = "<Image>/Filters/Effets rapides"

        if name == 'python-fu-vignette':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                vignette, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Effet Vignette"),
                _("Assombrit les bords de l'image (douceur et intensité réglables)."),
                name)
            procedure.set_menu_label(_("_Vignette…"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("softness", _("_Douceur"),
                                          _("Douceur de la transition (0-1)"), 0.0, 1.0, 0.8,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("strength", _("_Intensité"),
                                          _("Intensité de la vignette (0-1)"), 0.0, 1.0, 0.8,
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
                _("Amélioration du contraste local pour un aspect HDR."),
                name)
            procedure.set_menu_label(_("Tons _HDR…"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("strength", _("_Intensité"),
                                          _("Intensité de l'effet"), 0.1, 5.0, 1.5,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-vintage':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                vintage, None)
            procedure.set_image_types("RGB*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Effet Vintage / Rétro"),
                _("Désaturation + ton chaud + grain de film + vignette pour un aspect rétro."),
                name)
            procedure.set_menu_label(_("V_intage / Rétro…"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("grain-amount", _("Grain de _film"),
                                          _("Quantité de grain de film"),
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
                _("Aspect lumineux et aéré : exposition augmentée et contraste doux."),
                name)
            procedure.set_menu_label(_("High _Key…"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("amount", _("_Intensité"),
                                          _("Augmentation de l'exposition (x 3 IL)"),
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
                _("Aspect sombre et dramatique : ombres profondes et contraste riche."),
                name)
            procedure.set_menu_label(_("_Low Key…"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("amount", _("_Intensité"),
                                          _("Réduction de l'exposition (x 3 IL)"),
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
                _("Bichromie avec couleurs des ombres et des hautes lumières personnalisables."),
                name)
            procedure.set_menu_label(_("_Bichromie…"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            shadow_default = Gegl.Color.new(SHADOW_DEFAULT)
            highlight_default = Gegl.Color.new(HIGHLIGHT_DEFAULT)

            procedure.add_color_argument("shadow-color", _("Couleur des _ombres"),
                                         _("Couleur pour les tons sombres"),
                                         True, shadow_default,
                                         GObject.ParamFlags.READWRITE)
            procedure.add_color_argument("highlight-color", _("Couleur des _hautes lumières"),
                                         _("Couleur pour les tons clairs"),
                                         True, highlight_default,
                                         GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(QuickEffects.__gtype__, sys.argv)

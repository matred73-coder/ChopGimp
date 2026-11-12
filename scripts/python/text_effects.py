#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Effets de texte
#   Effets pour calques texte : 3D, Néon, Chrome, Contour, Ombre, Arc
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
#  Outils
# ---------------------------------------------------------------------------

def _targets(drawables):
    """Calques utilisables (pas les groupes)."""
    return [d for d in drawables if isinstance(d, Gimp.Layer) and not d.is_group()]


def _apply(drawable, op, props):
    """Applique (fusionne) un filtre GEGL sur le calque."""
    f = Gimp.DrawableFilter.new(drawable, op, "")
    cfg = f.get_config()
    for k, v in props.items():
        cfg.set_property(k, v)
    f.update()
    drawable.merge_filter(f)


def _fill_opaque(layer, color):
    """Remplit les pixels non transparents du calque avec une couleur unie."""
    layer.set_lock_alpha(True)
    Gimp.context_set_foreground(color)
    layer.fill(Gimp.FillType.FOREGROUND)
    layer.set_lock_alpha(False)


def _below(image, drawable, layer, name):
    """Insère `layer` juste sous `drawable`, à la taille de l'image."""
    image.insert_layer(layer, drawable.get_parent(), image.get_item_position(drawable) + 1)
    layer.set_name(name)
    layer.resize_to_image_size()
    return layer


def _finish(procedure, image):
    image.undo_group_end()
    Gimp.context_pop()
    Gimp.displays_flush()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def _begin(image):
    Gimp.context_push()
    image.undo_group_start()


# ---------------------------------------------------------------------------
#  Texte 3D
# ---------------------------------------------------------------------------

def text_3d(procedure, run_mode, image, drawables, config, data):
    """Effet 3D extrudé : copies décalées et assombries empilées sous le texte."""
    depth = 10       # nombre de copies
    step = 1         # décalage en px par copie

    _begin(image)
    try:
        for drawable in _targets(drawables):
            parent = drawable.get_parent()
            off = drawable.get_offsets()
            for i in range(1, depth + 1):
                dup = drawable.copy()
                image.insert_layer(dup, parent, image.get_item_position(drawable) + i)
                dup.set_name("%s 3D-%d" % (drawable.get_name(), i))
                dup.set_offsets(off.offset_x + step * i, off.offset_y + step * i)
                _apply(dup, "gegl:brightness-contrast",
                       {"brightness": -0.03 * i - 0.1, "contrast": 1.0})
    finally:
        result = _finish(procedure, image)
    return result


# ---------------------------------------------------------------------------
#  Lueur néon
# ---------------------------------------------------------------------------

def text_neon_glow(procedure, run_mode, image, drawables, config, data):
    """Lueur néon : copies colorées et floutées sous le texte, en mode Écran."""
    neon = Gegl.Color.new("#00ffff")

    _begin(image)
    try:
        for drawable in _targets(drawables):
            for radius, opacity, suffix in ((15.0, 85.0, ""), (5.0, 100.0, "-2")):
                glow = _below(image, drawable, drawable.copy(),
                              "%s Néon%s" % (drawable.get_name(), suffix))
                _fill_opaque(glow, neon)
                _apply(glow, "gegl:gaussian-blur",
                       {"std-dev-x": radius, "std-dev-y": radius})
                glow.set_mode(Gimp.LayerMode.SCREEN)
                glow.set_opacity(opacity)
    finally:
        result = _finish(procedure, image)
    return result


# ---------------------------------------------------------------------------
#  Chrome / Métal
# ---------------------------------------------------------------------------

def text_chrome(procedure, run_mode, image, drawables, config, data):
    """Aspect chromé : désaturation + estampage + contraste renforcé."""
    _begin(image)
    try:
        for drawable in _targets(drawables):
            _apply(drawable, "gegl:saturation", {"scale": 0.0})
            _apply(drawable, "gegl:emboss",
                   {"azimuth": 315.0, "elevation": 45.0, "depth": 3})
            _apply(drawable, "gegl:brightness-contrast",
                   {"contrast": 1.4, "brightness": 0.05})
    finally:
        result = _finish(procedure, image)
    return result


# ---------------------------------------------------------------------------
#  Texte avec contour
# ---------------------------------------------------------------------------

def text_outline(procedure, run_mode, image, drawables, config, data):
    """Contour : alpha du texte -> sélection agrandie -> remplissage sous le texte."""
    outline_size = 3
    outline_color = Gegl.Color.new("white")

    _begin(image)
    try:
        saved = None if Gimp.Selection.is_empty(image) else Gimp.Selection.save(image)
        for drawable in _targets(drawables):
            w, h = image.get_width(), image.get_height()
            outline = Gimp.Layer.new(image, "%s Contour" % drawable.get_name(), w, h,
                                     Gimp.ImageType.RGBA_IMAGE, 100.0, Gimp.LayerMode.NORMAL)
            image.insert_layer(outline, drawable.get_parent(),
                               image.get_item_position(drawable) + 1)
            image.select_item(Gimp.ChannelOps.REPLACE, drawable)
            Gimp.Selection.grow(image, outline_size)
            Gimp.context_set_foreground(outline_color)
            outline.edit_fill(Gimp.FillType.FOREGROUND)
        if saved is not None:
            image.select_item(Gimp.ChannelOps.REPLACE, saved)
            image.remove_channel(saved)
        else:
            Gimp.Selection.none(image)
    finally:
        result = _finish(procedure, image)
    return result


# ---------------------------------------------------------------------------
#  Ombre portée
# ---------------------------------------------------------------------------

def text_shadow(procedure, run_mode, image, drawables, config, data):
    """Ombre portée floutée et décalée sous le texte."""
    dx, dy = 4, 4
    blur = 8.0

    _begin(image)
    try:
        for drawable in _targets(drawables):
            shadow = drawable.copy()
            image.insert_layer(shadow, drawable.get_parent(),
                               image.get_item_position(drawable) + 1)
            shadow.set_name("%s Ombre" % drawable.get_name())
            off = drawable.get_offsets()
            shadow.set_offsets(off.offset_x + dx, off.offset_y + dy)
            shadow.resize_to_image_size()
            _fill_opaque(shadow, Gegl.Color.new("black"))
            _apply(shadow, "gegl:gaussian-blur", {"std-dev-x": blur, "std-dev-y": blur})
            shadow.set_opacity(60.0)
    finally:
        result = _finish(procedure, image)
    return result


# ---------------------------------------------------------------------------
#  Texte en arc
# ---------------------------------------------------------------------------

def _double_array(values):
    v = GObject.Value(Gimp.DoubleArray)
    Gimp.value_set_double_array(v, values)
    return v.get_value()


def text_arc(procedure, run_mode, image, drawables, config, data):
    """Courbe le calque en arc (filtre Courbure de GIMP, plug-in-curve-bend).

    Un calque texte est converti en pixels par l'opération.
    """
    pdb = Gimp.get_pdb()
    bend = pdb.lookup_procedure("plug-in-curve-bend")
    if bend is None:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error.new_literal(GLib.quark_from_string("photogimp"),
                                   "Le filtre « Courbure » (plug-in-curve-bend) est introuvable.", 0))

    # Courbe en cloche : bords à mi-hauteur, centre en haut (17 points max, -1 = inutilisé)
    xs = [0.0, 0.25, 0.5, 0.75, 1.0] + [-1.0] * 12
    ys = [0.5, 0.62, 0.66, 0.62, 0.5] + [-1.0] * 12

    error = None
    _begin(image)
    try:
        # Le filtre ne traiterait que la sélection : on la met de côté
        saved = None if Gimp.Selection.is_empty(image) else Gimp.Selection.save(image)
        Gimp.Selection.none(image)
        for drawable in _targets(drawables):
            cfg = bend.create_config()
            cfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
            cfg.set_property("image", image)
            cfg.set_core_object_array("drawables", [drawable])
            cfg.set_property("rotation", 0.0)
            cfg.set_property("smoothing", True)
            cfg.set_property("antialias", True)
            cfg.set_property("work-on-copy", False)
            cfg.set_property("curve-type", "smooth")
            cfg.set_property("upper-point-x", _double_array(xs))
            cfg.set_property("upper-point-y", _double_array(ys))
            cfg.set_property("lower-point-x", _double_array(xs))
            cfg.set_property("lower-point-y", _double_array(ys))
            res = bend.run(cfg)
            if res.index(0) != Gimp.PDBStatusType.SUCCESS:
                error = "Échec du filtre Courbure : %s" % pdb.get_last_error()
                break
        if saved is not None:
            image.select_item(Gimp.ChannelOps.REPLACE, saved)
            image.remove_channel(saved)
    finally:
        result = _finish(procedure, image)
    if error:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error.new_literal(GLib.quark_from_string("photogimp"), error, 0))
    return result


# ===========================================================================
#  Plugin registration
# ===========================================================================

class TextEffects(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-text-3d',
            'python-fu-text-neon-glow',
            'python-fu-text-chrome',
            'python-fu-text-outline',
            'python-fu-text-shadow',
            'python-fu-text-arc',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        effects = {
            'python-fu-text-3d': (
                text_3d,
                "Texte _3D",
                "Effet de texte 3D extrudé avec des copies décalées empilées.",
            ),
            'python-fu-text-neon-glow': (
                text_neon_glow,
                "Lueur _néon",
                "Ajoute une lueur néon autour du texte (calques flous en mode Écran).",
            ),
            'python-fu-text-chrome': (
                text_chrome,
                "_Chrome / Métal",
                "Reflet chromé / métallique par désaturation et estampage.",
            ),
            'python-fu-text-outline': (
                text_outline,
                "Texte avec _contour",
                "Ajoute un contour autour du texte (sélection agrandie et remplie).",
            ),
            'python-fu-text-shadow': (
                text_shadow,
                "Ombre _portée",
                "Ajoute une ombre portée floutée derrière le texte.",
            ),
            'python-fu-text-arc': (
                text_arc,
                "Texte en _arc",
                "Courbe le calque (texte) en arc.",
            ),
        }

        if name not in effects:
            return None

        entry = effects[name]
        func = entry[0]
        label = entry[1]
        doc = entry[2]

        procedure = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, func, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(
            Gimp.ProcedureSensitivityMask.DRAWABLE |
            Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(_(label), _(doc), name)
        procedure.set_menu_label(_(label))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Effets de texte")

        return procedure


Gimp.main(TextEffects.__gtype__, sys.argv)

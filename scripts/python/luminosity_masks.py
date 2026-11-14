#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Masques de luminosité
#   Masques de luminosité (Lumières, Ombres, Tons moyens) enregistrés
#   comme canaux pour des sélections tonales précises.
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GLib
import sys

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


def _select_luminosity(image, drawable):
    """Remplace la sélection par la luminosité du calque (blanc = sélectionné)."""
    temp = drawable.copy()
    image.insert_layer(temp, drawable.get_parent(), image.get_item_position(drawable))
    if temp.get_mask() is not None:
        temp.remove_mask(Gimp.MaskApplyMode.DISCARD)
    # Masque « copie en niveaux de gris du calque » = luminosité
    mask = temp.create_mask(Gimp.AddMaskType.COPY)
    temp.add_mask(mask)
    image.select_item(Gimp.ChannelOps.REPLACE, mask)
    image.remove_layer(temp)


def _save(image, name):
    channel = Gimp.Selection.save(image)
    channel.set_name(name)
    channel.set_visible(False)
    return channel


def generate_luminosity_masks(procedure, run_mode, image, drawables, config, data):
    """Crée 7 canaux : Lumières 1-3, Ombres 1-3, Tons moyens.

    Méthode classique (calculs de sélection GIMP) :
      L1 = luminosité,  O1 = 1 - L1
      L2 = L1 - O1,     L3 = L2 - O1
      O2 = O1 - L1,     O3 = O2 - L1
      Tons moyens = tout - L2 - O2
    """
    layers = [d for d in drawables if isinstance(d, Gimp.Layer)]
    if not layers:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error.new_literal(GLib.quark_from_string("photogimp"),
                                   _("Sélectionnez un calque."), 0))
    drawable = layers[0]

    image.undo_group_start()
    try:
        # Conserver la sélection de l'utilisateur
        saved = None if Gimp.Selection.is_empty(image) else Gimp.Selection.save(image)

        if drawable.is_group():
            visible = Gimp.Layer.new_from_visible(image, image, "_lum")
            image.insert_layer(visible, None, 0)
            _select_luminosity(image, visible)
            image.remove_layer(visible)
        else:
            _select_luminosity(image, drawable)

        l1 = _save(image, _("Lumières 1 (large)"))
        Gimp.Selection.invert(image)
        o1 = _save(image, _("Ombres 1 (large)"))

        image.select_item(Gimp.ChannelOps.REPLACE, l1)
        image.select_item(Gimp.ChannelOps.SUBTRACT, o1)
        l2 = _save(image, _("Lumières 2 (moyen)"))
        image.select_item(Gimp.ChannelOps.SUBTRACT, o1)
        _save(image, _("Lumières 3 (étroit)"))

        image.select_item(Gimp.ChannelOps.REPLACE, o1)
        image.select_item(Gimp.ChannelOps.SUBTRACT, l1)
        o2 = _save(image, _("Ombres 2 (moyen)"))
        image.select_item(Gimp.ChannelOps.SUBTRACT, l1)
        _save(image, _("Ombres 3 (étroit)"))

        Gimp.Selection.all(image)
        image.select_item(Gimp.ChannelOps.SUBTRACT, l2)
        image.select_item(Gimp.ChannelOps.SUBTRACT, o2)
        _save(image, _("Tons moyens"))

        if saved is not None:
            image.select_item(Gimp.ChannelOps.REPLACE, saved)
            image.remove_channel(saved)
        else:
            Gimp.Selection.none(image)
        image.set_selected_layers([drawable])
    finally:
        image.undo_group_end()
    Gimp.displays_flush()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class LuminosityMasks(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-luminosity-masks']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            generate_luminosity_masks, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Générer les masques de luminosité"),
            _("Crée 7 masques de luminosité (Lumières 1-3, Ombres 1-3, Tons moyens) "
              "sous forme de canaux. Chargez un canal comme sélection pour cibler "
              "précisément les tons clairs, moyens ou sombres."),
            name)
        procedure.set_menu_label(_("_Masques de luminosité"))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Select")

        return procedure


Gimp.main(LuminosityMasks.__gtype__, sys.argv)

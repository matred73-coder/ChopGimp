#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Configuration Densité +/-
#   Création en un clic des calques Éclaircir / Assombrir pour la retouche
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


def _gray_layer(image, name, mode):
    w, h = image.get_width(), image.get_height()
    ltype = (Gimp.ImageType.RGBA_IMAGE if image.get_base_type() == Gimp.ImageBaseType.RGB
             else Gimp.ImageType.GRAYA_IMAGE)
    return Gimp.Layer.new(image, name, w, h, ltype, 100.0, mode)


def dodge_burn_setup(procedure, run_mode, image, drawables, config, data):
    """Crée un ou deux calques gris 50 % en mode Superposition ou Lumière douce.

    Peindre en blanc éclaircit, peindre en noir assombrit ; le gris 50 % est
    neutre dans ces modes.
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-dodge-burn-setup')
        dialog = GimpUi.ProcedureDialog.new(procedure, config, _("Densité +/-"))
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    use_soft_light = config.get_property('soft-light')
    separate_layers = config.get_property('separate-layers')

    blend_mode = Gimp.LayerMode.SOFTLIGHT if use_soft_light else Gimp.LayerMode.OVERLAY

    # Insertion au-dessus du calque actif
    active = drawables[0] if drawables else None
    if isinstance(active, Gimp.Layer):
        parent = active.get_parent()
        position = image.get_item_position(active)
    else:
        parent, position = None, 0

    Gimp.context_push()
    image.undo_group_start()
    try:
        # Gris 50 % (sRGB 128) : neutre en Superposition / Lumière douce
        Gimp.context_set_foreground(Gegl.Color.new("#808080"))

        if separate_layers:
            group = Gimp.GroupLayer.new(image, _("Densité +/-"))
            image.insert_layer(group, parent, position)
            # Traverser : les modes des calques agissent sur l'image dessous
            group.set_mode(Gimp.LayerMode.PASS_THROUGH)

            burn = _gray_layer(image, _("Assombrir (peindre en noir)"), blend_mode)
            image.insert_layer(burn, group, 0)
            burn.fill(Gimp.FillType.FOREGROUND)

            dodge = _gray_layer(image, _("Éclaircir (peindre en blanc)"), blend_mode)
            image.insert_layer(dodge, group, 0)
            dodge.fill(Gimp.FillType.FOREGROUND)
            target = dodge
        else:
            target = _gray_layer(image, _("Densité +/-"), blend_mode)
            image.insert_layer(target, parent, position)
            target.fill(Gimp.FillType.FOREGROUND)

        image.set_selected_layers([target])
    finally:
        image.undo_group_end()
        Gimp.context_pop()

    # Prêt à peindre : blanc (éclaircir) à faible opacité
    Gimp.context_set_foreground(Gegl.Color.new("white"))
    Gimp.context_set_opacity(15.0)

    Gimp.displays_flush()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class DodgeBurnSetup(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-dodge-burn-setup']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            dodge_burn_setup, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Configuration Densité +/-"),
            _("Crée un ou deux calques gris 50 % en mode Superposition ou Lumière douce "
              "pour une retouche Densité +/- non destructive. "
              "Peignez en blanc pour éclaircir, en noir pour assombrir."),
            name)
        procedure.set_menu_label(_("_Densité +/- (Dodge && Burn)…"))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Retouche")

        procedure.add_boolean_argument("soft-light",
                                       _("Utiliser _Lumière douce"),
                                       _("Utiliser le mode Lumière douce au lieu de Superposition, "
                                         "pour un résultat plus subtil et naturel."),
                                       False, GObject.ParamFlags.READWRITE)

        procedure.add_boolean_argument("separate-layers",
                                       _("Calques _séparés Éclaircir/Assombrir"),
                                       _("Créer deux calques séparés (éclaircir / assombrir) "
                                         "dans un groupe, pour un contrôle indépendant."),
                                       True, GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(DodgeBurnSetup.__gtype__, sys.argv)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Configuration Densite +/-
#   One-click creation of dodge and burn layers for professional retouching
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


def dodge_burn_setup(procedure, run_mode, image, drawables, config, data):
    """Create Dodge & Burn layers filled with 50% gray.

    The user paints white to dodge (lighten) or black to burn (darken)
    on these layers, which are set to Overlay or Soft Light blend mode
    so that the 50% gray is invisible.
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-dodge-burn-setup')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    use_soft_light = config.get_property('soft-light')
    separate_layers = config.get_property('separate-layers')

    Gimp.context_push()
    image.undo_group_start()

    img_width = image.get_width()
    img_height = image.get_height()

    blend_mode = Gimp.LayerMode.SOFTLIGHT if use_soft_light else Gimp.LayerMode.OVERLAY

    # Get insertion position (above active layer)
    active_drawable = drawables[0] if drawables else image.get_active_drawable()
    parent = active_drawable.get_parent() if active_drawable else None
    position = 0
    if active_drawable:
        position = image.get_item_position(active_drawable)

    # 50% gray color
    gray_color = Gimp.RGB()
    gray_color.set(0.5, 0.5, 0.5)

    if separate_layers:
        # Create a group to hold both D&B layers
        group = Gimp.Layer.group_new(image)
        group.set_name("Dodge & Burn")
        image.insert_layer(group, parent, position)

        # Burn layer (bottom of group)
        burn_layer = Gimp.Layer.new(image, img_width, img_height,
                                    Gimp.ImageType.RGBA_IMAGE,
                                    "Assombrir (peindre en noir)",
                                    100.0, blend_mode)
        image.insert_layer(burn_layer, group, 0)

        # Fill burn layer with 50% gray
        Gimp.context_set_foreground(gray_color)
        burn_layer.edit_fill(Gimp.FillType.FOREGROUND)

        # Dodge layer (top of group)
        dodge_layer = Gimp.Layer.new(image, img_width, img_height,
                                     Gimp.ImageType.RGBA_IMAGE,
                                     "Eclaircir (peindre en blanc)",
                                     100.0, blend_mode)
        image.insert_layer(dodge_layer, group, 0)

        # Fill dodge layer with 50% gray
        dodge_layer.edit_fill(Gimp.FillType.FOREGROUND)

        # Set active layer to dodge layer for immediate use
        image.set_active_layer(dodge_layer)

    else:
        # Single combined D&B layer
        db_layer = Gimp.Layer.new(image, img_width, img_height,
                                  Gimp.ImageType.RGBA_IMAGE,
                                  "Dodge & Burn",
                                  100.0, blend_mode)
        image.insert_layer(db_layer, parent, position)

        # Fill with 50% gray
        Gimp.context_set_foreground(gray_color)
        db_layer.edit_fill(Gimp.FillType.FOREGROUND)

        image.set_active_layer(db_layer)

    # Set brush to a soft round brush for immediate painting
    # Set foreground to white (dodge) as default starting point
    white = Gimp.RGB()
    white.set(1.0, 1.0, 1.0)
    Gimp.context_set_foreground(white)

    # Set opacity to a low value for subtle work
    Gimp.context_set_opacity(15.0)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

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
            _("Configuration Densite +/-"),
            _("Creer un/des calque(s) gris 50% en mode Superposition ou Lumiere tamisee "
              "pour la retouche densite +/- non-destructive. "
              "Peignez en blanc pour eclaircir, en noir pour assombrir."),
            name)
        procedure.set_menu_label(_("_Densite +/- (Dodge && Burn)..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Retouching")

        procedure.add_boolean_argument("soft-light",
                                       _("Utiliser _Lumiere tamisee"),
                                       _("Utiliser le mode Lumiere tamisee au lieu de Superposition. "
                                         "La Lumiere tamisee donne un resultat plus subtil et naturel."),
                                       False, GObject.ParamFlags.READWRITE)

        procedure.add_boolean_argument("separate-layers",
                                       _("Calques _separes Eclaircir/Assombrir"),
                                       _("Creer deux calques separes (un pour eclaircir, un pour assombrir) "
                                         "dans un groupe, pour un controle independant."),
                                       True, GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(DodgeBurnSetup.__gtype__, sys.argv)

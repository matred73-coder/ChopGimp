#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Séparation de fréquences
#   Retouche beauté : calques basse / haute fréquence
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


def frequency_separation(procedure, run_mode, image, drawables, config, data):
    """Séparation de fréquences : calque « Basse fréquence » (couleur/tonalité,
    flou gaussien) + calque « Haute fréquence » (texture, mode Fusion du grain)
    dans un groupe. Les deux calques recomposent exactement l'original.
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-frequency-separation')
        dialog = GimpUi.ProcedureDialog.new(procedure, config, _("Séparation de fréquences"))
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    blur_radius = config.get_property('blur-radius')

    layers = [d for d in drawables if isinstance(d, Gimp.Layer) and not d.is_group()]
    if not layers:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error.new_literal(GLib.quark_from_string("photogimp"),
                                   _("Sélectionnez un calque (pas un groupe)."), 0))
    source = layers[0]

    Gimp.context_push()
    image.undo_group_start()
    try:
        parent = source.get_parent()
        position = image.get_item_position(source)

        group = Gimp.GroupLayer.new(image, _("Séparation de fréquences"))
        image.insert_layer(group, parent, position)

        # Basse fréquence : copie floutée (couleur / tonalité)
        low = source.copy()
        image.insert_layer(low, group, 0)
        low.set_name(_("Basse fréquence"))
        low.set_mode(Gimp.LayerMode.NORMAL)
        low.set_opacity(100.0)
        low.set_visible(True)
        blur = Gimp.DrawableFilter.new(low, "gegl:gaussian-blur", _("Flou gaussien"))
        cfg = blur.get_config()
        cfg.set_property("std-dev-x", float(blur_radius))
        cfg.set_property("std-dev-y", float(blur_radius))
        blur.update()
        low.merge_filter(blur)

        # Haute fréquence = original - basse fréquence + 50 % (Extraction de grain)
        tmp_low = low.copy()
        image.insert_layer(tmp_low, group, 0)
        high = source.copy()
        image.insert_layer(high, group, 0)
        high.set_opacity(100.0)
        high.set_visible(True)
        high.set_mode(Gimp.LayerMode.GRAIN_EXTRACT)
        merged = image.merge_down(high, Gimp.MergeType.CLIP_TO_BOTTOM_LAYER)
        merged.set_name(_("Haute fréquence"))
        # Recomposition : Fusion du grain au-dessus de la basse fréquence
        merged.set_mode(Gimp.LayerMode.GRAIN_MERGE)

        source.set_visible(False)
        image.set_selected_layers([merged])
    finally:
        image.undo_group_end()
        Gimp.context_pop()
    Gimp.displays_flush()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class FrequencySeparation(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-frequency-separation']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            frequency_separation, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Séparation de fréquences"),
            _("Sépare le calque en « Basse fréquence » (couleur/tonalité) et « Haute fréquence » "
              "(texture/détail) pour la retouche beauté. Peignez sur la basse fréquence pour "
              "lisser la couleur, sur la haute fréquence pour corriger la texture."),
            name)
        procedure.set_menu_label(_("Séparation de _fréquences…"))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Retouche")

        procedure.add_double_argument("blur-radius",
                                      _("Rayon de _flou"),
                                      _("Rayon du flou gaussien de la basse fréquence. "
                                        "Plus il est élevé, plus la haute fréquence contient de détails. "
                                        "Typique : 5-15 pour les portraits, 2-5 pour les photos produit."),
                                      1.0, 100.0, 10.0,
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(FrequencySeparation.__gtype__, sys.argv)

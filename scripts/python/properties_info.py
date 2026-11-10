#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Properties Info
#   Display comprehensive layer properties in a GTK dialog
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import GLib
import sys

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


def _format_size(bytes_val):
    """Format byte count to human-readable string."""
    if bytes_val < 1024:
        return f"{bytes_val} o"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} Ko"
    else:
        return f"{bytes_val / (1024 * 1024):.1f} Mo"


def _blend_mode_name(mode):
    """Return a French name for the blend mode."""
    mode_names = {
        Gimp.LayerMode.NORMAL: "Normal",
        Gimp.LayerMode.MULTIPLY: "Produit",
        Gimp.LayerMode.SCREEN: "Écran",
        Gimp.LayerMode.OVERLAY: "Superposition",
        Gimp.LayerMode.SOFTLIGHT: "Lumière tamisée",
        Gimp.LayerMode.HARDLIGHT: "Lumière crue",
        Gimp.LayerMode.DODGE: "Densité couleur -",
        Gimp.LayerMode.BURN: "Densité couleur +",
        Gimp.LayerMode.DARKEN_ONLY: "Assombrir",
        Gimp.LayerMode.LIGHTEN_ONLY: "Éclaircir",
        Gimp.LayerMode.DIFFERENCE: "Différence",
        Gimp.LayerMode.ADDITION: "Addition",
        Gimp.LayerMode.SUBTRACT: "Soustraire",
        Gimp.LayerMode.GRAIN_MERGE: "Fusion de grain",
        Gimp.LayerMode.GRAIN_EXTRACT: "Extraction de grain",
        Gimp.LayerMode.HSV_HUE: "Teinte TSV",
        Gimp.LayerMode.HSV_SATURATION: "Saturation TSV",
        Gimp.LayerMode.HSL_COLOR: "Couleur TSL",
        Gimp.LayerMode.HSV_VALUE: "Valeur TSV",
        Gimp.LayerMode.DIVIDE: "Diviser",
        Gimp.LayerMode.COLOR_ERASE: "Effacement couleur",
        Gimp.LayerMode.DISSOLVE: "Dissolution",
    }
    return mode_names.get(mode, str(mode))


def _image_type_name(img_type):
    """Return a French name for the image type."""
    type_names = {
        Gimp.ImageType.RGB_IMAGE: "RVB",
        Gimp.ImageType.RGBA_IMAGE: "RVB + Alpha",
        Gimp.ImageType.GRAY_IMAGE: "Niveaux de gris",
        Gimp.ImageType.GRAYA_IMAGE: "Niveaux de gris + Alpha",
        Gimp.ImageType.INDEXED_IMAGE: "Indexé",
        Gimp.ImageType.INDEXEDA_IMAGE: "Indexé + Alpha",
    }
    return type_names.get(img_type, str(img_type))


def properties_info(procedure, run_mode, image, drawables, config, data):
    """Show comprehensive properties of the active layer in a GTK dialog."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("props"),
                                                                  "Aucun calque actif.", 0))

    layer = drawables[0]
    pdb = Gimp.get_pdb()

    # Collect layer information
    info = []

    # --- General section ---
    info.append(("═══ GÉNÉRAL ═══", ""))
    info.append(("Nom", layer.get_name()))
    info.append(("Type", _image_type_name(layer.get_type())))
    info.append(("Largeur", f"{layer.get_width()} px"))
    info.append(("Hauteur", f"{layer.get_height()} px"))

    offsets = layer.get_offsets()
    info.append(("Position X", f"{offsets.offset_x} px"))
    info.append(("Position Y", f"{offsets.offset_y} px"))

    # --- Appearance ---
    info.append(("", ""))
    info.append(("═══ APPARENCE ═══", ""))
    info.append(("Opacité", f"{layer.get_opacity():.1f} %"))
    info.append(("Mode de fusion", _blend_mode_name(layer.get_mode())))
    info.append(("Visible", "Oui" if layer.get_visible() else "Non"))
    info.append(("Verrouillé (contenu)", "Oui" if layer.get_lock_content() else "Non"))
    info.append(("Verrouillé (alpha)", "Oui" if layer.get_lock_alpha() else "Non"))
    info.append(("Verrouillé (position)", "Oui" if layer.get_lock_position() else "Non"))

    # --- Properties ---
    info.append(("", ""))
    info.append(("═══ PROPRIÉTÉS ═══", ""))

    has_alpha = layer.has_alpha()
    info.append(("Canal alpha", "Oui" if has_alpha else "Non"))

    has_mask = layer.get_mask() is not None
    info.append(("Masque de calque", "Oui" if has_mask else "Non"))

    is_group = layer.is_group()
    info.append(("Groupe de calques", "Oui" if is_group else "Non"))

    # Check if text layer
    is_text = isinstance(layer, Gimp.TextLayer) if hasattr(Gimp, 'TextLayer') else False
    # Alternative check via PDB
    try:
        text_result = pdb.run_procedure('gimp-text-layer-get-text', [
            GObject.Value(Gimp.Layer, layer),
        ])
        text_content = text_result.index(1) if text_result else None
        is_text = text_content is not None
    except Exception:
        is_text = False
        text_content = None

    info.append(("Calque texte", "Oui" if is_text else "Non"))

    if is_text and text_content:
        info.append(("", ""))
        info.append(("═══ TEXTE ═══", ""))
        # Truncate long text
        display_text = text_content if len(str(text_content)) <= 100 else str(text_content)[:100] + "..."
        info.append(("Contenu", str(display_text)))
        try:
            font = pdb.run_procedure('gimp-text-layer-get-font', [
                GObject.Value(Gimp.Layer, layer),
            ]).index(1)
            info.append(("Police", str(font)))
        except Exception:
            pass
        try:
            font_size = pdb.run_procedure('gimp-text-layer-get-font-size', [
                GObject.Value(Gimp.Layer, layer),
            ])
            info.append(("Taille", f"{font_size.index(1):.1f}"))
        except Exception:
            pass
        try:
            color = pdb.run_procedure('gimp-text-layer-get-color', [
                GObject.Value(Gimp.Layer, layer),
            ]).index(1)
            info.append(("Couleur", str(color)))
        except Exception:
            pass

    # --- Image info ---
    info.append(("", ""))
    info.append(("═══ IMAGE ═══", ""))
    info.append(("Image", image.get_name()))
    info.append(("Dimensions image", f"{image.get_width()} × {image.get_height()} px"))

    try:
        profile = image.get_color_profile()
        if profile:
            info.append(("Profil couleur", "Présent"))
        else:
            info.append(("Profil couleur", "Aucun (sRGB par défaut)"))
    except Exception:
        info.append(("Profil couleur", "Non disponible"))

    # Memory estimate
    bpp = layer.get_bpp()
    mem_bytes = layer.get_width() * layer.get_height() * bpp
    info.append(("Mémoire calque (est.)", _format_size(mem_bytes)))

    # --- Build GTK dialog ---
    dialog = Gtk.Dialog(title="Propriétés du calque",
                        transient_for=None,
                        modal=True)
    dialog.add_button("_Fermer", Gtk.ResponseType.CLOSE)
    dialog.set_default_size(420, 500)

    content = dialog.get_content_area()
    content.set_spacing(6)
    content.set_margin_start(12)
    content.set_margin_end(12)
    content.set_margin_top(12)
    content.set_margin_bottom(12)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_vexpand(True)

    grid = Gtk.Grid()
    grid.set_column_spacing(16)
    grid.set_row_spacing(4)

    for row_idx, (label, value) in enumerate(info):
        if label.startswith("═══"):
            # Section header
            header = Gtk.Label()
            header.set_markup(f"<b>{label}</b>")
            header.set_halign(Gtk.Align.START)
            header.set_margin_top(8)
            grid.attach(header, 0, row_idx, 2, 1)
        elif label == "" and value == "":
            # Spacer
            spacer = Gtk.Label(label="")
            grid.attach(spacer, 0, row_idx, 2, 1)
        else:
            lbl = Gtk.Label()
            lbl.set_markup(f"<b>{label} :</b>")
            lbl.set_halign(Gtk.Align.END)
            lbl.set_valign(Gtk.Align.START)
            grid.attach(lbl, 0, row_idx, 1, 1)

            val = Gtk.Label(label=str(value))
            val.set_halign(Gtk.Align.START)
            val.set_selectable(True)
            val.set_line_wrap(True)
            grid.attach(val, 1, row_idx, 1, 1)

    scrolled.add(grid)
    content.pack_start(scrolled, True, True, 0)

    dialog.show_all()
    dialog.run()
    dialog.destroy()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class PropertiesInfo(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-properties-info',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-properties-info':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                properties_info, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Layer Properties"),
                _("Afficher les propriétés détaillées du calque actif : nom, type, taille, mode, masque, texte, etc."),
                name)
            procedure.set_menu_label(_("_Propriétés du calque"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Windows")

        else:
            return None

        return procedure


Gimp.main(PropertiesInfo.__gtype__, sys.argv)

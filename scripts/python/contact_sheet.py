#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Planche contact (Contact Sheet)
#   Generate a contact sheet / image grid from a folder of images.
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio
import os
import sys

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp',
                    '.webp', '.gif', '.xcf', '.psd', '.ora'}


def contact_sheet_run(procedure, run_mode, image, drawables, config, data):
    """Build a contact sheet from a folder of images."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-contact-sheet')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    input_folder  = config.get_property('input-folder')
    columns       = config.get_property('columns')
    rows          = config.get_property('rows')
    thumb_size    = config.get_property('thumb-size')
    spacing       = config.get_property('spacing')
    show_filename = config.get_property('show-filename')

    if input_folder is None:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR,
            GLib.Error("Aucun dossier source specifie."))

    folder_path = input_folder.get_path()
    if not os.path.isdir(folder_path):
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error(f"Le dossier n'existe pas : {folder_path}"))

    # Collect image files
    files = sorted([
        f for f in os.listdir(folder_path)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    ])

    if not files:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("Aucune image trouvee dans le dossier."))

    pdb = Gimp.get_pdb()

    # Compute sheet dimensions
    text_height = 20 if show_filename else 0
    cell_w = thumb_size + spacing
    cell_h = thumb_size + spacing + text_height
    max_per_page = columns * rows
    total_images = min(len(files), max_per_page)

    actual_rows = (total_images + columns - 1) // columns
    sheet_w = spacing + columns * cell_w
    sheet_h = spacing + actual_rows * cell_h

    # Create the contact sheet image
    sheet_image = Gimp.Image.new(sheet_w, sheet_h, Gimp.ImageBaseType.RGB)
    Gimp.Display.new(sheet_image)

    # White background layer
    bg_layer = Gimp.Layer.new(sheet_image, "Fond",
                              sheet_w, sheet_h,
                              Gimp.ImageType.RGB_IMAGE,
                              100.0, Gimp.LayerMode.NORMAL)
    sheet_image.insert_layer(bg_layer, None, 0)
    white_color = Gegl.Color.new("white")
    Gimp.context_set_foreground(white_color)
    bg_layer.edit_fill(Gimp.FillType.FOREGROUND)

    # Place each thumbnail
    for idx, filename in enumerate(files[:max_per_page]):
        col = idx % columns
        row = idx // columns
        x_pos = spacing + col * cell_w
        y_pos = spacing + row * cell_h

        filepath = os.path.join(folder_path, filename)
        gfile = Gio.File.new_for_path(filepath)

        try:
            # Load the image
            load_proc = pdb.lookup_procedure('gimp-file-load')
            load_cfg = load_proc.create_config()
            load_cfg.set_property('file', gfile)
            result = load_proc.run(load_cfg)
            src_image = result.index(1)

            if src_image is None:
                continue

            # Flatten and scale
            src_image.flatten()
            src_drawable = src_image.get_selected_drawables()[0]

            orig_w = src_image.get_width()
            orig_h = src_image.get_height()

            # Scale to fit within thumb_size x thumb_size
            ratio = min(thumb_size / orig_w, thumb_size / orig_h)
            new_w = max(1, int(orig_w * ratio))
            new_h = max(1, int(orig_h * ratio))
            src_image.scale_full(new_w, new_h, Gimp.InterpolationType.CUBIC)

            # Copy the scaled image
            src_drawable = src_image.get_selected_drawables()[0]
            Gimp.Selection.all(src_image)
            src_drawable.edit_copy()
            src_image.delete()

            # Paste as a new layer in the contact sheet
            floating = bg_layer.edit_paste(False)
            # Position the pasted layer
            center_x = x_pos + (thumb_size - new_w) // 2
            center_y = y_pos + (thumb_size - new_h) // 2
            floating.set_offsets(center_x, center_y)
            Gimp.floating_sel_anchor(floating)

            # Add filename text below the thumbnail
            if show_filename:
                display_name = os.path.splitext(filename)[0]
                if len(display_name) > 20:
                    display_name = display_name[:17] + "..."

                text_color = Gegl.Color.new("black")
                text_layer = Gimp.TextLayer.new(
                    sheet_image, display_name, "Sans", 10,
                    Gimp.Unit.point())
                sheet_image.insert_layer(text_layer, None, -1)
                text_layer.set_color(text_color)

                text_w = text_layer.get_width()
                text_x = x_pos + (thumb_size - text_w) // 2
                text_y = y_pos + thumb_size + 2
                text_layer.set_offsets(max(x_pos, text_x), text_y)

        except Exception:
            # Skip images that fail to load
            continue

    sheet_image.flatten()
    Gimp.displays_flush()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ContactSheet(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-contact-sheet']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            contact_sheet_run, None)
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.set_documentation(
            _("Planche contact"),
            _("Generer une planche contact (grille de vignettes) a partir d'un dossier "
              "d'images, avec nom de fichier optionnel sous chaque vignette."),
            name)
        procedure.set_menu_label(_("_Planche contact..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Workflow")

        procedure.add_file_argument("input-folder",
                                    _("_Dossier source"),
                                    _("Dossier contenant les images a inclure"),
                                    Gimp.FileChooserAction.SELECT_FOLDER,
                                    False, None,
                                    GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("columns", _("_Colonnes"),
                                   _("Nombre de colonnes de vignettes"),
                                   1, 20, 5,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("rows", _("_Lignes"),
                                   _("Nombre de lignes de vignettes"),
                                   1, 30, 6,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("thumb-size", _("_Taille vignette (px)"),
                                   _("Taille maximale de chaque vignette en pixels"),
                                   32, 1024, 200,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("spacing", _("E_spacement (px)"),
                                   _("Espacement entre les vignettes en pixels"),
                                   0, 100, 10,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("show-filename",
                                       _("Afficher le _nom de fichier"),
                                       _("Ajouter le nom de fichier sous chaque vignette"),
                                       True, GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(ContactSheet.__gtype__, sys.argv)

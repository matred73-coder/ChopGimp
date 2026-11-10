#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Fusion de donnees (Data Merge)
#   Photoshop-style Variables / Data-Driven Graphics:
#   Load CSV, replace text layers matching column headers, export variations.
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
import csv
import os
import sys

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


def _find_text_layers(image, layer=None):
    """Recursively find all text layers in the image, return dict {name: layer}."""
    result = {}
    if layer is None:
        children = image.get_layers()
    else:
        if hasattr(layer, 'get_children'):
            children = layer.get_children()
        else:
            children = []

    for child in children:
        if child.is_group():
            result.update(_find_text_layers(image, child))
        elif child.is_text_layer():
            result[child.get_name()] = child
    return result


def data_merge(procedure, run_mode, image, drawables, config, data):
    """Load CSV, replace text layers matching column headers, export each row."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi

        GimpUi.init('python-fu-data-merge')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    csv_file = config.get_property('csv-file')
    output_dir = config.get_property('output-folder')
    fmt = config.get_property('export-format')
    jpeg_quality = config.get_property('jpeg-quality')
    prefix = config.get_property('filename-prefix')

    # Validate CSV file
    if csv_file is None:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR,
            GLib.Error("Aucun fichier CSV specifie."))

    csv_path = csv_file.get_path()
    if not os.path.isfile(csv_path):
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error(f"Fichier CSV introuvable : {csv_path}"))

    # Validate output directory
    if output_dir is None:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR,
            GLib.Error("Aucun dossier de sortie specifie."))

    out_path = output_dir.get_path()
    os.makedirs(out_path, exist_ok=True)

    # Read CSV
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)
    except Exception as e:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error(f"Erreur lecture CSV : {e}"))

    if not headers or not rows:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("Le fichier CSV est vide ou sans en-tetes."))

    # Find text layers matching headers
    text_layers = _find_text_layers(image)
    matching_headers = [h for h in headers if h in text_layers]

    if not matching_headers:
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error(
                f"Aucun calque texte ne correspond aux en-tetes CSV.\n"
                f"En-tetes CSV : {', '.join(headers)}\n"
                f"Calques texte : {', '.join(text_layers.keys()) if text_layers else '(aucun)'}"))

    pdb = Gimp.get_pdb()
    Gimp.context_push()

    # Store original text for restoration
    original_texts = {}
    for header in matching_headers:
        layer = text_layers[header]
        original_texts[header] = layer.get_text()

    for row_idx, row in enumerate(rows):
        # Duplicate image for this row
        export_img = image.duplicate()
        export_text_layers = _find_text_layers(export_img)

        # Replace text in matching layers
        for header in matching_headers:
            if header in export_text_layers:
                layer = export_text_layers[header]
                value = row.get(header, '')
                layer.set_text(str(value))

        # Flatten for export
        export_img.flatten()
        export_drawable = export_img.get_selected_drawables()[0]

        # Build filename
        row_name = prefix + str(row_idx + 1).zfill(4)
        # Use first column value as part of name if available
        first_col = headers[0]
        if row.get(first_col):
            safe_name = "".join(c if c.isalnum() or c in '-_ ' else '_'
                                for c in str(row[first_col]))
            row_name = f"{prefix}{safe_name}_{row_idx + 1}"

        if fmt == "png":
            fpath = os.path.join(out_path, f"{row_name}.png")
            gfile = Gio.File.new_for_path(fpath)
            proc = pdb.lookup_procedure('file-png-export')
            pconfig = proc.create_config()
            pconfig.set_property('image', export_img)
            pconfig.set_property('file', gfile)
            pconfig.set_property('drawables',
                                 Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
            proc.run(pconfig)
        else:
            fpath = os.path.join(out_path, f"{row_name}.jpg")
            gfile = Gio.File.new_for_path(fpath)
            proc = pdb.lookup_procedure('file-jpeg-export')
            pconfig = proc.create_config()
            pconfig.set_property('image', export_img)
            pconfig.set_property('file', gfile)
            pconfig.set_property('drawables',
                                 Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
            pconfig.set_property('quality', jpeg_quality / 100.0)
            proc.run(pconfig)

        export_img.delete()

    Gimp.context_pop()
    Gimp.displays_flush()

    Gimp.message(f"Fusion de donnees terminee : {len(rows)} images exportees dans {out_path}")
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class DataMerge(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-data-merge']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            data_merge, None)
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.set_documentation(
            _("Data Merge — Fusion de donnees"),
            _("Charger un fichier CSV et generer une image par ligne en "
              "remplacant les calques texte correspondant aux en-tetes. "
              "Ideal pour badges, cartes de visite, certificats."),
            name)
        procedure.set_menu_label(_("_Fusion de donnees..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Workflow")

        procedure.add_file_argument("csv-file",
                                    _("Fichier _CSV"),
                                    _("Fichier CSV avec les donnees a fusionner"),
                                    Gimp.FileChooserAction.OPEN,
                                    False, None,
                                    GObject.ParamFlags.READWRITE)
        procedure.add_file_argument("output-folder",
                                    _("Dossier de _sortie"),
                                    _("Dossier de destination pour les images generees"),
                                    Gimp.FileChooserAction.SELECT_FOLDER,
                                    False, None,
                                    GObject.ParamFlags.READWRITE)

        fmt_choice = Gimp.Choice.new()
        fmt_choice.add("png", 0, _("PNG"), "")
        fmt_choice.add("jpeg", 1, _("JPEG"), "")
        procedure.add_choice_argument("export-format",
                                      _("_Format d'export"),
                                      _("Format de fichier pour les images exportees"),
                                      fmt_choice, "png",
                                      GObject.ParamFlags.READWRITE)

        procedure.add_int_argument("jpeg-quality",
                                   _("_Qualite JPEG"),
                                   _("Qualite JPEG si format JPEG selectionne (1-100)"),
                                   1, 100, 90,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_string_argument("filename-prefix",
                                      _("_Prefixe des fichiers"),
                                      _("Prefixe ajoute au nom de chaque fichier exporte"),
                                      "merge_",
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(DataMerge.__gtype__, sys.argv)

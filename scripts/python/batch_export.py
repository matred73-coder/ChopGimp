#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Batch Export
#   Export current or all open images in multiple formats/sizes
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


def batch_export(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi

        GimpUi.init('python-fu-batch-export')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    output_dir    = config.get_property('output-folder')
    export_jpeg   = config.get_property('export-jpeg')
    jpeg_quality  = config.get_property('jpeg-quality')
    export_png    = config.get_property('export-png')
    export_webp   = config.get_property('export-webp')
    export_tiff   = config.get_property('export-tiff')
    all_images    = config.get_property('all-images')
    resize_pct    = config.get_property('resize-percent')

    if output_dir is None:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR,
            GLib.Error("No output folder specified."))

    out_path = output_dir.get_path()
    if not os.path.isdir(out_path):
        try:
            os.makedirs(out_path, exist_ok=True)
        except OSError as e:
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error(f"Cannot create output folder: {e}"))

    pdb = Gimp.get_pdb()

    # Collect images to process
    if all_images:
        images = Gimp.list_images()
    else:
        images = [image]

    for img in images:
        # Get base name from image file or use "Untitled"
        file = img.get_file()
        if file is not None:
            basename = os.path.splitext(os.path.basename(file.get_path()))[0]
        else:
            basename = "Untitled"

        # Duplicate and flatten for export
        export_img = img.duplicate()
        export_img.flatten()

        # Resize if needed
        if resize_pct != 100:
            orig_w = export_img.get_width()
            orig_h = export_img.get_height()
            new_w = max(1, int(orig_w * resize_pct / 100))
            new_h = max(1, int(orig_h * resize_pct / 100))
            export_img.scale_full(new_w, new_h,
                                  Gimp.InterpolationType.CUBIC)

        export_drawable = export_img.get_selected_drawables()[0]

        # JPEG
        if export_jpeg:
            fpath = os.path.join(out_path, f"{basename}.jpg")
            gfile = Gio.File.new_for_path(fpath)
            proc = pdb.lookup_procedure('file-jpeg-export')
            pconfig = proc.create_config()
            pconfig.set_property('image', export_img)
            pconfig.set_property('file', gfile)
            pconfig.set_property('drawables', Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
            pconfig.set_property('quality', jpeg_quality / 100.0)
            proc.run(pconfig)

        # PNG
        if export_png:
            fpath = os.path.join(out_path, f"{basename}.png")
            gfile = Gio.File.new_for_path(fpath)
            proc = pdb.lookup_procedure('file-png-export')
            pconfig = proc.create_config()
            pconfig.set_property('image', export_img)
            pconfig.set_property('file', gfile)
            pconfig.set_property('drawables', Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
            proc.run(pconfig)

        # WebP
        if export_webp:
            fpath = os.path.join(out_path, f"{basename}.webp")
            gfile = Gio.File.new_for_path(fpath)
            proc = pdb.lookup_procedure('file-webp-export')
            pconfig = proc.create_config()
            pconfig.set_property('image', export_img)
            pconfig.set_property('file', gfile)
            pconfig.set_property('drawables', Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
            proc.run(pconfig)

        # TIFF
        if export_tiff:
            fpath = os.path.join(out_path, f"{basename}.tiff")
            gfile = Gio.File.new_for_path(fpath)
            proc = pdb.lookup_procedure('file-tiff-export')
            pconfig = proc.create_config()
            pconfig.set_property('image', export_img)
            pconfig.set_property('file', gfile)
            pconfig.set_property('drawables', Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
            proc.run(pconfig)

        export_img.delete()

    Gimp.displays_flush()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class BatchExport(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-batch-export']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            batch_export, None)
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.set_documentation(
            _("Export par lot en plusieurs formats"),
            _("Export current or all open images in JPEG, PNG, WebP, and/or TIFF "
              "with optional resize."),
            name)
        procedure.set_menu_label(_("_Export par lot..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/File")

        procedure.add_file_argument("output-folder",
                                    _("Output _Folder"),
                                    _("Dossier de destination pour les fichiers exportes"),
                                    Gimp.FileChooserAction.SELECT_FOLDER,
                                    False, None,
                                    GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("all-images",
                                       _("Exporter _toutes les images ouvertes"),
                                       _("Exporter toutes les images ouvertes (sinon l'image courante uniquement)"),
                                       False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("export-jpeg",
                                       _("_JPEG"), _("Exporter en JPEG"),
                                       True, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("jpeg-quality",
                                   _("_Qualite JPEG"),
                                   _("Qualite JPEG (1-100)"),
                                   1, 100, 85,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("export-png",
                                       _("_PNG"), _("Exporter en PNG"),
                                       False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("export-webp",
                                       _("_WebP"), _("Exporter en WebP"),
                                       False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("export-tiff",
                                       _("_TIFF"), _("Exporter en TIFF"),
                                       False, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("resize-percent",
                                   _("_Redimensionner %"),
                                   _("Pourcentage de redimensionnement (100 = taille originale)"),
                                   1, 1000, 100,
                                   GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(BatchExport.__gtype__, sys.argv)

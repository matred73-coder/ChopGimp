#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Processeur d'images (Image Processor)
#   Batch convert a folder of images to multiple formats with optional resize.
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
import json

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp',
                    '.webp', '.gif', '.xcf', '.psd', '.ora'}


def _load_and_apply_action(pdb, image, action_name):
    """Load and replay a saved action from the actions_recorder JSON store."""
    actions_dir = os.path.join(GLib.get_user_config_dir(), "GIMP", "3.0", "actions")
    action_file = os.path.join(actions_dir, f"{action_name}.json")

    if not os.path.isfile(action_file):
        return  # silently skip if action not found

    try:
        with open(action_file, 'r') as f:
            action_data = json.load(f)
    except Exception:
        return

    steps = action_data.get("steps", [])
    for step in steps:
        proc_name = step.get("procedure")
        args = step.get("args", {})
        proc = pdb.lookup_procedure(proc_name)
        if proc is None:
            continue
        try:
            pconfig = proc.create_config()
            pconfig.set_property('image', image)
            drawables = image.get_selected_drawables()
            if drawables:
                pconfig.set_property('drawables',
                                     Gimp.ObjectArray.new(Gimp.Drawable, drawables, False))
            for key, val in args.items():
                try:
                    pconfig.set_property(key, val)
                except Exception:
                    pass
            proc.run(pconfig)
        except Exception:
            continue


def image_processor_run(procedure, run_mode, image, drawables, config, data):
    """Batch process a folder of images: resize, apply action, export multi-format."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-image-processor')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    input_folder  = config.get_property('input-folder')
    output_folder = config.get_property('output-folder')
    save_jpeg     = config.get_property('save-jpeg')
    jpeg_quality  = config.get_property('jpeg-quality')
    save_png      = config.get_property('save-png')
    save_tiff     = config.get_property('save-tiff')
    save_webp     = config.get_property('save-webp')
    do_resize     = config.get_property('resize')
    max_width     = config.get_property('max-width')
    max_height    = config.get_property('max-height')
    action_name   = config.get_property('action-name')

    if input_folder is None or output_folder is None:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR,
            GLib.Error("Dossier source et/ou destination non specifie(s)."))

    in_path = input_folder.get_path()
    out_path = output_folder.get_path()

    if not os.path.isdir(in_path):
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error(f"Le dossier source n'existe pas : {in_path}"))

    os.makedirs(out_path, exist_ok=True)

    # Create sub-folders per format
    if save_jpeg:
        os.makedirs(os.path.join(out_path, "JPEG"), exist_ok=True)
    if save_png:
        os.makedirs(os.path.join(out_path, "PNG"), exist_ok=True)
    if save_tiff:
        os.makedirs(os.path.join(out_path, "TIFF"), exist_ok=True)
    if save_webp:
        os.makedirs(os.path.join(out_path, "WebP"), exist_ok=True)

    pdb = Gimp.get_pdb()

    # Collect files
    files = sorted([
        f for f in os.listdir(in_path)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    ])

    processed = 0

    for filename in files:
        filepath = os.path.join(in_path, filename)
        gfile = Gio.File.new_for_path(filepath)

        try:
            # Load
            load_proc = pdb.lookup_procedure('gimp-file-load')
            load_cfg = load_proc.create_config()
            load_cfg.set_property('file', gfile)
            result = load_proc.run(load_cfg)
            img = result.index(1)

            if img is None:
                continue

            img.flatten()
            basename = os.path.splitext(filename)[0]

            # Apply action if specified
            if action_name and action_name.strip():
                _load_and_apply_action(pdb, img, action_name.strip())

            # Resize if requested (fit within max_width x max_height)
            if do_resize:
                orig_w = img.get_width()
                orig_h = img.get_height()
                ratio = min(max_width / orig_w, max_height / orig_h)
                if ratio < 1.0:
                    new_w = max(1, int(orig_w * ratio))
                    new_h = max(1, int(orig_h * ratio))
                    img.scale_full(new_w, new_h, Gimp.InterpolationType.CUBIC)

            export_drawable = img.get_selected_drawables()[0]

            # Export JPEG
            if save_jpeg:
                fpath = os.path.join(out_path, "JPEG", f"{basename}.jpg")
                gf = Gio.File.new_for_path(fpath)
                proc = pdb.lookup_procedure('file-jpeg-export')
                pcfg = proc.create_config()
                pcfg.set_property('image', img)
                pcfg.set_property('file', gf)
                pcfg.set_property('drawables',
                                  Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
                pcfg.set_property('quality', jpeg_quality / 100.0)
                proc.run(pcfg)

            # Export PNG
            if save_png:
                fpath = os.path.join(out_path, "PNG", f"{basename}.png")
                gf = Gio.File.new_for_path(fpath)
                proc = pdb.lookup_procedure('file-png-export')
                pcfg = proc.create_config()
                pcfg.set_property('image', img)
                pcfg.set_property('file', gf)
                pcfg.set_property('drawables',
                                  Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
                proc.run(pcfg)

            # Export TIFF
            if save_tiff:
                fpath = os.path.join(out_path, "TIFF", f"{basename}.tiff")
                gf = Gio.File.new_for_path(fpath)
                proc = pdb.lookup_procedure('file-tiff-export')
                pcfg = proc.create_config()
                pcfg.set_property('image', img)
                pcfg.set_property('file', gf)
                pcfg.set_property('drawables',
                                  Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
                proc.run(pcfg)

            # Export WebP
            if save_webp:
                fpath = os.path.join(out_path, "WebP", f"{basename}.webp")
                gf = Gio.File.new_for_path(fpath)
                proc = pdb.lookup_procedure('file-webp-export')
                pcfg = proc.create_config()
                pcfg.set_property('image', img)
                pcfg.set_property('file', gf)
                pcfg.set_property('drawables',
                                  Gimp.ObjectArray.new(Gimp.Drawable, [export_drawable], False))
                proc.run(pcfg)

            img.delete()
            processed += 1

        except Exception:
            continue

    Gimp.displays_flush()
    Gimp.message(f"Processeur d'images : {processed}/{len(files)} images traitees.")
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ImageProcessor(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-image-processor']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            image_processor_run, None)
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.set_documentation(
            _("Processeur d'images"),
            _("Traitement par lot d'un dossier d'images : redimensionnement, "
              "application d'une action enregistree, export en JPEG/PNG/TIFF/WebP."),
            name)
        procedure.set_menu_label(_("_Processeur d'images..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters/Workflow")

        procedure.add_file_argument("input-folder",
                                    _("_Dossier source"),
                                    _("Dossier contenant les images a traiter"),
                                    Gimp.FileChooserAction.SELECT_FOLDER,
                                    False, None,
                                    GObject.ParamFlags.READWRITE)
        procedure.add_file_argument("output-folder",
                                    _("Dossier de _destination"),
                                    _("Dossier de sortie pour les images traitees"),
                                    Gimp.FileChooserAction.SELECT_FOLDER,
                                    False, None,
                                    GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("save-jpeg",
                                       _("Exporter en _JPEG"),
                                       _("Sauvegarder une copie JPEG de chaque image"),
                                       True, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("jpeg-quality",
                                   _("_Qualite JPEG"),
                                   _("Qualite JPEG (1-100)"),
                                   1, 100, 85,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("save-png",
                                       _("Exporter en _PNG"),
                                       _("Sauvegarder une copie PNG de chaque image"),
                                       False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("save-tiff",
                                       _("Exporter en _TIFF"),
                                       _("Sauvegarder une copie TIFF de chaque image"),
                                       False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("save-webp",
                                       _("Exporter en _WebP"),
                                       _("Sauvegarder une copie WebP de chaque image"),
                                       False, GObject.ParamFlags.READWRITE)
        procedure.add_boolean_argument("resize",
                                       _("_Redimensionner"),
                                       _("Redimensionner pour tenir dans les dimensions max"),
                                       False, GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("max-width",
                                   _("Largeur _max (px)"),
                                   _("Largeur maximale en pixels"),
                                   1, 30000, 1920,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_int_argument("max-height",
                                   _("_Hauteur max (px)"),
                                   _("Hauteur maximale en pixels"),
                                   1, 30000, 1080,
                                   GObject.ParamFlags.READWRITE)
        procedure.add_string_argument("action-name",
                                      _("_Action a appliquer"),
                                      _("Nom d'une action enregistree avec l'enregistreur d'actions "
                                        "(laisser vide pour aucune)"),
                                      "",
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(ImageProcessor.__gtype__, sys.argv)

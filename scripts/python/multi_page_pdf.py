#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#   PhotoGIMP Pro — Multi-Page PDF Export
#   Export layers as multi-page PDF
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import GObject, GLib
import sys, os, tempfile, subprocess


def pdf_export_run(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("multi_page_pdf")
        dialog = GimpUi.ProcedureDialog.new(procedure, config, "Export Multi-Page PDF")
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    output_path = config.get_property("output-file")
    if not output_path:
        output_path = os.path.expanduser("~/output.pdf")

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    layers = image.get_layers()

    if not layers:
        Gimp.message("No layers found.")
        image.undo_group_end()
        Gimp.context_pop()
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, GLib.Error())

    # Export each top-level layer as a temporary image then combine
    temp_dir = tempfile.mkdtemp(prefix="photogimp_pdf_")
    page_files = []

    for i, layer in enumerate(reversed(layers)):  # bottom to top = page order
        if not layer.get_visible():
            continue

        # Duplicate image, flatten to this layer only
        temp_image = image.duplicate()
        # Hide all layers except current one
        for tl in temp_image.get_layers():
            tl.set_visible(tl.get_name() == layer.get_name())

        temp_image.flatten()
        flat_layer = temp_image.get_active_drawable()

        # Export as temporary PDF page
        page_path = os.path.join(temp_dir, f"page_{i:04d}.pdf")
        pdb.run_procedure("file-pdf-export", [
            GObject.Value(Gimp.RunMode, Gimp.RunMode.NONINTERACTIVE),
            GObject.Value(Gimp.Image, temp_image),
            GObject.Value(GObject.TYPE_INT, 1),
            GObject.Value(Gimp.ObjectArray, [flat_layer]),
            GObject.Value(GLib.File, GLib.File.new_for_path(page_path)),
        ])
        page_files.append(page_path)
        temp_image.delete()

    # Try to merge PDFs
    if page_files:
        merged = False

        # Try pdfunite (poppler)
        try:
            subprocess.run(["pdfunite"] + page_files + [output_path],
                          check=True, capture_output=True)
            merged = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

        # Try qpdf
        if not merged:
            try:
                subprocess.run(["qpdf", "--empty", "--pages"] + page_files + ["--", output_path],
                              check=True, capture_output=True)
                merged = True
            except (FileNotFoundError, subprocess.CalledProcessError):
                pass

        if not merged and len(page_files) == 1:
            import shutil
            shutil.copy2(page_files[0], output_path)
            merged = True

        # Cleanup temp files
        for f in page_files:
            try:
                os.unlink(f)
            except OSError:
                pass
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass

        if merged:
            Gimp.message(f"PDF exported: {output_path}\n({len(page_files)} pages)")
        else:
            Gimp.message(f"Individual pages saved in {temp_dir}\n"
                        f"Install 'pdfunite' or 'qpdf' to merge automatically.\n"
                        f"  sudo apt install poppler-utils")

    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class MultiPagePdf(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["photogimp-multi-page-pdf"]

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, pdf_export_run, None)
        procedure.set_menu_label("Exporter PDF multi-pages...")
        procedure.set_icon_name("document-save")
        procedure.add_menu_path("<Image>/File/")
        procedure.set_documentation("Multi-Page PDF", "Export layers as PDF pages", name)
        procedure.set_attribution("PhotoGIMP Pro", "PhotoGIMP Pro", "2026")
        procedure.add_string_argument("output-file", "Fichier de sortie", "PDF output path", os.path.expanduser("~/output.pdf"), GObject.ParamFlags.READWRITE)
        return procedure

Gimp.main(MultiPagePdf.__gtype__, sys.argv)

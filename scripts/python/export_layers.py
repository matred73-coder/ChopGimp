#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Export All Layers
#   Export every layer as a separate file (PNG, JPEG, WebP, TIFF, PDF)
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio
import sys
import os

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


FORMATS = {
    "PNG":  (".png",  "file-png-save"),
    "JPEG": (".jpg",  "file-jpeg-save"),
    "WebP": (".webp", "file-webp-save"),
    "TIFF": (".tiff", "file-tiff-save"),
    "PDF":  (".pdf",  "file-pdf-save"),
}


def collect_layers(image, group=None, visible_only=True):
    """Recursively collect layers. Returns list of (layer, path_parts)."""
    result = []
    children = group.get_children() if group else image.get_layers()
    for layer in children:
        if visible_only and not layer.get_visible():
            continue
        if layer.is_group():
            sub = collect_layers(image, layer, visible_only)
            group_name = layer.get_name()
            for sublayer, parts in sub:
                result.append((sublayer, [group_name] + parts))
        else:
            result.append((layer, []))
    return result


def export_single_layer(image, layer, filepath, fmt_key, pdb, crop_to_content):
    """Duplicate image, keep only the target layer, export."""
    dup_image = image.duplicate()

    # Flatten to single layer matching the target
    # Remove all layers except the one matching our target
    all_layers = dup_image.get_layers()

    # Instead of selective removal, flatten then replace content:
    # Simpler: duplicate image, flatten, then just export
    # Better approach: create new image from layer

    # Create a new image from the layer
    w = layer.get_width()
    h = layer.get_height()

    new_image = Gimp.Image.new(w, h, image.get_base_type())
    new_layer = Gimp.Layer.new_from_drawable(layer, new_image)
    new_image.insert_layer(new_layer, None, 0)
    new_layer.set_offsets(0, 0)

    if crop_to_content:
        new_image.crop(
            new_layer.get_width(), new_layer.get_height(),
            0, 0)
        # Autocrop
        try:
            pdb.run_procedure("gimp-image-crop", [
                new_image,
                new_layer.get_width(),
                new_layer.get_height(),
                0, 0])
        except Exception:
            pass
        try:
            pdb.run_procedure("plug-in-autocrop", [new_image, new_layer])
        except Exception:
            pass

    # Flatten for export
    merged = new_image.flatten()

    # Export using PDB
    gfile = Gio.File.new_for_path(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext == ".png":
            pdb.run_procedure("file-png-save", [
                new_image, [merged], gfile,
                0,   # interlace
                9,   # compression
                1,   # save background
                1,   # save gamma
                1,   # save offset
                1,   # save resolution
                1,   # save creation time
                0,   # save color profile
            ])
        elif ext == ".jpg":
            pdb.run_procedure("file-jpeg-save", [
                new_image, [merged], gfile,
                0.92,  # quality
                0.0,   # smoothing
                1,     # optimize
                1,     # progressive
                "",    # comment
                0,     # subsmp
                1,     # baseline
                0,     # restart
                0,     # dct
            ])
        elif ext == ".webp":
            pdb.run_procedure("file-webp-save", [
                new_image, [merged], gfile,
                0,     # preset
                0,     # lossless
                90.0,  # quality
                100.0, # alpha quality
                0,     # animation
                0,     # loop
                0,     # minimize size
                0,     # kf distance
                0,     # exif
                0,     # iptc
                0,     # xmp
                0,     # delay
                0,     # force delay
            ])
        elif ext in (".tif", ".tiff"):
            pdb.run_procedure("file-tiff-save", [
                new_image, [merged], gfile, 0])
        elif ext == ".pdf":
            pdb.run_procedure("file-pdf-save", [
                new_image, [merged], gfile,
                0, 1, 1, 1, 0])
        else:
            # Fallback: try generic export
            pdb.run_procedure("gimp-file-overwrite", [
                new_image, merged, filepath])
    except Exception as e:
        # Try the generic file-save approach
        try:
            Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, new_image, [merged], gfile)
        except Exception:
            pass

    # Clean up
    new_image.delete()
    dup_image.delete()


def run_export_layers(procedure, run_mode, image, drawables, config, data):
    """Main plugin: dialog to configure export, then export each layer."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("python-fu-export-layers")

        dialog = Gtk.Dialog(title="Export All Layers", flags=0)
        dialog.set_default_size(480, 350)
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Export", Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_border_width(12)

        # Output folder
        hbox_dir = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_dir.pack_start(Gtk.Label(label="Output folder:"), False, False, 0)
        folder_chooser = Gtk.FileChooserButton(
            title="Select Output Folder",
            action=Gtk.FileChooserAction.SELECT_FOLDER)
        folder_chooser.set_current_folder(
            os.path.expanduser("~/Pictures"))
        hbox_dir.pack_start(folder_chooser, True, True, 0)
        content.pack_start(hbox_dir, False, False, 0)

        # Format
        hbox_fmt = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_fmt.pack_start(Gtk.Label(label="Format:"), False, False, 0)
        fmt_combo = Gtk.ComboBoxText()
        for fmt in FORMATS:
            fmt_combo.append_text(fmt)
        fmt_combo.set_active(0)
        hbox_fmt.pack_start(fmt_combo, False, False, 0)
        content.pack_start(hbox_fmt, False, False, 0)

        # Naming
        hbox_naming = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_naming.pack_start(Gtk.Label(label="Naming:"), False, False, 0)
        naming_combo = Gtk.ComboBoxText()
        naming_combo.append_text("Layer name")
        naming_combo.append_text("Sequential (001, 002, ...)")
        naming_combo.set_active(0)
        hbox_naming.pack_start(naming_combo, False, False, 0)
        content.pack_start(hbox_naming, False, False, 0)

        # Options
        chk_visible = Gtk.CheckButton(label="Visible layers only")
        chk_visible.set_active(True)
        content.pack_start(chk_visible, False, False, 0)

        chk_crop = Gtk.CheckButton(label="Crop each layer to content")
        chk_crop.set_active(False)
        content.pack_start(chk_crop, False, False, 0)

        chk_groups = Gtk.CheckButton(label="Layer groups as subfolders")
        chk_groups.set_active(True)
        content.pack_start(chk_groups, False, False, 0)

        # Status
        status = Gtk.Label(label="")
        status.set_xalign(0)
        content.pack_start(status, False, False, 0)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            out_dir = folder_chooser.get_filename()
            fmt_key = fmt_combo.get_active_text()
            use_names = naming_combo.get_active() == 0
            visible_only = chk_visible.get_active()
            crop = chk_crop.get_active()
            use_subfolders = chk_groups.get_active()

            dialog.destroy()

            if not out_dir:
                out_dir = os.path.expanduser("~/Pictures")

            os.makedirs(out_dir, exist_ok=True)

            ext = FORMATS[fmt_key][0]
            pdb = Gimp.get_pdb()

            layers = collect_layers(image, visible_only=visible_only)
            count = 0

            for i, (layer, path_parts) in enumerate(layers):
                if use_names:
                    # Sanitize layer name for filesystem
                    safe_name = layer.get_name()
                    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                        safe_name = safe_name.replace(ch, '_')
                    filename = f"{safe_name}{ext}"
                else:
                    filename = f"{i+1:03d}{ext}"

                if use_subfolders and path_parts:
                    sub = os.path.join(out_dir, *path_parts)
                    os.makedirs(sub, exist_ok=True)
                    filepath = os.path.join(sub, filename)
                else:
                    filepath = os.path.join(out_dir, filename)

                export_single_layer(image, layer, filepath, fmt_key, pdb, crop)
                count += 1

            Gimp.message(f"{count} calque(s) exporte(s) dans {out_dir}")
        else:
            dialog.destroy()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ExportLayers(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-export-layers']

    def do_create_procedure(self, name):
        if name == 'python-fu-export-layers':
            procedure = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, run_export_layers, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(
                Gimp.ProcedureSensitivityMask.DRAWABLE |
                Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Exporter tous les calques..."),
                _("Exporter chaque calque en fichier separe (PNG, JPEG, WebP, TIFF, PDF)."),
                name)
            procedure.set_menu_label(_("Exporter tous les _calques..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/File")
            return procedure

        return None


Gimp.main(ExportLayers.__gtype__, sys.argv)

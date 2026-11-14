#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Icon Generator
#   Generate multi-size icon sets (favicon, iOS, Android, custom) from current image
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gio
import sys
import os

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


ICON_PRESETS = {
    "Favicon": {
        "sizes": [16, 32, 48, 64, 96, 128, 192, 256, 512],
        "prefix": "favicon",
    },
    "iOS": {
        "sizes": [20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 1024],
        "prefix": "ios-icon",
    },
    "Android": {
        "sizes": [36, 48, 72, 96, 144, 192, 512],
        "prefix": "android-icon",
    },
}

ANDROID_DENSITY = {
    36: "ldpi",
    48: "mdpi",
    72: "hdpi",
    96: "xhdpi",
    144: "xxhdpi",
    192: "xxxhdpi",
    512: "playstore",
}


def export_icon_size(image, size, filepath, pdb):
    """Duplicate image, scale to size x size, export as PNG."""
    dup = image.duplicate()

    # Scale with cubic interpolation
    dup.scale_full(size, size, Gimp.InterpolationType.CUBIC)

    # Flatten
    merged = dup.flatten()

    # Exporter en PNG
    gfile = Gio.File.new_for_path(filepath)
    try:
        pdb.run_procedure("file-png-save", [
            dup, [merged], gfile,
            0,   # interlace
            9,   # compression
            1,   # save background
            1,   # save gamma
            1,   # save offset
            1,   # save resolution
            1,   # save creation time
            0,   # save color profile
        ])
    except Exception:
        # Fallback to generic save
        try:
            Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, dup, [merged], gfile)
        except Exception:
            pass

    dup.delete()


def run_icon_generator(procedure, run_mode, image, drawables, config, data):
    """Main plugin: dialog to select presets and sizes, then generate icons."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("python-fu-icon-generator")

        dialog = Gtk.Dialog(title="Generate Icons", flags=0)
        dialog.set_default_size(500, 480)
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Generate", Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_border_width(12)

        # Output folder
        hbox_dir = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_dir.pack_start(Gtk.Label(label="Output folder:"), False, False, 0)
        folder_chooser = Gtk.FileChooserButton(
            title="Select Output Folder",
            action=Gtk.FileChooserAction.SELECT_FOLDER)
        folder_chooser.set_current_folder(os.path.expanduser("~/Pictures/icons"))
        hbox_dir.pack_start(folder_chooser, True, True, 0)
        content.pack_start(hbox_dir, False, False, 0)

        # Preset checkboxes
        frame_presets = Gtk.Frame(label="Icon Presets")
        vbox_presets = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox_presets.set_border_width(8)

        chk_presets = {}
        for preset_name, preset_data in ICON_PRESETS.items():
            sizes_str = ", ".join(str(s) for s in preset_data["sizes"])
            chk = Gtk.CheckButton(label=f"{preset_name}  ({sizes_str})")
            chk.set_active(preset_name == "Favicon")
            chk_presets[preset_name] = chk
            vbox_presets.pack_start(chk, False, False, 0)

        frame_presets.add(vbox_presets)
        content.pack_start(frame_presets, False, False, 0)

        # Custom sizes
        frame_custom = Gtk.Frame(label="Custom Sizes")
        vbox_custom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox_custom.set_border_width(8)

        chk_custom = Gtk.CheckButton(label="Enable custom sizes")
        chk_custom.set_active(False)
        vbox_custom.pack_start(chk_custom, False, False, 0)

        hbox_custom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_custom.pack_start(
            Gtk.Label(label="Sizes (comma-separated):"), False, False, 0)
        custom_entry = Gtk.Entry()
        custom_entry.set_text("24, 48, 64, 128, 256")
        custom_entry.set_sensitive(False)
        hbox_custom.pack_start(custom_entry, True, True, 0)
        vbox_custom.pack_start(hbox_custom, False, False, 0)

        hbox_prefix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox_prefix.pack_start(Gtk.Label(label="Prefix:"), False, False, 0)
        prefix_entry = Gtk.Entry()
        prefix_entry.set_text("icon")
        prefix_entry.set_sensitive(False)
        hbox_prefix.pack_start(prefix_entry, True, True, 0)
        vbox_custom.pack_start(hbox_prefix, False, False, 0)

        def on_custom_toggle(_widget):
            active = chk_custom.get_active()
            custom_entry.set_sensitive(active)
            prefix_entry.set_sensitive(active)
        chk_custom.connect("toggled", on_custom_toggle)

        frame_custom.add(vbox_custom)
        content.pack_start(frame_custom, False, False, 0)

        # Info label
        info_label = Gtk.Label()
        info_label.set_markup(
            "<small>Source image will be scaled to square. "
            "Best results with a square source image.</small>")
        info_label.set_xalign(0)
        content.pack_start(info_label, False, False, 0)

        # Progress
        progress = Gtk.ProgressBar()
        progress.set_show_text(True)
        content.pack_start(progress, False, False, 0)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            out_dir = folder_chooser.get_filename()
            if not out_dir:
                out_dir = os.path.expanduser("~/Pictures/icons")
            os.makedirs(out_dir, exist_ok=True)

            pdb = Gimp.get_pdb()

            # Collect all sizes to generate
            tasks = []  # list of (size, filepath)

            for preset_name, chk in chk_presets.items():
                if not chk.get_active():
                    continue
                preset = ICON_PRESETS[preset_name]
                prefix = preset["prefix"]
                sub_dir = os.path.join(out_dir, preset_name.lower())
                os.makedirs(sub_dir, exist_ok=True)

                for size in preset["sizes"]:
                    if preset_name == "Android" and size in ANDROID_DENSITY:
                        fname = f"{prefix}-{ANDROID_DENSITY[size]}-{size}x{size}.png"
                    else:
                        fname = f"{prefix}-{size}x{size}.png"
                    tasks.append((size, os.path.join(sub_dir, fname)))

            # Custom sizes
            if chk_custom.get_active():
                raw = custom_entry.get_text().strip()
                prefix = prefix_entry.get_text().strip() or "icon"
                sub_dir = os.path.join(out_dir, "custom")
                os.makedirs(sub_dir, exist_ok=True)
                for part in raw.split(","):
                    part = part.strip()
                    try:
                        size = int(part)
                        if 1 <= size <= 4096:
                            fname = f"{prefix}-{size}x{size}.png"
                            tasks.append((size, os.path.join(sub_dir, fname)))
                    except ValueError:
                        pass

            dialog.destroy()

            # Generate icons
            total = len(tasks)
            for i, (size, filepath) in enumerate(tasks):
                progress.set_text(f"Generating {size}x{size}... ({i+1}/{total})")
                progress.set_fraction((i + 0.5) / max(total, 1))
                while Gtk.events_pending():
                    Gtk.main_iteration()

                export_icon_size(image, size, filepath, pdb)

            Gimp.message(f"{total} icone(s) generee(s) dans {out_dir}")
        else:
            dialog.destroy()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class IconGenerator(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-icon-generator']

    def do_create_procedure(self, name):
        if name == 'python-fu-icon-generator':
            procedure = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, run_icon_generator, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(
                Gimp.ProcedureSensitivityMask.DRAWABLE |
                Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Generer des icones..."),
                _("Generer des jeux d'icones multi-tailles (favicon, iOS, Android) a partir de l'image courante."),
                name)
            procedure.set_menu_label(_("Generer des _icones..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/File")
            return procedure

        return None


Gimp.main(IconGenerator.__gtype__, sys.argv)

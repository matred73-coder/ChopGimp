#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Google Fonts Installer
#   Install popular Google Fonts directly in GIMP
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
import sys
import os
import zipfile
import tempfile
import subprocess
import urllib.request

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

FONTS_DIR = os.path.expanduser("~/.local/share/fonts/google-fonts")
GF_DL_URL = "https://fonts.google.com/download?family={}"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"

# Curated list of popular Google Fonts, grouped by category
GOOGLE_FONTS = {
    "Sans-Serif": [
        "Roboto", "Open Sans", "Lato", "Montserrat", "Oswald", "Poppins",
        "Raleway", "Ubuntu", "Nunito", "Work Sans", "Inter", "Rubik",
        "Noto Sans", "PT Sans", "Mukta", "Cabin", "Karla", "Manrope",
        "DM Sans", "Quicksand",
    ],
    "Serif": [
        "Merriweather", "Playfair Display", "Lora", "PT Serif",
        "Noto Serif", "Libre Baskerville", "EB Garamond", "Crimson Text",
        "Bitter", "Cormorant Garamond",
    ],
    "Display": [
        "Bebas Neue", "Lobster", "Pacifico", "Righteous", "Abril Fatface",
        "Alfa Slab One", "Permanent Marker", "Bungee", "Fredoka One",
        "Titan One",
    ],
    "Handwriting": [
        "Dancing Script", "Caveat", "Satisfy", "Great Vibes",
        "Kaushan Script", "Sacramento", "Parisienne", "Cookie",
        "Indie Flower", "Shadows Into Light",
    ],
    "Monospace": [
        "Source Code Pro", "Fira Code", "Roboto Mono", "JetBrains Mono",
        "Ubuntu Mono", "IBM Plex Mono", "Space Mono", "Inconsolata",
        "Cousine", "Anonymous Pro",
    ],
}


def download_google_font(family):
    """Download a Google Font family zip, extract and install .ttf/.otf files."""
    os.makedirs(FONTS_DIR, exist_ok=True)

    encoded = urllib.parse.quote(family) if hasattr(urllib, 'parse') else family.replace(" ", "+")
    url = GF_DL_URL.format(encoded)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    installed = []
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                for member in zf.namelist():
                    lower = member.lower()
                    if lower.endswith((".ttf", ".otf")) and "__MACOSX" not in member:
                        basename = os.path.basename(member)
                        if not basename:
                            continue
                        dest = os.path.join(FONTS_DIR, basename)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        installed.append(basename)
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        return [], str(e)

    return installed, None


import urllib.parse  # noqa: E402 (ensure available)


def run_google_fonts(procedure, run_mode, image, drawables, config, data):
    """Main plugin entry: show font browser, download selected families."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("python-fu-google-fonts")

        dialog = Gtk.Dialog(title="Google Fonts Installer", flags=0)
        dialog.set_default_size(550, 550)
        dialog.add_button("_Close", Gtk.ResponseType.CLOSE)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_border_width(12)

        # Category filter
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox.pack_start(Gtk.Label(label="Category:"), False, False, 0)

        cat_combo = Gtk.ComboBoxText()
        cat_combo.append_text("All")
        for cat in GOOGLE_FONTS:
            cat_combo.append_text(cat)
        cat_combo.set_active(0)
        hbox.pack_start(cat_combo, False, False, 0)

        # Select all / none
        sel_all_btn = Gtk.Button(label="Select All")
        sel_none_btn = Gtk.Button(label="Select None")
        hbox.pack_end(sel_none_btn, False, False, 0)
        hbox.pack_end(sel_all_btn, False, False, 0)

        content.pack_start(hbox, False, False, 0)

        # Font list: selected, name, category
        store = Gtk.ListStore(bool, str, str)
        model_filter = store.filter_new()

        def populate_store(category="All"):
            store.clear()
            for cat, fonts in GOOGLE_FONTS.items():
                if category != "All" and cat != category:
                    continue
                for font in fonts:
                    store.append([False, font, cat])

        populate_store()

        tree = Gtk.TreeView(model=store)
        tree.set_headers_visible(True)

        toggle_render = Gtk.CellRendererToggle()
        toggle_render.set_property("activatable", True)

        def on_toggle(widget, path):
            store[path][0] = not store[path][0]
        toggle_render.connect("toggled", on_toggle)

        col_sel = Gtk.TreeViewColumn("", toggle_render, active=0)
        col_sel.set_fixed_width(40)
        tree.append_column(col_sel)

        name_render = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn("Font Family", name_render, text=1)
        col_name.set_expand(True)
        tree.append_column(col_name)

        cat_render = Gtk.CellRendererText()
        col_cat = Gtk.TreeViewColumn("Category", cat_render, text=2)
        col_cat.set_fixed_width(120)
        tree.append_column(col_cat)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add(tree)
        content.pack_start(scroll, True, True, 0)

        # Install button
        install_btn = Gtk.Button(label="Install Selected Fonts")
        content.pack_start(install_btn, False, False, 0)

        # Progress
        progress = Gtk.ProgressBar()
        progress.set_show_text(True)
        progress.set_text("Select fonts and click Install.")
        content.pack_start(progress, False, False, 0)

        def on_cat_changed(_widget):
            cat = cat_combo.get_active_text()
            populate_store(cat)
        cat_combo.connect("changed", on_cat_changed)

        def on_sel_all(_widget):
            for row in store:
                row[0] = True
        sel_all_btn.connect("clicked", on_sel_all)

        def on_sel_none(_widget):
            for row in store:
                row[0] = False
        sel_none_btn.connect("clicked", on_sel_none)

        def do_install(_widget):
            selected = [(row[1], row[2]) for row in store if row[0]]
            if not selected:
                progress.set_text("No fonts selected.")
                progress.set_fraction(0)
                return

            total = len(selected)
            installed_count = 0
            errors = []

            for i, (family, _cat) in enumerate(selected):
                progress.set_text(f"Downloading {family}... ({i+1}/{total})")
                progress.set_fraction((i + 0.5) / total)
                while Gtk.events_pending():
                    Gtk.main_iteration()

                files, err = download_google_font(family)
                if err:
                    errors.append(f"{family}: {err}")
                else:
                    installed_count += len(files)

                progress.set_fraction((i + 1) / total)
                while Gtk.events_pending():
                    Gtk.main_iteration()

            # fc-cache
            try:
                subprocess.run(["fc-cache", "-f", FONTS_DIR], timeout=30,
                               capture_output=True)
            except Exception:
                pass

            # Refresh GIMP fonts
            pdb = Gimp.get_pdb()
            try:
                pdb.run_procedure("gimp-fonts-refresh", [])
            except Exception:
                pass

            if errors:
                progress.set_text(
                    f"Done: {installed_count} files. Errors: {len(errors)}")
            else:
                progress.set_text(
                    f"Installed {installed_count} font file(s) to {FONTS_DIR}")

        install_btn.connect("clicked", do_install)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class GoogleFontsInstaller(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-google-fonts']

    def do_create_procedure(self, name):
        if name == 'python-fu-google-fonts':
            procedure = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, run_google_fonts, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(
                Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Google Fonts..."),
                _("Parcourir et installer les polices Google Fonts populaires directement dans GIMP."),
                name)
            procedure.set_menu_label(_("_Google Fonts..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Typography")
            return procedure

        return None


Gimp.main(GoogleFontsInstaller.__gtype__, sys.argv)

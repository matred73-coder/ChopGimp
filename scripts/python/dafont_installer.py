#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — DaFont Installer
#   Browse and install fonts from DaFont directly in GIMP
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
import urllib.parse
from html.parser import HTMLParser

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


FONTS_DIR = os.path.expanduser("~/.local/share/fonts")
DAFONT_BASE = "https://www.dafont.com"
DAFONT_SEARCH = "https://www.dafont.com/search.php?q={}"
DAFONT_DL = "https://dl.dafont.com/dl/?f={}"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"


class DaFontParser(HTMLParser):
    """Parse DaFont search results to extract font names and download slugs."""

    def __init__(self):
        super().__init__()
        self.fonts = []
        self._in_preview = False
        self._current_font = None
        self._in_author = False
        self._current_author = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        # Font preview links: <a class="preview" href="/fontname.font">
        if tag == "a":
            href = attrs_dict.get("href", "")
            cls = attrs_dict.get("class", "")
            if "preview" in cls and href.endswith(".font"):
                slug = href.rsplit("/", 1)[-1].replace(".font", "")
                self._current_font = slug
                self._in_preview = True

    def handle_data(self, data):
        if self._in_preview and self._current_font:
            name = data.strip()
            if name:
                self.fonts.append({
                    "name": name,
                    "slug": self._current_font,
                })
                self._in_preview = False
                self._current_font = None

    def handle_endtag(self, tag):
        if tag == "a":
            self._in_preview = False


def search_dafont(keyword):
    """Search DaFont and return list of font dicts."""
    url = DAFONT_SEARCH.format(urllib.parse.quote(keyword))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return []

    parser = DaFontParser()
    parser.feed(html)

    # Deduplicate by slug
    seen = set()
    unique = []
    for f in parser.fonts:
        if f["slug"] not in seen:
            seen.add(f["slug"])
            unique.append(f)
    return unique


def download_and_install_font(slug):
    """Download a font zip from DaFont, extract .ttf/.otf, install to user fonts dir."""
    os.makedirs(FONTS_DIR, exist_ok=True)

    url = DAFONT_DL.format(urllib.parse.quote(slug))
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
                    if lower.endswith((".ttf", ".otf")) and not member.startswith("__MACOSX"):
                        basename = os.path.basename(member)
                        if not basename:
                            continue
                        dest = os.path.join(FONTS_DIR, basename)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        installed.append(basename)
        finally:
            os.unlink(tmp_path)

        # Refresh font cache
        try:
            subprocess.run(["fc-cache", "-f", FONTS_DIR], timeout=30,
                           capture_output=True)
        except Exception:
            pass

    except Exception as e:
        return [], str(e)

    return installed, None


def run_dafont_browser(procedure, run_mode, image, drawables, config, data):
    """Main plugin entry: show search dialog, list results, download selected."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("python-fu-dafont-installer")

        # --- Search dialog ---
        dialog = Gtk.Dialog(
            title="Browse DaFont",
            flags=0,
        )
        dialog.set_default_size(500, 450)
        dialog.add_button("_Close", Gtk.ResponseType.CLOSE)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_border_width(12)

        # Search bar
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry = Gtk.Entry()
        entry.set_placeholder_text("Search DaFont...")
        entry.set_hexpand(True)
        hbox.pack_start(entry, True, True, 0)

        search_btn = Gtk.Button(label="Search")
        hbox.pack_start(search_btn, False, False, 0)
        content.pack_start(hbox, False, False, 0)

        # Results list
        store = Gtk.ListStore(bool, str, str)  # selected, name, slug
        tree = Gtk.TreeView(model=store)
        tree.set_headers_visible(True)

        toggle_render = Gtk.CellRendererToggle()
        toggle_render.set_property("activatable", True)

        def on_toggle(widget, path):
            store[path][0] = not store[path][0]
        toggle_render.connect("toggled", on_toggle)

        col_sel = Gtk.TreeViewColumn("Install", toggle_render, active=0)
        col_sel.set_fixed_width(60)
        tree.append_column(col_sel)

        name_render = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn("Font Name", name_render, text=1)
        col_name.set_expand(True)
        tree.append_column(col_name)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.add(tree)
        content.pack_start(scroll, True, True, 0)

        # Install button
        install_btn = Gtk.Button(label="Install Selected Fonts")
        content.pack_start(install_btn, False, False, 0)

        # Status label
        status_label = Gtk.Label(label="Enter a keyword and click Search.")
        status_label.set_xalign(0)
        content.pack_start(status_label, False, False, 0)

        def do_search(_widget=None):
            keyword = entry.get_text().strip()
            if not keyword:
                return
            store.clear()
            status_label.set_text("Searching...")
            # Force UI refresh
            while Gtk.events_pending():
                Gtk.main_iteration()

            results = search_dafont(keyword)
            if not results:
                status_label.set_text("No fonts found.")
                return
            for f in results:
                store.append([False, f["name"], f["slug"]])
            status_label.set_text(f"Found {len(results)} font(s).")

        def do_install(_widget=None):
            selected = [(row[1], row[2]) for row in store if row[0]]
            if not selected:
                status_label.set_text("No fonts selected.")
                return

            total_installed = []
            errors = []
            for name, slug in selected:
                status_label.set_text(f"Downloading {name}...")
                while Gtk.events_pending():
                    Gtk.main_iteration()
                files, err = download_and_install_font(slug)
                if err:
                    errors.append(f"{name}: {err}")
                else:
                    total_installed.extend(files)

            # Refresh GIMP fonts
            pdb = Gimp.get_pdb()
            try:
                pdb.run_procedure("gimp-fonts-refresh", [])
            except Exception:
                pass

            if errors:
                status_label.set_text(
                    f"Installed {len(total_installed)} file(s). Errors: {'; '.join(errors)}")
            else:
                status_label.set_text(
                    f"Installed {len(total_installed)} font file(s) to {FONTS_DIR}")

        search_btn.connect("clicked", do_search)
        entry.connect("activate", do_search)
        install_btn.connect("clicked", do_install)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class DaFontInstaller(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-dafont-installer']

    def do_create_procedure(self, name):
        if name == 'python-fu-dafont-installer':
            procedure = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, run_dafont_browser, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(
                Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Parcourir DaFont..."),
                _("Rechercher, previsualiser et installer des polices depuis DaFont.com directement dans GIMP."),
                name)
            procedure.set_menu_label(_("Parcourir _DaFont..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Typography")
            return procedure

        return None


Gimp.main(DaFontInstaller.__gtype__, sys.argv)

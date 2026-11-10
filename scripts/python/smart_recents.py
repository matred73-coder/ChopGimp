#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Fichiers recents intelligents
#   Enhanced recent files browser: groups by folder, shows file info
#   (name, path, modified date, size). Reads from GIMP's recent files
#   via GLib.RecentManager or the recently-used.xbel file.
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib
import sys
import os
import time
from collections import defaultdict
from urllib.parse import unquote, urlparse

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

# Image file extensions that GIMP can open
IMAGE_EXTENSIONS = {
    '.xcf', '.xcf.gz', '.xcf.bz2', '.xcf.xz',
    '.psd', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif',
    '.webp', '.svg', '.ico', '.raw', '.cr2', '.nef', '.arw', '.dng',
    '.ora', '.kra', '.exr', '.hdr', '.heic', '.heif', '.avif',
    '.pdf', '.eps', '.ai',
}


def _is_image_file(filepath):
    """Check if a file path looks like an image GIMP can open."""
    lower = filepath.lower()
    for ext in IMAGE_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


def _get_recent_image_files():
    """Get recent image files from GLib.RecentManager."""
    recent_mgr = GLib.RecentManager.get_default()
    items = recent_mgr.get_items()

    files = []
    for item in items:
        uri = item.get_uri()
        if not uri:
            continue

        # Convert URI to local path
        parsed = urlparse(uri)
        if parsed.scheme not in ('file', ''):
            continue

        filepath = unquote(parsed.path)

        if not _is_image_file(filepath):
            continue

        if not os.path.exists(filepath):
            continue

        try:
            stat = os.stat(filepath)
            files.append({
                'path': filepath,
                'name': os.path.basename(filepath),
                'folder': os.path.dirname(filepath),
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'modified_str': time.strftime('%Y-%m-%d %H:%M',
                                              time.localtime(stat.st_mtime)),
            })
        except OSError:
            continue

    # Sort by most recently modified
    files.sort(key=lambda f: f['modified'], reverse=True)
    return files


def _format_size(size_bytes):
    """Format file size in human-readable units."""
    if size_bytes < 1024:
        return "{} B".format(size_bytes)
    elif size_bytes < 1024 * 1024:
        return "{:.1f} KB".format(size_bytes / 1024)
    elif size_bytes < 1024 * 1024 * 1024:
        return "{:.1f} MB".format(size_bytes / (1024 * 1024))
    else:
        return "{:.2f} GB".format(size_bytes / (1024 * 1024 * 1024))


# ---------------------------------------------------------------------------
# Fichiers recents intelligents — grouped by folder
# ---------------------------------------------------------------------------
def smart_recents(procedure, run_mode, image, drawables, config, data):
    files = _get_recent_image_files()

    if not files:
        Gimp.message("Aucun fichier image recent trouve.\n"
                      "Open some images in GIMP to populate this list.")
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    # Group by folder
    by_folder = defaultdict(list)
    for f in files:
        by_folder[f['folder']].append(f)

    # Build display
    lines = [
        "Fichiers recents intelligents",
        "=" * 50,
        "",
        "Total: {} recent image files in {} folders".format(len(files), len(by_folder)),
        "",
    ]

    # Sort folders by most recent file within
    sorted_folders = sorted(by_folder.keys(),
                            key=lambda d: max(f['modified'] for f in by_folder[d]),
                            reverse=True)

    for folder in sorted_folders:
        folder_files = by_folder[folder]
        # Shorten home path for display
        display_folder = folder.replace(os.path.expanduser('~'), '~')
        lines.append("[{}]".format(display_folder))

        for f in folder_files:
            lines.append("  {} | {} | {}".format(
                f['name'],
                _format_size(f['size']),
                f['modified_str']))

        lines.append("")

    lines.append("Tip: Use File > Open Recent to quickly re-open files.")

    Gimp.message("\n".join(lines))
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Open Recent by Path — convenience for scripting
# ---------------------------------------------------------------------------
def open_recent_file(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-open-recent-file')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    filepath = config.get_property('file-path')

    if not filepath or not os.path.exists(filepath):
        Gimp.message("Fichier introuvable : {}".format(filepath))
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())

    # Open the file via PDB
    pdb = Gimp.get_pdb()
    gio_file = GLib.filename_to_uri(filepath, None)

    try:
        proc = pdb.lookup_procedure('gimp-file-load')
        pc = proc.create_config()
        pc.set_property('run-mode', Gimp.RunMode.NONINTERACTIVE)
        file_obj = Gimp.File.new(filepath)
        pc.set_property('file', file_obj)
        result = proc.run(pc)

        loaded_image = result.index(1)
        if loaded_image:
            Gimp.Display.new(loaded_image)
            Gimp.displays_flush()
    except Exception as e:
        Gimp.message("Erreur a l'ouverture du fichier : {}".format(str(e)))
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Recent Files Stats
# ---------------------------------------------------------------------------
def recent_stats(procedure, run_mode, image, drawables, config, data):
    files = _get_recent_image_files()

    if not files:
        Gimp.message("Aucun fichier image recent trouve.")
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    # Compute stats
    total_size = sum(f['size'] for f in files)
    by_ext = defaultdict(int)
    for f in files:
        _, ext = os.path.splitext(f['name'].lower())
        by_ext[ext] += 1

    # Sort extensions by frequency
    sorted_exts = sorted(by_ext.items(), key=lambda x: x[1], reverse=True)

    lines = [
        "Statistiques des fichiers recents",
        "=" * 35,
        "",
        "Total files: {}".format(len(files)),
        "Total size: {}".format(_format_size(total_size)),
        "Folders: {}".format(len(set(f['folder'] for f in files))),
        "",
        "File types:",
    ]
    for ext, count in sorted_exts:
        lines.append("  {:<10s} {:>3d} files".format(ext if ext else "(none)", count))

    lines.append("")
    if files:
        lines.append("Most recent: {} ({})".format(files[0]['name'], files[0]['modified_str']))
        lines.append("Oldest: {} ({})".format(files[-1]['name'], files[-1]['modified_str']))

    Gimp.message("\n".join(lines))
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class SmartRecents(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-smart-recents',
            'python-fu-open-recent-file',
            'python-fu-recent-stats',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-smart-recents':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                smart_recents, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Fichiers recents intelligents"),
                _("Browse recent image files grouped by folder with file info "
                  "(name, size, modification date)."),
                name)
            procedure.set_menu_label(_("Fichiers _recents intelligents..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/File")

        elif name == 'python-fu-open-recent-file':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                open_recent_file, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Ouvrir un fichier recent par chemin"),
                _("Ouvrir un fichier recent en fournissant son chemin complet."),
                name)
            procedure.set_menu_label(_("_Ouvrir un fichier recent par chemin..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/File")

            procedure.add_string_argument("file-path", _("Chemin du _fichier"),
                                          _("Chemin complet du fichier image a ouvrir"),
                                          "",
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-recent-stats':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                recent_stats, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Statistiques des fichiers recents"),
                _("Afficher les statistiques des fichiers image recents : nombre par type, taille totale, etc."),
                name)
            procedure.set_menu_label(_("_Statistiques des fichiers recents"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/File")

        else:
            return None

        return procedure


Gimp.main(SmartRecents.__gtype__, sys.argv)

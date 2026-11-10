#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Workspace Switcher
#   Save and restore GIMP workspace layouts via sessionrc files.
#   Pre-built workspaces: Photography, Design, Painting.
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
import shutil

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


GIMP_CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "GIMP", "3.0")
WORKSPACES_DIR = os.path.join(GIMP_CONFIG_DIR, "workspaces")
SESSIONRC_PATH = os.path.join(GIMP_CONFIG_DIR, "sessionrc")


def _ensure_workspaces_dir():
    """Create the workspaces directory and pre-built files if missing."""
    os.makedirs(WORKSPACES_DIR, exist_ok=True)
    _create_prebuilt_workspaces()


def _create_prebuilt_workspaces():
    """Write pre-built workspace sessionrc files if they don't exist."""

    # Photography workspace: layers, histogram, curves prominent
    photo_path = os.path.join(WORKSPACES_DIR, "Photography.sessionrc")
    if not os.path.exists(photo_path):
        with open(photo_path, 'w') as f:
            f.write(_PHOTOGRAPHY_SESSIONRC)

    # Design workspace: paths, colors, gradients prominent
    design_path = os.path.join(WORKSPACES_DIR, "Design.sessionrc")
    if not os.path.exists(design_path):
        with open(design_path, 'w') as f:
            f.write(_DESIGN_SESSIONRC)

    # Painting workspace: brushes, dynamics, palettes prominent
    painting_path = os.path.join(WORKSPACES_DIR, "Painting.sessionrc")
    if not os.path.exists(painting_path):
        with open(painting_path, 'w') as f:
            f.write(_PAINTING_SESSIONRC)


# ---------------------------------------------------------------------------
# Pre-built sessionrc content
# These are minimal sessionrc snippets focusing on dock layout.
# GIMP merges these with defaults for any unspecified settings.
# ---------------------------------------------------------------------------

_PHOTOGRAPHY_SESSIONRC = """\
# PhotoGIMP Pro — Espace de travail Photographie
# Optimized for photo editing: Layers, Histogram, Curves, Levels
# Save via Windows > Workspaces > Enregistrer l'espace de travail actuel

(session-info "dock"
    (position 0 0)
    (size 300 800)
    (open-on-exit)
    (aux-info
        (active-page "Layers"))
    (book
        (current-page 0)
        (dockable "gimp-layer-list"
            (tab-style automatic))
        (dockable "gimp-channel-list"
            (tab-style automatic))
        (dockable "gimp-histogram-editor"
            (tab-style automatic))
    )
    (book
        (current-page 0)
        (dockable "gimp-color-balance"
            (tab-style automatic))
        (dockable "gimp-curves"
            (tab-style automatic))
        (dockable "gimp-levels"
            (tab-style automatic))
    )
)

(session-info "dock"
    (position 1620 0)
    (size 300 800)
    (open-on-exit)
    (book
        (current-page 0)
        (dockable "gimp-tool-options"
            (tab-style automatic))
    )
    (book
        (current-page 0)
        (dockable "gimp-undo-history"
            (tab-style automatic))
        (dockable "gimp-navigation-view"
            (tab-style automatic))
    )
)

(last-tip-shown 0)
"""

_DESIGN_SESSIONRC = """\
# PhotoGIMP Pro — Espace de travail Design
# Optimized for graphic design: Paths, Colors, Gradients, Fonts
# Save via Windows > Workspaces > Enregistrer l'espace de travail actuel

(session-info "dock"
    (position 0 0)
    (size 300 800)
    (open-on-exit)
    (aux-info
        (active-page "Layers"))
    (book
        (current-page 0)
        (dockable "gimp-layer-list"
            (tab-style automatic))
        (dockable "gimp-vectors-list"
            (tab-style automatic))
        (dockable "gimp-channel-list"
            (tab-style automatic))
    )
    (book
        (current-page 0)
        (dockable "gimp-colormap-editor"
            (tab-style automatic))
        (dockable "gimp-gradient-editor"
            (tab-style automatic))
        (dockable "gimp-palette-editor"
            (tab-style automatic))
    )
)

(session-info "dock"
    (position 1620 0)
    (size 300 800)
    (open-on-exit)
    (book
        (current-page 0)
        (dockable "gimp-tool-options"
            (tab-style automatic))
    )
    (book
        (current-page 0)
        (dockable "gimp-font-list"
            (tab-style automatic))
        (dockable "gimp-pattern-list"
            (tab-style automatic))
        (dockable "gimp-document-list"
            (tab-style automatic))
    )
)

(last-tip-shown 0)
"""

_PAINTING_SESSIONRC = """\
# PhotoGIMP Pro — Espace de travail Peinture
# Optimized for digital painting: Brushes, Dynamics, Palettes, Colors
# Save via Windows > Workspaces > Enregistrer l'espace de travail actuel

(session-info "dock"
    (position 0 0)
    (size 300 800)
    (open-on-exit)
    (aux-info
        (active-page "Layers"))
    (book
        (current-page 0)
        (dockable "gimp-layer-list"
            (tab-style automatic))
    )
    (book
        (current-page 0)
        (dockable "gimp-brush-list"
            (tab-style automatic))
        (dockable "gimp-dynamics-list"
            (tab-style automatic))
        (dockable "gimp-mypaint-brush-list"
            (tab-style automatic))
    )
)

(session-info "dock"
    (position 1620 0)
    (size 300 800)
    (open-on-exit)
    (book
        (current-page 0)
        (dockable "gimp-tool-options"
            (tab-style automatic))
    )
    (book
        (current-page 0)
        (dockable "gimp-palette-editor"
            (tab-style automatic))
        (dockable "gimp-colormap-editor"
            (tab-style automatic))
        (dockable "gimp-symmetry-editor"
            (tab-style automatic))
    )
)

(last-tip-shown 0)
"""


# ---------------------------------------------------------------------------
# Enregistrer l'espace de travail actuel
# ---------------------------------------------------------------------------
def save_workspace(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-save-workspace')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    ws_name = config.get_property('workspace-name')
    if not ws_name or ws_name.strip() == "":
        ws_name = "MyWorkspace"

    _ensure_workspaces_dir()

    # Sanitize name for filename
    safe_name = "".join(c for c in ws_name if c.isalnum() or c in (' ', '-', '_')).strip()
    dest = os.path.join(WORKSPACES_DIR, safe_name + ".sessionrc")

    if os.path.exists(SESSIONRC_PATH):
        shutil.copy2(SESSIONRC_PATH, dest)
        Gimp.message("Espace de travail '{}' enregistre dans :\n{}".format(ws_name, dest))
    else:
        Gimp.message("Erreur : sessionrc introuvable a {}".format(SESSIONRC_PATH))
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Restore helpers
# ---------------------------------------------------------------------------
def _restore_workspace(procedure, name, label):
    """Copy a named workspace sessionrc back and notify user to restart."""
    _ensure_workspaces_dir()

    src = os.path.join(WORKSPACES_DIR, name + ".sessionrc")
    if not os.path.exists(src):
        Gimp.message("Fichier d'espace de travail introuvable : {}".format(src))
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error())

    # Backup current sessionrc
    backup = SESSIONRC_PATH + ".backup"
    if os.path.exists(SESSIONRC_PATH):
        shutil.copy2(SESSIONRC_PATH, backup)

    shutil.copy2(src, SESSIONRC_PATH)
    Gimp.message(
        "Espace de travail {} applique.\n"
        "Veuillez redemarrer GIMP pour que la disposition prenne effet.\n"
        "(Le sessionrc precedent a ete sauvegarde dans sessionrc.backup)".format(label))

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def restore_photography(procedure, run_mode, image, drawables, config, data):
    return _restore_workspace(procedure, "Photography", "Photography")


def restore_design(procedure, run_mode, image, drawables, config, data):
    return _restore_workspace(procedure, "Design", "Design")


def restore_painting(procedure, run_mode, image, drawables, config, data):
    return _restore_workspace(procedure, "Painting", "Painting")


# ===========================================================================
# Plugin registration
# ===========================================================================
class WorkspaceSwitcher(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-save-workspace',
            'python-fu-ws-photography',
            'python-fu-ws-design',
            'python-fu-ws-painting',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        menu_base = "<Image>/Fenetres/Espaces de travail"

        if name == 'python-fu-save-workspace':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                save_workspace, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Enregistrer l'espace de travail actuel"),
                _("Enregistrer la disposition actuelle des fenetres GIMP comme espace de travail nomme."),
                name)
            procedure.set_menu_label(_("_Enregistrer l'espace de travail actuel..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_string_argument("workspace-name", _("_Nom de l'espace de travail"),
                                          _("Nom de cet espace de travail layout"),
                                          "MyWorkspace",
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-ws-photography':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                restore_photography, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Espace de travail Photographie"),
                _("Restaurer la disposition de l'espace de travail Photographie (redemarrage requis)."),
                name)
            procedure.set_menu_label(_("Espace de travail _Photographie"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-ws-design':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                restore_design, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Espace de travail Design"),
                _("Restaurer la disposition de l'espace de travail Design (redemarrage requis)."),
                name)
            procedure.set_menu_label(_("Espace de travail _Design"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        elif name == 'python-fu-ws-painting':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                restore_painting, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
            procedure.set_documentation(
                _("Espace de travail Peinture"),
                _("Restaurer la disposition de l'espace de travail Peinture (redemarrage requis)."),
                name)
            procedure.set_menu_label(_("Espace de travail Pe_inture"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

        else:
            return None

        return procedure


Gimp.main(WorkspaceSwitcher.__gtype__, sys.argv)

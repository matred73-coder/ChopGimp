#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Actions Recorder
#   Record, play, and manage macro action scripts
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
import json
import time
import glob

def N_(message): return message
def _(message): return GLib.dgettext(None, message)

ACTIONS_DIR = os.path.expanduser("~/.config/GIMP/3.0/photogimp-actions")


def _ensure_actions_dir():
    """Create the actions directory if it does not exist."""
    os.makedirs(ACTIONS_DIR, exist_ok=True)


def _list_actions():
    """Return sorted list of (name, filepath) for saved actions."""
    _ensure_actions_dir()
    actions = []
    for fp in sorted(glob.glob(os.path.join(ACTIONS_DIR, "*.json"))):
        name = os.path.splitext(os.path.basename(fp))[0]
        actions.append((name, fp))
    return actions


def record_action(procedure, run_mode, image, drawables, config, data):
    """Record an action — creates a Python script template from PDB operations.

    Since GIMP 3.0 does not expose a PDB interception API, we generate a
    template script with the most common retouching operations that the user
    can customize.  The template captures current image state (dimensions,
    active layer, etc.) and provides a replayable skeleton.
    """
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-record-action')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    action_name = config.get_property('action-name')
    if not action_name or not action_name.strip():
        action_name = "action_" + time.strftime("%Y%m%d_%H%M%S")

    _ensure_actions_dir()

    # Capture current image state for the template
    img_width = image.get_width()
    img_height = image.get_height()
    base_type = image.get_base_type().value_nick
    n_layers = len(image.get_layers())
    active_name = ""
    active_drawables = image.get_selected_drawables()
    if active_drawables:
        active_name = active_drawables[0].get_name()

    # Build a replayable Python script template
    script_lines = [
        "# PhotoGIMP Pro Action: " + action_name,
        "# Recorded: " + time.strftime("%Y-%m-%d %H:%M:%S"),
        "# Original image: {}x{}, {}, {} layers".format(
            img_width, img_height, base_type, n_layers),
        "#",
        "# Edit the 'steps' list below to build your action.",
        "# Each step is a dict with 'procedure' (PDB name) and 'args'.",
        "# When played back, each procedure is called via Gimp.get_pdb().",
        "",
        "STEPS = [",
        "    # Example steps — replace with your actual operations:",
        "    # {",
        '    #     "procedure": "gimp-drawable-brightness-contrast",',
        '    #     "args": ["__drawable__", 0.2, 0.1]',
        "    # },",
        "    # {",
        '    #     "procedure": "gimp-drawable-hue-saturation",',
        '    #     "args": ["__drawable__", 0, 0.0, 0.0, 20.0, 0.0]',
        "    # },",
        "    # {",
        '    #     "procedure": "gimp-image-flatten",',
        '    #     "args": ["__image__"]',
        "    # },",
        "]",
    ]

    # Save as JSON metadata + embedded script
    action_data = {
        "name": action_name,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_image": {
            "width": img_width,
            "height": img_height,
            "base_type": base_type,
            "layers": n_layers,
            "active_layer": active_name,
        },
        "script": "\n".join(script_lines),
    }

    filepath = os.path.join(ACTIONS_DIR, action_name + ".json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(action_data, f, indent=2, ensure_ascii=False)

    Gimp.message(_("Action '{}' enregistree dans :\n{}").format(action_name, filepath))
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def play_action(procedure, run_mode, image, drawables, config, data):
    """Play a saved action by executing its embedded script steps."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-play-action')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    action_name = config.get_property('action-name')
    if not action_name or not action_name.strip():
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("No action name specified."))

    filepath = os.path.join(ACTIONS_DIR, action_name + ".json")
    if not os.path.isfile(filepath):
        # Try exact path as fallback
        if os.path.isfile(action_name):
            filepath = action_name
        else:
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error("Action file not found: " + filepath))

    with open(filepath, 'r', encoding='utf-8') as f:
        action_data = json.load(f)

    script_text = action_data.get("script", "")
    if not script_text.strip():
        Gimp.message(_("L'action '{}' n'a pas de contenu de script.").format(action_name))
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    # Execute the embedded script in a controlled namespace
    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    drawable = drawables[0] if drawables else None

    # Parse STEPS from the script and execute via PDB
    namespace = {}
    try:
        exec(script_text, namespace)
    except Exception as e:
        image.undo_group_end()
        Gimp.context_pop()
        return procedure.new_return_values(
            Gimp.PDBStatusType.EXECUTION_ERROR,
            GLib.Error("Script parse error: " + str(e)))

    steps = namespace.get("STEPS", [])
    errors = []
    for i, step in enumerate(steps):
        proc_name = step.get("procedure", "")
        raw_args = step.get("args", [])

        if not proc_name:
            continue

        # Replace placeholder tokens
        resolved_args = []
        for arg in raw_args:
            if arg == "__image__":
                resolved_args.append(image)
            elif arg == "__drawable__":
                resolved_args.append(drawable)
            else:
                resolved_args.append(arg)

        try:
            pdb_proc = pdb.lookup_procedure(proc_name)
            if pdb_proc is None:
                errors.append("Step {}: procedure '{}' not found".format(i + 1, proc_name))
                continue

            pdb_config = pdb_proc.create_config()
            arg_specs = pdb_proc.get_arguments()

            for j, arg_val in enumerate(resolved_args):
                if j < len(arg_specs):
                    prop_name = arg_specs[j].get_name()
                    pdb_config.set_property(prop_name, arg_val)

            result = pdb.run_procedure_config(proc_name, pdb_config)
            status = result.index(0)
            if status != Gimp.PDBStatusType.SUCCESS:
                errors.append("Step {}: '{}' returned non-success".format(i + 1, proc_name))
        except Exception as e:
            errors.append("Step {}: {} — {}".format(i + 1, proc_name, str(e)))

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()

    if errors:
        Gimp.message(_("Action terminee avec des erreurs :\n") + "\n".join(errors))
    else:
        Gimp.message(_("Action '{}' rejouee avec succes ({} etapes).").format(
            action_data.get("name", action_name), len(steps)))

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def manage_actions(procedure, run_mode, image, drawables, config, data):
    """Lister toutes les actions enregistrees avec leurs details."""
    actions = _list_actions()

    if not actions:
        Gimp.message(_("Aucune action enregistree trouvee dans :\n") + ACTIONS_DIR)
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    lines = [_("Actions enregistrees dans {} :").format(ACTIONS_DIR), ""]
    for name, fp in actions:
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data_obj = json.load(f)
            created = data_obj.get("created", "unknown")
            src = data_obj.get("source_image", {})
            dims = "{}x{}".format(src.get("width", "?"), src.get("height", "?"))
            lines.append("  - {} (created: {}, source: {})".format(name, created, dims))
        except Exception:
            lines.append("  - {} (error reading metadata)".format(name))

    lines.append("")
    lines.append(_("Pour rejouer une action, utilisez Filtres > Flux de travail > Rejouer une action..."))
    lines.append(_("Les fichiers d'actions sont dans : ") + ACTIONS_DIR)

    Gimp.message("\n".join(lines))
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ActionsRecorder(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-record-action',
            'python-fu-play-action',
            'python-fu-manage-actions',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-record-action':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                record_action, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Enregistrer une action..."),
                _("Create a replayable action template from current image state. "
                  "Edit the generated JSON/script to define your macro steps."),
                name)
            procedure.set_menu_label(_("_Enregistrer une action..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Workflow")

            procedure.add_string_argument("action-name",
                                          _("_Nom de l'action"),
                                          _("Nom de cette action (alphanumerique, sans espaces)"),
                                          "my_action",
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-play-action':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                play_action, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Rejouer une action..."),
                _("Rejouer une action (macro) enregistree sur l'image courante."),
                name)
            procedure.set_menu_label(_("_Rejouer une action..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Workflow")

            procedure.add_string_argument("action-name",
                                          _("_Nom de l'action"),
                                          _("Nom de l'action a rejouer"),
                                          "",
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-manage-actions':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                manage_actions, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Gerer les actions"),
                _("Lister toutes les actions enregistrees avec leurs details."),
                name)
            procedure.set_menu_label(_("_Gerer les actions"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Filters/Workflow")

        else:
            return None

        return procedure


Gimp.main(ActionsRecorder.__gtype__, sys.argv)

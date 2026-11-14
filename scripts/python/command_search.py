#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Recherche de commande (Command Search)
#   Enhanced command palette: search and run any PhotoGIMP Pro plugin.
#   Custom GTK dialog with fuzzy search, filtered list, and Run button.
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

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


# ---------------------------------------------------------------------------
#  Complete list of PhotoGIMP Pro plugins
#  (procedure_name, display_label, menu_location)
# ---------------------------------------------------------------------------

PLUGIN_REGISTRY = [
    # Auto Adjustments
    ("python-fu-auto-levels", "Niveaux auto", "Image > Reglages auto"),
    ("python-fu-auto-contrast", "Contraste auto", "Image > Reglages auto"),
    ("python-fu-auto-color", "Couleur auto", "Image > Reglages auto"),
    # Traitement par lots (ChopGimp)
    ("chopgimp-batch", "Traitement par lots", "Fichier > Exporter"),
    # Color Palette Generator
    ("python-fu-palette-from-image", "Palette depuis l'image", "Filtres > Couleur"),
    ("python-fu-palette-from-color", "Palette depuis une couleur", "Filtres > Couleur"),
    # CSS Generator
    ("python-fu-css-generator", "Generateur CSS", "Filtres > Web"),
    # DaFont Installer
    ("python-fu-dafont-installer", "Installer polices DaFont", "Filtres > Typographie"),
    # Dodge & Burn Setup
    ("python-fu-dodge-burn-setup", "Dodge & Burn (configuration)", "Filtres > Retouche"),
    # Exporter les calques → Générer les ressources (ChopGimp)
    ("chopgimp-generate-assets", "Generer les ressources (calques)", "Fichier > Exporter"),
    ("chopgimp-export-web", "Exporter pour le web", "Fichier > Exporter"),
    # Frequency Separation
    ("python-fu-frequency-separation", "Separation de frequence", "Filtres > Retouche"),
    # Google Fonts
    ("python-fu-google-fonts", "Google Fonts", "Filtres > Typographie"),
    # Grid System
    ("python-fu-grid-system", "Systeme de grille", "Image > Grille"),
    # Icon Generator
    ("python-fu-icon-generator", "Generateur d'icones", "Filtres > Web"),
    # Compositions de calques (ChopGimp)
    ("chopgimp-layer-comps", "Compositions de calques", "Fenetres"),
    # Lorem Ipsum (ChopGimp)
    ("chopgimp-text-lorem", "Texte de remplissage (Lorem ipsum)", "Calque > Texte"),
    # Multi-Page PDF
    ("python-fu-multi-page-pdf", "PDF multi-pages", "Fichier"),
    # Quick Color
    ("python-fu-quick-color", "Couleur rapide", "Filtres > Couleur"),
    # Quick Effects
    ("python-fu-quick-vignette", "Vignettage rapide", "Filtres > Effets rapides"),
    ("python-fu-quick-film-grain", "Grain film rapide", "Filtres > Effets rapides"),
    ("python-fu-quick-tilt-shift", "Tilt-shift rapide", "Filtres > Effets rapides"),
    # Mise a l'echelle selon le contenu (ChopGimp, Liquid Rescale)
    ("chopgimp-liquid-rescale", "Mise a l'echelle selon le contenu", "Image"),
    # Smart Sharpen
    ("python-fu-smart-sharpen", "Nettete intelligente", "Filtres > Amelioration"),
    # Split Toning
    ("python-fu-split-toning", "Virage partiel", "Filtres > Couleur"),
    # Effets de texte (ChopGimp : déformation, styles de calque)
    ("chopgimp-text-warp", "Deformer le texte (arc, drapeau...)", "Calque > Texte"),
    ("chopgimp-layer-style", "Style de calque (ombre, lueur, biseau, contour)", "Calque > Style de calque"),
    # Camera Raw (ChopGimp)
    ("chopgimp-camera-raw", "Camera Raw", "Filtres"),
    # Vector Align
    ("python-fu-align-left", "Aligner a gauche", "Filtres > Vecteur"),
    ("python-fu-align-center-h", "Centrer horizontalement", "Filtres > Vecteur"),
    ("python-fu-align-right", "Aligner a droite", "Filtres > Vecteur"),
    ("python-fu-align-top", "Aligner en haut", "Filtres > Vecteur"),
    ("python-fu-align-center-v", "Centrer verticalement", "Filtres > Vecteur"),
    ("python-fu-align-bottom", "Aligner en bas", "Filtres > Vecteur"),
    # Actions Recorder
    ("python-fu-record-action", "Enregistrer une action", "Filtres > Automatisation"),
    ("python-fu-play-action", "Lire une action", "Filtres > Automatisation"),

    # Data Merge
    ("python-fu-data-merge", "Fusion de donnees (CSV)", "Filtres > Workflow"),
    # Text Styles
    ("python-fu-save-text-style", "Enregistrer style de texte", "Filtres > Typographie"),
    ("python-fu-apply-text-style", "Appliquer style de texte", "Filtres > Typographie"),
    ("python-fu-manage-text-styles", "Gerer les styles de texte", "Filtres > Typographie"),
    # Sample Average
    ("python-fu-sample-average", "Pipette moyenne", "Filtres > Couleur"),
    # Command Search (self!)
    ("python-fu-command-search", "Recherche de commande", "Edition"),
]


def _fuzzy_match(query, text):
    """Simple fuzzy matching: all query chars must appear in order in text."""
    query = query.lower()
    text = text.lower()

    # First try substring match (higher priority)
    if query in text:
        return True

    # Then fuzzy: each char of query appears in order in text
    qi = 0
    for ch in text:
        if qi < len(query) and ch == query[qi]:
            qi += 1
    return qi == len(query)


def _score_match(query, text):
    """Score a match: lower is better. Substring match scores best."""
    query_l = query.lower()
    text_l = text.lower()

    if text_l == query_l:
        return 0  # Exact match
    if text_l.startswith(query_l):
        return 1  # Starts with
    if query_l in text_l:
        return 2 + text_l.index(query_l)  # Substring match, earlier is better
    return 100  # Fuzzy match


def command_search(procedure, run_mode, image, drawables, config, data):
    """Show a searchable command palette and execute selected plugin."""
    if run_mode != Gimp.RunMode.INTERACTIVE:
        # Non-interactive: run the specified procedure directly
        proc_name = config.get_property('procedure-name')
        if proc_name:
            pdb = Gimp.get_pdb()
            proc = pdb.lookup_procedure(proc_name)
            if proc:
                pc = proc.create_config()
                if image:
                    try:
                        pc.set_property('image', image)
                    except Exception:
                        pass
                    try:
                        if drawables:
                            pc.set_property('drawables',
                                            Gimp.ObjectArray.new(Gimp.Drawable, drawables, False))
                    except Exception:
                        pass
                pc.set_property('run-mode', Gimp.RunMode.INTERACTIVE)
                proc.run(pc)
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

    # Interactive mode: show GTK dialog with search
    gi.require_version('GimpUi', '3.0')
    gi.require_version('Gtk', '3.0')
    from gi.repository import GimpUi, Gtk, Gdk

    GimpUi.init('python-fu-command-search')

    # Build the dialog
    dialog = Gtk.Dialog(
        title="Recherche de commande — PhotoGIMP Pro",
        transient_for=None,
        modal=True,
        destroy_with_parent=True,
    )
    dialog.set_default_size(650, 500)
    dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    run_button = dialog.add_button("_Executer", Gtk.ResponseType.OK)
    run_button.get_style_context().add_class("suggested-action")

    content = dialog.get_content_area()
    content.set_spacing(8)
    content.set_border_width(12)

    # Search entry
    search_label = Gtk.Label(label="Tapez pour rechercher une commande :")
    search_label.set_xalign(0)
    content.pack_start(search_label, False, False, 0)

    search_entry = Gtk.Entry()
    search_entry.set_placeholder_text("Rechercher...")
    content.pack_start(search_entry, False, False, 0)

    # ListStore: label, menu_path, procedure_name
    store = Gtk.ListStore(str, str, str)
    filtered_store = store.filter_new()

    current_query = [""]  # mutable container for closure

    def visible_func(model, iter, data):
        q = current_query[0]
        if not q:
            return True
        label = model[iter][0]
        menu = model[iter][1]
        return _fuzzy_match(q, label) or _fuzzy_match(q, menu)

    filtered_store.set_visible_func(visible_func)

    # Populate store (seulement les procédures réellement installées)
    pdb = Gimp.get_pdb()
    for proc_name, label, menu in PLUGIN_REGISTRY:
        if pdb.procedure_exists(proc_name):
            store.append([label, menu, proc_name])

    # Sorted model (sort by label)
    sorted_store = Gtk.TreeModelSort(model=filtered_store)
    sorted_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)

    tree = Gtk.TreeView(model=sorted_store)
    tree.set_headers_visible(True)
    tree.set_search_column(0)

    # Columns
    renderer_text = Gtk.CellRendererText()
    col_label = Gtk.TreeViewColumn("Commande", renderer_text, text=0)
    col_label.set_expand(True)
    col_label.set_resizable(True)
    tree.append_column(col_label)

    col_menu = Gtk.TreeViewColumn("Menu", renderer_text, text=1)
    col_menu.set_resizable(True)
    tree.append_column(col_menu)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroll.add(tree)
    content.pack_start(scroll, True, True, 0)

    # Status label
    status_label = Gtk.Label()
    status_label.set_xalign(0)
    content.pack_start(status_label, False, False, 0)

    def update_status():
        n = sorted_store.iter_n_children(None)
        status_label.set_text(f"{n} commande(s) trouvee(s)")

    def on_search_changed(entry):
        current_query[0] = entry.get_text().strip()
        filtered_store.refilter()
        update_status()
        # Auto-select first result
        if sorted_store.iter_n_children(None) > 0:
            tree.get_selection().select_path(Gtk.TreePath.new_first())

    search_entry.connect("changed", on_search_changed)

    # Double-click to run
    def on_row_activated(treeview, path, column):
        dialog.response(Gtk.ResponseType.OK)

    tree.connect("row-activated", on_row_activated)

    # Enter key in search entry triggers run
    def on_key_press(widget, event):
        if event.keyval == Gdk.KEY_Return or event.keyval == Gdk.KEY_KP_Enter:
            dialog.response(Gtk.ResponseType.OK)
            return True
        return False

    search_entry.connect("key-press-event", on_key_press)

    # Select first item initially
    update_status()
    if sorted_store.iter_n_children(None) > 0:
        tree.get_selection().select_path(Gtk.TreePath.new_first())

    dialog.show_all()
    search_entry.grab_focus()

    response = dialog.run()

    selected_proc = None
    if response == Gtk.ResponseType.OK:
        sel = tree.get_selection()
        model, tree_iter = sel.get_selected()
        if tree_iter:
            selected_proc = model[tree_iter][2]

    dialog.destroy()

    # Execute selected procedure
    if selected_proc:
        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure(selected_proc)
        if proc:
            pc = proc.create_config()
            # Set image and drawables if the procedure expects them
            try:
                if image:
                    pc.set_property('image', image)
            except Exception:
                pass
            try:
                if drawables:
                    pc.set_property('drawables',
                                    Gimp.ObjectArray.new(Gimp.Drawable, drawables, False))
            except Exception:
                pass
            pc.set_property('run-mode', Gimp.RunMode.INTERACTIVE)
            proc.run(pc)
        else:
            Gimp.message(f"Procedure '{selected_proc}' introuvable dans le PDB.")

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class CommandSearch(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-command-search']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            command_search, None)
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.set_documentation(
            _("Command Search — PhotoGIMP Pro"),
            _("Rechercher et executer n'importe quel plugin PhotoGIMP Pro. "
              "Recherche floue par nom ou emplacement dans les menus."),
            name)
        procedure.set_menu_label(_("_Recherche de commande..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Edit")

        procedure.add_string_argument("procedure-name",
                                      _("_Nom de la procedure"),
                                      _("Nom PDB de la procedure a executer (mode non-interactif)"),
                                      "",
                                      GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(CommandSearch.__gtype__, sys.argv)

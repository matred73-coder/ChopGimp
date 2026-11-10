#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Galerie de filtres (Filter Browser / Gallery)
#   Visual filter gallery with curated GEGL operations.
#   Browse by category, select a filter, adjust params, apply with preview.
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
# Curated filter catalog — ~30 popular GEGL operations organized by category
# Each entry: (gegl_op, french_label, category, {default_props})
# ---------------------------------------------------------------------------
FILTER_CATALOG = [
    # --- Flou (Blur) ---
    ("gegl:gaussian-blur",      "Flou gaussien",          "blur",     {"std-dev-x": 5.0, "std-dev-y": 5.0}),
    ("gegl:motion-blur-linear", "Flou directionnel",      "blur",     {"length": 20.0, "angle": 0.0}),
    ("gegl:motion-blur-zoom",   "Flou de zoom",           "blur",     {"factor": 0.1}),
    ("gegl:median-blur",        "Flou median",            "blur",     {"radius": 3}),
    ("gegl:pixelize",           "Pixelisation",           "blur",     {"size-x": 10, "size-y": 10}),

    # --- Nettete (Sharpen) ---
    ("gegl:unsharp-mask",       "Masque flou (nettete)",  "sharpen",  {"std-dev": 3.0, "scale": 0.5, "threshold": 0.0}),

    # --- Couleur (Color) ---
    ("gegl:saturation",         "Saturation",             "color",    {"scale": 1.5}),
    ("gegl:hue-chroma",         "Teinte / Chroma",        "color",    {"hue": 0.0, "chroma": 0.0, "lightness": 0.0}),
    ("gegl:color-temperature",  "Temperature couleur",    "color",    {"original-temperature": 6500.0, "intended-temperature": 5000.0}),
    ("gegl:brightness-contrast","Luminosite / Contraste", "color",    {"brightness": 0.0, "contrast": 0.2}),
    ("gegl:exposure",           "Exposition",             "color",    {"exposure": 0.5}),
    ("gegl:levels",             "Niveaux",                "color",    {"in-low": 0.0, "in-high": 1.0, "out-low": 0.0, "out-high": 1.0}),
    ("gegl:invert-linear",      "Inverser",               "color",    {}),
    ("gegl:mono-mixer",         "Melangeur mono (N&B)",   "color",    {"preserve-luminosity": True}),
    ("gegl:threshold",          "Seuil",                  "color",    {"value": 0.5}),
    ("gegl:posterize",          "Posteriser",             "color",    {"levels": 4}),
    ("gegl:color-rotate",       "Rotation de couleurs",   "color",    {}),

    # --- Distorsion (Distort) ---
    ("gegl:spherize",           "Spheriser",              "distort",  {"amount": 1.0}),
    ("gegl:shift",              "Decalage",               "distort",  {"shift": 10.0}),
    ("gegl:ripple",             "Ondulation",             "distort",  {"amplitude": 10.0, "period": 80.0}),
    ("gegl:whirl-pinch",        "Tourbillon",             "distort",  {"whirl": 90.0, "pinch": 0.0, "radius": 300.0}),
    ("gegl:polar-coordinates",  "Coordonnees polaires",   "distort",  {}),

    # --- Artistique (Artistic) ---
    ("gegl:cartoon",            "Bande dessinee",         "artistic", {"mask-radius": 7.0, "pct-black": 0.2}),
    ("gegl:oil-painting",       "Peinture a l'huile",    "artistic", {"mask-radius": 4, "exponent": 8}),
    ("gegl:softglow",           "Lueur douce",            "artistic", {"glow-radius": 10.0, "brightness": 0.3, "sharpness": 0.85}),
    ("gegl:emboss",             "Relief / Estampage",     "artistic", {"azimuth": 315.0, "elevation": 45.0, "depth": 2}),
    ("gegl:waterpixels",        "Aquarelle pixels",       "artistic", {"size": 32, "smoothness": 1.0}),

    # --- Lumiere (Light) ---
    ("gegl:vignette",           "Vignette",               "light",    {"softness": 3.0, "strength": 1.0}),
    ("gegl:bloom",              "Halo lumineux (Bloom)",  "light",    {"threshold": 50.0, "softness": 25.0, "radius": 10.0, "strength": 50.0}),
    ("gegl:lens-flare",         "Halo de lentille",       "light",    {"pos-x": 0.5, "pos-y": 0.5}),
    ("gegl:shadows-highlights", "Ombres / Hautes lum.",   "light",    {"shadows": 50.0, "highlights": -50.0}),

    # --- Bruit / Rendu (Render/Noise) ---
    ("gegl:noise-hsv",          "Bruit HSV (grain)",      "render",   {"dulling": 4, "value-distance": 0.1}),
]

# Category labels (French)
CATEGORY_LABELS = {
    "blur":     "Flou",
    "sharpen":  "Nettete",
    "color":    "Couleur",
    "distort":  "Distorsion",
    "artistic": "Artistique",
    "light":    "Lumiere",
    "render":   "Rendu / Bruit",
}


def filter_browser_run(procedure, run_mode, image, drawables, config, data):
    """Show the filter gallery and apply the selected filter."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, GdkPixbuf

        GimpUi.init('python-fu-filter-browser')

        # Build a custom GTK dialog for the gallery
        dialog = Gtk.Dialog(
            title="Galerie de filtres",
            flags=0)
        dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Appliquer", Gtk.ResponseType.OK)
        dialog.set_default_size(700, 500)

        content = dialog.get_content_area()

        # Main horizontal pane: category tree | filter list + params
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hbox.set_margin_start(8)
        hbox.set_margin_end(8)
        hbox.set_margin_top(8)
        hbox.set_margin_bottom(8)
        content.pack_start(hbox, True, True, 0)

        # Left: Category list
        cat_store = Gtk.ListStore(str, str)  # id, label
        for cat_id, cat_label in CATEGORY_LABELS.items():
            cat_store.append([cat_id, cat_label])

        cat_tree = Gtk.TreeView(model=cat_store)
        cat_renderer = Gtk.CellRendererText()
        cat_column = Gtk.TreeViewColumn("Categorie", cat_renderer, text=1)
        cat_tree.append_column(cat_column)
        cat_tree.set_headers_visible(True)

        cat_scroll = Gtk.ScrolledWindow()
        cat_scroll.set_min_content_width(140)
        cat_scroll.add(cat_tree)
        hbox.pack_start(cat_scroll, False, False, 0)

        # Middle: Filter list for selected category
        filter_store = Gtk.ListStore(str, str, int)  # gegl_op, label, catalog_index
        filter_tree = Gtk.TreeView(model=filter_store)
        filter_renderer = Gtk.CellRendererText()
        filter_column = Gtk.TreeViewColumn("Filtre", filter_renderer, text=1)
        filter_tree.append_column(filter_column)
        filter_tree.set_headers_visible(True)

        filter_scroll = Gtk.ScrolledWindow()
        filter_scroll.set_min_content_width(200)
        filter_scroll.add(filter_tree)
        hbox.pack_start(filter_scroll, True, True, 0)

        # Right: Info/params area
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_label = Gtk.Label(label="Selectionnez une categorie puis un filtre.")
        info_label.set_line_wrap(True)
        info_label.set_xalign(0)
        info_box.pack_start(info_label, False, False, 0)

        params_label = Gtk.Label(label="")
        params_label.set_line_wrap(True)
        params_label.set_xalign(0)
        params_label.set_selectable(True)
        info_box.pack_start(params_label, False, False, 0)

        info_scroll = Gtk.ScrolledWindow()
        info_scroll.set_min_content_width(220)
        info_scroll.add(info_box)
        hbox.pack_start(info_scroll, False, True, 0)

        # State tracking
        state = {"selected_index": -1}

        def on_category_changed(selection):
            model, treeiter = selection.get_selected()
            if treeiter is None:
                return
            cat_id = model[treeiter][0]
            filter_store.clear()
            for idx, (op, label, cat, props) in enumerate(FILTER_CATALOG):
                if cat == cat_id:
                    filter_store.append([op, label, idx])

        def on_filter_changed(selection):
            model, treeiter = selection.get_selected()
            if treeiter is None:
                return
            cat_idx = model[treeiter][2]
            op, label, cat, props = FILTER_CATALOG[cat_idx]
            state["selected_index"] = cat_idx
            info_label.set_text(f"{label}\nOperation GEGL : {op}")
            if props:
                props_text = "\n".join(f"  {k} = {v}" for k, v in props.items())
                params_label.set_text(f"Parametres par defaut :\n{props_text}")
            else:
                params_label.set_text("Aucun parametre configurable.")

            # Apply preview using DrawableFilter
            for drawable in drawables:
                try:
                    filt = Gimp.DrawableFilter.new(drawable, op, "")
                    fc = filt.get_config()
                    for k, v in props.items():
                        try:
                            fc.set_property(k, v)
                        except Exception:
                            pass
                    filt.update()
                    Gimp.displays_flush()
                except Exception:
                    pass

        cat_tree.get_selection().connect("changed", on_category_changed)
        filter_tree.get_selection().connect("changed", on_filter_changed)

        # Select first category
        cat_tree.get_selection().select_iter(cat_store.get_iter_first())

        dialog.show_all()
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.OK:
            # Remove any pending preview filter
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())

        if state["selected_index"] < 0:
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())

        # Apply the selected filter permanently
        selected = FILTER_CATALOG[state["selected_index"]]
    else:
        # Non-interactive: use the filter-index parameter
        filter_index = config.get_property('filter-index')
        if filter_index < 0 or filter_index >= len(FILTER_CATALOG):
            return procedure.new_return_values(
                Gimp.PDBStatusType.CALLING_ERROR,
                GLib.Error("Index de filtre invalide."))
        selected = FILTER_CATALOG[filter_index]

    op, label, cat, props = selected

    Gimp.context_push()
    image.undo_group_start()

    for drawable in drawables:
        try:
            filt = Gimp.DrawableFilter.new(drawable, op, "")
            fc = filt.get_config()
            for k, v in props.items():
                try:
                    fc.set_property(k, v)
                except Exception:
                    pass
            drawable.merge_filter(filt)
        except Exception:
            Gimp.message(f"Impossible d'appliquer le filtre : {op}")

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class FilterBrowser(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-filter-browser']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            filter_browser_run, None)
        procedure.set_image_types("RGB*, GRAY*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                       Gimp.ProcedureSensitivityMask.DRAWABLES)
        procedure.set_documentation(
            _("Galerie de filtres"),
            _("Naviguer et appliquer des filtres GEGL par categorie : Flou, Nettete, "
              "Couleur, Distorsion, Artistique, Lumiere, Rendu. "
              "Environ 30 operations GEGL les plus populaires avec apercu."),
            name)
        procedure.set_menu_label(_("_Galerie de filtres..."))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Filters")

        # Non-interactive parameter: index into FILTER_CATALOG
        procedure.add_int_argument("filter-index",
                                   _("_Index du filtre"),
                                   _("Index du filtre dans le catalogue (pour usage non interactif)"),
                                   0, len(FILTER_CATALOG) - 1, 0,
                                   GObject.ParamFlags.READWRITE)

        return procedure


Gimp.main(FilterBrowser.__gtype__, sys.argv)

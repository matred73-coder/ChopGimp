#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Ecran d'accueil
#   Creates a welcome image with feature list, shortcuts cheat sheet,
#   recent files info, and version details.
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio
import sys
import os
from urllib.parse import unquote, urlparse

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


# ---------------------------------------------------------------------------
#  Data
# ---------------------------------------------------------------------------

VERSION = "1.0"

FEATURES = [
    ("Niveaux auto / Contraste auto / Couleur auto", "Image > Reglages auto"),
    ("Remplissage selon le contenu", "Edition > Remplissage selon le contenu"),
    ("Separation de frequence", "Filtres > Retouche"),
    ("Correcteur localise", "Filtres > Retouching"),
    ("HDR Merge / Focus Stacking", "Filtres > Workflow"),
    ("Fusion de donnees (CSV)", "Filtres > Workflow"),
    ("Export par lot", "Fichier > Export par lot"),
    ("Styles de calques (ombre, contour, biseautage)", "Filtres > Styles de calques"),
    ("Effets de texte (3D, neon, chrome)", "Filtres > Typographie"),
    ("Styles de texte (presets)", "Filtres > Typographie"),
    ("Bibliotheque de formes vectorielles", "Filtres > Vector"),
    ("Generateur de palettes de couleurs", "Filtres > Couleur"),
    ("Pipette moyenne", "Filtres > Couleur"),
    ("Grille / Guide system", "Image > Grille"),
    ("Generateur d'icones (multi-tailles)", "Filtres > Web"),
    ("Carving de coutures (Content-Aware Scale)", "Filtres > Deformation"),
    ("Chargeur de LUT", "Filtres > Couleur"),
    ("Installation Google Fonts / DaFont", "Filtres > Typographie"),
    ("PDF multi-pages", "Fichier"),
    ("Recherche de commande", "Edition"),
]

TOP_SHORTCUTS = [
    ("Ctrl+Shift+E", "Exporter sous"),
    ("Ctrl+J", "Dupliquer le calque"),
    ("Ctrl+T", "Transformation libre"),
    ("Ctrl+Shift+N", "Nouveau calque"),
    ("Ctrl+E", "Fusionner vers le bas"),
    ("Ctrl+D", "Deselectionner"),
    ("Ctrl+Shift+I", "Inverser la selection"),
    ("Ctrl+Z", "Annuler"),
    ("Ctrl+Y", "Retablir"),
    ("Ctrl+A", "Tout selectionner"),
    ("B", "Pinceau"),
    ("E", "Gomme"),
    ("V", "Deplacement"),
    ("M", "Selection rectangulaire"),
    ("L", "Lasso"),
    ("W", "Baguette magique"),
    ("G", "Degrade / Remplissage"),
    ("S", "Tampon de duplication"),
    ("T", "Texte"),
    ("Space", "Deplacement main"),
]


def _get_recent_files(max_count=8):
    """Get recent image files from GLib.RecentManager."""
    image_exts = {'.xcf', '.psd', '.png', '.jpg', '.jpeg', '.gif', '.bmp',
                  '.tiff', '.tif', '.webp', '.svg', '.raw', '.cr2', '.nef'}
    recent_files = []
    try:
        recent_mgr = GLib.RecentManager.get_default()
        items = recent_mgr.get_items()
        for item in items:
            uri = item.get_uri()
            if uri.startswith('file://'):
                path = unquote(urlparse(uri).path)
                ext = os.path.splitext(path)[1].lower()
                if ext in image_exts:
                    basename = os.path.basename(path)
                    recent_files.append(basename)
                    if len(recent_files) >= max_count:
                        break
    except Exception:
        pass
    return recent_files


def _draw_filled_rect(image, layer, x, y, w, h, color):
    """Draw a filled rectangle on the given layer."""
    pdb = Gimp.get_pdb()
    Gimp.context_set_foreground(color)
    image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)
    layer.edit_fill(Gimp.FillType.FOREGROUND)
    Gimp.Selection.none(image)


def _create_text(image, text, font_name, size, color, x, y):
    """Create a text layer and position it."""
    pdb = Gimp.get_pdb()

    text_layer = Gimp.TextLayer.new(image, text, Gimp.Font.get_by_name(font_name), size, Gimp.Unit.px())
    if text_layer is None:
        # Fallback: try with Sans
        text_layer = Gimp.TextLayer.new(image, text, Gimp.Font.get_by_name("Sans"), size, Gimp.Unit.px())
    if text_layer is None:
        return None

    image.insert_layer(text_layer, None, -1)
    text_layer.set_offsets(x, y)
    text_layer.set_color(color)
    return text_layer


def welcome_screen(procedure, run_mode, image, drawables, config, data):
    """Create a PhotoGIMP Pro welcome screen image."""
    Gimp.context_push()
    # image arg may be None when no image is open (ALWAYS sensitivity mask)

    pdb = Gimp.get_pdb()
    img_w, img_h = 1200, 800

    # Create new image
    new_image = Gimp.Image.new(img_w, img_h, Gimp.ImageBaseType.RGB)
    new_image.undo_disable()

    # --- Background layer ---
    bg = Gimp.Layer.new(new_image, "Fond", img_w, img_h,
                        Gimp.ImageType.RGB_IMAGE, 100.0,
                        Gimp.LayerMode.NORMAL)
    new_image.insert_layer(bg, None, -1)

    # Dark gradient background
    dark_bg = Gegl.Color.new("#1a1a2e")
    _draw_filled_rect(new_image, bg, 0, 0, img_w, img_h, dark_bg)

    # Header bar
    header_color = Gegl.Color.new("#16213e")
    _draw_filled_rect(new_image, bg, 0, 0, img_w, 90, header_color)

    # Accent line
    accent_color = Gegl.Color.new("#e94560")
    _draw_filled_rect(new_image, bg, 0, 88, img_w, 4, accent_color)

    # --- Title ---
    white = Gegl.Color.new("#ffffff")
    accent_text = Gegl.Color.new("#e94560")
    light_gray = Gegl.Color.new("#b0b0b0")
    mid_gray = Gegl.Color.new("#808080")
    section_bg = Gegl.Color.new("#0f3460")

    _create_text(new_image, "PhotoGIMP Pro", "Sans Bold", 36, white, 30, 25)
    _create_text(new_image, f"v{VERSION}", "Sans", 18, accent_text, 330, 38)

    # --- Features section (left column) ---
    _draw_filled_rect(new_image, bg, 20, 105, 560, 30, section_bg)
    _create_text(new_image, "Fonctionnalites principales", "Sans Bold", 16, white, 30, 108)

    y_pos = 145
    for feat_name, feat_menu in FEATURES[:12]:
        _create_text(new_image, f"  {feat_name}", "Sans", 11, light_gray, 30, y_pos)
        _create_text(new_image, feat_menu, "Sans Italic", 10, mid_gray, 400, y_pos + 1)
        y_pos += 22

    # More features
    for feat_name, feat_menu in FEATURES[12:]:
        _create_text(new_image, f"  {feat_name}", "Sans", 11, light_gray, 30, y_pos)
        _create_text(new_image, feat_menu, "Sans Italic", 10, mid_gray, 400, y_pos + 1)
        y_pos += 22

    # --- Shortcuts section (right column) ---
    _draw_filled_rect(new_image, bg, 620, 105, 560, 30, section_bg)
    _create_text(new_image, "Raccourcis clavier essentiels", "Sans Bold", 16, white, 630, 108)

    y_pos = 145
    for key, action in TOP_SHORTCUTS:
        _create_text(new_image, key, "Monospace Bold", 11, accent_text, 635, y_pos)
        _create_text(new_image, action, "Sans", 11, light_gray, 800, y_pos)
        y_pos += 22

    # --- Recent files section ---
    recent_y = 600
    _draw_filled_rect(new_image, bg, 20, recent_y, 560, 30, section_bg)
    _create_text(new_image, "Fichiers recents", "Sans Bold", 16, white, 30, recent_y + 3)

    recent_files = _get_recent_files()
    ry = recent_y + 40
    if recent_files:
        for rf in recent_files:
            _create_text(new_image, f"  {rf}", "Sans", 11, light_gray, 30, ry)
            ry += 20
    else:
        _create_text(new_image, "  (aucun fichier recent)", "Sans Italic", 11, mid_gray, 30, ry)

    # --- Version info (bottom right) ---
    _draw_filled_rect(new_image, bg, 620, recent_y, 560, 30, section_bg)
    _create_text(new_image, "A propos", "Sans Bold", 16, white, 630, recent_y + 3)
    info_y = recent_y + 40
    _create_text(new_image, f"PhotoGIMP Pro v{VERSION}", "Sans Bold", 13, white, 635, info_y)
    _create_text(new_image, "Raccourcis et workflows inspires de Photoshop", "Sans", 11, light_gray, 635, info_y + 25)
    _create_text(new_image, "GIMP 3.0 + Python 3 + GEGL", "Sans", 11, light_gray, 635, info_y + 45)
    _create_text(new_image, "Licence : GPL v3+", "Sans", 11, mid_gray, 635, info_y + 65)
    _create_text(new_image, "Aide > Ecran d'accueil PhotoGIMP Pro", "Sans Italic", 11, mid_gray, 635, info_y + 90)

    # --- Footer ---
    _draw_filled_rect(new_image, bg, 0, img_h - 25, img_w, 25, header_color)
    _create_text(new_image, "Astuce : utilisez Edition > Recherche de commande pour trouver rapidement n'importe quel outil",
                 "Sans Italic", 10, mid_gray, 30, img_h - 22)

    new_image.undo_enable()

    # Display the new image
    display = Gimp.Display.new(new_image)
    Gimp.displays_flush()
    Gimp.context_pop()

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class WelcomeScreen(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ['python-fu-welcome-screen']

    def do_create_procedure(self, name):
        Gegl.init(None)

        procedure = Gimp.ImageProcedure.new(self, name,
                                            Gimp.PDBProcType.PLUGIN,
                                            welcome_screen, None)
        procedure.set_image_types("*")
        procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        procedure.set_documentation(
            _("PhotoGIMP Pro Welcome Screen"),
            _("Afficher l'ecran d'accueil PhotoGIMP Pro avec la liste des "
              "fonctionnalites, les raccourcis clavier, les fichiers recents "
              "et les informations de version."),
            name)
        procedure.set_menu_label(_("_Ecran d'accueil PhotoGIMP Pro"))
        procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
        procedure.add_menu_path("<Image>/Help")

        return procedure


Gimp.main(WelcomeScreen.__gtype__, sys.argv)

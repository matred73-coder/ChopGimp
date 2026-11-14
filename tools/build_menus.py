#!/usr/bin/env python3
"""
PhotoGIMP Pro v2 — génère la barre de menus « Photoshop » à partir des menus
de GIMP installé (aucun élément GIMP n'est supprimé, seulement réorganisé).

Ordre Photoshop :
  Fichier · Édition · Image · Couleurs · Calque · Texte · Sélection ·
  Filtres · Affichage · Fenêtres · Aide
- Nouveau sous-menu « Image > Réglages » (réglages essentiels, comme Photoshop).
- Le menu « Outils » de GIMP passe dans « Fenêtres > Outils ».
- Nouveau menu « Texte ».

GIMP lit ces menus via la variable GIMP_TESTING_MENUS_PATH (posée par le
lanceur PhotoGIMP Pro). Le dossier de sortie contient TOUS les .ui.

Usage : build_menus.py <dossier menus GIMP> <dossier de sortie>
"""
import os
import re
import shutil
import sys
import xml.dom.minidom

src_dir, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
for f in os.listdir(src_dir):
    if f.endswith(".ui"):
        shutil.copy(os.path.join(src_dir, f), os.path.join(out_dir, f))

lines = open(os.path.join(src_dir, "image-menu.ui"), encoding="utf-8").read().split("\n")

# Découpe des sous-menus de premier niveau (indentation 4 espaces)
blocks, start = [], None
for n, l in enumerate(lines):
    if l == "    <submenu>":
        start = n
    elif l == "    </submenu>" and start is not None:
        label = re.search(r">([^<]+)</attribute>", lines[start + 1]).group(1)
        blocks.append((label, start, n))
        start = None

found = [b[0] for b in blocks]
expected = ["_File", "_Edit", "_Select", "_View", "_Image", "_Layer",
            "_Colors", "_Tools", "Filte_rs", "_Windows", "_Help"]
missing = [e for e in expected if e not in found]
if missing:
    sys.exit("Menus GIMP inattendus (version différente ?) : manquants %s, trouvés %s" % (missing, found))

head = lines[:blocks[0][1]]
tail = lines[blocks[-1][2] + 1:]
get = {b[0]: lines[b[1]:b[2] + 1] for b in blocks}


def as_submenu(block, label, indent="  "):
    """Transforme un menu de 1er niveau en sous-menu imbriqué avec un nouveau libellé."""
    out = [indent + l for l in block]
    out[1] = indent + '      <attribute name="label" translatable="no">%s</attribute>' % label
    return out


def insert_before_close(block, extra):
    """Ajoute des lignes juste avant le </submenu> final d'un bloc."""
    return block[:-1] + extra + block[-1:]


# IMPORTANT : les menus de 1er niveau gardent leur libellé GIMP d'origine
# (traduit à l'affichage : Fichier, Édition…). Les plug-ins s'y accrochent
# par ce nom (« <Image>/Filters/… ») : le renommer crée des menus en double.
# « Couleurs » reste donc un menu de 1er niveau (beaucoup de plug-ins y
# vont) ; « Image > Réglages » en reprend l'essentiel, comme Photoshop.
REGLAGES = [
    ["filters-brightness-contrast", "filters-levels", "filters-curves", "filters-exposure"],
    ["filters-hue-saturation", "filters-color-balance", "filters-mono-mixer",
     "filters-channel-mixer", "filters-color-temperature", "filters-colorize"],
    ["filters-invert-perceptual", "filters-posterize", "filters-threshold"],
    ["filters-shadows-highlights", "filters-desaturate"],
]
reglages = ["      <section>", "        <submenu>",
            '          <attribute name="label" translatable="no">_Réglages</attribute>']
for sec in REGLAGES:
    reglages.append("          <section>")
    reglages += ['            <item><attribute name="action">app.%s</attribute></item>' % a for a in sec]
    reglages.append("          </section>")
reglages += ["        </submenu>", "      </section>"]

# « Outils » imbriqué dans Fenêtre (libellé d'origine conservé → traduit)
outils = ["      <section>"] + ["  " + l for l in get["_Tools"]] + ["      </section>"]

image = get["_Image"][:2] + reglages + get["_Image"][2:]
# Les panneaux courants directement dans le menu, comme Photoshop : c'est là
# qu'on rouvre un panneau fermé. La liste complète reste dans le sous-menu
# « Fenêtres ancrables ».
PANNEAUX = [["dialogs-layers", "dialogs-channels", "dialogs-paths"],
            ["dialogs-colors", "dialogs-palettes", "dialogs-gradients", "dialogs-patterns",
             "dialogs-brushes", "dialogs-fonts"],
            ["dialogs-character", "dialogs-paragraph", "dialogs-glyphs", "dialogs-text-styles",
             "dialogs-fonts-preview", "dialogs-document-texts"],
            ["dialogs-undo-history", "dialogs-navigation", "dialogs-histogram", "dialogs-cursor"]]
panneaux = []
for sec in PANNEAUX:
    panneaux.append("      <section>")
    panneaux += ['        <item><attribute name="action">app.%s</attribute></item>' % a for a in sec]
    panneaux.append("      </section>")
# Fenêtres > Espace de travail (Photoshop), Modifier la barre d'outils
espace = ["      <section>",
          "      <submenu>",
          '        <attribute name="label" translatable="no">_Espace de travail</attribute>',
          "        <section>"] + \
    ['          <item><attribute name="action">app.windows-workspace-%s</attribute></item>' % w
     for w in ["essentiel", "photographie", "peinture", "typographie", "illustration"]] + \
    ["        </section>", "        <section>",
     '          <item><attribute name="action">app.windows-workspace-personnel</attribute></item>',
     '          <item><attribute name="action">app.windows-workspace-save</attribute></item>',
     "        </section>",
     "      </submenu>",
     '      <item><attribute name="action">app.windows-edit-toolbar</attribute></item>',
     "      </section>"]
fenetre = get["_Windows"][:2] + espace + panneaux + get["_Windows"][2:]
fenetre = insert_before_close(fenetre, outils)

texte = """    <submenu>
      <attribute name="label" translatable="no">_Texte</attribute>
      <section>
        <item><attribute name="action">app.tools-text</attribute></item>
        <item><attribute name="action">app.dialogs-fonts</attribute></item>
        <item><attribute name="action">app.dialogs-character</attribute></item>
        <item><attribute name="action">app.dialogs-paragraph</attribute></item>
        <item><attribute name="action">app.dialogs-glyphs</attribute></item>
        <item><attribute name="action">app.dialogs-text-styles</attribute></item>
        <item><attribute name="action">app.dialogs-fonts-preview</attribute></item>
        <item><attribute name="action">app.dialogs-document-texts</attribute></item>
      </section>
      <section>
        <item><attribute name="action">app.chopgimp-text-warp</attribute></item>
        <item><attribute name="action">app.chopgimp-text-on-path</attribute></item>
        <item><attribute name="action">app.chopgimp-text-in-shape</attribute></item>
        <item><attribute name="action">app.chopgimp-text-fx-clear</attribute></item>
      </section>
      <section>
        <item><attribute name="action">app.chopgimp-text-outline</attribute></item>
        <item><attribute name="action">app.chopgimp-text-outline-letters</attribute></item>
        <item><attribute name="action">app.chopgimp-text-work-path</attribute></item>
      </section>
      <section>
        <item><attribute name="action">app.chopgimp-text-find-replace</attribute></item>
        <item><attribute name="action">app.chopgimp-text-lorem</attribute></item>
      </section>
      <section>
        <item><attribute name="action">app.layers-text-to-path</attribute></item>
        <item><attribute name="action">app.layers-text-along-path</attribute></item>
      </section>
    </submenu>""".split("\n")


# ── Calque : sous-menus Photoshop en tête ─────────────────────────────
# « Style de calque » : filtres non destructifs natifs (modifiables via
# l'icône fx du calque). Le plug-in photogimp_ps y ajoute Contour, Lueur
# externe, Ombre interne, Effacer le style (même libellé → même sous-menu).
# « Nouveau calque de réglage » : actions ChopGimp layers-adjustment-* (groupe
# « ◐ » + vraie fenêtre de réglage de GIMP sur le groupe).
ADJ_ACTIONS = ["layers-adjustment-" + k for k in ['levels', 'curves', 'brightness-contrast', 'exposure', 'vibrance', 'hue-saturation', 'color-balance', 'black-white', 'photo-filter', 'channel-mixer', 'colorize', 'invert', 'posterize', 'threshold', 'shadows-highlights']]


def adjustment_submenu(indent):
    i = " " * indent
    return ([i + "<submenu>",
             i + '  <attribute name="label" translatable="no">Nouveau calque de réglage</attribute>',
             i + "  <section>"] +
            [i + '    <item><attribute name="action">app.%s</attribute></item>' % a for a in ADJ_ACTIONS] +
            [i + "  </section>", i + "</submenu>"])
STYLE_NATIFS = ["filters-dropshadow", "filters-gegl-inner-glow", "filters-gegl-bevel",
                "filters-gegl-color-overlay", "filters-long-shadow", "filters-emboss"]


def style_submenu(indent):
    i = " " * indent
    l = [i + "<submenu>",
         i + '  <attribute name="label" translatable="no">Style de calque</attribute>',
         i + "  <section>"]
    l += [i + '    <item><attribute name="action">app.%s</attribute></item>' % a for a in STYLE_NATIFS]
    l += [i + "  </section>", i + "</submenu>"]
    return l


calque_head = ["      <section>"] + style_submenu(8) + adjustment_submenu(8) + ["      </section>"]
calque = get["_Layer"][:2] + calque_head + get["_Layer"][2:]

# Affichage > Apparence (ChopGimp) : variantes, accent, densité, police, taille
def radio_sub(label, prefix, keys):
    return ["      <submenu>",
            '        <attribute name="label" translatable="no">%s</attribute>' % label,
            "        <section>"] + \
           ['          <item><attribute name="action">app.windows-%s-%s</attribute></item>' % (prefix, k)
            for k in keys] + \
           ["        </section>", "      </submenu>"]


apparence = ["    <submenu>",
             '      <attribute name="label" translatable="no">_Apparence</attribute>',
             "      <section>"] + \
    ['        <item><attribute name="action">app.windows-appearance-%s</attribute></item>' % k
     for k in ["sombre", "gris", "gris-clair", "clair", "contraste", "affinity", "krita"]] + \
    ["      </section>", "      <section>"] + \
    ["  " + l for l in radio_sub("_Couleur d'accent", "accent",
                                 ["variante", "bleu", "cyan", "violet", "vert", "orange",
                                  "rouge", "rose", "jaune"])] + \
    ["  " + l for l in radio_sub("_Densité", "density", ["compact", "normal", "comfortable"])] + \
    ["  " + l for l in radio_sub("_Police de l'interface", "ui-font", ["inter", "source", "system"])] + \
    ["  " + l for l in radio_sub("_Taille de l'interface", "ui-size", ["90", "100", "115", "130"])] + \
    ["      </section>", "    </submenu>"]
affichage = insert_before_close(get["_View"], ["      <section>"] + ["  " + l for l in apparence] +
                                ["      </section>"])

order = [
    get["_File"],
    get["_Edit"],
    image,
    get["_Colors"],
    calque,
    texte,
    get["_Select"],
    get["Filte_rs"],
    affichage,
    fenetre,
    get["_Help"],
]

out = list(head)
out[0:0] = []
for b in order:
    out += b + [""]
out += tail
text = "\n".join(out)
text = text.replace("This file is automatically generated. Do not edit!",
                    "PhotoGIMP Pro v2 : généré par tools/build_menus.py — ne pas éditer.")
xml.dom.minidom.parseString(text.encode("utf-8"))   # validation XML
open(os.path.join(out_dir, "image-menu.ui"), "w", encoding="utf-8").write(text)

# ── Clic droit du panneau Calques : ordre du menu contextuel Photoshop ──
# Racine conservée (« Layers Menu ») : les plug-ins s'y accrochent via
# « <Layers>/Layers Menu/… ».
def items(actions, ind=8):
    return "\n".join(" " * ind + '<item><attribute name="action">app.%s</attribute></item>' % a
                     for a in actions)


def sub(label, actions, ind=6, translatable=False):
    t = 'translatable="no"' if not translatable else 'translatable="yes" context="layers-action"'
    return ("%s<submenu>\n%s  <attribute name=\"label\" %s>%s</attribute>\n%s\n%s</submenu>"
            % (" " * ind, " " * ind, t, label, items(actions, ind + 2), " " * ind))


def sec(*parts):
    return "      <section>\n" + "\n".join(parts) + "\n      </section>"


layers_popup = """<?xml version="1.0" encoding="utf-8"?>
<!-- PhotoGIMP Pro v2 : généré par tools/build_menus.py — ne pas éditer. -->
<interface>
  <menu id="/layers-popup">
    <submenu>
      <attribute name="label" translatable="yes" context="layers-action">Layers Menu</attribute>
      <attribute name="icon">gimp-layers</attribute>
%s
%s
%s
%s
%s
%s
%s
%s
    </submenu>
  </menu>
</interface>
""" % (
    sec(items(["layers-edit-attributes", "layers-edit-text", "layers-edit-vector"])),
    sec(items(["layers-new", "layers-duplicate", "layers-delete", "layers-new-group",
               "layers-new-from-visible"])),
    sec("\n".join(style_submenu(8)),
        "\n".join(adjustment_submenu(8)),
        sub("Mode de composition", ["layers-composite-mode-auto", "layers-composite-mode-union",
                                    "layers-composite-mode-clip-to-backdrop",
                                    "layers-composite-mode-clip-to-layer",
                                    "layers-composite-mode-intersection"], 8)),
    sec(items(["layers-rasterize", "layers-revert-rasterize", "layers-text-to-path",
               "layers-text-along-path"])),
    sec(sub("Masque de fusion", ["layers-mask-add", "layers-mask-apply", "layers-mask-delete",
                                 "layers-mask-show", "layers-mask-edit", "layers-mask-disable",
                                 "layers-mask-selection-replace"], 8),
        sub("Transparence", ["layers-alpha-add", "layers-alpha-remove",
                             "layers-alpha-selection-replace"], 8),
        sub("Taille", ["layers-resize", "layers-resize-to-image", "layers-scale"], 8)),
    sec(items(["layers-anchor", "layers-merge-down", "layers-merge-group", "layers-merge-layers",
               "layers-flatten-image"])),
    sec(sub("Couleur de l'étiquette", ["layers-color-tag-none", "layers-color-tag-red",
                                        "layers-color-tag-orange", "layers-color-tag-yellow",
                                        "layers-color-tag-green", "layers-color-tag-blue",
                                        "layers-color-tag-violet", "layers-color-tag-gray",
                                        "layers-color-tag-brown"], 8)),
    sec(sub("Espaces de fusion avancés", ["layers-blend-space-auto", "layers-blend-space-rgb-linear",
                                          "layers-blend-space-rgb-non-linear",
                                          "layers-blend-space-rgb-perceptual",
                                          "layers-composite-space-auto",
                                          "layers-composite-space-rgb-linear",
                                          "layers-composite-space-rgb-non-linear",
                                          "layers-composite-space-rgb-perceptual"], 8)),
)
xml.dom.minidom.parseString(layers_popup.encode("utf-8"))
open(os.path.join(out_dir, "layers-menu.ui"), "w", encoding="utf-8").write(layers_popup)
print("menus Photoshop écrits dans", out_dir)

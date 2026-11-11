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
fenetre = insert_before_close(get["_Windows"], outils)

texte = """    <submenu>
      <attribute name="label" translatable="no">_Texte</attribute>
      <section>
        <item><attribute name="action">app.tools-text</attribute></item>
        <item><attribute name="action">app.dialogs-fonts</attribute></item>
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
# « Nouveau calque de réglage » est entièrement fourni par le plug-in.
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


calque_head = ["      <section>"] + style_submenu(8) + [
    "        <submenu>",
    '          <attribute name="label" translatable="no">Nouveau calque de réglage</attribute>',
    "        </submenu>",
    "      </section>"]
calque = get["_Layer"][:2] + calque_head + get["_Layer"][2:]

order = [
    get["_File"],
    get["_Edit"],
    image,
    get["_Colors"],
    calque,
    texte,
    get["_Select"],
    get["Filte_rs"],
    get["_View"],
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
        '        <submenu>\n          <attribute name="label" translatable="no">Nouveau calque de réglage</attribute>\n        </submenu>',
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

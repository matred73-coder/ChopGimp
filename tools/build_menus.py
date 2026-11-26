#!/usr/bin/env python3
"""
ChopGimp — génère la barre de menus « Photoshop » à partir des menus
de GIMP installé (aucun élément GIMP n'est supprimé, seulement réorganisé).

Ordre Photoshop :
  Fichier · Édition · Image · Calque · Vecteur · Texte · Sélection ·
  Filtres · Affichage · Fenêtres · Aide
- « Image > Réglages » reprend tout l'ancien menu Couleurs (fondu, sans
  doublons) ; Image > Guides passe dans Affichage, Fusionner les calques
  visibles / Aplatir dans Calque (patch 0139 : les plug-ins suivent).
- Calque : toutes les créations de calques en tête ; menu « Vecteur »
  (ex-Objet) : tout le vectoriel. Un garde-fou arrête la génération si
  une action d'origine de GIMP disparaît des menus.
- Le menu « Outils » de GIMP passe dans « Fenêtres > Outils ».
- Nouveau menu « Texte ».

tools/install_data.sh recopie les .ui produits dans share/gimp/3.0/menus
(ils remplacent ceux de GIMP). Le dossier de sortie contient TOUS les .ui.

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


def insert_before_close(block, extra):
    """Ajoute des lignes juste avant le </submenu> final d'un bloc."""
    return block[:-1] + extra + block[-1:]


# IMPORTANT : les menus de 1er niveau gardent leur libellé GIMP d'origine
# (traduit à l'affichage : Fichier, Édition…). Les plug-ins s'y accrochent
# par ce nom (« <Image>/Filters/… ») : le renommer crée des menus en double.
# Exception (ChopGimp 3.27.4) : le menu « Couleurs » est fondu dans
# « Image > Réglages », Image > Guides passe dans Affichage et les
# commandes [Arrange] dans Calque ; les plug-ins qui visent les anciens
# chemins y sont redirigés par la table de app/plug-in/plug-in-menu-path.c
# (patch 0139). Le menu Image est construit plus bas (après les fonctions
# communes acts / submenu).

# « Outils » imbriqué dans Fenêtre (libellé d'origine conservé → traduit)
outils = ["      <section>"] + ["  " + l for l in get["_Tools"]] + ["      </section>"]
# Les panneaux courants directement dans le menu, comme Photoshop : c'est là
# qu'on rouvre un panneau fermé. La liste complète reste dans le sous-menu
# « Fenêtres ancrables ».
PANNEAUX = [["dialogs-layers", "dialogs-channels", "dialogs-paths",
             "dialogs-appearance", "dialogs-stroke", "dialogs-global-colors",
             "dialogs-symbols", "dialogs-transform", "dialogs-vbrushes"],
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
# l'icône fx du calque). Le plug-in photogimp_ps y ajoute Effacer le style
# (même libellé → même sous-menu).
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
# Contour, Lueur externe, Ombre interne : actions ChopGimp filters-chopgimp-*
# (fenêtre du filtre, comme l'ombre portée, avec des réglages de départ)
STYLE_NATIFS = ["filters-dropshadow", "filters-chopgimp-stroke", "filters-chopgimp-outer-glow",
                "filters-chopgimp-inner-shadow", "filters-chopgimp-inner-glow", "filters-gegl-bevel",
                "filters-gegl-color-overlay", "filters-long-shadow", "filters-emboss"]

# Fenêtre « Style de calque » unifiée (ChopGimp 3.26, lot B) : tous les effets
# du calque, à cocher et à régler (tools/gimpfiltertool-layerstyle.c)
STYLE_FENETRE = ["layers-style-dialog"]

# Copier / coller le style de calque (ChopGimp, presse-papiers de styles)
STYLE_PRESSE_PAPIERS = ["layers-style-copy", "layers-style-paste", "layers-style-paste-add"]

# Pixelliser le style de calque (ChopGimp) : fusion des filtres de GIMP
# (bouton de la liste fx) sur tous les calques sélectionnés
STYLE_PIXELLISER = ["layers-style-rasterize"]


def style_submenu(indent):
    i = " " * indent
    l = [i + "<submenu>",
         i + '  <attribute name="label" translatable="no">Style de calque</attribute>',
         i + "  <section>"]
    l += [i + '    <item><attribute name="action">app.%s</attribute></item>' % a for a in STYLE_FENETRE]
    l += [i + "  </section>", i + "  <section>"]
    l += [i + '    <item><attribute name="action">app.%s</attribute></item>' % a for a in STYLE_NATIFS]
    l += [i + "  </section>", i + "  <section>"]
    l += [i + '    <item><attribute name="action">app.%s</attribute></item>' % a for a in STYLE_PRESSE_PAPIERS]
    l += [i + "  </section>", i + "  <section>"]
    l += [i + '    <item><attribute name="action">app.%s</attribute></item>' % a for a in STYLE_PIXELLISER]
    l += [i + "  </section>", i + "</submenu>"]
    return l


# ── Calque (ChopGimp 3.27.4, réorganisation des menus) ─────────────────
# Ordre Photoshop : toutes les créations de calques en tête, puis
# dupliquer / fusionner / supprimer, style, masques, pile, taille.
# Les sections d'origine de GIMP (texte/pixelliser, Pile, Masque,
# Transparence, Transformer, tailles) sont reprises telles quelles. Les
# actions des plug-ins sont placées par leur nom (app.<procédure>) : ces
# plug-ins ne déclarent plus de chemin « <Image>/Layer… » (sinon elles
# apparaîtraient deux fois).
def layer_sections(block):
    """Sections de 1er niveau (indentation 6) du menu Calque de GIMP."""
    secs, cur = [], None
    for l in block[2:-1]:
        if l == "      <section>":
            cur = [l]
        elif l == "      </section>" and cur is not None:
            cur.append(l)
            secs.append(cur)
            cur = None
        elif cur is not None:
            cur.append(l)
    return secs


def pick(secs, marker):
    found = [s for s in secs if any(marker in l for l in s)]
    if len(found) != 1:
        sys.exit("Menu Calque de GIMP inattendu : section « %s » introuvable" % marker)
    return found[0]


def acts(actions, indent):
    return [" " * indent + '<item><attribute name="action">app.%s</attribute></item>' % a
            for a in actions]


def submenu(label, sections, indent):
    """Sous-menu ; sections = liste de listes d'actions (séparées par un trait)."""
    i = " " * indent
    l = [i + "<submenu>", i + '  <attribute name="label" translatable="no">%s</attribute>' % label]
    for sec in sections:
        l += [i + "  <section>"] + acts(sec, indent + 4) + [i + "  </section>"]
    return l + [i + "</submenu>"]


_secs = layer_sections(get["_Layer"])
SEC_TEXTE = pick(_secs, "layers-text-to-path")  # texte vers chemin, pixelliser
SEC_PILE = pick(_secs, "Stac_k")                # Pile, Masque, Transparence, Transformer
SEC_TAILLE = pick(_secs, "layers-resize")       # tailles et recadrages

calque = get["_Layer"][:2] + [
    "      <section>",
    '        <attribute name="section-name" translatable="no">Structure</attribute>'] + \
    acts(["layers-new", "layers-new-group", "layers-new-from-visible"], 8) + \
    adjustment_submenu(8) + \
    submenu("Nouveau calque de _remplissage",
            [["chopgimp-fill-color", "chopgimp-fill-gradient", "chopgimp-fill-pattern"]], 8) + \
    acts(["chopgimp-sketch-layer"], 8) + [
    "      </section>",
    "      <section>"] + \
    acts(["layers-duplicate", "layers-anchor", "layers-delete"], 8) + [
    "      </section>",
    # fusions (Fusionner les calques visibles et Aplatir viennent du menu
    # Image, comme Photoshop) ; section « Arrange » : Aligner les calques
    # visibles (plug-in, redirigé depuis <Image>/Image/[Arrange])
    "      <section>",
    '        <attribute name="section-name" translatable="no">Arrange</attribute>'] + \
    acts(["layers-merge-down", "layers-merge-group", "image-merge-layers", "image-flatten",
          "photogimp-stamp-visible"], 8) + [
    "      </section>",
    "      <section>"] + \
    style_submenu(8) + \
    acts(["photogimp-clipping-toggle"], 8) + \
    submenu("Objet _dynamique",
            [["chopgimp-smart-convert", "chopgimp-smart-edit", "chopgimp-smart-replace"]], 8) + [
    "      </section>"] + \
    SEC_TEXTE + SEC_PILE + SEC_TAILLE + [
    "      <section>"] + \
    acts(["layers-image-trace", "chopgimp-flats"], 8) + [
    "      </section>"] + get["_Layer"][-1:]

# ── Vecteur (ex-« Objet ») : tout le vectoriel au même endroit ─────────
# Commandes de ChopGimp (layers-vobjects-*, layers-image-trace-*) et des
# plug-ins chopgimp_vector / chopgimp_fx / chopgimp_atelier / photogimp_ps
# (app.<procédure>). Un seul Pathfinder : celui du plug-in agit sur les
# objets sélectionnés d'un calque vectoriel, sinon sur les calques
# vectoriels sélectionnés (les actions layers-vobjects-pathfinder-* ne
# sont plus dans les menus, les raccourcis visent déjà le plug-in).
# (libellé du sous-menu ou None, [sections d'actions])
VECTEUR_MENU = [
    [(None, [["layers-vobjects-group", "layers-vobjects-ungroup"]])],
    [("_Disposition", [["layers-vobjects-raise-to-top", "layers-vobjects-raise",
                        "layers-vobjects-lower", "layers-vobjects-lower-to-bottom"]]),
     ("_Aligner", [["layers-vobjects-align-left", "layers-vobjects-align-hcenter",
                    "layers-vobjects-align-right", "layers-vobjects-align-top",
                    "layers-vobjects-align-vcenter", "layers-vobjects-align-bottom"],
                   ["layers-vobjects-distribute-h", "layers-vobjects-distribute-v"],
                   # 3.29.0 : Aligner sur (sélection, objet clé, plan de travail)
                   ["layers-vobjects-align-to-selection", "layers-vobjects-align-to-key",
                    "layers-vobjects-align-to-artboard", "layers-vobjects-key-none"]]),
     # 3.29.0 (vectoriel « complet », bloc 2) : Transformer
     ("_Transformer", [["layers-vobjects-transform-again", "layers-vobjects-transform-each"],
                       ["layers-vobjects-flip-h", "layers-vobjects-flip-v"],
                       ["layers-vobjects-corners-reset"], ["dialogs-transform"]])],
    [(None, [["layers-vobjects-lock", "layers-vobjects-unlock-all",
              "layers-vobjects-hide", "layers-vobjects-show-all"]])],
    [("_Masque d'écrêtage", [["layers-vobjects-clip-make", "layers-vobjects-clip-release"]]),
     ("_Pathfinder", [["chopgimp-pathfinder-union", "chopgimp-pathfinder-minus",
                       "chopgimp-pathfinder-intersect", "chopgimp-pathfinder-exclude"],
                      ["chopgimp-pathfinder-divide"]]),
     ("_Contours", [["chopgimp-contour-offset", "chopgimp-contour-outline",
                     "chopgimp-contour-simplify", "chopgimp-contour-round"],
                    ["chopgimp-contour-reverse", "chopgimp-contour-close"]]),
     ("_Nœuds", [["chopgimp-nodes-corner", "chopgimp-nodes-smooth",
                  "chopgimp-nodes-symmetric", "chopgimp-nodes-auto"],
                 ["chopgimp-nodes-line", "chopgimp-nodes-curve"],
                 ["chopgimp-nodes-align-left", "chopgimp-nodes-align-hcenter",
                  "chopgimp-nodes-align-right", "chopgimp-nodes-align-top",
                  "chopgimp-nodes-align-vcenter", "chopgimp-nodes-align-bottom",
                  "chopgimp-nodes-distribute-h", "chopgimp-nodes-distribute-v"],
                 ["chopgimp-nodes-select-all", "chopgimp-nodes-delete", "chopgimp-nodes-join",
                  "chopgimp-nodes-break", "chopgimp-nodes-round"]]),
     ("_Effets de tracé", [["chopgimp-path-effects-dialog"],
                           ["chopgimp-fx-zigzag", "chopgimp-fx-roughen", "chopgimp-fx-wave",
                            "chopgimp-fx-pucker", "chopgimp-fx-twist", "chopgimp-fx-width",
                            "chopgimp-fx-arrows"],
                           ["chopgimp-fx-stroke-inside", "chopgimp-fx-stroke-outside",
                            "chopgimp-fx-brush-stroke"],
                           ["chopgimp-vector-eraser"],
                           ["chopgimp-fx-edit", "chopgimp-fx-remove"]]),
     # 3.27.6 (lot V6 point 8) : Distorsion (enveloppes, déformations)
     ("D_istorsion", [["layers-vobjects-distort-warp", "layers-vobjects-distort-mesh",
                       "layers-vobjects-distort-top", "layers-vobjects-distort-free"],
                      ["layers-vobjects-distort-edit-envelope",
                       "layers-vobjects-distort-edit-contents",
                       "layers-vobjects-distort-to-mesh"],
                      ["layers-vobjects-distort-expand", "layers-vobjects-distort-release"]])],
    # 3.29.1 (bloc 3 « couleur et matière ») : Transition, Filet et dégradés,
    # Masque d'opacité, Motif
    [("T_ransition", [["layers-vobjects-blend-make", "layers-vobjects-blend-options"],
                      ["layers-vobjects-blend-release", "layers-vobjects-blend-expand",
                       "layers-vobjects-blend-reverse", "layers-vobjects-blend-spine"]]),
     ("_Filet et dégradés", [["layers-vobjects-mesh-make", "layers-vobjects-freeform-make"],
                             ["layers-vobjects-stroke-gradient-within",
                              "layers-vobjects-stroke-gradient-along",
                              "layers-vobjects-stroke-gradient-across"]]),
     ("Masque d'_opacité", [["layers-vobjects-opmask-make", "layers-vobjects-opmask-release"],
                            ["layers-vobjects-opmask-clip", "layers-vobjects-opmask-invert"]]),
     ("_Motif", [["layers-vobjects-pattern-make", "layers-vobjects-pattern-apply",
                  "layers-vobjects-pattern-options"],
                 ["layers-vobjects-pattern-edit", "layers-vobjects-pattern-finish"]])],
    # 3.30.0 (blocs vectoriels 4 et 5) : Répétition, Formes de pinceau
    [("Ré_pétition", [["layers-vobjects-repeat-radial", "layers-vobjects-repeat-grid",
                       "layers-vobjects-repeat-mirror", "layers-vobjects-repeat-options"],
                      ["layers-vobjects-repeat-release", "layers-vobjects-repeat-expand"]]),
     ("Formes de pi_nceau", [["layers-vobjects-brush-calligraphic", "layers-vobjects-brush-art",
                              "layers-vobjects-brush-pattern", "layers-vobjects-brush-scatter",
                              "layers-vobjects-brush-options"],
                             ["layers-vobjects-brush-define", "dialogs-vbrushes"],
                             ["layers-vobjects-brush-release", "layers-vobjects-brush-expand"]])],
    # 3.28.1 (lot V6 points 6 et 7) : Peinture dynamique, Symboles
    [("_Peinture dynamique", [["layers-vobjects-livepaint-make", "layers-vobjects-livepaint-add"],
                              ["layers-vobjects-livepaint-gap"],
                              ["layers-vobjects-livepaint-expand",
                               "layers-vobjects-livepaint-release"]]),
     ("S_ymboles", [["layers-vobjects-symbol-new", "layers-vobjects-symbol-edit",
                     "layers-vobjects-symbol-break"], ["dialogs-symbols"]])],
    # 3.27.2 (lot V3) : panneaux Aspect et Contour ; (lot V6.2) Couleurs globales
    [(None, [["dialogs-appearance", "dialogs-stroke", "dialogs-global-colors",
              "dialogs-symbols", "dialogs-transform", "layers-vobjects-style-picker",
              "layers-vobjects-recolor"]])],
    # 3.27.3 (lot V5 et V6 point 4) : Vectorisation dynamique
    [("_Vectorisation", [["layers-image-trace", "layers-image-trace-options",
                          "layers-image-trace-expand"]]),
     ("C_onvertir", [["layers-vobjects-merge", "layers-vobjects-split",
                      "layers-vobjects-decompose", "photogimp-split-shapes"]])],
    # 3.29.3 : sélection par couleur / taille, nettoyage, couleurs
    [("_Sélectionner", [["layers-vobjects-select-all", "layers-vobjects-select-inverse"],
                         ["layers-vobjects-select-next-above", "layers-vobjects-select-next-below"],
                         ["layers-vobjects-select-same-fill", "layers-vobjects-select-same-stroke",
                          "layers-vobjects-select-same-color"],
                         ["layers-vobjects-select-smaller"]]),
     ("_Nettoyer", [["layers-vobjects-delete-smaller", "layers-vobjects-fill-holes"],
                    ["layers-vobjects-simplify", "layers-vobjects-merge-same-color"]]),
     ("Co_uleurs", [["layers-vobjects-drawing-colors"],
                    ["layers-vobjects-swap-fill-stroke", "layers-vobjects-fill-none",
                     "layers-vobjects-stroke-none"]])],
    [(None, [["layers-vobjects-lock-others", "layers-vobjects-hide-others"]])],
    [(None, [["layers-vobjects-select-all", "layers-vobjects-delete"]])],
]


def vecteur_menu(indent):
    i = " " * indent
    l = []
    for sec in VECTEUR_MENU:
        l.append(i + "<section>")
        for label, sections in sec:
            if label is None:
                for s_ in sections:
                    l += acts(s_, indent + 2)
            else:
                l += submenu(label, sections, indent + 2)
        l.append(i + "</section>")
    return l


objet = (["    <submenu>",
          '      <attribute name="label" translatable="no">_Vecteur</attribute>'] +
         vecteur_menu(6) + ["    </submenu>"])


# ── Image (ChopGimp 3.27.4) : ordre Photoshop, Couleurs fondu dedans ───
# Mode / Codage / Gestion des couleurs ; Réglages (tout l'ancien menu
# Couleurs, sans doublons) ; Tons / Contraste / Couleur auto ; tailles et
# rotation ; recadrages ; contenu et IA ; dupliquer, instantanés ;
# propriétés. Les sous-menus et sections nommées de GIMP gardent leur
# libellé d'origine : les plug-ins redirigés (« <Image>/Image/Réglages/
# Info », « …/[Modify] », « …/Map/[Colormap] »…) s'y retrouvent.
def sub_block(block, marker):
    """Lignes du sous-menu de GIMP dont le libellé contient « marker »."""
    for n, l in enumerate(block):
        if marker in l and 'name="label"' in l:
            start = n - 1
            ind = block[start][:len(block[start]) - len(block[start].lstrip())]
            for m in range(start + 1, len(block)):
                if block[m] == ind + "</submenu>":
                    return block[start:m + 1]
    sys.exit("Menu de GIMP inattendu : sous-menu « %s » introuvable" % marker)


def reindent(lines, indent):
    cur = len(lines[0]) - len(lines[0].lstrip())
    return [" " * indent + l[cur:] if l.strip() else l for l in lines]


def gimp_submenu(label_line, sections, indent):
    """Sous-menu au libellé GIMP d'origine (traduit), sections d'actions."""
    i = " " * indent
    l = [i + "<submenu>", i + "  " + label_line.strip()]
    for sec in sections:
        name = None
        if sec and sec[0].startswith("["):
            name, sec = sec[0][1:-1], sec[1:]
        l.append(i + "  <section>")
        if name:
            l.append(i + '    <attribute name="section-name" translatable="no">%s</attribute>' % name)
        l += acts(sec, indent + 4)
        l.append(i + "  </section>")
    return l + [i + "</submenu>"]


def label_line(block, marker):
    return [l for l in sub_block(block, marker) if 'name="label"' in l][0]


_img, _col = get["_Image"], get["_Colors"]
_img_secs = layer_sections(_img)
SEC_MODE = pick(_img_secs, "image-convert-rgb")            # Mode, Codage, Gestion des couleurs
TRANSFORMER = reindent(sub_block(_img, ">_Transform<"), 8)
GUIDES = reindent(sub_block(_img, ">_Guides<"), 8)
METADONNEES = reindent(sub_block(_img, ">Meta_data<"), 8)

REGLAGES = reindent(
    ["<submenu>", '  <attribute name="label" translatable="no">_Réglages</attribute>'] +
    ["  " + l for l in
     ["<section>"] + acts(["filters-brightness-contrast", "filters-levels", "filters-curves",
                           "filters-exposure"], 2) + ["</section>"] +
     ["<section>"] + acts(["filters-hue-saturation", "filters-hue-chroma", "filters-saturation",
                           "filters-color-balance", "filters-color-temperature",
                           "filters-colorize", "photogimp-split-toning",
                           "filters-channel-mixer", "filters-mono-mixer"], 2) + ["</section>"] +
     ["<section>", '  <attribute name="section-name" translatable="no">Invert</attribute>'] +
     acts(["filters-invert-perceptual", "filters-invert-linear", "filters-invert-value"], 2) +
     ["</section>"] +
     # « Modify » : Ôter les pixels chauds (plug-in) s'y ajoute ;
     # Couleur vers alpha reste dans Calque > Transparence
     ["<section>", '  <attribute name="section-name" translatable="no">Modify</attribute>'] +
     acts(["filters-posterize", "filters-threshold", "filters-dither", "filters-rgb-clip"], 2) +
     ["</section>"] +
     ["<section>"] + acts(["filters-shadows-highlights", "filters-desaturate"], 2) +
     ["</section>"] +
     ["<section>"] +
     gimp_submenu(label_line(_col, ">_Auto<"),
                  [["drawable-equalize", "drawable-levels-stretch", "filters-stretch-contrast",
                    "filters-stretch-contrast-hsv", "filters-color-enhance"]], 2) +
     gimp_submenu(label_line(_col, ">C_omponents<"), [["filters-component-extract"]], 2) +
     gimp_submenu(label_line(_col, ">D_esaturate<"), [["filters-c2g", "filters-sepia"]], 2) +
     gimp_submenu(label_line(_col, ">_Map<"),
                  [["[Colormap]"], ["filters-alien-map", "filters-color-exchange",
                                    "filters-color-rotate"]], 2) +
     gimp_submenu(label_line(_col, ">_Tone Mapping<"),
                  [["filters-fattal-2002", "filters-mantiuk-2006", "filters-reinhard-2005",
                    "filters-stress"]], 2) +
     gimp_submenu(label_line(_col, ">I_nfo<"), [["dialogs-histogram"]], 2) +
     ["</section>"]] +
    ["</submenu>"], 8)

image = _img[:2] + SEC_MODE + [
    "      <section>"] + REGLAGES + [
    "      </section>",
    "      <section>"] + \
    acts(["python-fu-auto-levels", "python-fu-auto-contrast", "python-fu-auto-color"], 8) + [
    "      </section>",
    "      <section>",
    '        <attribute name="section-name" translatable="no">Scale</attribute>'] + \
    acts(["image-scale", "image-resize", "image-print-size", "image-resize-to-layers",
          "image-resize-to-selection"], 8) + TRANSFORMER + [
    "      </section>",
    "      <section>",
    '        <attribute name="section-name" translatable="no">Crop</attribute>'] + \
    acts(["image-crop-to-selection", "image-crop-to-content", "chopgimp-perspective-crop",
          "chopgimp-straighten"], 8) + [
    "      </section>",
    "      <section>"] + \
    acts(["chopgimp-liquid-rescale", "chopgimp-ia-remove-background", "chopgimp-ia-upscale"], 8) + [
    "      </section>",
    "      <section>",
    '        <attribute name="section-name" translatable="no">New</attribute>'] + \
    acts(["image-duplicate"], 8) + \
    submenu("I_nstantané", [["chopgimp-snapshot-new", "chopgimp-snapshot-revert"]], 8) + [
    "      </section>",
    "      <section>",
    '        <attribute name="section-name" translatable="no">Properties</attribute>'] + \
    acts(["image-properties"], 8) + METADONNEES + [
    "      </section>"] + _img[-1:]

# Affichage : Guides (sous-menu de GIMP, scripts redirigés depuis
# <Image>/Image/Guides) et Configurer la grille, après « Afficher… »
GUIDES_SECTION = ["      <section>"] + GUIDES + acts(["image-configure-grid"], 8) + ["      </section>"]

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
def insert_after_section_of(block, marker, extra):
    """Insère « extra » après la section de 1er niveau contenant « marker »."""
    n = [i for i, l in enumerate(block) if marker in l]
    if len(n) != 1:
        sys.exit("Menu de GIMP inattendu : « %s » introuvable" % marker)
    end = next(i for i in range(n[0], len(block)) if block[i] == "      </section>")
    return block[:end + 1] + extra + block[end + 1:]


vue = insert_after_section_of(get["_View"], "app.view-show-guides<", GUIDES_SECTION)
affichage = insert_before_close(vue, ["      <section>"] + ["  " + l for l in apparence] +
                                ["      </section>",
                                 "      <section>",
                                 '        <item><attribute name="action">app.view-popup-palette</attribute></item>',
                                 '        <item><attribute name="action">app.view-timelapse</attribute></item>',
                                 "      </section>"])

order = [
    get["_File"],
    insert_before_close(get["_Edit"], [
        "      <section>",
        "        <submenu>",
        '          <attribute name="label" translatable="no">Actions</attribute>',
        '          <item><attribute name="action">app.edit-macro-record</attribute></item>',
        '          <item><attribute name="action">app.edit-macro-play</attribute></item>',
        "        </submenu>",
        "      </section>"]),
    image,
    calque,
    objet,
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
                    "ChopGimp : généré par tools/build_menus.py — ne pas éditer.")
xml.dom.minidom.parseString(text.encode("utf-8"))   # validation XML
_act = re.compile(r'name="action">app\.([^<]+)<')
_lost = sorted(set(_act.findall("\n".join(lines))) - set(_act.findall(text)))
if _lost:
    sys.exit("Actions GIMP perdues par la réorganisation des menus : %s" % ", ".join(_lost))
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
<!-- ChopGimp : généré par tools/build_menus.py — ne pas éditer. -->
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

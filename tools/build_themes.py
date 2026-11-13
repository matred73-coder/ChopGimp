#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — génère le thème « ChopGimp » et ses variantes de couleurs.

    python3 tools/build_themes.py          écrit themes/ChopGimp/ et l'alias PS-Dark
    python3 tools/build_themes.py --check  vérifie seulement (lint), code 1 si erreur

Structure produite (themes/ChopGimp/) :
    common.css, common-dark.css, common-light.css, system.css, ui/   (base GIMP 3.2.8)
    ps-overrides.css      surcouche « Photoshop » : uniquement des variables, tailles en rem
    palette-<variante>.css  les couleurs d'une variante
    gimp-dark.css         sombre      (schéma « sombre » de GIMP)
    gimp-gray.css         gris moyen  (schéma « gris »)
    gimp-light.css        clair       (schéma « clair »)

Les autres variantes (gris clair, contraste élevé, Affinity, Krita) sont des
palettes ajoutées après le thème par app/gui/themes.c (réglage
[appearance] variant de chopgimprc), au-dessus du schéma indiqué par BASE.
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "themes", "src")          # fichiers de base (copiés)
OUT = os.path.join(ROOT, "themes", "ChopGimp")
ALIAS = os.path.join(ROOT, "themes", "PS-Dark")

NAMES = [
    "ps-accent", "ps-accent-hover", "ps-accent-pressed",
    "ps-canvas", "ps-field", "ps-chrome", "ps-list", "ps-button-border", "ps-white",
    "fg-color", "bg-color", "border-color",
    "dimmed-fg-color", "disabled-fg-color", "disabled-button-color",
    "hover-color", "widget-bg-color", "selected-color",
    "extreme-bg-color", "extreme-selected-color",
    "strong-border-color", "stronger-border-color", "edge-border-color",
    "scrollbar-slider-color", "scrollbar-trough-color", "ruler-color",
    # ajoutées pour ne plus rien coder en dur dans ps-overrides.css
    "ps-danger", "ps-danger-fg", "ps-progress", "ps-knob", "ps-check-border",
    "scrollbar-slider-hover-color", "scrollbar-slider-active-color",
    "ps-tooltip-bg", "ps-tooltip-fg",
    "ps-strong-fg",          # texte mis en avant (onglet actif, ligne sélectionnée)
]

BLUE = ("#378EF0", "#4B9CF5", "#2680EB")
BLUE_L = ("#1473E6", "#2680EB", "#0D66D0")

PALETTES = {
    # nom : (libellé, schéma de base, couleurs dans l'ordre de NAMES)
    "sombre": ("Sombre (Photoshop)", "dark", BLUE + (
        "#1E1E1E", "#252525", "#262626", "#2B2B2B", "#5A5A5A", "#FFFFFF",
        "#DCDCDC", "#323232", "#1A1A1A",
        "#A8A8A8", "#7A7A7A", "#5A5A5A",
        "#3E3E3E", "#252525", "#4A4A4A",
        "#2B2B2B", "#4A4A4A",
        "#262626", "#4A4A4A", "#1A1A1A",
        "#5A5A5A", "transparent", "rgba(0,0,0,0.25)",
        "#E34850", "#FF7B82", "#4E4E4E", "#E0E0E0", "#8A8A8A",
        "#7A7A7A", "#9A9A9A", "#484848", "#FFFFFF", "#FFFFFF")),
    "gris": ("Gris moyen", "gray", BLUE + (
        "#3A3A3A", "#454545", "#424242", "#4A4A4A", "#6E6E6E", "#FFFFFF",
        "#E8E8E8", "#535353", "#3A3A3A",
        "#BDBDBD", "#8C8C8C", "#6E6E6E",
        "#5F5F5F", "#454545", "#6A6A6A",
        "#4A4A4A", "#6A6A6A",
        "#424242", "#6A6A6A", "#3A3A3A",
        "#7A7A7A", "transparent", "rgba(0,0,0,0.20)",
        "#E34850", "#FF9AA0", "#666666", "#F0F0F0", "#9A9A9A",
        "#8C8C8C", "#A8A8A8", "#3A3A3A", "#FFFFFF", "#FFFFFF")),
    "gris-clair": ("Gris clair", "light", BLUE_L + (
        "#A0A0A0", "#D6D6D6", "#ABABAB", "#C4C4C4", "#8C8C8C", "#FFFFFF",
        "#1E1E1E", "#B8B8B8", "#9A9A9A",
        "#3E3E3E", "#6E6E6E", "#9A9A9A",
        "#C6C6C6", "#D6D6D6", "#D9D9D9",
        "#C4C4C4", "#E0E0E0",
        "#A6A6A6", "#8C8C8C", "#9A9A9A",
        "#8C8C8C", "transparent", "rgba(0,0,0,0.12)",
        "#C9252D", "#B0141B", "#9C9C9C", "#FFFFFF", "#6E6E6E",
        "#6E6E6E", "#5A5A5A", "#3E3E3E", "#FFFFFF", "#000000")),
    "clair": ("Clair", "light", BLUE_L + (
        "#D4D4D4", "#FFFFFF", "#E8E8E8", "#FAFAFA", "#C2C2C2", "#FFFFFF",
        "#1E1E1E", "#F0F0F0", "#D0D0D0",
        "#5A5A5A", "#9A9A9A", "#D0D0D0",
        "#E1E1E1", "#FFFFFF", "#DADADA",
        "#FAFAFA", "#DADADA",
        "#DCDCDC", "#C2C2C2", "#D0D0D0",
        "#A8A8A8", "transparent", "rgba(0,0,0,0.08)",
        "#C9252D", "#B0141B", "#C8C8C8", "#FFFFFF", "#8A8A8A",
        "#8C8C8C", "#6E6E6E", "#323232", "#FFFFFF", "#000000")),
    "contraste": ("Contraste élevé", "dark", ("#FFD400", "#FFE14D", "#E6BE00") + (
        "#000000", "#000000", "#000000", "#000000", "#FFFFFF", "#FFFFFF",
        "#FFFFFF", "#0A0A0A", "#FFFFFF",
        "#F0F0F0", "#A0A0A0", "#808080",
        "#303030", "#000000", "#0050FF",
        "#000000", "#0050FF",
        "#FFFFFF", "#FFFFFF", "#FFFFFF",
        "#FFFFFF", "transparent", "rgba(255,255,255,0.25)",
        "#FF4040", "#FF8080", "#0050FF", "#FFFFFF", "#FFFFFF",
        "#FFD400", "#FFE14D", "#000000", "#FFFFFF", "#FFFFFF")),
    "affinity": ("Anthracite (Affinity)", "dark", ("#00B4E6", "#33C3EB", "#0096C2") + (
        "#1A1B1E", "#26272B", "#222327", "#2A2B2F", "#505259", "#FFFFFF",
        "#E3E4E8", "#2E2F33", "#18191C",
        "#A4A6AD", "#6E7078", "#505259",
        "#3A3B40", "#26272B", "#44464D",
        "#2A2B2F", "#44464D",
        "#222327", "#44464D", "#18191C",
        "#5A5C63", "transparent", "rgba(0,0,0,0.25)",
        "#E34850", "#FF7B82", "#4A4C53", "#E3E4E8", "#7A7C84",
        "#6E7078", "#8A8C94", "#3A3B40", "#FFFFFF", "#FFFFFF")),
    "krita": ("Gris bleuté (Krita)", "dark", ("#3DAEE9", "#5CBBEE", "#2C9AD4") + (
        "#232629", "#1D2023", "#2A2E32", "#232629", "#5C6166", "#FFFFFF",
        "#EFF0F1", "#31363B", "#1D2023",
        "#A1A9B1", "#6E757C", "#4D5257",
        "#3B4045", "#232629", "#2F5A75",
        "#232629", "#2F5A75",
        "#2A2E32", "#4D5257", "#1D2023",
        "#5C6166", "transparent", "rgba(0,0,0,0.25)",
        "#DA4453", "#F07E8A", "#4D5257", "#EFF0F1", "#7F8C8D",
        "#6E757C", "#8A9299", "#31363B", "#EFF0F1", "#FFFFFF")),
}

SCHEME_FILES = {"dark": ("gimp-dark.css", "sombre", "common-dark.css"),
                "gray": ("gimp-gray.css", "gris", "common-dark.css"),
                "light": ("gimp-light.css", "clair", "common-light.css")}

HEADER = """/* ═══════════════════════════════════════════════════════════════
 * ChopGimp — {what}
 * Fichier GÉNÉRÉ par tools/build_themes.py : ne pas modifier à la main.
 * ═══════════════════════════════════════════════════════════════ */
"""


def palette_css(name):
    label, base, colors = PALETTES[name]
    assert len(colors) == len(NAMES), name
    lines = [HEADER.format(what="palette « %s » (schéma %s)" % (label, base))]
    for key, value in zip(NAMES, colors):
        lines.append("@define-color %-30s %s;" % (key, value))
    return "\n".join(lines) + "\n"


def lint(path):
    """Pas de taille en pt (la mise à l'échelle des Préférences ne marche
    qu'en rem) ni de couleur codée en dur hors des palettes."""
    errors = []
    text = open(path, encoding="utf-8").read()
    body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for n, line in enumerate(body.split("\n"), 1):
        if re.search(r"\d+(\.\d+)?pt\b", line):
            errors.append("%s:%d: taille en pt (utiliser rem)" % (path, n))
        if re.search(r"#[0-9A-Fa-f]{3,8}\b|\brgba?\(", line):
            errors.append("%s:%d: couleur codée en dur (utiliser une variable)" % (path, n))
    return errors


def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for f in ("common.css", "common-dark.css", "common-light.css", "system.css"):
        shutil.copy(os.path.join(SRC, f), OUT)
    shutil.copytree(os.path.join(SRC, "ui"), os.path.join(OUT, "ui"))
    shutil.copy(os.path.join(SRC, "ps-overrides.css"), OUT)

    for name in PALETTES:
        open(os.path.join(OUT, "palette-%s.css" % name), "w", encoding="utf-8").write(palette_css(name))

    for scheme, (fname, palette, common) in SCHEME_FILES.items():
        open(os.path.join(OUT, fname), "w", encoding="utf-8").write(
            HEADER.format(what="schéma %s" % scheme) +
            '@import url("palette-%s.css");\n@import url("%s");\n@import url("ps-overrides.css");\n'
            % (palette, common))

    # ancien nom du thème (configurations existantes) : simple renvoi
    if os.path.isdir(ALIAS):
        shutil.rmtree(ALIAS)
    os.makedirs(ALIAS)
    for fname, _, _ in SCHEME_FILES.values():
        open(os.path.join(ALIAS, fname), "w", encoding="utf-8").write(
            HEADER.format(what="ancien nom « PS-Dark », renvoie vers ChopGimp") +
            '@import url("../ChopGimp/%s");\n' % fname)

    # liste des variantes pour le code C (nom, libellé, schéma)
    with open(os.path.join(OUT, "variants.txt"), "w", encoding="utf-8") as f:
        for name, (label, base, _) in PALETTES.items():
            f.write("%s\t%s\t%s\n" % (name, base, label))


def main():
    errors = lint(os.path.join(SRC, "ps-overrides.css"))
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    if "--check" in sys.argv:
        print("thème : OK")
        return
    build()
    print("thème ChopGimp : %d variantes écrites dans %s" % (len(PALETTES), OUT))


if __name__ == "__main__":
    main()

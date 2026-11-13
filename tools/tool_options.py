#!/usr/bin/env python3
"""
PhotoGIMP Pro — options par défaut des outils, façon Photoshop.

Fusionne les valeurs ci-dessous dans ~/.config/GIMP/3.2/tool-options/<outil>
(les autres réglages de l'utilisateur sont conservés). Propriétés et valeurs
vérifiées dans les sources de GIMP 3.2.8 (app/tools/*options.c).

Usage : tool_options.py <dossier tool-options>
"""
import os
import re
import sys

TRANSFORM_PS = {                    # Ctrl+T Photoshop 2019+ : proportionnel par défaut
    "constrain-scale": "yes",
    "show-preview": "yes",
    "composited-preview": "yes",
    "synchronous-preview": "yes",
    "preview-opacity": "1.0",
    "grid-type": "none",
}

OPTIONS = {
    # Déplacement (V) : déplace le calque actif (Photoshop, sélection auto désactivée)
    "gimp-move-tool": {"move-type": "layer", "move-current": "yes"},
    # Recadrage (C) : supprime les pixels recadrés, peut agrandir la zone de travail
    "gimp-crop-tool": {"delete-pixels": "yes", "allow-growing": "yes", "layer-only": "no",
                       "highlight": "yes", "highlight-opacity": "0.6"},
    "gimp-unified-transform-tool": TRANSFORM_PS,
    "gimp-scale-tool": TRANSFORM_PS,
    "gimp-perspective-tool": {"show-preview": "yes", "composited-preview": "yes", "grid-type": "none"},
    "gimp-rotate-tool": {"show-preview": "yes", "composited-preview": "yes", "grid-type": "none"},
    # Sélections : anticrénelage, pas de contour progressif
    "gimp-rect-select-tool": {"antialias": "yes", "feather": "no"},
    "gimp-ellipse-select-tool": {"antialias": "yes", "feather": "no"},
    "gimp-free-select-tool": {"antialias": "yes", "feather": "no"},
    # Baguette magique (W) : tolérance 32, contiguë, calque courant
    "gimp-fuzzy-select-tool": {"threshold": "32.0", "antialias": "yes", "sample-merged": "no",
                               "feather": "no"},
    "gimp-by-color-select-tool": {"threshold": "32.0", "antialias": "yes"},
    # Pot de peinture : tolérance 32, couleurs similaires
    "gimp-bucket-fill-tool": {"threshold": "32.0", "fill-area": "similar-colors",
                              "antialias": "yes", "sample-merged": "no"},
    # Pipette (I) : définit la couleur de premier plan, pas de fenêtre d'info
    "gimp-color-picker-tool": {"pick-target": "foreground", "use-info-window": "no",
                               "sample-average": "no"},
    # Texte (T) : taille en points, édition sur le canevas
    "gimp-text-tool": {"font-size-unit": "points", "font-size": "24.0", "antialias": "yes",
                       "use-editor": "no", "show-on-canvas": "no"},
    # Tampon (S) / Correcteur (J) : « Aligné » comme Photoshop
    "gimp-clone-tool": {"align-mode": "yes"},
    "gimp-heal-tool": {"align-mode": "yes"},
    # Forme (U) : fond bleu plein, sans contour (comme un calque de forme Photoshop)
    "gimp-shape-tool": {"enable-fill": "yes", "enable-stroke": "no",
                        "fill-foreground": '(color "R\'G\'B\' u8" 3 "\\050\\140\\240" 0)',
                        "stroke-foreground": '(color "R\'G\'B\' u8" 3 "\\0\\0\\0" 0)',
                        "stroke-width": "4.0"},
    # Zoom (Z) : ne redimensionne pas la fenêtre
    "gimp-zoom-tool": {"auto-resize": "no"},
}


def merge(path, values):
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        text = "# GIMP %s options\n\n# end of %s options\n" % ((os.path.basename(path),) * 2)
    for k, v in values.items():
        pat = re.compile(r"^\(%s [^\n]*\)\n" % re.escape(k), re.M)
        text = pat.sub("", text)
    block = "".join("(%s %s)\n" % kv for kv in values.items())
    m = re.search(r"^# end of", text, re.M)
    text = text[:m.start()] + block + "\n" + text[m.start():] if m else text + block
    open(path, "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    d = sys.argv[1]
    os.makedirs(d, exist_ok=True)
    for tool, values in OPTIONS.items():
        merge(os.path.join(d, tool), values)
    print("%d outils configurés façon Photoshop" % len(OPTIONS))

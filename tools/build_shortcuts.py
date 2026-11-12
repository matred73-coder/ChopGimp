#!/usr/bin/env python3
"""
PhotoGIMP Pro v2 — générateur de config/shortcutsrc (raccourcis Photoshop).

- PS_MAP : correspondance Photoshop (Windows/Linux) → actions GIMP 3.2.
- Chaque action est vérifiée contre data/gimp-3.2.8-default-shortcuts.json
  (actions réelles de GIMP 3.2.8 + raccourcis par défaut).
- Conflits : si une touche Photoshop est déjà prise par défaut par une autre
  action GIMP, cette action perd ce raccourci (ses autres raccourcis restent).
- Aucune touche n'est attribuée deux fois (vérifié, le script échoue sinon).

Usage : python3 tools/build_shortcuts.py  → écrit config/shortcutsrc
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = os.path.join(ROOT, "data", "gimp-3.2.8-default-shortcuts.json")
OUT = os.path.join(ROOT, "config", "shortcutsrc")

P, S, A = "<Primary>", "<Shift>", "<Alt>"

# (section, action, [raccourcis], commentaire)
PS_MAP = [
    # ── Outils (touches simples Photoshop) ─────────────────────────────
    ("Outils", "tools-move",               ["v"],            "Déplacement"),
    ("Outils", "tools-align",              [S + "v"],        "Alignement (groupe Déplacement)"),
    ("Outils", "tools-rect-select",        ["m"],            "Rectangle de sélection"),
    ("Outils", "tools-ellipse-select",     [S + "m"],        "Ellipse de sélection"),
    ("Outils", "tools-free-select",        ["l"],            "Lasso"),
    ("Outils", "tools-iscissors",          [S + "l"],        "Lasso magnétique (ciseaux intelligents)"),
    ("Outils", "tools-fuzzy-select",       ["w"],            "Baguette magique"),
    ("Outils", "tools-foreground-select",  [S + "w"],        "Sélection d'objet / rapide (premier plan)"),
    ("Outils", "tools-by-color-select",    [S + A + "w"],    "Plage de couleurs"),
    ("Outils", "tools-crop",               ["c"],            "Recadrage"),
    ("Outils", "tools-perspective",        [S + "c"],        "Recadrage perspective"),
    ("Outils", "tools-color-picker",       ["i"],            "Pipette"),
    ("Outils", "tools-measure",            [S + "i"],        "Règle"),
    ("Outils", "tools-heal",               ["j"],            "Correcteur"),
    ("Outils", "tools-paintbrush",         ["b"],            "Pinceau"),
    ("Outils", "tools-pencil",             [S + "b"],        "Crayon"),
    ("Outils", "tools-airbrush",           [S + A + "b"],    "Aérographe"),
    ("Outils", "tools-mypaint-brush",      [P + A + "b"],    "Pinceau MyPaint"),
    ("Outils", "tools-clone",              ["s"],            "Tampon de duplication"),
    ("Outils", "tools-perspective-clone",  [S + "s"],        "Tampon de motif / perspective"),
    ("Outils", "tools-eraser",             ["e"],            "Gomme"),
    ("Outils", "tools-gradient",           ["g"],            "Dégradé"),
    ("Outils", "tools-bucket-fill",        [S + "g"],        "Pot de peinture"),
    ("Outils", "tools-convolve",           [S + "r"],        "Goutte d'eau / Netteté"),
    ("Outils", "tools-hand",               ["h"],            "Main"),
    ("Outils", "tools-rotate-view",        ["r"],            "Rotation de la vue"),
    ("Outils", "tools-smudge",             [S + A + "r"],    "Doigt"),
    ("Outils", "tools-dodge-burn",         ["o"],            "Densité − / +"),
    ("Outils", "tools-path",               ["p"],            "Plume"),
    ("Outils", "tools-text",               ["t"],            "Texte"),
    ("Outils", "tools-shape",              ["u"],            "Forme (rectangle, ellipse, polygone, étoile, ligne)"),
    ("Outils", "tools-zoom",               ["z"],            "Zoom"),
    ("Outils", "tools-unified-transform",  [P + "t"],        "Transformation manuelle (Ctrl+T)"),
    ("Outils", "tools-scale",              [P + A + "t"],    "Mise à l'échelle"),
    ("Outils", "tools-rotate",             [S + "t"],        "Rotation"),
    ("Outils", "tools-warp",               [S + P + "x"],    "Fluidité (déformation)"),
    ("Outils", "tools-cage",               [S + A + "t"],    "Déformation de la marionnette (cage)"),

    ("Opacité", "tools-opacity-ps-10", ["1"], "Opacité 10 % (outil de peinture ou calque)"),
    ("Opacité", "tools-opacity-ps-20", ["2"], "Opacité 20 % (outil de peinture ou calque)"),
    ("Opacité", "tools-opacity-ps-30", ["3"], "Opacité 30 % (outil de peinture ou calque)"),
    ("Opacité", "tools-opacity-ps-40", ["4"], "Opacité 40 % (outil de peinture ou calque)"),
    ("Opacité", "tools-opacity-ps-50", ["5"], "Opacité 50 % (outil de peinture ou calque)"),
    ("Opacité", "tools-opacity-ps-60", ["6"], "Opacité 60 % (outil de peinture ou calque)"),
    ("Opacité", "tools-opacity-ps-70", ["7"], "Opacité 70 % (outil de peinture ou calque)"),
    ("Opacité", "tools-opacity-ps-80", ["8"], "Opacité 80 % (outil de peinture ou calque)"),
    ("Opacité", "tools-opacity-ps-90", ["9"], "Opacité 90 % (outil de peinture ou calque)"),
    ("Opacité", "tools-opacity-ps-100", ["0"], "Opacité 100 % (outil de peinture ou calque)"),

    # ── Couleurs, pinceau ──────────────────────────────────────────────
    ("Couleurs", "context-colors-default", ["d"],            "Couleurs par défaut"),
    ("Couleurs", "context-colors-swap",    ["x"],            "Permuter premier plan / arrière-plan"),
    ("Couleurs", "quick-mask-toggle",      ["q"],            "Mode masque"),
    ("Pinceau", "tools-size-decrease",     ["bracketleft"],  "Diminuer la taille ["),
    ("Pinceau", "tools-size-increase",     ["bracketright"], "Augmenter la taille ]"),
    ("Pinceau", "tools-hardness-decrease", [S + "bracketleft"],  "Diminuer la dureté"),
    ("Pinceau", "tools-hardness-increase", [S + "bracketright"], "Augmenter la dureté"),

    # ── Fichier ────────────────────────────────────────────────────────
    ("Fichier", "image-new",               [P + "n"],        "Nouveau"),
    ("Fichier", "file-open",               [P + "o"],        "Ouvrir"),
    ("Fichier", "file-open-as-layers",     [P + S + A + "o"], "Importer (ouvrir en calques)"),
    ("Fichier", "view-close",              [P + "w"],        "Fermer"),
    ("Fichier", "file-close-all",          [P + A + "w"],    "Tout fermer"),
    ("Fichier", "file-save",               [P + "s"],        "Enregistrer"),
    ("Fichier", "file-save-as",            [P + S + "s"],    "Enregistrer sous"),
    ("Fichier", "file-export-as",          [P + S + A + "w"], "Exporter sous"),
    ("Fichier", "file-export",             [P + S + A + "s"], "Exporter (ancien Enregistrer pour le Web)"),
    ("Fichier", "file-quit",               [P + "q"],        "Quitter"),

    # ── Édition ────────────────────────────────────────────────────────
    ("Édition", "edit-undo",               [P + "z"],        "Annuler"),
    ("Édition", "edit-redo",               [P + S + "z"],    "Rétablir"),
    ("Édition", "edit-strong-undo",        [P + A + "z"],    "Annuler (pas à pas)"),
    ("Édition", "edit-cut",                [P + "x"],        "Couper"),
    ("Édition", "edit-copy",               [P + "c"],        "Copier"),
    ("Édition", "edit-copy-visible",       [P + S + "c"],    "Copier avec fusion"),
    ("Édition", "edit-paste",              [P + "v"],        "Coller"),
    ("Édition", "edit-paste-in-place",     [P + S + "v"],    "Coller sur place"),
    ("Édition", "edit-paste-into",         [P + S + A + "v"], "Coller dedans"),
    ("Édition", "edit-paste-as-new-image", [P + A + "v"],    "Coller comme nouvelle image"),
    ("Édition", "edit-clear",              ["Delete"],       "Effacer"),
    ("Édition", "chopgimp-content-aware-fill", [S + "F5"],   "Remplir d'après le contenu"),
    ("Édition", "edit-fill-fg",            [A + "BackSpace"], "Remplir avec la couleur de premier plan"),
    ("Édition", "edit-fill-bg",            [P + "BackSpace"], "Remplir avec la couleur d'arrière-plan"),
    ("Édition", "dialogs-preferences",     [P + "k"],        "Préférences"),
    ("Édition", "dialogs-keyboard-shortcuts", [P + S + A + "k"], "Raccourcis clavier"),

    # ── Image ──────────────────────────────────────────────────────────
    ("Image", "filters-levels",            [P + "l"],        "Niveaux"),
    ("Image", "filters-curves",            [P + "m"],        "Courbes"),
    ("Image", "filters-hue-saturation",    [P + "u"],        "Teinte / Saturation"),
    ("Image", "filters-color-balance",     [P + "b"],        "Balance des couleurs"),
    ("Image", "filters-desaturate",        [P + S + "u"],    "Désaturation"),
    ("Image", "filters-invert-perceptual", [P + "i"],        "Négatif"),
    ("Image", "filters-threshold",         [P + S + A + "t"],    "Seuil"),
    ("Image", "drawable-levels-stretch",   [P + S + "l"],    "Tons auto"),
    ("Image", "filters-brightness-contrast", [P + A + "l"],  "Luminosité / Contraste"),
    ("Image", "image-scale",               [P + A + "i"],    "Taille de l'image"),
    ("Image", "image-resize",              [P + A + "c"],    "Taille de la zone de travail"),
    ("Image", "image-crop-to-selection",   [P + A + "x"],    "Recadrer sur la sélection"),
    ("Image", "image-duplicate",           [P + S + A + "d"], "Dupliquer l'image"),

    # ── Calque ─────────────────────────────────────────────────────────
    ("Calque", "layers-new",               [P + S + "n"],    "Nouveau calque"),
    ("Calque", "layers-duplicate",         [P + "j"],        "Dupliquer le calque (Calque par copie)"),
    ("Calque", "layers-new-group",         [P + "g"],        "Grouper les calques"),
    ("Calque", "layers-merge-down",        [P + "e"],        "Fusionner avec le calque inférieur"),
    ("Calque", "image-merge-layers",       [P + S + "e"],    "Fusionner les calques visibles"),
    ("Calque", "photogimp-stamp-visible",  [P + S + A + "e"], "Fusionner sur un nouveau calque (tampon visible)"),
    ("Calque", "photogimp-clipping-toggle", [P + A + "g"],   "Créer / annuler le masque d'écrêtage"),
    ("Calque", "layers-new-last-values",   [P + S + A + "n"], "Nouveau calque sans boîte de dialogue"),
    ("Calque", "layers-raise",             [P + "bracketright"], "Premier plan d'un niveau"),
    ("Calque", "layers-lower",             [P + "bracketleft"],  "Arrière-plan d'un niveau"),
    ("Calque", "layers-raise-to-top",      [P + S + "bracketright"], "Premier plan"),
    ("Calque", "layers-lower-to-bottom",   [P + S + "bracketleft"],  "Arrière-plan"),
    ("Calque", "layers-select-previous",   [A + "bracketright"], "Sélectionner le calque du dessus"),
    ("Calque", "layers-select-next",       [A + "bracketleft"],  "Sélectionner le calque du dessous"),
    ("Calque", "layers-mask-add",          [P + A + "m"],    "Ajouter un masque de fusion"),
    ("Calque", "layers-anchor",            [P + A + "h"],    "Ancrer la sélection flottante"),

    # ── Sélection ──────────────────────────────────────────────────────
    ("Sélection", "select-all",            [P + "a"],        "Tout sélectionner"),
    ("Sélection", "select-none",           [P + "d"],        "Désélectionner"),
    ("Sélection", "select-invert",         [P + S + "i"],    "Intervertir"),
    ("Sélection", "select-feather",        [S + "F6"],       "Contour progressif"),
    ("Sélection", "select-cut-float",      [P + S + "j"],    "Calque par coupure (sélection flottante)"),

    # ── Filtre ─────────────────────────────────────────────────────────
    ("Filtre", "filters-repeat",           [P + A + "f"],    "Dernier filtre"),
    ("Filtre", "filters-reshow",           [P + S + A + "f"], "Réafficher le dernier filtre"),

    # ── Affichage ──────────────────────────────────────────────────────
    ("Affichage", "view-zoom-in",          [P + "plus", P + "equal", P + "KP_Add"], "Zoom avant"),
    ("Affichage", "view-zoom-out",         [P + "minus", P + "KP_Subtract"], "Zoom arrière"),
    ("Affichage", "view-zoom-fit-in",      [P + "0", P + "KP_0"], "Taille écran"),
    ("Affichage", "view-zoom-1-1",         [P + "1", P + A + "0"], "100 %"),
    ("Affichage", "view-show-rulers",      [P + "r"],        "Règles"),
    ("Affichage", "view-show-guides",      [P + "semicolon"], "Repères"),
    ("Affichage", "view-show-grid",        [P + "apostrophe"], "Grille"),
    ("Affichage", "view-snap-to-guides",   [P + S + "semicolon"], "Magnétisme"),
    ("Affichage", "view-show-selection",   [P + "h"],        "Extras (afficher la sélection)"),
    ("Affichage", "view-fullscreen",       ["f", "F11"],     "Mode plein écran"),
    ("Affichage", "windows-hide-docks",    ["Tab"],          "Masquer les panneaux"),
    ("Affichage", "view-rotate-reset",     [S + "Escape"],   "Réinitialiser la rotation"),

    # ── Fenêtre ────────────────────────────────────────────────────────
    ("Fenêtre", "dialogs-brushes",         ["F5"],           "Pinceaux"),
    ("Fenêtre", "dialogs-colors",          ["F6"],           "Couleur"),
    ("Fenêtre", "dialogs-layers",          ["F7"],           "Calques"),
    ("Fenêtre", "dialogs-cursor",         ["F8"],           "Infos"),
    ("Fenêtre", "dialogs-undo-history",    [A + "F9"],       "Historique"),
]


def norm(k):
    """Normalise un raccourci pour comparaison (modificateurs triés, touche en minuscules)."""
    mods = re.findall(r"<([^>]+)>", k)
    key = re.sub(r"<[^>]+>", "", k)
    mods = sorted({{"control": "primary", "ctrl": "primary"}.get(m.lower(), m.lower()) for m in mods})
    if len(key) == 1:
        key = key.lower()
    return "".join("<%s>" % m for m in mods) + key


def main():
    global PS_MAP
    if "--v2" in sys.argv:   # GIMP non recompilé : actions ajoutées par les patchs absentes
        PS_MAP = [e for e in PS_MAP if not e[1].startswith(("tools-opacity-ps-", "tools-hand",
                                                             "tools-rotate-view", "tools-shape"))]
    defaults = json.load(open(DEFAULTS))
    errors = []

    # 1. actions valides
    for _, act, _, _ in PS_MAP:
        if act not in defaults and not act.startswith(("photogimp-", "chopgimp-", "tools-opacity-ps-", "tools-hand", "tools-rotate-view", "tools-shape")):
            errors.append("action inconnue de GIMP 3.2.8 : %s" % act)

    # 2. aucune touche attribuée deux fois dans PS_MAP
    owner = {}
    for _, act, keys, _ in PS_MAP:
        for k in keys:
            n = norm(k)
            if n in owner and owner[n] != act:
                errors.append("touche %s attribuée à %s ET %s" % (k, owner[n], act))
            owner[n] = act
    if errors:
        print("\n".join(errors))
        sys.exit(1)

    # 3. conflits avec les raccourcis par défaut des autres actions
    mapped = {act for _, act, _, _ in PS_MAP}
    freed = {}
    for act, keys in defaults.items():
        # Les actions contextuelles (édition de texte, outil chemin) cohabitent
        # avec les raccourcis globaux : on ne les touche pas.
        if act in mapped or not keys or act.startswith(("text-tool-", "tool-path-")):
            continue
        keep = [k for k in keys if norm(k) not in owner]
        if len(keep) != len(keys):
            freed[act] = (keys, keep)

    lines = ["# GIMP shortcutsrc — PhotoGIMP Pro v2 (raccourcis Photoshop)",
             "# Généré par tools/build_shortcuts.py — ne pas éditer à la main.",
             "# Les actions absentes gardent leur raccourci GIMP par défaut.",
             "", "(file-version 1)", ""]
    section = None
    for sec, act, keys, comment in PS_MAP:
        if sec != section:
            lines += ["", "# ── %s %s" % (sec, "─" * (60 - len(sec)))]
            section = sec
        lines.append('(action "%s"%s)  # %s' % (act, "".join(' "%s"' % k for k in keys), comment))

    lines += ["", "# ── Raccourcis GIMP libérés (touche reprise par un raccourci Photoshop) ──"]
    for act in sorted(freed):
        old, keep = freed[act]
        lines.append('(action "%s"%s)  # était : %s' % (act, "".join(' "%s"' % k for k in keep), " ".join(old)))
    lines += ["", "# end of shortcutsrc", ""]

    # GIMP n'accepte pas les commentaires en fin de ligne : on les place au-dessus.
    final = []
    for l in lines:
        if l.startswith("(action") and "  # " in l:
            code, com = l.split("  # ", 1)
            final += ["# " + com, code]
        else:
            final.append(l)
    open(OUT, "w").write("\n".join(final))
    print("%d raccourcis Photoshop, %d actions GIMP libérées → %s" % (len(PS_MAP), len(freed), OUT))
    for act in sorted(freed):
        print("  libéré :", act, freed[act][0], "→", freed[act][1])


if __name__ == "__main__":
    main()

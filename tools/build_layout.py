#!/usr/bin/env python3
"""
PhotoGIMP Pro v2 — génère config/toolrc (boîte à outils façon Photoshop) et
config/sessionrc (espace de travail « Essentiel »).

Usage : build_layout.py   → écrit config/toolrc et config/sessionrc
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Boîte à outils : ordre et groupes de la barre d'outils Photoshop.
# Un tuple = un groupe (le 1er est l'outil affiché), une chaîne = outil seul.
TOOLBOX = [
    ("move", "align"),                                        # V
    ("rect-select", "ellipse-select"),                        # M
    ("free-select", "iscissors"),                             # L
    ("fuzzy-select", "foreground-select", "by-color-select"), # W
    ("crop", "perspective"),                                  # C
    ("color-picker", "measure"),                              # I
    ("spot-heal", "heal"),                                    # J
    ("paintbrush", "pencil", "airbrush", "mypaint-brush", "ink"),  # B
    ("clone", "perspective-clone"),                           # S
    ("eraser",),                                              # E
    ("gradient", "bucket-fill"),                              # G
    ("convolve", "smudge"),                                   # Goutte d'eau / Doigt
    ("dodge-burn",),                                          # O
    ("path", "direct-select"),                                # P / A
    ("text",),                                                # T
    ("shape", "shape-builder"),                               # U / Maj+Alt+M
    ("unified-transform", "scale", "rotate", "shear", "flip",
     "transform-3d", "handle-transform", "warp", "cage", "offset"),  # Ctrl+T
    ("hand", "rotate-view"),                                  # H / R
    ("zoom",),                                                # Z
]
# Outils de réglage : accessibles par Image > Réglages, masqués de la boîte.
HIDDEN = ["brightness-contrast", "threshold", "levels", "curves", "gegl"]

ICON = {"dodge-burn": "gimp-tool-dodge", "convolve": "gimp-tool-blur",
        "gegl": "gimp-gegl", "hand": "chopgimp-tool-hand",
        "rotate-view": "chopgimp-tool-rotate-view", "shape": "chopgimp-tool-shape",
        "spot-heal": "chopgimp-tool-spot-heal",
        "direct-select": "chopgimp-tool-direct-select",
        "shape-builder": "chopgimp-tool-shape-builder"}


def info(tool, visible=True, indent=""):
    icon = ICON.get(tool, "gimp-tool-" + tool)
    return ('%s(GimpToolInfo "gimp-%s-tool"\n%s    (icon-name "%s")\n%s    (visible %s))'
            % (indent, tool, indent, icon, indent, "yes" if visible else "no"))


def toolrc():
    out = ["# GIMP toolrc — PhotoGIMP Pro v2 (ordre de la barre d'outils Photoshop)",
           "# Généré par tools/build_layout.py", "", "(file-version 1)", ""]
    for g in TOOLBOX:
        if len(g) == 1:
            out.append(info(g[0]))
            continue
        children = "\n".join(info(t, indent="        ") for t in g)
        out.append('(GimpToolGroup "tool group"\n    (visible yes)\n    (active-tool "gimp-%s-tool")\n'
                   '    (children\n%s))' % (g[0], children))
    for t in HIDDEN:
        out.append(info(t, visible=False))
    out += ["", "# end of toolrc", ""]
    return "\n".join(out)


def dockable(name, tab="automatic", preview=None, extra=None, locked=False):
    s = '            (dockable "%s"\n' % name
    if locked:
        s += "                (locked)\n"
    s += "                (tab-style %s)\n" % tab
    if preview:
        s += "                (preview-size %d)\n" % preview
    aux = ['(show-button-bar "true")'] + (extra or [])
    s += "                (aux-info\n" + "\n".join("                    " + a for a in aux) + "))"
    return s


def book(pos, dockables):
    s = "        (book\n"
    if pos is not None:
        s += "            (position %d)\n" % pos
    s += "            (current-page 0)\n" + "\n".join(dockables) + ")"
    return s


def sessionrc():
    color = book(None, [dockable("gimp-color-editor"), dockable("gimp-palette-editor"),
                        dockable("gimp-gradient-list"), dockable("gimp-pattern-grid")])
    # v3 : les options d'outil sont dans la barre d'options horizontale ;
    # le panneau complet reste accessible (bouton à droite de la barre).
    props = book(250, [dockable("gimp-undo-history"),
                       dockable("chopgimp-character"),
                       dockable("chopgimp-paragraph"),
                       dockable("gimp-brush-grid"),
                       dockable("gimp-cursor-view", extra=['(frame-1-mode "pixel")', '(frame-2-mode "rgb-percent")'])])
    layers = book(330, [dockable("gimp-layer-list", tab="name", preview=64),
                        dockable("gimp-channel-list", tab="name", preview=32),
                        dockable("gimp-path-list", tab="name", preview=32)])
    return """# GIMP sessionrc — PhotoGIMP Pro v2 (espace de travail « Essentiel »)
# Généré par tools/build_layout.py. L'installeur conserve la position/taille
# de votre fenêtre principale ; GIMP réécrit ce fichier à chaque fermeture.

(session-info "toplevel"
    (factory-entry "gimp-single-image-window")
    @GEOMETRY@
    (open-on-exit)
    (aux-info
        (left-docks-width "46")
        (right-docks-width "330")
        (maximized "yes"))
    (gimp-toolbox
        (side left))
    (gimp-dock
        (side right)
%s
%s
%s))

(hide-docks no)
(single-window-mode yes)
(show-tabs yes)
(tabs-position 0)
(last-tip-shown 0)

# end of sessionrc
""" % (color, props, layers)


if __name__ == "__main__":
    import sys
    open(os.path.join(ROOT, "config", "toolrc"), "w").write(toolrc())
    sess = sessionrc()
    if "--v2" in sys.argv:   # GIMP non recompilé (Snap) : pas de barre d'options
        sess = sess.replace('            (dockable "gimp-undo-history"',
                            '            (dockable "gimp-tool-options"\n                (locked)\n'
                            '                (tab-style automatic)\n                (aux-info\n'
                            '                    (show-button-bar "true")))\n'
                            '            (dockable "gimp-undo-history"', 1)
    open(os.path.join(ROOT, "config", "sessionrc"), "w").write(sess)
    print("config/toolrc et config/sessionrc générés")

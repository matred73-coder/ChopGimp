#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# PhotoGIMP Pro v2 — installeur (GIMP 3.2 Snap)
#
#   ./install.sh               installe / met à jour
#   ./install.sh --uninstall   restaure la configuration GIMP d'origine
#   ./install.sh --status      affiche l'état de l'installation
#
# Installe : thème PS-Dark, icônes PS-Line, boîte à outils et panneaux
# façon Photoshop, raccourcis Photoshop, barre de menus Photoshop
# (via le lanceur « PhotoGIMP Pro »).
# Ne touche pas aux plug-ins, brosses, polices, préférences de performance.
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$SRC/VERSION")"
GIMP_CFG="$HOME/.config/GIMP/3.2"
PG_DIR="$GIMP_CFG/photogimp"
BACKUPS="$HOME/.config/GIMP/photogimp-backups"
SNAP_GIMP="/snap/gimp/current/usr/share/gimp/3.0"
# Dossier d'icônes vu par GTK dans le Snap ($XDG_DATA_HOME/icons) — voir install_icons
SNAP_ICONS="$HOME/snap/gimp/current/.local/share/icons"
APPS="$HOME/.local/share/applications"
BIN="$HOME/.local/bin"

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; B='\033[0;34m'; N='\033[0m'
step() { echo -e "${G}[✓]${N} $1"; }
warn() { echo -e "${Y}[!]${N} $1"; }
die()  { echo -e "${R}[✗]${N} $1"; exit 1; }

gimp_running() { pgrep -x gimp >/dev/null 2>&1 || pgrep -x gimp-3.2 >/dev/null 2>&1; }

backup() {
    mkdir -p "$BACKUPS"
    local ts; ts="$(date +%Y%m%d-%H%M%S)"
    local name="3.2-$ts.tar.gz"
    # La toute première sauvegarde (config sans PhotoGIMP v2) est marquée « origine »
    if [ ! -f "$BACKUPS/ORIGINE" ]; then
        name="3.2-origine-$ts.tar.gz"
        echo "$name" > "$BACKUPS/ORIGINE"
    fi
    tar czf "$BACKUPS/$name" -C "$HOME/.config/GIMP" 3.2
    step "Sauvegarde de la configuration : $BACKUPS/$name"
}

status() {
    echo -e "${B}PhotoGIMP Pro${N} — source v$VERSION"
    echo "  Installé      : $(cat "$PG_DIR/VERSION" 2>/dev/null || echo non)"
    echo "  GIMP Snap     : $(readlink -f /snap/gimp/current 2>/dev/null || echo absent)"
    echo "  Menus générés : $(cat "$PG_DIR/menus.stamp" 2>/dev/null || echo 'au prochain lancement')"
    echo "  Sauvegarde d'origine : $(cat "$BACKUPS/ORIGINE" 2>/dev/null || echo aucune)"
}

uninstall() {
    gimp_running && die "Fermez GIMP avant de désinstaller."
    local orig; orig="$(cat "$BACKUPS/ORIGINE" 2>/dev/null || true)"
    [ -n "$orig" ] && [ -f "$BACKUPS/$orig" ] || die "Aucune sauvegarde d'origine trouvée dans $BACKUPS"
    backup
    rm -rf "$GIMP_CFG"
    tar xzf "$BACKUPS/$orig" -C "$HOME/.config/GIMP"
    rm -f "$APPS/gimp_gimp.desktop" "$BIN/photogimp"
    rm -rf "$SNAP_ICONS/PS-Line"
    update-desktop-database "$APPS" >/dev/null 2>&1 || true
    step "Configuration d'origine restaurée ($orig). Lanceur PhotoGIMP retiré."
}

install_theme() {
    rm -rf "$GIMP_CFG/themes/PS-Dark"
    mkdir -p "$GIMP_CFG/themes"
    cp -r "$SRC/themes/PS-Dark" "$GIMP_CFG/themes/"
    printf '/* PhotoGIMP Pro v2 : surcharge utilisateur. Le style est dans themes/PS-Dark. */\n' > "$GIMP_CFG/gimp.css"
    step "Thème PS-Dark"
}

install_icons() {
    local dst="$GIMP_CFG/icons/PS-Line"
    rm -rf "$dst"; mkdir -p "$GIMP_CFG/icons"
    # Base complète = icônes Default de GIMP (aucune icône manquante)…
    cp -r "$SNAP_GIMP/icons/Default" "$dst"
    chmod -R u+w "$dst"
    # …puis surcouche des icônes PS-Line originales.
    python3 -I "$SRC/icons/build_icons.py" >/dev/null
    cp -r "$SRC/icons/PS-Line/overlay/." "$dst/"
    sed -i -e 's/^Name=.*/Name=PS-Line/' \
           -e 's/^Comment=.*/Comment=PhotoGIMP Pro — icônes style Photoshop (originales)/' \
           -e '/^Hidden=/d' "$dst/index.theme"
    # GIMP ne communique pas à GTK le dossier des jeux d'icônes utilisateur au
    # démarrage (seul le nom du thème est transmis) : sans cette copie dans le
    # chemin de recherche GTK du Snap, toutes les icônes apparaissent manquantes.
    mkdir -p "$SNAP_ICONS"
    rm -rf "$SNAP_ICONS/PS-Line"
    cp -r "$dst" "$SNAP_ICONS/PS-Line"
    step "Icônes PS-Line ($(ls "$SRC/icons/PS-Line/overlay/scalable/apps" | grep -c -- '-symbolic.svg') icônes redessinées)"
}

merge_gimprc() {
    python3 -I - "$GIMP_CFG/gimprc" <<'EOF'
import re, sys
p = sys.argv[1]
try:
    s = open(p).read()
except FileNotFoundError:
    s = "# GIMP gimprc\n\n# end of gimprc\n"
view = """    (show-menubar yes)
    (show-statusbar yes)
    (show-rulers yes)
    (show-scrollbars yes)
    (show-selection yes)
    (show-layer-boundary no)
    (show-canvas-boundary no)
    (show-guides yes)
    (show-grid no)
    (show-sample-points yes)
    (snap-to-guides yes)
    (snap-to-grid no)
    (snap-to-canvas yes)
    (snap-to-bbox yes)
    (snap-to-equidistance yes)
    (padding-mode custom)
    (padding-color (color-rgb 0.118 0.118 0.118))
    (padding-in-show-all no)"""
simple = {
    "theme": '"PS-Dark"', "theme-color-scheme": "dark",
    "icon-theme": '"PS-Line"', "prefer-symbolic-icons": "yes",
    "toolbox-wilber": "no", "toolbox-color-area": "yes", "toolbox-foo-area": "no",
    "toolbox-image-area": "no", "toolbox-groups": "yes",
    "layer-preview-size": "medium", "show-tool-tips": "yes",
}
image = """    (width 1920)
    (height 1080)
    (unit pixels)
    (xresolution 72)
    (yresolution 72)
    (resolution-unit inches)
    (image-type rgb)
    (precision u8-non-linear)
    (fill-type white)"""
blocks = {"default-view": view, "default-fullscreen-view": view, "default-image": image}

def drop(s, key):
    """Supprime une entrée « (key …) » de premier niveau, même sur plusieurs lignes."""
    pat = re.compile(r"^\(%s[ \n]" % re.escape(key), re.M)
    m = pat.search(s)
    while m:
        depth, j = 0, m.start()
        while True:
            c = s[j]
            depth += (c == "(") - (c == ")")
            j += 1
            if depth == 0:
                break
        if j < len(s) and s[j] == "\n":
            j += 1
        s = s[:m.start()] + s[j:]
        m = pat.search(s)
    return s

for k in list(simple) + list(blocks):
    s = drop(s, k)
s = re.sub(r"# PhotoGIMP Pro v2[^\n]*\n", "", s)
add = "# PhotoGIMP Pro v2 — apparence\n"
add += "".join("(%s %s)\n" % kv for kv in simple.items())
add += "".join("(%s\n%s)\n" % (k, v) for k, v in blocks.items())
if "# end of gimprc" in s:
    s = s.replace("# end of gimprc", add + "\n# end of gimprc")
else:
    s += "\n" + add
open(p, "w").write(s)
EOF
    step "gimprc (thème, icônes, boîte à outils, fond #1E1E1E, magnétisme, document par défaut)"
}

install_layout() {
    python3 -I "$SRC/tools/build_layout.py" --v2 >/dev/null
    python3 -I "$SRC/tools/build_shortcuts.py" --v2 >/dev/null
    cp "$SRC/config/toolrc" "$GIMP_CFG/toolrc"
    cp "$SRC/config/shortcutsrc" "$GIMP_CFG/shortcutsrc"
    # sessionrc : on garde la position / taille / écran de la fenêtre principale actuelle
    local geom
    geom="$(python3 -I - "$GIMP_CFG/sessionrc" <<'EOF'
import re, sys
try:
    s = open(sys.argv[1]).read()
except FileNotFoundError:
    s = ""
m = re.search(r'\(factory-entry "gimp-single-image-window"\)(.*?)\(open-on-exit\)', s, re.S)
g = []
if m:
    for k in ("position", "size", "monitor"):
        mm = re.search(r"\(%s [^)]*\)" % k, m.group(1))
        if mm:
            g.append(mm.group(0))
print("\n    ".join(g) if g else "(position 0 0)\n    (size 1920 1080)")
EOF
)"
    python3 -I - "$SRC/config/sessionrc" "$GIMP_CFG/sessionrc" "$geom" <<'EOF'
import sys
src, dst, geom = sys.argv[1:4]
open(dst, "w").write(open(src).read().replace("@GEOMETRY@", geom))
EOF
    step "Boîte à outils, panneaux « Essentiel » et raccourcis Photoshop"
}

install_documents() {
    python3 -I "$SRC/tools/build_documents.py" >/dev/null
    cp "$SRC/config/templaterc" "$GIMP_CFG/templaterc"
    mkdir -p "$GIMP_CFG/tool-presets" "$GIMP_CFG/palettes"
    # anciens préréglages v1 (anglais) remplacés par les PS-*.gtp
    rm -f "$GIMP_CFG/tool-presets/"{Clone-Aligned,Eraser-Hard,Eraser-Soft,Hard-Round-Brush,Healing-Brush,Soft-Round-Brush}.gtp
    rm -f "$GIMP_CFG/tool-presets/"PS-*.gtp
    cp "$SRC/presets/tool-presets/"*.gtp "$GIMP_CFG/tool-presets/"
    cp "$SRC/presets/palettes/"*.gpl "$GIMP_CFG/palettes/"
    step "Modèles « Nouveau document » ($(grep -c '^(GimpTemplate' "$SRC/config/templaterc")), préréglages d'outils, nuanciers"
}

install_tools() {
    python3 -I "$SRC/tools/tool_options.py" "$GIMP_CFG/tool-options" >/dev/null
    # Molette façon Photoshop : Alt+molette = zoom, Ctrl+molette = défilement horizontal
    python3 -I - "$GIMP_CFG/controllerrc" <<'PYEOF'
import re, sys
p = sys.argv[1]
try:
    s = open(p).read()
except FileNotFoundError:
    sys.exit(0)
ps = {"scroll-up-alt": "view-zoom-in", "scroll-down-alt": "view-zoom-out",
      "scroll-up-primary": "view-scroll-left", "scroll-down-primary": "view-scroll-right"}
m = re.search(r'\(GimpControllerInfo "Main Mouse Wheel".*?\(mapping(.*?)\)\)\n', s, re.S)
if m:
    body = m.group(1)
    for k in ps:
        body = re.sub(r'\n\s*\(map "%s" "[^"]*"\)' % re.escape(k), "", body)
    body += "".join('\n        (map "%s" "%s")' % kv for kv in ps.items())
    s = s[:m.start(1)] + body + s[m.end(1):]
    open(p, "w").write(s)
PYEOF
    step "Outils façon Photoshop (déplacement, recadrage, Ctrl+T, baguette, texte…) + molette"
}

# Plug-ins v1 désactivés (voir data/audit-plugins-v1.json) : remplacés par
# photogimp_ps, ou cassés sous GIMP 3.2. Déplacés (pas supprimés) dans
# photogimp/plug-ins-desactives/ — réversible.
PLUGINS_OFF="$(cat "$SRC/config/plugins-v1-off.txt")"

install_plugins() {
    local off="$PG_DIR/plug-ins-desactives" n=0
    mkdir -p "$off" "$GIMP_CFG/plug-ins"
    for p in $PLUGINS_OFF; do
        if [ -d "$GIMP_CFG/plug-ins/$p" ]; then
            rm -rf "$off/$p"; mv "$GIMP_CFG/plug-ins/$p" "$off/"; n=$((n+1))
        fi
    done
    rm -rf "$GIMP_CFG/plug-ins/photogimp_ps"
    cp -r "$SRC/plug-ins/photogimp_ps" "$GIMP_CFG/plug-ins/"
    chmod +x "$GIMP_CFG/plug-ins/photogimp_ps/photogimp_ps.py"
    step "Plug-in photogimp_ps (écrêtage, styles, calques de réglage) ; $n plug-ins v1 désactivés"
}

install_menus_launcher() {
    mkdir -p "$PG_DIR" "$APPS" "$BIN"
    cp "$SRC/tools/build_menus.py" "$PG_DIR/build_menus.py"
    rm -rf "$PG_DIR/menus" "$PG_DIR/menus.stamp"
    if python3 -I "$PG_DIR/build_menus.py" "$SNAP_GIMP/menus" "$PG_DIR/menus" >/dev/null; then
        readlink -f /snap/gimp/current > "$PG_DIR/menus.stamp"
    else
        warn "Menus Photoshop non générés (GIMP démarrera avec ses menus d'origine)"
    fi
    install -m 755 "$SRC/launcher/photogimp" "$BIN/photogimp"
    # Remplace l'entrée GIMP du menu des applications (même nom de fichier que
    # celle du Snap : la version utilisateur est prioritaire) → tout lancement
    # de GIMP (dock, « Ouvrir avec ») passe par le lanceur PhotoGIMP Pro.
    sed -e "s#^Exec=.*#Exec=$BIN/photogimp %U#" \
        -e 's#^Name=.*#Name=PhotoGIMP Pro (v2, GIMP Snap)#' \
        -e '/^Name\[/d' \
        -e 's#^Comment=.*#Comment=GIMP avec interface façon Photoshop#' \
        -e '/^Comment\[/d' \
        /var/lib/snapd/desktop/applications/gimp_gimp.desktop > "$APPS/gimp_gimp.desktop"
    update-desktop-database "$APPS" >/dev/null 2>&1 || true
    echo "$VERSION" > "$PG_DIR/VERSION"
    step "Barre de menus Photoshop + lanceur « PhotoGIMP Pro » ($BIN/photogimp)"
}

case "${1:-}" in
    --uninstall) uninstall; exit 0 ;;
    --status)    status; exit 0 ;;
    ""|--install) ;;
    *) die "Option inconnue : $1 (voir l'en-tête du script)" ;;
esac

echo -e "\n${B}═══ PhotoGIMP Pro v$VERSION — installation ═══${N}\n"
[ -d "$SNAP_GIMP" ] || die "GIMP Snap introuvable ($SNAP_GIMP). Installez : sudo snap install gimp"
[ -d "$GIMP_CFG" ] || die "Lancez GIMP une première fois pour créer $GIMP_CFG"
gimp_running && die "Fermez GIMP avant d'installer (il réécrit sa configuration à la fermeture)."

backup
install_theme
install_icons
merge_gimprc
install_layout
install_documents
install_tools
install_plugins
install_menus_launcher

echo -e "\n${G}Terminé.${N} Lancez « PhotoGIMP Pro » depuis le menu des applications"
echo "ou avec la commande : photogimp"
echo "Retour à la configuration d'origine : ./install.sh --uninstall"

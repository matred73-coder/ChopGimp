#!/bin/sh
# ═══════════════════════════════════════════════════════════════
# PhotoGIMP Pro v3 — installe les données « Photoshop » dans le paquet
# Flatpak (exécuté par flatpak-builder, module photogimp-data, APRÈS GIMP).
#
#   sh tools/install_data.sh <préfixe>     (préfixe = /app dans le Flatpak)
#
# Tout devient réglage d'usine : thème, icônes, menus, gimprc système,
# disposition, outils, raccourcis, modèles, préréglages, plug-ins.
# ═══════════════════════════════════════════════════════════════
set -eu
DEST="$1"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$DEST/share/gimp/3.0"
ETC="$DEST/etc/gimp/3.0"
PLUG="$DEST/lib/gimp/3.0/plug-ins"
TMP="$(mktemp -d)"

echo "== PhotoGIMP Pro $(cat "$SRC/VERSION") → $DEST"

# 1. Générateurs (fichiers dérivés)
python3 "$SRC/tools/build_layout.py"
python3 "$SRC/tools/build_shortcuts.py"
python3 "$SRC/tools/build_documents.py"
python3 "$SRC/icons/build_icons.py"

# 2. Thème PS-Dark
rm -rf "$DATA/themes/PS-Dark"
cp -r "$SRC/themes/PS-Dark" "$DATA/themes/"

# 3. Icônes PS-Line = Default de GIMP + surcouche originale
rm -rf "$DATA/icons/PS-Line"
cp -r "$DATA/icons/Default" "$DATA/icons/PS-Line"
cp -r "$SRC/icons/PS-Line/overlay/." "$DATA/icons/PS-Line/"
sed -i -e 's/^Name=.*/Name=PS-Line/' -e '/^Hidden=/d' \
       -e 's/^Comment=.*/Comment=PhotoGIMP Pro — icônes style Photoshop (originales)/' \
       "$DATA/icons/PS-Line/index.theme"

# 4. Menus Photoshop (remplacent ceux de GIMP)
python3 "$SRC/tools/build_menus.py" "$DATA/menus" "$TMP/menus"
cp "$TMP/menus/"*.ui "$DATA/menus/"

# 5. Réglages système (etc/gimp/3.0) : lus par GIMP tant que l'utilisateur
#    n'a pas ses propres fichiers
mkdir -p "$ETC/tool-options"
cat "$SRC/config/gimprc-photogimp" >> "$ETC/gimprc"
sed 's/@GEOMETRY@/(position 0 0)\n    (size 1600 900)/' "$SRC/config/sessionrc" > "$ETC/sessionrc"
cp "$SRC/config/toolrc" "$ETC/toolrc"
cp "$SRC/config/templaterc" "$ETC/templaterc"
cp "$SRC/config/shortcutsrc" "$ETC/shortcutsrc"          # lu grâce au patch 0001
python3 "$SRC/tools/wheel_ps.py" "$ETC/controllerrc"
python3 "$SRC/tools/tool_options.py" "$ETC/tool-options"  # lu grâce au patch 0001

# 6. Préréglages d'outils et nuanciers
mkdir -p "$DATA/tool-presets/PhotoGIMP" "$DATA/palettes"
cp "$SRC/presets/tool-presets/"*.gtp "$DATA/tool-presets/PhotoGIMP/"
cp "$SRC/presets/palettes/"*.gpl "$DATA/palettes/"

# 7. Plug-ins : photogimp_ps + plug-ins v1 validés par l'audit
install_plugin() {   # $1 = nom, $2 = fichier source
    mkdir -p "$PLUG/$1"
    install -m 755 "$2" "$PLUG/$1/$1.py"
}
install_plugin photogimp_ps "$SRC/plug-ins/photogimp_ps/photogimp_ps.py"
OFF=" $(tr '\n' ' ' < "$SRC/config/plugins-v1-off.txt") "
for f in "$SRC/scripts/python/"*.py; do
    n="$(basename "$f" .py)"
    case "$OFF" in *" $n "*) continue ;; esac
    install_plugin "$n" "$f"
done

# 8. Lanceur : nom et description
DESK="$DEST/share/applications/gimp.desktop"
if [ -f "$DESK" ]; then
    sed -i -e 's/^Name=.*/Name=PhotoGIMP Pro/' -e '/^Name\[/d' \
           -e 's/^GenericName=.*/GenericName=Éditeur d'"'"'images façon Photoshop/' -e '/^GenericName\[/d' \
           -e 's/^Comment=.*/Comment=GIMP avec interface et fonctionnement façon Photoshop/' -e '/^Comment\[/d' \
           "$DESK"
fi

# 9. Métadonnées AppStream : nom affiché dans les logithèques et « flatpak list »
for META in "$DEST"/share/metainfo/*.xml; do
    [ -f "$META" ] || continue
    python3 - "$META" <<'PYEOF'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
s = re.sub(r"<name>[^<]*</name>", "<name>PhotoGIMP Pro</name>", s, count=1)
s = re.sub(r'\s*<name xml:lang="[^"]*">[^<]*</name>', "", s)
s = re.sub(r"<summary>[^<]*</summary>", "<summary>GIMP avec interface et gestes façon Photoshop</summary>", s, count=1)
s = re.sub(r'\s*<summary xml:lang="[^"]*">[^<]*</summary>', "", s)
open(p, "w", encoding="utf-8").write(s)
PYEOF
done

rm -rf "$TMP"
echo "== PhotoGIMP Pro : données installées"

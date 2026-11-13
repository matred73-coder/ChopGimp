#!/bin/sh
# ═══════════════════════════════════════════════════════════════
# ChopGimp — installe les données « Photoshop » dans le paquet
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

echo "== ChopGimp $(cat "$SRC/VERSION") → $DEST"

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

# 3b. Icônes des boutons de panneaux : aussi dans le thème de secours de GIMP,
#     pour qu'elles existent quel que soit le thème d'icônes choisi
mkdir -p "$DATA/icons/hicolor/scalable/actions"
for i in "$SRC/icons/PS-Line/overlay/scalable/apps/"chopgimp-panel-*.svg \
         "$SRC/icons/PS-Line/overlay/scalable/apps/"chopgimp-dock-*.svg; do
    install -m 644 "$i" "$DATA/icons/hicolor/scalable/actions/"
done

# 3b'. Dictionnaire français (Hunspell, Dicollecte « classique », MPL 2.0)
#      pour la vérification d'orthographe des textes (app/widgets/chopgimp-spell.c)
mkdir -p "$DEST/share/hunspell"
cp "$SRC/data/hunspell/fr.aff" "$SRC/data/hunspell/fr.dic" "$DEST/share/hunspell/"

# 3c. Curseurs « façon Photoshop » (un par outil, tools/build_cursors.py),
#     chargés par app/widgets/gimpcursor.c depuis cursors/chopgimp
mkdir -p "$DATA/cursors/chopgimp"
cp "$SRC/cursors/PS-Line/"*.png "$SRC/cursors/PS-Line/chopgimp-cursors.ini" "$DATA/cursors/chopgimp/"

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

# 5b. Dynamique « Pression taille + opacité » (bouton stylet double de
#     Photoshop) : dérivée de « Pressure Opacity » + pression sur la taille
python3 - "$DATA/dynamics/Basic/Pressure-Opacity.gdyn" "$DATA/dynamics/Basic/Pression-taille-opacite.gdyn" <<'PYEOF'
import re, sys
s = open(sys.argv[1]).read()
s = s.replace('(name "Pressure Opacity")', '(name "Pression taille + opacité")', 1)
i = s.index("(size-output")
j = s.index("(use-pressure no)", i)
s = s[:j] + "(use-pressure yes)" + s[j + len("(use-pressure no)"):]
open(sys.argv[2], "w").write(s)
PYEOF

# 6. Préréglages d'outils et nuanciers
mkdir -p "$DATA/tool-presets/PhotoGIMP" "$DATA/palettes"
cp "$SRC/presets/tool-presets/"*.gtp "$DATA/tool-presets/PhotoGIMP/"
cp "$SRC/presets/palettes/"*.gpl "$DATA/palettes/"

# 7. Plug-ins : photogimp_ps + plug-ins v1 validés par l'audit
install_plugin() {   # $1 = nom, $2 = fichier source
    mkdir -p "$PLUG/$1"
    install -m 755 "$2" "$PLUG/$1/$1.py"
}
for d in "$SRC/plug-ins/"*/; do          # plug-ins ChopGimp (photogimp_ps, chopgimp_fx…)
    n="$(basename "$d")"
    install_plugin "$n" "$d$n.py"
done
OFF=" $(tr '\n' ' ' < "$SRC/config/plugins-v1-off.txt") "
for f in "$SRC/scripts/python/"*.py; do
    n="$(basename "$f" .py)"
    case "$OFF" in *" $n "*) continue ;; esac
    install_plugin "$n" "$f"
done

# 8. Lanceur : nom et description
DESK="$DEST/share/applications/gimp.desktop"
if [ -f "$DESK" ]; then
    sed -i -e 's/^Name=.*/Name=ChopGimp/' -e '/^Name\[/d' \
           -e 's/^GenericName=.*/GenericName=Éditeur d'"'"'images façon Photoshop/' -e '/^GenericName\[/d' \
           -e 's/^Comment=.*/Comment=Retouche d'"'"'images avec une interface familière (basé sur GIMP)/' -e '/^Comment\[/d' \
           "$DESK"
fi

# 9. Identité ChopGimp : icône d'application (remplace Wilber), écran de
#    démarrage, logo « À propos », logo du thème d'icônes
[ -f "$SRC/branding/chopgimp.svg" ] || { echo "branding/ manquant : lancer tools/make_branding.py"; exit 1; }
for SZ in 16 22 24 32 36 48 64 72 96 128 192 256 512; do
    if [ -d "$DEST/share/icons/hicolor/${SZ}x${SZ}/apps" ]; then
        install -m 644 "$SRC/branding/png/chopgimp-$SZ.png" "$DEST/share/icons/hicolor/${SZ}x${SZ}/apps/gimp.png"
    fi
done
install -m 644 "$SRC/branding/chopgimp.svg" "$DEST/share/icons/hicolor/scalable/apps/gimp.svg"
install -m 644 "$SRC/branding/splash.png" "$DATA/images/gimp-splash.png"
install -m 644 "$SRC/branding/logo-128.png" "$DATA/images/gimp-logo.png"
for T in PS-Line Default; do
    L="$DATA/icons/$T/scalable/logo/unisize"
    [ -d "$L" ] || continue
    install -m 644 "$SRC/branding/chopgimp.svg" "$L/gimp-wilber.svg"
    install -m 644 "$SRC/branding/chopgimp-symbolic.svg" "$L/gimp-wilber-symbolic.svg"
done

# 10. Métadonnées AppStream : nom affiché dans les logithèques et « flatpak list »
for META in "$DEST"/share/metainfo/*.xml; do
    [ -f "$META" ] || continue
    python3 - "$META" <<'PYEOF'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
s = re.sub(r"<name>[^<]*</name>", "<name>ChopGimp</name>", s, count=1)
s = re.sub(r'\s*<name xml:lang="[^"]*">[^<]*</name>', "", s)
s = re.sub(r"<summary>[^<]*</summary>", "<summary>Retouche d'images avec une interface familière (basé sur GIMP)</summary>", s, count=1)
s = re.sub(r'\s*<summary xml:lang="[^"]*">[^<]*</summary>', "", s)
open(p, "w", encoding="utf-8").write(s)
PYEOF
done

rm -rf "$TMP"
echo "== ChopGimp : données installées"

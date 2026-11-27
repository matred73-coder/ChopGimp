#!/bin/bash
# ChopGimp 4.2.9 — scénario du banc graphique : Sélection directe (A).
# Deux carrés dans un calque vectoriel ; A sur le 1er, clic sur le 2e (doit
# être sélectionné : X 230 dans la barre d'options), glisser du 2e (X/Y
# changent, repères commentés pendant le glisser), Annuler (retour à 230,100),
# flèches (Droite + Maj+Droite : X 241), Alt+glisser (copie : 3 objets).
# Captures dans $D/shots/ds-*.png, à relire. Coordonnées pour l'écran
# virtuel 1600x900 et la disposition par défaut (image à 100 %).
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
D="${CHOPGIMP_GUITEST:-/tmp/cg-guitest-$(id -u)}"
mkdir -p "$D/shots"
cp "$HERE/scenarios/deux-formes.py" "$D/prep.py"
timeout 200 flatpak run --env=PREP_OUT="$D/deux.xcf" --filesystem="$D" \
  --command=gimp-console-3.2 org.cen_na.ChopGimp -i --batch-interpreter=python-fu-eval \
  -b "exec(open('$D/prep.py').read())" -b "Gimp.get_pdb().lookup_procedure('gimp-quit').run(None)" \
  > "$D/prep.log" 2>&1 || true
"$HERE/guitest.sh" start "$D/deux.xcf"
U() { "$HERE/guitest.sh" ui "$@"; }
S="$D/shots"
U click 430 49 , sleep 1 , action tools-direct-select , sleep 0.5
U click 528 464 , sleep 1 , shot "$S/ds-1-forme1.png"
U click 708 506 , sleep 1 , shot "$S/ds-2-forme2.png"
U move 708 506 , down , rel 10 -4 , rel 10 -4 , rel 10 -4 , rel 10 -4 , rel 10 -4 , \
  sleep 0.5 , shot "$S/ds-3-glisser.png" , up , sleep 1 , shot "$S/ds-4-deplace.png"
U action edit-undo , sleep 1 , shot "$S/ds-5-annule.png"
U move 600 300 , key Right , key Right shift , sleep 1 , shot "$S/ds-6-fleches.png"
U move 720 540 , keydown Alt_L , down , rel 0 10 , rel 0 10 , rel 0 10 , rel 0 10 , up , \
  keyup Alt_L , sleep 1 , shot "$S/ds-7-alt-copie.png"
echo "captures : $S/ds-*.png (arrêt : tools/gui-test/guitest.sh stop)"

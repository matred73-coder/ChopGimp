#!/bin/bash
# Outil de développement ChopGimp. Données dans $DEV (modèles d'IA de test, fichiers de mesure).
DEV=${CHOPGIMP_DEV:-$HOME/.cache/chopgimp-dev}
D=$DEV/smoke
rm -rf "$D"; mkdir -p "$D/cfg"
mkdir -p "$D/cfg/ia-modeles"; cp $DEV/models/u2netp.onnx "$D/cfg/ia-modeles/u2netp.onnx"; cp $DEV/models/super-resolution-10.onnx "$D/cfg/ia-modeles/superres.onnx"; echo '{"segmentation": "u2netp"}' > "$D/cfg/ia-modeles/reglages.json"
timeout 300 flatpak run --env=GIMP3_DIRECTORY=$D/cfg --env=SMOKE_OUT=$D/out.txt --env=SMOKE_TMP=$D/tmp \
  --filesystem=$D --filesystem=$HOME/DOCKER/photogimp-pro:ro \
  --command=gimp-console-3.2 org.cen_na.ChopGimp -i --batch-interpreter=python-fu-eval \
  -b "exec(open('$HOME/DOCKER/photogimp-pro/tools/smoke_test.py').read())" > $D/log.txt 2>&1
grep "^ÉCHEC" $D/out.txt; echo "OK: $(grep -c '^OK' $D/out.txt)  ÉCHEC: $(grep -c '^ÉCHEC' $D/out.txt)"
[ "$(grep -c "^ÉCHEC" $D/out.txt)" = "0" ] && [ "$(grep -c "^OK" $D/out.txt)" -gt 0 ]

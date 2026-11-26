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
# 3.31.0 (lot 4b) : le PSD exporté relu par un lecteur indépendant (psd-tools)
V=$DEV/venv-psd-tools
if [ ! -x "$V/bin/python" ] || ! "$V/bin/python" -c "import psd_tools" 2>/dev/null; then
  { python3 -m venv "$V" 2>/dev/null || { python3 -m venv --without-pip "$V" && \
      curl -sS https://bootstrap.pypa.io/get-pip.py | "$V/bin/python" - -q; }; } && \
    "$V/bin/python" -m pip install -q psd-tools >/dev/null 2>&1
fi
if [ -f "$D/tmp/psd-tools.psd" ] && "$V/bin/python" -c "import psd_tools" 2>/dev/null; then
  "$V/bin/python" "$HOME/DOCKER/photogimp-pro/tools/dev/check_psd_tools.py" "$D/tmp/psd-tools.psd" >> $D/out.txt
else
  echo "ÉCHEC  psd-tools  lecteur indépendant indisponible ou PSD absent" >> $D/out.txt
fi
grep "^ÉCHEC" $D/out.txt; echo "OK: $(grep -c '^OK' $D/out.txt)  ÉCHEC: $(grep -c '^ÉCHEC' $D/out.txt)"
[ "$(grep -c "^ÉCHEC" $D/out.txt)" = "0" ] && [ "$(grep -c "^OK" $D/out.txt)" -gt 0 ]

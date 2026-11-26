#!/bin/bash
# Banc de performance du vectoriel (3.29.2) : tools/dev/bench_vector.py
# dans le paquet installé. Résultat : $DEV/bench-vector/out.txt
DEV=${CHOPGIMP_DEV:-$HOME/.cache/chopgimp-dev}
D=$DEV/bench-vector
rm -rf "$D"; mkdir -p "$D/cfg" "$D/tmp"
timeout 1800 nice -n 10 flatpak run --env=GIMP3_DIRECTORY=$D/cfg --env=BENCH_OUT=$D/out.txt --env=BENCH_TMP=$D/tmp \
  --filesystem=$D --filesystem=$HOME/DOCKER/photogimp-pro:ro \
  --command=gimp-console-3.2 org.cen_na.ChopGimp -i --batch-interpreter=python-fu-eval \
  -b "exec(open('$HOME/DOCKER/photogimp-pro/tools/dev/bench_vector.py').read())" > $D/log.txt 2>&1
column -t -s $'\t' $D/out.txt

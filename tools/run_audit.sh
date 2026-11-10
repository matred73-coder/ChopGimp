#!/bin/bash
# Lance le banc de test des plug-ins dans un GIMP console isolé (config copiée).
# Reprend là où il s'est arrêté ; une procédure qui bloque/plante est marquée HANG.
B="$HOME/DOCKER/photogimp-pro/build"
export PG_PROCS="${PG_PROCS:-$B/all-procs.txt}" PG_OUT="$B/audit.jsonl"
export PG_SKIP="python-fu-dafont-installer python-fu-google-fonts python-fu-batch-export python-fu-image-processor python-fu-contact-sheet python-fu-data-merge photogimp-multi-page-pdf python-fu-export-layers"
for i in $(seq 1 40); do
  env -i HOME="$HOME" PATH=/usr/bin:/bin:/snap/bin XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
      GIMP3_DIRECTORY="$B/testcfg" PG_PROCS="$PG_PROCS" PG_OUT="$PG_OUT" PG_SKIP="$PG_SKIP" \
      timeout 240 snap run --shell gimp -c "gimp-console-3.2 -i --batch-interpreter=python-fu-eval -b 'exec(open(\"$HOME/DOCKER/photogimp-pro/tools/audit_plugins.py\").read())' >> $B/audit-stderr.log 2>&1" >> "$B/audit-console.log" 2>&1
  last=$(tail -1 "$PG_OUT" 2>/dev/null)
  if echo "$last" | grep -q '"STARTED"'; then
     echo "$last" | sed 's/"STARTED"/"HANG"/' >> "$PG_OUT"
  else
     total=$(wc -w < "$PG_PROCS"); lines=$(wc -l < "$PG_PROCS")
     n=$(grep -vc '"STARTED"' "$PG_OUT")
     [ "$n" -ge $((total - lines)) ] && break
  fi
done
echo "FIN audit"

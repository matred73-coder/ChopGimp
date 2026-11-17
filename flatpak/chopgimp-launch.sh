#!/bin/sh
# ChopGimp — lanceur (commande du Flatpak et du .desktop), installé en
# /app/bin/chopgimp par tools/install_data.sh.
#
# Environnement de performance, puis GIMP :
#   - mimalloc (/app/lib/libmimalloc.so.2) remplace l'allocateur de la glibc :
#     moins de contention entre les fils de GEGL, mémoire rendue plus vite.
#     CHOPGIMP_NO_MIMALLOC=1 le désactive, par exemple :
#       flatpak run --env=CHOPGIMP_NO_MIMALLOC=1 org.cen_na.ChopGimp
#   - les variables déjà définies par l'utilisateur sont respectées.
MI=/app/lib/libmimalloc.so.2
if [ -z "${CHOPGIMP_NO_MIMALLOC:-}" ] && [ -e "$MI" ]; then
    export LD_PRELOAD="$MI${LD_PRELOAD:+:$LD_PRELOAD}"
fi
exec /app/bin/gimp-3.2 "$@"

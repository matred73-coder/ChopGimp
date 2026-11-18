#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# ChopGimp — banc de mesure des performances (interface réelle)
#
#   env -i HOME=$HOME PATH=$PATH USER=$USER bash tools/dev/bench-all.sh [fichier.xcf …]
#
# Fichiers pris dans $CHOPGIMP_DEV/prof (défaut ~/.cache/chopgimp-dev/prof) ;
# par défaut user.xcf (affiche avec effets) puis user-nofx.xcf (sans effets).
# Lance ChopGimp installé dans le banc graphique sans écran
# (tools/gui-test), ouvre le fichier puis rejoue des gestes :
#
#   ouverture       ouverture par D-Bus jusqu'au rendu complet
#   trait           coup de gomme en zigzag sur le calque actif
#   deplacement     glisser le calque actif avec l'outil Déplacement
#   zoom+ / zoom-   4 crans de zoom avant / arrière
#   defilement      à 100 %, Espace + glisser (deux fois 360 px)
#   masquer/afficher  œil d'un calque avec effets (le calque actif)
#   ctrl-vignette   Ctrl + clic sur sa vignette (sélection d'après l'alpha)
#
# Colonnes (voir tools/dev/bench_probe.py) : durée jusqu'à la fin du calcul,
# CPU du fil principal, CPU total, plus longue occupation continue du fil
# principal, délai de réponse max / 95e centile de la boucle principale.
#
# Variables : BENCH_REPEAT=n (répétitions de chaque geste, défaut 1),
#   BENCH_SHOTS=1 (captures après chaque geste dans $CHOPGIMP_DEV/bench-shots),
#   BENCH_EYE="x y", BENCH_THUMB="x y" (œil / vignette du calque actif dans
#   le panneau Calques, défaut : disposition d'usine 1600×900, user.xcf),
#   BENCH_GIMPRC (lignes de gimprc, ex. "(background-render yes)"),
#   CHOPGIMP_GUITEST_FLATPAK_ARGS (ex. "--env=CHOPGIMP_NO_MIMALLOC=1").
# Le banc a son propre dossier ($CHOPGIMP_GUITEST, défaut /tmp/claude-1000/cgb)
# et n'arrête que ses propres processus : d'autres bancs peuvent tourner.
# ═══════════════════════════════════════════════════════════════
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DEV=${CHOPGIMP_DEV:-$HOME/.cache/chopgimp-dev}
export CHOPGIMP_GUITEST=${CHOPGIMP_GUITEST:-/tmp/claude-1000/cgb}
D=$CHOPGIMP_GUITEST
G="$ROOT/tools/gui-test/guitest.sh"
REPEAT=${BENCH_REPEAT:-1}
read -r EX EY <<< "${BENCH_EYE:-1283 660}"
read -r TX TY <<< "${BENCH_THUMB:-1405 660}"
FILES=("$@"); [ ${#FILES[@]} -eq 0 ] && FILES=(user.xcf user-nofx.xcf)
OUT=$(mktemp -d)
RES="$OUT/results.tsv"
SHOTS=$DEV/bench-shots
[ "${BENCH_SHOTS:-0}" = 1 ] && mkdir -p "$SHOTS"
PID=

ui() { "$G" ui "$@" > /dev/null 2>&1; }

# arrêt limité à CE banc (guitest.sh stop tue aussi les autres gnome-shell sans écran)
bench_stop() {
    env XDG_RUNTIME_DIR="$D/run" flatpak kill org.cen_na.ChopGimp 2> /dev/null
    sleep 1
    for p in $(ls /proc | grep -E '^[0-9]+$'); do
        [ "$p" = "$$" ] && continue
        grep -qa "XDG_RUNTIME_DIR=$D/run" /proc/$p/environ 2> /dev/null && kill "$p" 2> /dev/null
    done
    sleep 1
    rm -rf "$D"
}
trap 'bench_stop; rm -rf "$OUT"' EXIT

find_pid() {
    local p
    for p in $(pgrep '^gimp'); do
        grep -qxE 'gimp(-3\.2)?' /proc/$p/comm 2> /dev/null || continue
        tr '\0' '\n' < /proc/$p/environ 2> /dev/null | grep -qx "GIMP3_DIRECTORY=$D/cfg" && { echo "$p"; return; }
    done
}

cpu() { awk '{print $14 + $15}' /proc/$PID/stat; }

# attend que ChopGimp soit au repos (moins de 5 % d'un cœur pendant 2 s)
settle() {
    local a b n=0
    a=$(cpu)
    while [ $n -lt ${1:-60} ]; do
        sleep 2; b=$(cpu); n=$((n + 2))
        [ $((b - a)) -le 10 ] && return
        a=$b
    done
}

# measure <nom> <commandes ui…> : mesure le geste jusqu'à la fin du calcul
measure() {
    local name=$1 r; shift
    rm -f "$D/done" "$D/done.ready"
    python3 -I "$HERE/bench_probe.py" "$D" "$PID" "$D/done" > "$OUT/r.json" &
    local probe=$!
    while [ ! -e "$D/done.ready" ]; do sleep 0.05; done
    ui "$@"
    touch "$D/done"
    wait $probe
    r=$(cat "$OUT/r.json")
    printf '%s\t%s\t%s\n' "$FILE" "$name" "$r" >> "$RES"
    [ "${BENCH_SHOTS:-0}" = 1 ] && ui shot "$SHOTS/$FILE-$name.png"
    echo "  $name $r" >&2
}

for FILE in "${FILES[@]}"; do
    echo "== $FILE" >&2
    bench_stop
    # BENCH_GIMPRC="(background-render yes)" : lignes ajoutées au gimprc du banc
    if [ -n "${BENCH_GIMPRC:-}" ]; then
        mkdir -p "$D/cfg"; printf '%s\n' "$BENCH_GIMPRC" > "$D/cfg/gimprc"
    fi
    "$G" start > /dev/null 2>&1
    PID=$(find_pid)
    [ -n "$PID" ] || { echo "ChopGimp n'a pas démarré (voir $D/gimp.log)"; exit 1; }
    settle 90
    grep -q libmimalloc /proc/$PID/maps && MI=oui || MI=non
    echo "# $FILE : ChopGimp $(flatpak info org.cen_na.ChopGimp 2> /dev/null | awk '/Commit/{print substr($2,1,8)}'), mimalloc $MI, ${CHOPGIMP_GUITEST_FLATPAK_ARGS:-}"
    # fenêtres d'accueil (GIMP, puis ChopGimp)
    ui key Escape , sleep 1 , move 1042 49 , click 1042 49 , sleep 1 , move 242 49 , click 242 49 , sleep 1
    cp "$DEV/prof/$FILE" "$D/"
    for i in $(seq "$REPEAT"); do
        [ "$i" -gt 1 ] && { ui action view-close; sleep 2; settle; }
        rm -f "$D/done" "$D/done.ready"
        python3 -I "$HERE/bench_probe.py" "$D" "$PID" "$D/done" --open "$D/$FILE" > "$OUT/r.json"
        printf '%s\t%s\t%s\n' "$FILE" ouverture "$(cat "$OUT/r.json")" >> "$RES"
        echo "  ouverture $(cat "$OUT/r.json")" >&2
        settle
    done
    [ "${BENCH_SHOTS:-0}" = 1 ] && ui shot "$SHOTS/$FILE-ouverture.png"

    for i in $(seq "$REPEAT"); do
        ui action tools-eraser; settle
        measure trait move 600 400 , down , rel 200 0 , rel 0 200 , rel -200 0 , rel 0 -200 , \
                rel 200 200 , rel -200 0 , rel 200 -200 , up
        ui action edit-undo; settle

        ui action tools-move; settle
        measure deplacement move 520 330 , down , rel 80 60 , rel 60 -40 , up
        ui action edit-undo; settle

        measure zoom+ action view-zoom-in , action view-zoom-in , action view-zoom-in , action view-zoom-in
        measure zoom- action view-zoom-out , action view-zoom-out , action view-zoom-out , action view-zoom-out
        ui action view-zoom-fit-in; settle

        ui action view-zoom-1-1; settle
        measure defilement move 650 500 , keydown space , sleep 0.3 , down , rel -300 -200 , \
                rel -300 -200 , up , keyup space
        ui action view-zoom-fit-in; settle

        measure masquer click "$EX" "$EY"
        measure afficher click "$EX" "$EY"

        measure ctrl-vignette keydown Control_L , click "$TX" "$TY" , keyup Control_L
        ui action select-none; settle
    done
done

python3 - "$RES" <<'PYEOF'
import json, sys
from collections import OrderedDict
rows = OrderedDict()
for line in open(sys.argv[1]):
    f, name, js = line.rstrip("\n").split("\t", 2)
    rows.setdefault((f, name), []).append(json.loads(js))
cols = [("wall_s", "durée s"), ("main_cpu_s", "CPU fil pr. s"), ("total_cpu_s", "CPU total s"),
        ("busy_max_ms", "occup. max ms"), ("lat_max_ms", "délai max ms"), ("lat_p95_ms", "délai p95 ms")]
print("%-16s %-14s" % ("fichier", "geste") + "".join(" %13s" % c[1] for c in cols))
for (f, name), rs in rows.items():
    # médiane des répétitions
    med = {k: sorted(r[k] for r in rs)[len(rs) // 2] for k, _ in cols}
    print("%-16s %-14s" % (f[:16], name) + "".join(" %13s" % med[k] for k, _ in cols))
PYEOF

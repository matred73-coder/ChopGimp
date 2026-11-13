#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# ChopGimp — banc de test graphique SANS ÉCRAN
#
# Lance un GNOME Shell « headless » (écran virtuel 1600x900) isolé de la
# session de l'utilisateur (bus D-Bus privé, réglages en mémoire), puis
# ChopGimp dedans avec une configuration vierge. ui.py prend des captures
# et simule souris / clavier : on peut vérifier l'interface sans rien
# afficher sur l'écran réel.
#
#   tools/gui-test/guitest.sh start            compositeur + ChopGimp
#   tools/gui-test/guitest.sh gimp [fichier]   (re)lance seulement ChopGimp
#   tools/gui-test/guitest.sh ui <commandes>   voir ui.py (shot, click, drag…)
#   tools/gui-test/guitest.sh nooverview      ferme la vue d'ensemble GNOME
#   tools/gui-test/guitest.sh stop             arrête tout et nettoie
#
# Dossier de travail : $CHOPGIMP_GUITEST (défaut /tmp/cg-guitest-$UID).
# Il doit rester COURT : les sockets Unix sont limités à 108 caractères.
# Prérequis : gnome-shell ≥ 45, flatpak, python3-gi. Lancer hors de tout
# bac à sable, avec un environnement propre (pas celui d'un Snap).
# ═══════════════════════════════════════════════════════════════
set -u
D="${CHOPGIMP_GUITEST:-/tmp/cg-guitest-$(id -u)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
APP=org.cen_na.ChopGimp
CLEAN="env -i HOME=$HOME USER=${USER:-$(id -un)} LANG=fr_FR.UTF-8 LANGUAGE=fr_FR:fr PATH=/usr/bin:/bin"

start_shell() {
    mkdir -p "$D/config" "$D/cache" "$D/data" "$D/cfg" "$D/shots"
    mkdir -p -m 700 "$D/run"
    setsid $CLEAN XDG_RUNTIME_DIR="$D/run" XDG_CONFIG_HOME="$D/config" \
        XDG_CACHE_HOME="$D/cache" XDG_DATA_HOME="$D/data" GSETTINGS_BACKEND=memory \
        dbus-run-session -- bash -c "echo \"\$DBUS_SESSION_BUS_ADDRESS\" > '$D/bus'; \
            exec gnome-shell --headless --virtual-monitor 1600x900 --wayland-display wl-chop \
                 --unsafe-mode --no-x11 > '$D/shell.log' 2>&1" < /dev/null > /dev/null 2>&1 &
    for _ in $(seq 30); do [ -S "$D/run/wl-chop" ] && break; sleep 0.5; done
    [ -S "$D/run/wl-chop" ] || { echo "le compositeur n'a pas démarré, voir $D/shell.log"; exit 1; }
    sleep 3
}

start_gimp() {
    setsid $CLEAN XDG_RUNTIME_DIR="$D/run" WAYLAND_DISPLAY=wl-chop XDG_SESSION_TYPE=wayland \
        DBUS_SESSION_BUS_ADDRESS="$(cat "$D/bus")" \
        flatpak run --env=GIMP3_DIRECTORY="$D/cfg" --filesystem="$D" ${CHOPGIMP_GUITEST_FLATPAK_ARGS:-} $APP "$@" \
        < /dev/null > "$D/gimp.log" 2>&1 &
    sleep "${CHOPGIMP_GUITEST_WAIT:-28}"
    # GNOME démarre dans la vue d'ensemble : on la ferme par D-Bus (mode
    # « unsafe » de GNOME Shell), puis on ferme la fenêtre d'accueil
    no_overview
}

# Ferme la vue d'ensemble de GNOME Shell (elle revient parfois toute seule)
no_overview() {
    for _ in 1 2 3; do
        $CLEAN DBUS_SESSION_BUS_ADDRESS="$(cat "$D/bus")" gdbus call --session \
            --dest org.gnome.Shell --object-path /org/gnome/Shell \
            --method org.gnome.Shell.Eval "Main.overview.hide(); Main.overview.show = () => {}; Main.overview.toggle = () => {}; Main.overview.visible" \
            > "$D/overview.txt" 2>&1
        sleep 0.8
        grep -q "'false'" "$D/overview.txt" && break
    done
}

stop_gimp() {
    env XDG_RUNTIME_DIR="$D/run" flatpak kill $APP 2>/dev/null
    sleep 1
}

case "${1:-}" in
    start) start_shell; shift; start_gimp "$@" ;;
    gimp)  stop_gimp; shift; start_gimp "$@" ;;
    ui)    shift; exec $CLEAN python3 -I "$HERE/ui.py" "$D" "$@" ;;
    nooverview) no_overview ;;
    stop)  stop_gimp
           pkill -f "[g]nome-shell --headless --virtual-monitor 1600x900 --wayland-display wl-chop"
           sleep 1; rm -rf "$D" ;;
    *)     sed -n '2,22p' "$0"; exit 1 ;;
esac

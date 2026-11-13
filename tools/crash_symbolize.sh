#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# ChopGimp — traduit la pile d'appels d'un rapport de plantage
#
#   tools/crash_symbolize.sh <rapport.txt>
#
# Les rapports (CrashLog/chopgimp-crash-*.txt, écrits par
# app/chopgimp-crash.c) donnent pour chaque appel « module +décalage ».
# On retrouve la fonction, le fichier et la ligne grâce aux symboles de
# débogage du paquet (extension org.cen_na.ChopGimp.Debug, produite par
# flatpak-builder dans flatpak/repo), extraits une fois dans
# build/debug-sym/<commit>/.
#
# Le rapport doit venir de la version compilée ici (même commit) ;
# les bibliothèques du runtime GNOME (/usr/lib) restent non traduites.
# Prérequis : ostree, elfutils (eu-addr2line), flatpak.
#
#   tools/crash_symbolize.sh <rapport.txt> [commit de l'extension Debug]
# (le commit permet de traduire un rapport d'une version plus ancienne,
#  voir « ostree log --repo=flatpak/repo runtime/org.cen_na.ChopGimp.Debug/x86_64/stable »)
# ═══════════════════════════════════════════════════════════════
set -u
REPORT="${1:?usage : $0 rapport.txt}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$ROOT/flatpak/repo"
APP=org.cen_na.ChopGimp
DREF="runtime/$APP.Debug/x86_64/stable"

A2L="$(command -v eu-addr2line || command -v addr2line)"
commit="${2:-$(ostree rev-parse --repo="$REPO" "$DREF" 2>/dev/null)}" || {
    echo "Pas de symboles de débogage dans $REPO (lancer « make build »)." >&2; exit 1; }
SYM="$ROOT/build/debug-sym/$commit"
if [ ! -d "$SYM/files" ]; then
    echo "Extraction des symboles ($commit)…" >&2
    mkdir -p "$ROOT/build/debug-sym"
    ostree checkout --repo="$REPO" -U "$commit" "$SYM" >/dev/null || exit 1
fi

# l'application installée doit être celle du dépôt, sinon les décalages
# ne correspondent pas
installed="$(flatpak info --show-commit "$APP" 2>/dev/null)"
built="$(ostree rev-parse --repo="$REPO" "app/$APP/x86_64/stable" 2>/dev/null)"
[ -n "$installed" ] && [ "$installed" != "$built" ] &&
    echo "Attention : l'application installée ($installed) n'est pas celle du dépôt ($built)." >&2
LOC="$(flatpak info --show-location "$APP" 2>/dev/null)/files"

# /app/... → fichier .debug
debug_file() {
    local mod="$1" rel real
    case "$mod" in
        /app/*) rel="${mod#/app/}" ;;
        *) return 1 ;;
    esac
    [ -f "$SYM/files/$rel.debug" ] && { echo "$SYM/files/$rel.debug"; return; }
    # lien de bibliothèque (libX.so.0 → libX.so.0.N.M)
    if [ -e "$LOC/$rel" ]; then
        real="$(readlink -f "$LOC/$rel")"
        real="${real#"$LOC"/}"
        [ -f "$SYM/files/$real.debug" ] && { echo "$SYM/files/$real.debug"; return; }
    fi
    ls "$SYM/files/$rel".*.debug 2>/dev/null | head -1
}

in_stack=0
while IFS= read -r line; do
    case "$line" in
        "== Pile d'appels"*) in_stack=1; echo "$line"; continue ;;
        "== "*) in_stack=0 ;;
    esac
    if [ $in_stack = 1 ] && [[ "$line" =~ ^\ +#([0-9]+)\ ([^ ]+)\ \+(0x[0-9a-f]+) ]]; then
        n="${BASH_REMATCH[1]}"; mod="${BASH_REMATCH[2]}"; off="${BASH_REMATCH[3]}"
        dbg="$(debug_file "$mod")"
        if [ -n "$dbg" ]; then
            # adresse de retour : -1 pour viser l'instruction d'appel
            addr="$(printf '0x%x' $((off > 0 ? off - 1 : 0)))"
            # eu-addr2line (elfutils) lit le DWARF 5 de GCC 16, pas les vieux binutils
            res="$($A2L -f -i -e "$dbg" "$addr" 2>/dev/null | paste -d' ' - - |
                   sed 's|/run/build/[^ ]*/_flatpak_build/\.\./||; s|/run/build/[^/]*/||')"
            printf '  #%s %s\n      → %s\n' "$n" "${mod##*/}" "${res//$'\n'/$'\n'        (en ligne) }"
        else
            echo "$line"
        fi
    else
        echo "$line"
    fi
done < "$REPORT"

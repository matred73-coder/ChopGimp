#!/bin/bash
# Outil de développement ChopGimp. Données dans $DEV (modèles d'IA de test, fichiers de mesure).
DEV=${CHOPGIMP_DEV:-$HOME/.cache/chopgimp-dev}
# Mesure : temps CPU (fil principal et total) de ChopGimp pendant un trait scripté sur une copie de l'affiche
cd ~/DOCKER/photogimp-pro
export CHOPGIMP_GUITEST=/tmp/claude-1000/cgt
G=tools/gui-test/guitest.sh
S=$DEV
FILE=${1:-user.xcf}; TOOL=${2:-e}
$G stop >/dev/null 2>&1; mkdir -p /tmp/claude-1000/cgt; cp $S/prof/$FILE /tmp/claude-1000/cgt/
$G start /tmp/claude-1000/cgt/$FILE >/dev/null 2>&1; sleep 55
$G ui key Escape , sleep 1 , move 1042 49 , click 1042 49 , sleep 1 , move 242 49 , click 242 49 , sleep 2 , key $TOOL , sleep 3 >/dev/null 2>&1
pid=$(ps -eo pid,args | awk '$2=="gimp" && $3 ~ /cgt/ {print $1}' | tail -1)
rd() { awk '{print $14+$15}' /proc/$pid/task/$pid/stat; }
rt() { awk '{print $14+$15}' /proc/$pid/stat; }
m1=$(rd); t1=$(rt); s=$(date +%s.%N)
$G ui move 600 400 , down , rel 200 0 , rel 0 200 , rel -200 0 , rel 0 -200 , rel 200 200 , rel -200 0 , rel 200 -200 , up >/dev/null 2>&1
e=$(date +%s.%N); sleep 4
m2=$(rd); t2=$(rt)
echo "trait $(echo "$e - $s" | bc) s ; fil principal $((m2-m1)) cs ; total $((t2-t1)) cs (centièmes de s CPU)"
$G ui shot /tmp/claude-1000/cgt/shots/bench.png >/dev/null 2>&1

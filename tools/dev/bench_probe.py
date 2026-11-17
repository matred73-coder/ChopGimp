#!/usr/bin/env python3
"""Sonde de mesure ChopGimp (utilisée par tools/dev/bench-all.sh).

  bench_probe.py <dossier-banc> <pid> <fichier-fin> [--open <fichier.xcf>]

Échantillonne le processus GIMP <pid> toutes les 10 ms jusqu'à ce que
<fichier-fin> existe, puis attend que le calcul soit terminé (processus au
repos pendant 0,8 s, 60 s au plus) et écrit une ligne JSON sur stdout :

  wall_s      début → fin du dernier calcul (rendu terminé)
  main_cpu_s  temps CPU du fil principal (interface)
  total_cpu_s temps CPU de tout le processus (fils de calcul GEGL compris)
  busy_max_ms plus longue période où le fil principal est occupé ≥ 90 %
              (schedstat, résolution 10 ms) : pendant ce temps l'interface
              ne répond pas
  lat_max_ms  plus long délai de réponse du fil principal à un appel D-Bus
  lat_p95_ms  (org.gtk.Actions.Describe toutes les 25 ms, traité par la
              boucle principale de GTK comme les clics) : à-coup ressenti

Avec --open, la sonde demande elle-même l'ouverture du fichier par D-Bus
(org.gimp.GIMP.UI.Open) et s'arrête quand le rendu est terminé.
"""
import json
import os
import sys
import threading
import time

import gi
from gi.repository import Gio, GLib

H, PID, DONE = sys.argv[1], int(sys.argv[2]), sys.argv[3]
OPEN = sys.argv[sys.argv.index("--open") + 1] if "--open" in sys.argv else None
HZ = os.sysconf("SC_CLK_TCK")
PERIOD = 0.010
IDLE_CPU = 0.10        # processus « au repos » sous 10 % d'un cœur
IDLE_FOR = 0.8
MAX_SETTLE = 60.0


def main_run_ns():
    with open("/proc/%d/task/%d/schedstat" % (PID, PID)) as f:
        return int(f.read().split()[0])


def proc_cpu_s():
    with open("/proc/%d/stat" % PID) as f:
        s = f.read()
    v = s[s.rindex(")") + 2:].split()
    return (int(v[11]) + int(v[12])) / HZ        # utime + stime (fils compris)


bus = Gio.DBusConnection.new_for_address_sync(
    open(os.path.join(H, "bus")).read().strip(),
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
    None, None)
owner = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                      "GetNameOwner", GLib.Variant("(s)", ("org.cen_na.ChopGimp.UI",)),
                      None, Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]

lat = []
stop = threading.Event()


def pinger():
    # connexion à part : les appels de la sonde ne doivent pas attendre l'ouverture
    conn = Gio.DBusConnection.new_for_address_sync(
        open(os.path.join(H, "bus")).read().strip(),
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None)
    while not stop.is_set():
        t = time.monotonic()
        try:
            conn.call_sync(owner, "/org/cen_na/ChopGimp", "org.gtk.Actions", "Describe",
                           GLib.Variant("(s)", ("edit-undo",)), None, Gio.DBusCallFlags.NONE,
                           120000, None)
        except GLib.Error:
            pass
        lat.append(time.monotonic() - t)
        time.sleep(0.025)


opened = {}
started = threading.Event()      # le fil principal a commencé un calcul


def opener():
    t = time.monotonic()
    try:
        bus.call_sync(owner, "/org/gimp/GIMP/UI", "org.gimp.GIMP.UI", "Open",
                      GLib.Variant("(s)", (Gio.File.new_for_path(OPEN).get_uri(),)),
                      None, Gio.DBusCallFlags.NONE, 300000, None)
    except GLib.Error as e:
        opened["error"] = str(e)
    # l'ouverture est mise en file d'attente : on attend qu'elle commence
    while not started.is_set() and time.monotonic() - t < 5:
        time.sleep(0.01)
    open(DONE, "w").close()


threading.Thread(target=pinger, daemon=True).start()
time.sleep(0.05)

t0 = time.monotonic()
m0, c0 = main_run_ns(), proc_cpu_s()
open(DONE + ".ready", "w").close()      # bench-all.sh peut envoyer les événements
if OPEN:
    threading.Thread(target=opener, daemon=True).start()

busy_max = run = 0.0
last_busy = t0
prev_t, prev_m = t0, m0
hist = []                   # (t, cpu) pour la détection du repos
done_at = None
while True:
    time.sleep(PERIOD)
    t, m, c = time.monotonic(), main_run_ns(), proc_cpu_s()
    dt = t - prev_t
    if (m - prev_m) / 1e9 >= 0.9 * dt:
        run += dt
        busy_max = max(busy_max, run)
        started.set()
    else:
        run = 0.0
    prev_t, prev_m = t, m
    hist.append((t, c))
    while hist and hist[0][0] < t - IDLE_FOR:
        hist.pop(0)
    window_busy = (hist[-1][1] - hist[0][1]) / max(hist[-1][0] - hist[0][0], 1e-3)
    if window_busy > IDLE_CPU or run > 0:
        last_busy = t
    if done_at is None and os.path.exists(DONE):
        done_at = t
    if done_at is not None and (t - last_busy >= IDLE_FOR or t - done_at > MAX_SETTLE):
        break

stop.set()
m1, c1 = main_run_ns(), proc_cpu_s()
lat_ms = sorted(x * 1000 for x in lat) or [0.0]
res = {
    "wall_s": round(max(last_busy, done_at) - t0, 2),
    "main_cpu_s": round((m1 - m0) / 1e9, 2),
    "total_cpu_s": round(c1 - c0, 2),
    "busy_max_ms": int(busy_max * 1000),
    "lat_max_ms": int(lat_ms[-1]),
    "lat_p95_ms": int(lat_ms[int(0.95 * (len(lat_ms) - 1))]),
}
res.update({k: round(v, 2) if isinstance(v, float) else v for k, v in opened.items()})
print(json.dumps(res))

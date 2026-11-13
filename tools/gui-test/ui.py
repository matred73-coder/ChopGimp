#!/usr/bin/env python3
"""Pilote du banc de test graphique ChopGimp (compositeur GNOME sans écran).
À lancer par : tools/gui-test/guitest.sh ui <commandes>

  ui.py shot <fichier.png>            capture de l'écran virtuel
  ui.py click <x> <y> [bouton]        clic (1 = gauche, 3 = droit)
  ui.py dclick <x> <y>                double-clic
  ui.py drag <x1> <y1> <x2> <y2>      glisser-déposer
  ui.py move <x> <y>                  déplacer le pointeur
  ui.py key <keysym> [shift]          touche (nom X11 : Tab, Escape…)
  ui.py down | up | rel <dx> <dy>     bouton enfoncé / relâché / déplacement relatif
  ui.py keydown | keyup <keysym>      touche maintenue (ex. Shift_L, Alt_L) / relâchée
  ui.py sleep <secondes>
  ui.py action <nom>                  action ChopGimp (ex. windows-hide-docks)
  ui.py actions [filtre]              liste des actions exportées
Plusieurs commandes peuvent s'enchaîner, séparées par « , ».
"""
import os
import sys
import time

import gi
gi.require_version("Gdk", "3.0")
from gi.repository import Gio, GLib, Gdk

# 1er argument : dossier de travail du banc (voir guitest.sh)
H = sys.argv.pop(1)
bus = Gio.DBusConnection.new_for_address_sync(
    open(os.path.join(H, "bus")).read().strip(),
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
    None, None)


def call(dest, path, iface, method, args=None):
    return bus.call_sync(dest, path, iface, method, args, None, Gio.DBusCallFlags.NONE, 30000, None)


class Pointer:
    """Session org.gnome.Mutter.RemoteDesktop (souris et clavier virtuels)."""

    def __init__(self):
        r = call("org.gnome.Mutter.RemoteDesktop", "/org/gnome/Mutter/RemoteDesktop",
                 "org.gnome.Mutter.RemoteDesktop", "CreateSession")
        self.path = r.unpack()[0]
        self.s("Start")
        time.sleep(0.2)
        # le tout premier événement clavier d'une session est perdu :
        # une touche Maj « à blanc » l'absorbe
        for down in (True, False):
            self.s("NotifyKeyboardKeysym", GLib.Variant("(ub)", (Gdk.KEY_Shift_L, down)))
        time.sleep(0.3)

    def s(self, method, args=None):
        return call("org.gnome.Mutter.RemoteDesktop", self.path,
                    "org.gnome.Mutter.RemoteDesktop.Session", method, args)

    def move(self, x, y):
        # pas de flux d'écran : on cale le pointeur dans le coin puis on avance
        # (le coin haut-gauche déclenche la vue d'ensemble de GNOME : on cale
        #  donc le pointeur en bas à droite de l'écran virtuel 1600x900)
        self.s("NotifyPointerMotionRelative", GLib.Variant("(dd)", (5000.0, 5000.0)))
        time.sleep(0.08)
        self.s("NotifyPointerMotionRelative", GLib.Variant("(dd)", (float(x) - 1599.0, float(y) - 899.0)))
        time.sleep(0.15)

    def rel(self, dx, dy):
        self.s("NotifyPointerMotionRelative", GLib.Variant("(dd)", (float(dx), float(dy))))
        time.sleep(0.03)

    def button(self, b, down):
        code = {1: 0x110, 2: 0x112, 3: 0x111}[b]     # BTN_LEFT / MIDDLE / RIGHT
        self.s("NotifyPointerButton", GLib.Variant("(ib)", (code, down)))
        time.sleep(0.06)

    def click(self, x, y, b=1):
        self.move(x, y)
        self.button(b, True)
        self.button(b, False)

    def dclick(self, x, y):
        self.move(x, y)
        for _ in range(2):
            self.button(1, True)
            self.button(1, False)

    def drag(self, x1, y1, x2, y2, steps=24):
        self.move(x1, y1)
        time.sleep(0.5)
        self.button(1, True)
        time.sleep(0.3)
        for i in range(steps):
            self.rel((x2 - x1) / steps, (y2 - y1) / steps)
        time.sleep(0.4)
        self.button(1, False)

    def key(self, name, shift=False):
        sym = Gdk.keyval_from_name(name)
        if shift:
            self.s("NotifyKeyboardKeysym", GLib.Variant("(ub)", (Gdk.KEY_Shift_L, True)))
        self.s("NotifyKeyboardKeysym", GLib.Variant("(ub)", (sym, True)))
        time.sleep(0.05)
        self.s("NotifyKeyboardKeysym", GLib.Variant("(ub)", (sym, False)))
        if shift:
            self.s("NotifyKeyboardKeysym", GLib.Variant("(ub)", (Gdk.KEY_Shift_L, False)))

    def stop(self):
        try:
            self.s("Stop")
        except Exception:
            pass


def shot(path):
    r = call("org.gnome.Shell.Screenshot", "/org/gnome/Shell/Screenshot",
             "org.gnome.Shell.Screenshot", "Screenshot", GLib.Variant("(bbs)", (True, False, path)))
    print("capture", r.unpack())


def app_owner():
    # GIMP n'enregistre pas le nom de l'application elle-même, seulement son
    # service « .UI » : on s'adresse à la connexion qui le possède.
    return call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                "GetNameOwner", GLib.Variant("(s)", ("org.cen_na.ChopGimp.UI",))).unpack()[0]


APP = (app_owner() if "action" in " ".join(sys.argv) else "", "/org/cen_na/ChopGimp", "org.gtk.Actions")


def action(name, value=None):
    """Active une action ; value : paramètre entier (actions radio)."""
    params = [GLib.Variant("i", int(value))] if value is not None else []
    call(APP[0], APP[1], APP[2], "Activate", GLib.Variant("(sava{sv})", (name, params, {})))
    print("action", name)


def actions(flt=""):
    names = call(APP[0], APP[1], APP[2], "List").unpack()[0]
    for n in sorted(names):
        if flt in n:
            print(n)


def main():
    cmds, cur = [], []
    for a in sys.argv[1:]:
        if a == ",":
            cmds.append(cur)
            cur = []
        else:
            cur.append(a)
    if cur:
        cmds.append(cur)
    ptr = None
    for c in cmds:
        op, args = c[0], c[1:]
        if op in ("click", "dclick", "drag", "move", "key", "down", "up", "rel",
                  "keydown", "keyup") and ptr is None:
            ptr = Pointer()
        if op == "shot":
            shot(args[0])
        elif op == "click":
            ptr.click(int(args[0]), int(args[1]), int(args[2]) if len(args) > 2 else 1)
        elif op == "dclick":
            ptr.dclick(int(args[0]), int(args[1]))
        elif op == "drag":
            ptr.drag(*[int(v) for v in args[:4]])
        elif op in ("keydown", "keyup"):
            ptr.s("NotifyKeyboardKeysym",
                  GLib.Variant("(ub)", (Gdk.keyval_from_name(args[0]), op == "keydown")))
        elif op == "down":
            ptr.button(1, True)
        elif op == "up":
            ptr.button(1, False)
        elif op == "rel":
            n = 12
            for _ in range(n):
                ptr.rel(int(args[0]) / n, int(args[1]) / n)
        elif op == "move":
            ptr.move(int(args[0]), int(args[1]))
        elif op == "key":
            ptr.key(args[0], len(args) > 1)
        elif op == "action":
            action(args[0], args[1] if len(args) > 1 else None)
        elif op == "actions":
            actions(args[0] if args else "")
        elif op == "sleep":
            time.sleep(float(args[0]))
        else:
            sys.exit("commande inconnue : " + op)
        time.sleep(0.3)
    if ptr:
        ptr.stop()


main()

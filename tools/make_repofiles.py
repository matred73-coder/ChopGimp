#!/usr/bin/env python3
"""
PhotoGIMP Pro — génère les fichiers d'installation du dépôt Flatpak privé :
  dist/photogimp.flatpakrepo     (ajouter le dépôt : flatpak remote-add)
  dist/PhotoGimpPro.flatpakref   (installer en un clic / une commande)

Usage : make_repofiles.py <url du dépôt> [<id clé GPG>] <dossier de sortie>
"""
import base64
import os
import subprocess
import sys

url = sys.argv[1].rstrip("/") + "/"
key = sys.argv[2] if len(sys.argv) > 3 else ""
out = sys.argv[-1]
os.makedirs(out, exist_ok=True)

gpg = ""
if key:
    raw = subprocess.run(["gpg", "--export", key], check=True, capture_output=True).stdout
    gpg = "GPGKey=" + base64.b64encode(raw).decode() + "\n"

common = "Title=PhotoGIMP Pro\nComment=GIMP recompilé façon Photoshop\n"

open(os.path.join(out, "photogimp.flatpakrepo"), "w").write(
    "[Flatpak Repo]\n" + common + "Url=" + url + "\n" + gpg +
    "DefaultBranch=stable\n")

open(os.path.join(out, "PhotoGimpPro.flatpakref"), "w").write(
    "[Flatpak Ref]\nName=org.cen_na.PhotoGimpPro\nBranch=stable\n" + common +
    "Url=" + url + "\nRuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo\n"
    "IsRuntime=false\n" + gpg)

print("Fichiers d'installation écrits dans", out, "(signés)" if key else "(non signés)")

#!/usr/bin/env python3
"""
PhotoGIMP Pro v3 — génère flatpak/org.cen_na.ChopGimp.json à partir du
manifeste officiel Flathub de GIMP (flatpak/upstream/org.gimp.GIMP.json).

Modifications :
- identifiant org.cen_na.ChopGimp (installable à côté de GIMP)
- configuration séparée (pas d'accès à ~/.config/GIMP de l'hôte)
- pas d'extensions Flathub (plug-ins / manuel) propres à org.gimp.GIMP
- patchs PhotoGIMP (patches/gimp-3.2.8/*.patch) appliqués sur GIMP 3.2.8
- module « photogimp-data » : réglages, thème, icônes, menus, plug-ins

Usage : make_manifest.py [--vanilla]   (--vanilla : GIMP sans patch ni données)
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FP = os.path.join(ROOT, "flatpak")
APP_ID = "org.cen_na.ChopGimp"
vanilla = "--vanilla" in sys.argv

m = json.load(open(os.path.join(FP, "upstream", "org.gimp.GIMP.json")))
m["app-id"] = APP_ID
m["finish-args"] = [a for a in m["finish-args"] if not a.startswith("--filesystem=xdg-config/GIMP")]
m.pop("add-extensions", None)
m["tags"] = ["GTK+3", "photogimp"]


def fix_paths(mods):
    for i, x in enumerate(mods):
        if isinstance(x, str):
            mods[i] = "upstream/" + x
            continue
        for s in x.get("sources", []):
            if isinstance(s, dict) and "paths" in s:
                s["paths"] = ["upstream/" + p for p in s["paths"]]
            if isinstance(s, dict) and "path" in s:
                s["path"] = "upstream/" + s["path"]
        fix_paths(x.get("modules", []))


fix_paths(m["modules"])

gimp = next(x for x in m["modules"] if isinstance(x, dict) and x["name"] == "gimp")
gimp["config-opts"] = [o if not o.startswith("-Dbuild-id=") else "-Dbuild-id=%s.flatpak" % APP_ID
                       for o in gimp["config-opts"]]
gimp["post-install"] = [c for c in gimp["post-install"] if "extensions" not in c]

if not vanilla:
    patches = sorted(glob.glob(os.path.join(ROOT, "patches", "gimp-3.2.8", "*.patch")))
    if patches:
        gimp["sources"].append({"type": "patch", "use-git-am": True,
                                "paths": [os.path.relpath(p, FP) for p in patches]})
    # Données PhotoGIMP Pro, installées après GIMP (voir tools/install_data.sh)
    m["modules"].append({
        "name": "photogimp-data",
        "buildsystem": "simple",
        "sources": [{"type": "dir", "path": "..", "skip": [".git", "build", ".backups",
                                                          "flatpak/.flatpak-builder",
                                                          "flatpak/build-dir", "dist"]}],
        "build-commands": ["sh tools/install_data.sh ${FLATPAK_DEST}"],
    })

out = os.path.join(FP, APP_ID + (".vanilla" if vanilla else "") + ".json")
json.dump(m, open(out, "w"), indent=4, ensure_ascii=False)
print("manifeste écrit :", out)

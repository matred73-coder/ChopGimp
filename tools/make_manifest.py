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


def find_module(mods, name):
    for x in mods:
        if isinstance(x, dict):
            if x.get("name") == name:
                return x
            found = find_module(x.get("modules", []), name)
            if found:
                return found
    return None


# ── poppler accessible depuis Python (gi.repository.Poppler) : l'import
#    vectoriel PDF/AI de ChopGimp (plug-in chopgimp_vector_import) l'utilise
poppler = find_module(m["modules"], "poppler")
if poppler is not None:
    poppler["config-opts"] = ["-DENABLE_GOBJECT_INTROSPECTION=ON"
                              if o.startswith("-DENABLE_GOBJECT_INTROSPECTION") else o
                              for o in poppler["config-opts"]]

# ── Moteur géométrique d'Inkscape (lib2geom 1.4, celle d'Inkscape 1.4) et
#    ses dépendances, avant GIMP : outils vectoriels avancés (Pathfinder,
#    décalages, effets de chemin…). Seules les bibliothèques partagées
#    restent dans le paquet.
GEOM_MODULES = [
    {"name": "boost",
     "buildsystem": "simple",
     "sources": [{"type": "archive",
                  "url": "https://archives.boost.io/release/1.87.0/source/boost_1_87_0.tar.bz2",
                  "sha256": "af57be25cb4c4f4b413ed692fe378affb4352ea50fbe294a11ef548f4d527d89"}],
     "build-commands": ["./bootstrap.sh --prefix=${FLATPAK_DEST} --with-libraries=system",
                        "./b2 -j${FLATPAK_BUILDER_N_JOBS} install variant=release link=shared"],
     "cleanup": ["*"]},
    {"name": "gsl",
     "config-opts": ["--disable-static"],
     "sources": [{"type": "archive", "url": "https://ftp.gnu.org/gnu/gsl/gsl-2.8.tar.gz",
                  "sha256": "6a99eeed15632c6354895b1dd542ed5a855c0f15d9ad1326c6fe2b2c9e423190"}],
     "cleanup": ["/bin", "/include", "/lib/pkgconfig", "/share", "*.la"]},
    {"name": "double-conversion",
     "buildsystem": "cmake-ninja",
     "config-opts": ["-DBUILD_SHARED_LIBS=ON", "-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_POLICY_VERSION_MINIMUM=3.5", "-DCMAKE_INSTALL_LIBDIR=lib"],
     "sources": [{"type": "git", "url": "https://github.com/google/double-conversion.git",
                  "tag": "v3.3.1", "commit": "ae0dbfeb9744efd216c95b30555049d75d47116a"}],
     "cleanup": ["/include", "/lib/cmake"]},
    {"name": "lib2geom",
     "buildsystem": "cmake-ninja",
     "builddir": True,
     "config-opts": ["-D2GEOM_BUILD_SHARED=ON", "-D2GEOM_TESTING=OFF",
                     "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
                     "-DCMAKE_INSTALL_LIBDIR=lib"],
     "sources": [{"type": "git", "url": "https://gitlab.com/inkscape/lib2geom.git",
                  "tag": "1.4", "commit": "23316118755def8156c268f767894c145130e07d"}],
     "cleanup": ["/lib/cmake"]},
]

# ── liblqr (Liquid Rescale) : Image > Mise à l'échelle selon le contenu
#    (plug-in chopgimp_base, appel par ctypes)
LQR_MODULES = [
    {"name": "liblqr",
     # code ancien : prototypes « () » refusés par la norme C23 de GCC 16
     "config-opts": ["--disable-static", "CFLAGS=-O2 -g -std=gnu17"],
     "cleanup": ["/include", "/lib/pkgconfig", "*.la"],
     "sources": [{"type": "archive",
                  "url": "https://github.com/carlobaldassi/liblqr/archive/refs/tags/v0.4.3.tar.gz",
                  "sha256": "64b0c4ac76d39cca79501b3f53544af3fc5f72b536ac0f28d2928319bfab6def"}]},
]

# ── IA locale (plug-in chopgimp_ia) : numpy + onnxruntime, paquets
#    précompilés pour le Python du runtime (3.14). Les modèles ne sont pas
#    dans le paquet : téléchargés à la première utilisation, après accord.
NUMPY_WHL = "numpy-2.5.4-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
ORT_WHL = "onnxruntime-1.32.0-cp314-cp314-manylinux_2_28_x86_64.whl"
IA_MODULES = [
    {"name": "python-ia",
     "buildsystem": "simple",
     "build-commands": ["python3 -m pip install --no-index --no-deps --no-build-isolation "
                        "--prefix=${FLATPAK_DEST} %s %s" % (NUMPY_WHL, ORT_WHL)],
     "sources": [
         {"type": "file", "dest-filename": NUMPY_WHL,
          "url": "https://files.pythonhosted.org/packages/16/d5/928078d2b28f26829b138b4a6c3980045022fb409f570657a224ae60ef4e/" + NUMPY_WHL,
          "sha256": "d549420b8858885cea8838a727842249218b9c1da24dd517e25c9c7a948310a3"},
         {"type": "file", "dest-filename": ORT_WHL,
          "url": "https://files.pythonhosted.org/packages/94/b5/cd55e7f1dfcf2e5fbf3a6915a8c6b4cf81df091e81de2db40e58357ffba4/" + ORT_WHL,
          "sha256": "48b878f9551d465aa79ee94ecaf49a1f6b5d27f2975efa775ded374db14d0af1"}]},
]

if not vanilla:
    gi = m["modules"].index(gimp)
    m["modules"][gi:gi] = GEOM_MODULES + LQR_MODULES + IA_MODULES
    # Correctifs GEGL (plantage multi-thread des tuiles mipmap, cf. patches/gegl-0.4.72)
    gegl = next(x for x in m["modules"] if isinstance(x, dict) and x["name"] == "gegl")
    for p in sorted(glob.glob(os.path.join(ROOT, "patches", "gegl-0.4.72", "*.patch"))):
        gegl["sources"].append({"type": "patch", "path": os.path.relpath(p, FP)})
    patches = sorted(glob.glob(os.path.join(ROOT, "patches", "gimp-3.2.8", "*.patch")))
    if patches:
        # gimp-data est un sous-module : « git am » ne peut pas y appliquer
        # l'icône Windows (gimp.ico, patch 0045), inutile sous Linux.
        gimp["sources"].append({"type": "patch", "use-git-am": True,
                                "options": ["--exclude=gimp-data/*"],
                                "paths": [os.path.relpath(p, FP) for p in patches]})
    # Resynthesizer (GPL) : remplissage d'après le contenu, correcteur de sélection
    m["modules"].append({
        "name": "resynthesizer",
        "buildsystem": "meson",
        "sources": [{"type": "git", "url": "https://github.com/bootchk/resynthesizer.git",
                     "tag": "v3.0.1", "commit": "bddb1dfb6bddc2363bf74d79a95a60691bc46279"}],
    })
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

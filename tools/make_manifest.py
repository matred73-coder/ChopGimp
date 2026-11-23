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

# ── libpotrace 1.16 : Calque > Vectoriser… (3.27.3, lot V5), moteur des
#    contours remplis (app/path/chopgimp-trace.cc). Seule la bibliothèque
#    partagée reste dans le paquet (pas l'outil potrace ni mkbitmap).
POTRACE_MODULES = [
    {"name": "potrace",
     "config-opts": ["--with-libpotrace", "--disable-static"],
     "cleanup": ["/bin", "/include", "/share", "*.la"],
     "sources": [{"type": "archive",
                  "url": "https://potrace.sourceforge.net/download/1.16/potrace-1.16.tar.gz",
                  "sha256": "be8248a17dedd6ccbaab2fcc45835bb0502d062e40fbded3bc56028ce5eb7acc"}]},
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
                        "--prefix=${FLATPAK_DEST} %s %s" % (NUMPY_WHL, ORT_WHL),
                        # allègement : tests, outils de développement et stubs inutiles à l'exécution
                        "SP=${FLATPAK_DEST}/lib/python3.14/site-packages; "
"find $SP/numpy -type d -name tests -prune -exec rm -rf {} + ; "
                        "rm -rf $SP/numpy/f2py $SP/numpy/_pyinstaller "
                        "$SP/onnxruntime/tools $SP/onnxruntime/transformers $SP/onnxruntime/quantization "
                        "$SP/onnxruntime/datasets ; "
                        "find $SP/numpy $SP/onnxruntime -name '*.pyi' -delete"],
     "sources": [
         {"type": "file", "dest-filename": NUMPY_WHL,
          "url": "https://files.pythonhosted.org/packages/16/d5/928078d2b28f26829b138b4a6c3980045022fb409f570657a224ae60ef4e/" + NUMPY_WHL,
          "sha256": "d549420b8858885cea8838a727842249218b9c1da24dd517e25c9c7a948310a3"},
         {"type": "file", "dest-filename": ORT_WHL,
          "url": "https://files.pythonhosted.org/packages/94/b5/cd55e7f1dfcf2e5fbf3a6915a8c6b4cf81df091e81de2db40e58357ffba4/" + ORT_WHL,
          "sha256": "48b878f9551d465aa79ee94ecaf49a1f6b5d27f2975efa775ded374db14d0af1"}]},
]

# ── Performances : options de compilation (make build LTO=… PGO=…)
#
# Le SDK GNOME compile en -O2 avec durcissement et pointeurs de pile
# (-fno-omit-frame-pointer, -D_GLIBCXX_ASSERTIONS). On garde le durcissement
# (FORTIFY, stack-protector, CET) et les symboles (-g, traceur de plantage),
# mais :
#   - babl et GEGL (boucles de calcul par pixel) : -O3, sans pointeur de pile,
#     -fno-semantic-interposition (appels internes des bibliothèques en
#     direct), sans assertions de la STL C++ (opérations GEGL en C++) ;
#   - GIMP : -O2 (code d'interface surtout ; ses modes de fusion profitent de
#     LTO / PGO plutôt que de -O3).
#   - architecture de base inchangée (x86-64 générique) : babl et GEGL
#     compilent déjà leurs variantes x86-64-v2/v3 (v4 pour babl) choisies à
#     l'exécution selon le processeur (vérifié : /app/lib/babl-0.1/x86-64-v3-*.so,
#     /app/lib/gegl-0.4/*-x86_64-v3.so).
#   - LTO (optimisation à l'édition de liens) : CHOPGIMP_LTO=1 (défaut) pour
#     babl et GEGL, « all » pour GIMP aussi, 0 pour aucun.
#   - PGO (optimisation guidée par profil) de GIMP : CHOPGIMP_PGO=1, voir
#     pgo_gimp() ; double le temps de compilation de GIMP.
#   - GIMP : -fno-semantic-interposition (libgimp*, appels internes en
#     direct) ; CHOPGIMP_GIMP_O=3 pour le compiler en -O3 (défaut -O2).
LTO = os.environ.get("CHOPGIMP_LTO", "1")
PGO = os.environ.get("CHOPGIMP_PGO", "0") == "1"
GIMP_O = os.environ.get("CHOPGIMP_GIMP_O", "2")
FAST_LIB_CFLAGS = "-O3 -fomit-frame-pointer -fno-semantic-interposition"
GIMP_CFLAGS = ("-O3 " if GIMP_O == "3" else "") + "-fno-semantic-interposition"

# mimalloc : allocateur plus rapide que celui de la glibc pour les nombreux
# petits blocs de GEGL/GLib en multi-fil ; préchargé par le lanceur
# (flatpak/chopgimp-launch.sh, CHOPGIMP_NO_MIMALLOC=1 pour le désactiver).
MIMALLOC_MODULE = {
    "name": "mimalloc",
    "buildsystem": "cmake-ninja",
    "config-opts": ["-DCMAKE_BUILD_TYPE=Release", "-DMI_BUILD_TESTS=OFF",
                    "-DMI_BUILD_STATIC=OFF", "-DMI_BUILD_OBJECT=OFF",
                    "-DMI_OVERRIDE=ON", "-DCMAKE_INSTALL_LIBDIR=lib"],
    "sources": [{"type": "git", "url": "https://github.com/microsoft/mimalloc.git",
                 "tag": "v2.5.2", "commit": "2406cc5f3ab6d6e54fe560cdd66fa46eee775312"}],
    "cleanup": ["/include", "/lib/cmake", "/lib/pkgconfig", "/share"],
}


def add_build_options(mod, cflags, cxxflags=None):
    bo = mod.setdefault("build-options", {})
    bo["cflags"] = (bo.get("cflags", "") + " " + cflags).strip()
    bo["cxxflags"] = (bo.get("cxxflags", "") + " " + (cxxflags or cflags)).strip()


def pgo_gimp(gimp):
    """Compile GIMP deux fois dans le même dossier : instrumentée
    (-fprofile-generate), entraînée par tools/dev/pgo_train.py dans
    gimp-console (calques, effets, modes de fusion, projection, sélections,
    peinture, réglages, XCF), puis optimisée avec le profil (-fprofile-use).
    -fprofile-partial-training : le code non exercé par l'entraînement
    (interface) reste optimisé normalement au lieu d'être traité comme froid.
    Les mêmes options meson que le module d'origine (buildsystem meson de
    flatpak-builder : --prefix, --libdir, wrap_mode=nodownload)."""
    opts = " ".join("'%s'" % o for o in gimp["config-opts"])
    setup = ("meson setup _pgo --prefix=${FLATPAK_DEST} --libdir=${FLATPAK_DEST}/lib "
             "-Dwrap_mode=nodownload %s" % opts)
    # options de profil passées à C / C++ directement : -Db_pgo de meson
    # échoue sur les extensions en Vala (goat-exercises). libgcov n'est pas
    # réexportée par libgimp* (sinon tools/defcheck.py échoue : mangle_path).
    gen = "-fprofile-generate -fprofile-update=atomic"
    use = "-fprofile-use -fprofile-partial-training -Wno-missing-profile"
    train_env = ("HOME=$PWD/_train/home GIMP3_DIRECTORY=$PWD/_train/cfg PGO_DIR=$PWD/_train PGO_SIZE=2000 "
                 "XDG_CONFIG_HOME=$PWD/_train/home/.config XDG_CACHE_HOME=$PWD/_train/home/.cache "
                 "GI_TYPELIB_PATH=${FLATPAK_DEST}/lib/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH} ")
    gimp["buildsystem"] = "simple"
    gimp["build-commands"] = [
        "CFLAGS=\"$CFLAGS %s\" CXXFLAGS=\"$CXXFLAGS %s\" LDFLAGS=\"$LDFLAGS %s\" %s"
        % (gen, gen, gen + " -Wl,--exclude-libs,libgcov.a", setup),
        "ninja -C _pgo -j${FLATPAK_BUILDER_N_JOBS} install",
        # entraînement : sans écran, configuration jetable dans le dossier de
        # compilation ; deux passes (la première initialise la configuration,
        # interroge les greffons et charge polices et données)
        "mkdir -p _train/home _train/cfg && for pass in 1 2; do " + train_env +
        "timeout 1800 ${FLATPAK_DEST}/bin/gimp-console-3.2 -i --quit "
        "--batch-interpreter=python-fu-eval -b \"exec(open('pgo_train.py').read())\" "
        "> _train/console-$pass.log 2>&1 || { echo \"PGO : passe $pass incomplète\"; "
        "tail -30 _train/console-$pass.log; }; "
        "cat _train/pgo_train.log || true; done",
        "echo \"PGO : $(find _pgo -name '*.gcda' | wc -l) profils\"",
        "meson configure _pgo -Dc_args=\"$CFLAGS %s\" -Dcpp_args=\"$CXXFLAGS %s\" "
        "-Dc_link_args=\"$LDFLAGS %s\" -Dcpp_link_args=\"$LDFLAGS %s\"" % (use, use, use, use),
        "ninja -C _pgo -j${FLATPAK_BUILDER_N_JOBS} install",
        "rm -rf _train",
    ]
    gimp.pop("config-opts", None)
    gimp["sources"].append({"type": "file", "path": "../tools/dev/pgo_train.py"})


def tune_build(m, gimp):
    for name in ("babl", "gegl"):
        mod = find_module(m["modules"], name)
        add_build_options(mod, FAST_LIB_CFLAGS, FAST_LIB_CFLAGS + " -Wp,-U_GLIBCXX_ASSERTIONS")
        if LTO in ("1", "all"):
            mod["config-opts"] = mod.get("config-opts", []) + ["-Db_lto=true"]
    add_build_options(gimp, GIMP_CFLAGS)
    if LTO == "all":
        gimp["config-opts"] = gimp["config-opts"] + ["-Db_lto=true"]
    if PGO:
        pgo_gimp(gimp)
    m["modules"].insert(m["modules"].index(gimp), MIMALLOC_MODULE)
    # lanceur : environnement de performance puis gimp-3.2 (aussi pour le .desktop)
    m["command"] = "chopgimp"


if not vanilla:
    # en-têtes et fichiers de développement : inutiles à l'exécution
    m["cleanup"] = sorted(set(m.get("cleanup", []) + ["/include", "/lib/pkgconfig"]))
    gi = m["modules"].index(gimp)
    m["modules"][gi:gi] = GEOM_MODULES + LQR_MODULES + POTRACE_MODULES + IA_MODULES
    # Correctifs GEGL (plantage multi-thread des tuiles mipmap, cf. patches/gegl-0.4.72)
    gegl = next(x for x in m["modules"] if isinstance(x, dict) and x["name"] == "gegl")
    for p in sorted(glob.glob(os.path.join(ROOT, "patches", "gegl-0.4.72", "*.patch"))):
        gegl["sources"].append({"type": "patch", "path": os.path.relpath(p, FP)})
    # Correctifs babl (extraction directe de l'alpha, verrou de la conversion
    # de référence, cf. patches/babl-0.1.128)
    babl = next(x for x in m["modules"] if isinstance(x, dict) and x["name"] == "babl")
    for p in sorted(glob.glob(os.path.join(ROOT, "patches", "babl-0.1.128", "*.patch"))):
        babl["sources"].append({"type": "patch", "path": os.path.relpath(p, FP)})
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
    # ── Performances (3.25.0) : options de compilation, PGO, mimalloc
    tune_build(m, gimp)
    # Données PhotoGIMP Pro, installées après GIMP (voir tools/install_data.sh)
    m["modules"].append({
        "name": "photogimp-data",
        "buildsystem": "simple",
        # artefacts de construction exclus (plusieurs Go : dépôts, build-dirs)
        "sources": [{"type": "dir", "path": "..", "skip": [".git", "build", ".backups",
                                                          "flatpak/.flatpak-builder",
                                                          "flatpak/build-dir",
                                                          "flatpak/build-dir-vanilla",
                                                          "flatpak/build-deps-test",
                                                          "flatpak/repo",
                                                          "flatpak/repo-vanilla",
                                                          "dist"]}],
        "build-commands": ["sh tools/install_data.sh ${FLATPAK_DEST}",
                           # allègement : traductions limitées au français et à l'anglais
                           "find ${FLATPAK_DEST}/share/locale -mindepth 1 -maxdepth 1 "
                           "! -name 'fr*' ! -name 'en*' -exec rm -rf {} +"],
    })

out = os.path.join(FP, APP_ID + (".vanilla" if vanilla else "") + ".json")
json.dump(m, open(out, "w"), indent=4, ensure_ascii=False)
print("manifeste écrit :", out)

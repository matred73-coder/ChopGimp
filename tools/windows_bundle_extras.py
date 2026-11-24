#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════
# ChopGimp — compléments du dossier autonome Windows (gimp-clang64)
#
#   python3 tools/windows_bundle_extras.py <gimp-clang64> <sources GIMP> [préfixe MSYS2]
#
# Le script de bundle de GIMP ne copie que ce qui est LIÉ aux exécutables.
# Les greffons ChopGimp chargent en plus, à l'exécution :
#   - des DLL par ctypes / g_module_open : liblqr (Liquid Rescale),
#     libhunspell (orthographe), Ghostscript (EPS/AI, déjà présent) ;
#   - des bibliothèques GObject par « gi » : Poppler (import PDF vectoriel),
#     Rsvg, Gst (export du timelapse en WebM) ;
#   - les greffons GStreamer de la chaîne du timelapse.
# Ce script les copie, avec leurs dépendances (tools/lib_bundle.py de GIMP).
# À lancer après la création du dossier autonome (ninja install), avant
# l'installateur ou la version portable. Ne modifie rien d'autre.
# Prérequis MSYS2 : hunspell, liblqr, gstreamer, gst-plugins-base, gst-plugins-good.
# ═══════════════════════════════════════════════════════════════
import os
import shutil
import subprocess
import sys

DLLS = ["liblqr-1-0.dll", "libhunspell-1.7-0.dll", "libgs-10.dll"]
TYPELIBS = ["Poppler", "Rsvg", "Gst"]
# chaîne du timelapse (chopgimp_atelier) : multifilesrc ! pngdec ! videoconvert !
# videoscale ! capsfilter ! vp8enc ! webmmux ! filesink
GST_PLUGINS = ["libgstcoreelements.dll", "libgstmultifile.dll", "libgstpng.dll",
               "libgstvideoconvertscale.dll", "libgstvpx.dll", "libgstmatroska.dll"]


def main(bundle, gimp_src, msys):
    env = dict(os.environ, PATH=os.path.join(msys, "bin") + os.pathsep + os.environ["PATH"])
    bin_dir = os.path.join(bundle, "bin")
    gir_dir = os.path.join(bundle, "lib", "girepository-1.0")
    gst_dir = os.path.join(bundle, "lib", "gstreamer-1.0")
    to_scan = []

    def copy(src, dst_dir):
        if not os.path.exists(src):
            sys.exit(f"absent : {src} (paquet MSYS2 manquant ?)")
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.basename(src))
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
            print(f"  + {os.path.relpath(dst, bundle)}")
        return dst

    print("== DLL chargées à l'exécution")
    for d in DLLS:
        to_scan.append(copy(os.path.join(msys, "bin", d), bin_dir))

    print("== bibliothèques GObject (gi)")
    seen = set()
    queue = list(TYPELIBS)
    while queue:
        ns = queue.pop(0)
        if ns in seen:
            continue
        seen.add(ns)
        out = subprocess.run(["g-ir-inspect", "--print-typelibs", "--print-shlibs", ns],
                             capture_output=True, text=True, env=env, check=True).stdout
        for line in out.splitlines():
            kind, _, value = line.partition(": ")
            if kind == "typelib":
                queue.append(value.split("-")[0])
            elif kind == "shlib":
                to_scan.append(copy(os.path.join(msys, "bin", value), bin_dir))
        typelib = [f for f in os.listdir(os.path.join(msys, "lib", "girepository-1.0"))
                   if f.startswith(ns + "-") and f.endswith(".typelib")]
        for t in typelib:
            copy(os.path.join(msys, "lib", "girepository-1.0", t), gir_dir)

    print("== greffons GStreamer (timelapse)")
    for p in GST_PLUGINS:
        to_scan.append(copy(os.path.join(msys, "lib", "gstreamer-1.0", p), gst_dir))

    print("== dépendances")
    for b in to_scan:
        subprocess.run([sys.executable, os.path.join(gimp_src, "tools", "lib_bundle.py"),
                        b, msys + "/", bundle], env=env, check=True,
                       stdout=subprocess.DEVNULL)
    print(f"== compléments ChopGimp ajoutés à {bundle}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) not in (3, 4):
        sys.exit("usage : windows_bundle_extras.py <gimp-clang64> <sources GIMP> [préfixe MSYS2]")
    main(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]),
         sys.argv[3] if len(sys.argv) == 4 else "C:/msys64/clang64")

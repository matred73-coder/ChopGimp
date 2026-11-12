#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════
# ChopGimp — identité visuelle du build Windows (MSYS2 CLANG64)
#
#   python3 tools/windows_branding.py ico       <source GIMP>
#       → remplace gimp-data/images/logo/gimp.ico (icône de gimp*.exe,
#         compilée dans l'exécutable par gimp.rc) ; À LANCER AVANT ninja.
#
#   python3 tools/windows_branding.py installer <dossier de build>
#       → remplace les images de l'installateur Inno générées par meson
#         (-Dwindows-installer=true) : setup.ico, gimp.scale-*.bmp,
#         installsplash_*.bmp, install-end.scale-*.bmp, splash-dimensions.h.
#         À LANCER APRÈS ninja, AVANT 3_dist-gimp-inno.ps1.
#
# Sources : branding/png/chopgimp-*.png et branding/splash.png.
# Nécessite Pillow (pacman -S mingw-w64-clang-x86_64-python-pillow).
# ═══════════════════════════════════════════════════════════════
import io
import os
import re
import shutil
import struct
import sys

from PIL import Image, ImageFilter

# Console Windows (cp1252) : ne jamais planter sur un caractère accentué
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PNG_DIR = os.path.join(SRC, "branding", "png")
SPLASH = os.path.join(SRC, "branding", "splash.png")

# Tailles reprises de gimp-data/images/logo/gen-setup-ico.py.in
ICO_SIZES = [16, 20, 22, 24, 32, 40, 48, 64, 96, 128, 256]

# Position horizontale du logo « Cg » dans splash.png (centre du disque),
# utilisée pour cadrer la bande verticale de la page de fin.
SPLASH_LOGO_X = 0.285   # décalé à gauche : la bande s'arrête avant le texte


def logo(size):
    """Logo carré RGBA à la taille demandée (PNG exact si fourni)."""
    exact = os.path.join(PNG_DIR, f"chopgimp-{size}.png")
    if os.path.exists(exact):
        return Image.open(exact).convert("RGBA")
    big = Image.open(os.path.join(PNG_DIR, "chopgimp-512.png")).convert("RGBA")
    return big.resize((size, size), Image.LANCZOS)


def write_ico(path):
    """ICO multi-tailles, chaque entrée encodée en PNG (Windows Vista+)."""
    blobs = []
    for size in ICO_SIZES:
        buf = io.BytesIO()
        logo(size).save(buf, "PNG")
        blobs.append((size, buf.getvalue()))
    out = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    for size, data in blobs:
        dim = 0 if size >= 256 else size
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for _, data in blobs:
        out += data
    with open(path, "wb") as f:
        f.write(out)
    print(f"  {path}")


def write_bmp_rgba(img, path):
    """BMP 32 bits avec alpha (BITMAPV5HEADER + BI_BITFIELDS), comme
    l'export « rgba-8888 » de GIMP attendu par WizardImageAlphaFormat."""
    img = img.convert("RGBA")
    w, h = img.size
    pixels = img.transpose(Image.FLIP_TOP_BOTTOM).tobytes("raw", "BGRA")
    header = struct.pack(
        "<IiiHHIIiiII", 124, w, h, 1, 32, 3, len(pixels), 2835, 2835, 0, 0)
    header += struct.pack("<IIII", 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    header += struct.pack("<I", 0x73524742)          # LCS_sRGB
    header += b"\0" * 36 + struct.pack("<III", 0, 0, 0)
    header += struct.pack("<IIII", 4, 0, 0, 0)       # LCS_GM_IMAGES
    file_header = struct.pack("<2sIHHI", b"BM", 14 + len(header) + len(pixels),
                              0, 0, 14 + len(header))
    with open(path, "wb") as f:
        f.write(file_header + header + pixels)


def splash_scaled(height):
    img = Image.open(SPLASH).convert("RGB")
    w, h = img.size
    return img.resize((int(height / h * w), height), Image.LANCZOS)


def do_ico(gimp_src):
    target = os.path.join(gimp_src, "gimp-data", "images", "logo", "gimp.ico")
    backup = target + ".gimp-orig"
    if not os.path.exists(backup):
        shutil.copy2(target, backup)
    print("== icône de l'exécutable")
    write_ico(target)


def do_installer(build_dir):
    out = os.path.join(build_dir, "build", "windows", "installer")
    if not os.path.isdir(out):
        sys.exit(f"{out} absent : configurer avec -Dwindows-installer=true puis ninja")
    print(f"== images de l'installateur → {out}")

    write_ico(os.path.join(out, "setup.ico"))

    # Petite icône en haut à droite (gen-gimp-bmp.py.in : logo à 71 %)
    for scale, side in [("100", 58), ("125", 71), ("150", 85), ("175", 103),
                        ("200", 112), ("225", 129), ("250", 147)]:
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        dim = int(side * 0.71)
        canvas.paste(logo(512).resize((dim, dim), Image.LANCZOS),
                     ((side - dim) // 2, (side - dim) // 2))
        write_bmp_rgba(canvas, os.path.join(out, f"gimp.scale-{scale}.bmp"))

    # Écran d'accueil (splash2installer.py.in) : mêmes hauteurs
    for scale, height in [("100", 314), ("125", 386), ("150", 459), ("175", 556),
                          ("200", 604), ("225", 700), ("250", 797)]:
        splash_scaled(height).save(
            os.path.join(out, f"installsplash_top.scale-{scale}.bmp"), "BMP")
    splash_scaled(314).filter(ImageFilter.GaussianBlur(27.5)).save(
        os.path.join(out, "installsplash_bottom.bmp"), "BMP")

    # Page de fin : bande verticale centrée sur le logo
    for scale, tw, th in [("100", 164, 314), ("125", 202, 386), ("150", 240, 459),
                          ("175", 290, 556), ("200", 315, 604), ("225", 366, 700),
                          ("250", 416, 797)]:
        img = splash_scaled(th)
        x = int(img.width * SPLASH_LOGO_X - tw / 2)
        x = max(0, min(x, img.width - tw))
        img.crop((x, 0, x + tw, th)).save(
            os.path.join(out, f"install-end.scale-{scale}.bmp"), "BMP")

    w, h = Image.open(SPLASH).size
    with open(os.path.join(out, "splash-dimensions.h"), "w") as f:
        f.write(f"#define GIMP_SPLASH_WIDTH  {w}\n#define GIMP_SPLASH_HEIGHT {h}\n")
    print("== images de l'installateur ChopGimp écrites")

    # Textes de l'installateur (lang/*.setup.isl générés par meson) :
    # « GIMP » → « ChopGimp » dans les valeurs, jamais dans les clés.
    lang_dir = os.path.join(out, "lang")
    count = 0
    for name in sorted(os.listdir(lang_dir)):
        if not name.endswith(".isl"):
            continue
        path = os.path.join(lang_dir, name)
        raw = open(path, "rb").read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        lines = raw.decode("utf-8-sig").split("\n")
        for i, line in enumerate(lines):
            key, sep, value = line.partition("=")
            if not sep or key.startswith((";", "[")):
                continue
            if key.strip() == "AboutSetupNote":
                value = "ChopGimp, basé sur GIMP (gimp.org)"
            else:
                value = re.sub(r"\bGIMP\b", "ChopGimp", value)
            lines[i] = key + sep + value
        text = "\n".join(lines)
        with open(path, "wb") as f:
            f.write((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
        count += 1
    print(f"== textes de l'installateur : {count} langues passées à ChopGimp")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("ico", "installer"):
        sys.exit(__doc__ or "usage: windows_branding.py ico|installer <dossier>")
    {"ico": do_ico, "installer": do_installer}[sys.argv[1]](sys.argv[2])

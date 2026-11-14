#!/usr/bin/env python3
"""
PhotoGIMP Pro — génère :
  config/templaterc        modèles « Nouveau document » classés comme Photoshop
                           (Photo, Impression, Illustration, Web, Mobile,
                           Vidéo, Réseaux sociaux)
  presets/tool-presets/    préréglages d'outils façon Photoshop (pinceaux
                           ronds durs/flous, gommes, tampon, correcteur)

Usage : build_documents.py
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def px(mm, ppi=300):
    return int(round(mm / 25.4 * ppi))


# (catégorie, nom, largeur, hauteur, unité d'affichage, ppp, fond)
# largeur/hauteur en pixels, ou en mm si unité = millimeters
T = []


def add(cat, name, w, h, unit="pixels", ppi=72, fill="white"):
    if unit == "millimeters":
        w, h = px(w, ppi), px(h, ppi)
    T.append((cat, name, w, h, unit, ppi, fill))


# Par défaut (en tête de liste, comme « Taille Photoshop par défaut »)
add("Défaut", "Document par défaut 1920×1080", 1920, 1080)

# Photo (300 ppp, tailles de tirage françaises)
for name, w, h in [("Paysage 15×10 cm", 150, 100), ("Portrait 10×15 cm", 100, 150),
                   ("Paysage 18×13 cm", 180, 130), ("Portrait 13×18 cm", 130, 180),
                   ("Paysage 24×18 cm", 240, 180), ("Portrait 18×24 cm", 180, 240),
                   ("Paysage 30×20 cm", 300, 200), ("Carré 20×20 cm", 200, 200)]:
    add("Photo", name, w, h, "millimeters", 300)

# Impression
for name, w, h in [("A4 portrait", 210, 297), ("A4 paysage", 297, 210),
                   ("A3 portrait", 297, 420), ("A3 paysage", 420, 297),
                   ("A5 portrait", 148, 210), ("A5 paysage", 210, 148),
                   ("A2 affiche", 420, 594), ("A6 carte postale", 148, 105),
                   ("Carte de visite 85×55 mm", 85, 55), ("Lettre US", 215.9, 279.4),
                   ("Flyer DL 99×210 mm", 99, 210)]:
    add("Impression", name, w, h, "millimeters", 300)

# Illustration
add("Illustration", "Affiche 40×60 cm", 400, 600, "millimeters", 300)
add("Illustration", "Toile 4000×4000", 4000, 4000, ppi=300)
add("Illustration", "Grille 1920×1080", 1920, 1080)

# Web
for name, w, h in [("Web courant 1366×768", 1366, 768), ("Web grand 1920×1080", 1920, 1080),
                   ("Web moyen 1440×900", 1440, 900), ("Web minimum 1024×768", 1024, 768),
                   ("Écran 2K 2560×1440", 2560, 1440), ("Bannière 1200×628", 1200, 628)]:
    add("Web", name, w, h)

# Mobile
for name, w, h in [("iPhone 15 1179×2556", 1179, 2556), ("iPhone 15 Pro Max 1290×2796", 1290, 2796),
                   ("Android 1080×1920", 1080, 1920), ("Android 1440×3120", 1440, 3120),
                   ("iPad 1640×2360", 1640, 2360), ("iPad Pro 12,9 pouces 2048×2732", 2048, 2732)]:
    add("Mobile", name, w, h)

# Vidéo
for name, w, h in [("HD 720p 1280×720", 1280, 720), ("Full HD 1080p 1920×1080", 1920, 1080),
                   ("UHD 4K 3840×2160", 3840, 2160), ("DCI 4K 4096×2160", 4096, 2160),
                   ("UHD 8K 7680×4320", 7680, 4320), ("Vertical 1080×1920", 1080, 1920)]:
    add("Vidéo", name, w, h)

# Réseaux sociaux
for name, w, h in [("Instagram publication 1080×1080", 1080, 1080),
                   ("Instagram portrait 1080×1350", 1080, 1350),
                   ("Instagram / TikTok story 1080×1920", 1080, 1920),
                   ("Facebook publication 1200×630", 1200, 630),
                   ("Facebook couverture 851×315", 851, 315),
                   ("LinkedIn bannière 1584×396", 1584, 396),
                   ("LinkedIn publication 1200×627", 1200, 627),
                   ("X (Twitter) en-tête 1500×500", 1500, 500),
                   ("YouTube miniature 1280×720", 1280, 720),
                   ("YouTube bannière 2560×1440", 2560, 1440),
                   ("Pinterest épingle 1000×1500", 1000, 1500)]:
    add("Réseaux sociaux", name, w, h)


def templaterc():
    out = ["# GIMP templaterc — PhotoGIMP Pro (modèles « Nouveau document » façon Photoshop)",
           "# Généré par tools/build_documents.py", ""]
    for cat, name, w, h, unit, ppi, fill in T:
        out.append('(GimpTemplate "%s — %s"\n    (width %d)\n    (height %d)\n    (unit %s)\n'
                   '    (xresolution %d)\n    (yresolution %d)\n    (resolution-unit %s)\n'
                   '    (image-type rgb)\n    (precision u8-non-linear)\n    (fill-type %s)\n'
                   '    (comment "")\n    (filename ""))'
                   % (cat, name, w, h, unit, ppi, ppi,
                      "millimeters" if unit == "millimeters" else "inches", fill))
    out += ["", "# end of templaterc", ""]
    return "\n".join(out)


# Préréglages d'outils (name, tool, icon, options GimpPaintOptions)
PRESETS = [
    ("Pinceau rond dur", "gimp-paintbrush-tool", "gimp-tool-paintbrush",
     "2. Hardness 100", 30, 1.0, "Pressure Size"),
    ("Pinceau rond flou", "gimp-paintbrush-tool", "gimp-tool-paintbrush",
     "2. Hardness 025", 60, 1.0, "Pressure Size"),
    ("Pinceau rond flou (opacité pression)", "gimp-paintbrush-tool", "gimp-tool-paintbrush",
     "2. Hardness 025", 60, 1.0, "Pressure Opacity"),
    ("Crayon 1 px", "gimp-pencil-tool", "gimp-tool-pencil",
     "2. Hardness 100", 1, 1.0, None),
    ("Gomme ronde dure", "gimp-eraser-tool", "gimp-tool-eraser",
     "2. Hardness 100", 40, 1.0, "Pressure Size"),
    ("Gomme ronde floue", "gimp-eraser-tool", "gimp-tool-eraser",
     "2. Hardness 025", 80, 1.0, "Pressure Size"),
    ("Tampon de duplication (aligné)", "gimp-clone-tool", "gimp-tool-clone",
     "2. Hardness 050", 50, 1.0, None),
    ("Correcteur", "gimp-heal-tool", "gimp-tool-heal",
     "2. Hardness 075", 30, 1.0, None),
    ("Densité − / + (doux)", "gimp-dodge-burn-tool", "gimp-tool-dodge",
     "2. Hardness 025", 80, 0.5, None),
]


OPT_CLASS = {"gimp-paintbrush-tool": "GimpPaintOptions", "gimp-pencil-tool": "GimpPencilOptions",
             "gimp-eraser-tool": "GimpEraserOptions", "gimp-clone-tool": "GimpCloneOptions",
             "gimp-heal-tool": "GimpSourceOptions", "gimp-dodge-burn-tool": "GimpDodgeBurnOptions"}


def preset(name, tool, icon, brush, size, opacity, dyn):
    extra = ""
    if tool == "gimp-clone-tool":
        extra = "    (align-mode yes)\n"
    if dyn:
        dyn_lines = '    (dynamics "%s")\n    (dynamics-enabled yes)\n' % dyn
    else:
        dyn_lines = "    (dynamics-enabled no)\n"
    return ('# GIMP tool preset file — PhotoGIMP Pro\n\n'
            '(icon-name "%s")\n(name "%s")\n(tool-options "%s"\n'
            '    (tool "%s")\n    (brush "%s")\n%s    (brush-size %.1f)\n'
            '    (opacity %.2f)\n%s)\n'
            '(use-fg-bg no)\n(use-brush yes)\n(use-dynamics yes)\n(use-gradient no)\n'
            '(use-pattern no)\n(use-palette no)\n(use-font no)\n\n# end of GIMP tool preset file\n'
            % (icon, name, OPT_CLASS[tool], tool, brush, dyn_lines, size, opacity, extra))


def slug(s):
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")


if __name__ == "__main__":
    open(os.path.join(ROOT, "config", "templaterc"), "w").write(templaterc())
    d = os.path.join(ROOT, "presets", "tool-presets")
    os.makedirs(d, exist_ok=True)
    # seulement les préréglages générés ici (« PS-… ») : les autres
    # (Peinture-…, Melangeur-…) sont écrits à la main
    for f in os.listdir(d):
        if f.startswith("PS-") and f.endswith(".gtp"):
            os.unlink(os.path.join(d, f))
    for p in PRESETS:
        open(os.path.join(d, "PS-" + slug(p[0]) + ".gtp"), "w").write(preset(*p))
    print("%d modèles, %d préréglages d'outils" % (len(T), len(PRESETS)))

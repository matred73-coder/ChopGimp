#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — fichiers de test SVG et EPS pour l'import vectoriel.

    python3 tools/fixtures/make_vector.py dossier/

test.svg : 400×300, calques Inkscape « Fond » (rectangle orange, dégradé)
           et « Dessin » (cercle bleu, texte « Salut SVG » 32 px gras),
           plus un calque « Caché » masqué (étoile verte).
test.eps : 300×200 pt, rectangle rouge, courbe bleue (contour 3 pt),
           texte « Bonjour EPS » Helvetica 20 pt.
"""
import os
import sys

SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="400" height="300" viewBox="0 0 400 300">
  <defs>
    <linearGradient id="g1" x1="0" x2="1"><stop offset="0" stop-color="#ffff00"/><stop offset="1" stop-color="#00ffff"/></linearGradient>
  </defs>
  <g id="calque1" inkscape:groupmode="layer" inkscape:label="Fond">
    <rect x="20" y="20" width="160" height="100" fill="#ff8800"/>
    <rect x="20" y="250" width="360" height="30" fill="url(#g1)"/>
  </g>
  <g id="calque2" inkscape:groupmode="layer" inkscape:label="Dessin">
    <circle cx="280" cy="80" r="50" fill="#2255ff" stroke="#000000" stroke-width="4"/>
    <text x="40" y="200" style="font-size:32px;font-family:DejaVu Sans;font-weight:bold;fill:#aa0000">Salut SVG</text>
  </g>
  <g id="calque3" inkscape:groupmode="layer" inkscape:label="Caché" style="display:none">
    <path d="M 200 150 L 220 200 L 180 170 L 230 170 L 190 200 Z" fill="#00aa00"/>
  </g>
</svg>
"""

EPS = """%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: 0 0 300 200
%%EndComments
1 0 0 setrgbcolor
20 110 120 70 rectfill
0 0 1 setrgbcolor 3 setlinewidth
160 40 moveto 200 180 240 0 280 120 curveto stroke
/Helvetica findfont 20 scalefont setfont
0 0 0 setrgbcolor 20 40 moveto (Bonjour EPS) show
showpage
%%EOF
"""


def write(folder):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "test.svg"), "w", encoding="utf-8") as f:
        f.write(SVG)
    with open(os.path.join(folder, "test.eps"), "w", encoding="latin-1") as f:
        f.write(EPS)


if __name__ == "__main__":
    write(sys.argv[1] if len(sys.argv) > 1 else ".")

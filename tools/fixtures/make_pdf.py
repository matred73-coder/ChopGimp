#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — fabrique un PDF de test pour l'import vectoriel (étape Vectoriel I).

    python3 tools/fixtures/make_pdf.py sortie.pdf

Page A5 paysage (595 × 420 pt) :
  base           rectangle rouge plein (50,50 200×100)
  calque « Bleu »   triangle bleu (OCG visible)
  calque « Vert »   courbe verte, contour 4 pt (OCG masqué)
  texte          « Bonjour PDF » Helvetica 24 pt noir
  image          2×2 pixels RGB agrandie à 100×100
  dégradé        bande jaune → cyan (shading axial sous découpe)
"""
import sys
import zlib

W, H = 595, 420


def build():
    content = b"""q 1 0 0 rg 50 270 200 100 re f Q
/OC /L1 BDC q 0 0 1 rg 300 270 m 400 270 l 350 370 l h f Q EMC
/OC /L2 BDC q 0 0.6 0 RG 4 w 50 150 m 150 250 250 50 350 150 c S Q EMC
BT /F1 24 Tf 0 0 0 rg 60 60 Td (Bonjour PDF) Tj ET
q 100 0 0 100 450 250 cm /Im1 Do Q
q 50 20 200 30 re W n /Sh1 sh Q
"""
    img = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0])
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R /OCProperties << /OCGs [5 0 R 6 0 R] "
        b"/D << /Order [5 0 R 6 0 R] /OFF [6 0 R] >> >> >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents 4 0 R /Resources "
        b"<< /Properties << /L1 5 0 R /L2 6 0 R >> /Font << /F1 7 0 R >> /XObject << /Im1 8 0 R >> "
        b"/Shading << /Sh1 9 0 R >> >> >>" % (W, H),
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /OCG /Name (Bleu) >>",
        b"<< /Type /OCG /Name (Vert) >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceRGB "
        b"/BitsPerComponent 8 /Length %d >>\nstream\n" % len(img) + img + b"\nendstream",
        b"<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [50 0 250 0] /Extend [true true] "
        b"/Function << /FunctionType 2 /Domain [0 1] /C0 [1 1 0] /C1 [0 1 1] /N 1 >> >>",
    ]
    out = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n"
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


def write(path):
    with open(path, "wb") as f:
        f.write(build())


if __name__ == "__main__":
    write(sys.argv[1] if len(sys.argv) > 1 else "chopgimp-test.pdf")

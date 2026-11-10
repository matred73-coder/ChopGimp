#!/usr/bin/env python3
"""Planche de contrôle des icônes PS-Line (rendu librsvg, fond Photoshop)."""
import sys, os, glob, cairo, gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
src, out = sys.argv[1], sys.argv[2]
size = int(sys.argv[3]) if len(sys.argv) > 3 else 48
files = sorted(f for f in glob.glob(os.path.join(src, '*-symbolic.svg')))
cols = 8; cw, ch = size + 64, size + 34
rows = (len(files) + cols - 1) // cols
surf = cairo.ImageSurface(cairo.FORMAT_RGB24, cols * cw, rows * ch)
cr = cairo.Context(surf); cr.set_source_rgb(0.196, 0.196, 0.196); cr.paint()
for i, f in enumerate(files):
    x, y = (i % cols) * cw, (i // cols) * ch
    data = open(f).read().replace('#bebebe', '#dcdcdc')
    h = Rsvg.Handle.new_from_data(data.encode())
    cr.save(); cr.translate(x + (cw - size) / 2, y + 6)
    vp = Rsvg.Rectangle(); vp.x = 0; vp.y = 0; vp.width = size; vp.height = size
    h.render_document(cr, vp); cr.restore()
    # aperçu taille réelle 16 px
    cr.save(); cr.translate(x + 4, y + 6)
    vp2 = Rsvg.Rectangle(); vp2.x = 0; vp2.y = 0; vp2.width = 16; vp2.height = 16
    h.render_document(cr, vp2); cr.restore()
    name = os.path.basename(f).replace('-symbolic.svg', '').replace('gimp-tool-', '')
    cr.set_source_rgb(0.75, 0.75, 0.75); cr.select_font_face('Sans'); cr.set_font_size(10)
    ext = cr.text_extents(name); cr.move_to(x + (cw - ext.width) / 2, y + size + 22); cr.show_text(name)
surf.write_to_png(out); print(out, len(files))

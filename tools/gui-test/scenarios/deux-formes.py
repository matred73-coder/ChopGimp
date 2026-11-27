# Banc graphique ChopGimp 4.2.9 : XCF 400x300 avec un calque vectoriel de deux
# carrés (objets 50,50 et 230,100, côté 100). Lancé par direct-select.sh.
import os, functools
from gi.repository import Gimp, Gio
OUT = os.environ["PREP_OUT"]
pdb = Gimp.get_pdb()
def run(name, **kw):
    p = pdb.lookup_procedure(name); c = p.create_config()
    for k, v in kw.items(): c.set_property(k, v)
    return p.run(c)
im = Gimp.Image.new(400, 300, Gimp.ImageBaseType.RGB)
bg = Gimp.Layer.new(im, "Fond", 400, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
im.insert_layer(bg, None, 0); bg.fill(Gimp.FillType.WHITE)
pa = Gimp.Path.new(im, "Formes"); im.insert_path(pa, None, 0)
for x, y, s in ((50, 50, 100), (230, 100, 100)):
    st = pa.bezier_stroke_new_moveto(x, y)
    for px, py in ((x + s, y), (x + s, y + s), (x, y + s)):
        pa.bezier_stroke_lineto(st, px, py)
    pa.stroke_close(st)
vl = Gimp.VectorLayer.new(im, pa); im.insert_layer(vl, None, 0)
vl.set_enable_fill(True); vl.set_enable_stroke(True); vl.set_stroke_width(2); vl.refresh()
im.set_selected_layers([vl])
r = run("chopgimp-vobjects-command", image=im, command="split-new")
x = run("chopgimp-vobjects-get-xml", layer=vl)
Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, im, Gio.File.new_for_path(OUT), None)
open(OUT + ".txt", "w").write(str(r.index(1)) + "\n" + x.index(1))

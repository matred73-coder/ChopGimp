"""
ChopGimp — test de fonctionnement exécuté DANS le paquet Flatpak :
  flatpak run --command=gimp-console-3.2 <app-id> -i --batch-interpreter=python-fu-eval \
      -b 'exec(open("tools/smoke_test.py").read())'
Résultats : <SMOKE_OUT> (une ligne « OK|ÉCHEC  test  détail » par test).
"""
import os
import traceback

from gi.repository import Gimp, Gegl, Gio

OUT = os.environ.get("SMOKE_OUT", "/tmp/chopgimp-smoke.txt")
TMP = os.environ.get("SMOKE_TMP", "/tmp/chopgimp-smoke")
os.makedirs(TMP, exist_ok=True)
pdb = Gimp.get_pdb()
results = []


def report(ok, name, detail=""):
    results.append("%s  %s  %s" % ("OK    " if ok else "ÉCHEC ", name, detail))


def run(proc, **kw):
    p = pdb.lookup_procedure(proc)
    cfg = p.create_config()
    for k, v in kw.items():
        if k == "drawables":
            cfg.set_core_object_array(k, v)
        else:
            cfg.set_property(k, v)
    res = p.run(cfg)
    return res


def color(r, g, b):
    c = Gegl.Color.new("black")
    c.set_rgba(r, g, b, 1.0)
    return c


def test_image():
    img = Gimp.Image.new(400, 300, Gimp.ImageBaseType.RGB)
    bg = Gimp.Layer.new(img, "Fond", 400, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
    img.insert_layer(bg, None, 0)
    Gimp.context_set_foreground(color(0.2, 0.4, 0.8))
    bg.edit_fill(Gimp.FillType.FOREGROUND)
    grp = Gimp.GroupLayer.new(img, "Groupe")
    img.insert_layer(grp, None, 0)
    a = Gimp.Layer.new(img, "Rouge", 400, 300, Gimp.ImageType.RGBA_IMAGE, 80, Gimp.LayerMode.MULTIPLY)
    img.insert_layer(a, grp, 0)
    a.fill(Gimp.FillType.TRANSPARENT)
    img.select_rectangle(Gimp.ChannelOps.REPLACE, 50, 50, 200, 150)
    Gimp.context_set_foreground(color(0.9, 0.1, 0.1))
    a.edit_fill(Gimp.FillType.FOREGROUND)
    Gimp.Selection.none(img)
    mask = a.create_mask(Gimp.AddMaskType.WHITE)
    a.add_mask(mask)
    return img


def count_layers(items):
    n = 0
    for it in items:
        n += 1
        if it.is_group():
            n += count_layers(it.get_children())
    return n


try:
    # 1. PSD : export puis réimport (calques, groupe, masque, mode, opacité)
    img = test_image()
    psd = Gio.File.new_for_path(os.path.join(TMP, "test.psd"))
    res = run("file-psd-export", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": img, "file": psd})
    report(res.index(0) == Gimp.PDBStatusType.SUCCESS, "Export PSD", psd.get_path())
    img2 = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, psd)
    top = img2.get_layers()
    grp = [l for l in top if l.is_group()]
    report(len(grp) == 1, "PSD : groupe de calques conservé", "%d groupe(s)" % len(grp))
    report(count_layers(top) == 3, "PSD : nombre de calques", "%d (attendu 3)" % count_layers(top))
    if grp:
        child = grp[0].get_children()[0]
        report(child.get_mask() is not None, "PSD : masque de fusion conservé")
        report(child.get_mode() == Gimp.LayerMode.MULTIPLY, "PSD : mode de fusion conservé",
               str(child.get_mode()))
        report(abs(child.get_opacity() - 80) < 1, "PSD : opacité conservée", "%.0f %%" % child.get_opacity())

    # 2. PDF : export puis réimport
    pdf = Gio.File.new_for_path(os.path.join(TMP, "test.pdf"))
    res = run("file-pdf-export", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": img, "file": pdf})
    report(res.index(0) == Gimp.PDBStatusType.SUCCESS, "Export PDF", pdf.get_path())
    img3 = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, pdf)
    report(img3 is not None and len(img3.get_layers()) >= 1, "Import PDF",
           "%dx%d, %d page(s)" % (img3.get_width(), img3.get_height(), len(img3.get_layers())))

    # 3. Fonctions de calques façon Photoshop (plug-in photogimp_ps)
    for proc in ["photogimp-style-stroke", "photogimp-style-outer-glow", "photogimp-style-inner-shadow",
                 "photogimp-adj-curves", "photogimp-adj-hue-saturation", "photogimp-clipping-toggle",
                 "photogimp-stamp-visible", "photogimp-style-clear"]:
        im = test_image()
        lay = [l for l in im.get_layers() if l.is_group()][0].get_children()[0]
        if proc == "photogimp-clipping-toggle":
            # calque posé sur un autre (cas d'usage réel de l'écrêtage)
            lay = Gimp.Layer.new(im, "Texture", 400, 300, Gimp.ImageType.RGBA_IMAGE, 100,
                                 Gimp.LayerMode.NORMAL)
            im.insert_layer(lay, None, 0)
        im.set_selected_layers([lay])
        try:
            r = run(proc, **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im, "drawables": [lay]})
            ok_ = r.index(0) == Gimp.PDBStatusType.SUCCESS
            detail = ""
            if proc == "photogimp-clipping-toggle" and ok_:
                ok_ = lay.get_composite_mode() == Gimp.LayerCompositeMode.CLIP_TO_BACKDROP
                detail = "groupe « %s »" % lay.get_parent().get_name() if lay.get_parent() else ""
            report(ok_, "Calques : " + proc, detail)
        except Exception as e:
            report(False, "Calques : " + proc, repr(e)[:120])

    # 4. Réglages d'usine présents (thème, icônes, menus, raccourcis)
    data = Gimp.data_directory()
    sysconf = Gimp.sysconf_directory()
    for label, path in [("Thème PS-Dark", os.path.join(data, "themes", "PS-Dark", "gimp-dark.css")),
                        ("Icônes PS-Line", os.path.join(data, "icons", "PS-Line", "index.theme")),
                        ("Menus Photoshop", os.path.join(data, "menus", "layers-menu.ui")),
                        ("Raccourcis d'usine", os.path.join(sysconf, "shortcutsrc")),
                        ("Options d'outils d'usine", os.path.join(sysconf, "tool-options", "gimp-move-tool"))]:
        report(os.path.exists(path), label, path)
except Exception:
    report(False, "Exception", traceback.format_exc().replace("\n", " | ")[:400])

open(OUT, "w").write("\n".join(results) + "\n")
pdb.lookup_procedure("gimp-quit").run(pdb.lookup_procedure("gimp-quit").create_config())

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

    # 3b. Formes : un calque vectoriel à 2 formes → 2 calques vectoriels
    try:
        im = Gimp.Image.new(400, 300, Gimp.ImageBaseType.RGB)
        bg = Gimp.Layer.new(im, "Fond", 400, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im.insert_layer(bg, None, 0)
        path = Gimp.Path.new(im, "Formes")
        im.insert_path(path, None, 0)
        path.bezier_stroke_new_ellipse(100, 150, 50, 40, 0)
        path.bezier_stroke_new_ellipse(280, 150, 60, 50, 0)
        vl = Gimp.VectorLayer.new(im, path)
        im.insert_layer(vl, None, 0)
        vl.set_enable_fill(True)
        vl.set_fill_color(color(0.9, 0.2, 0.2))
        vl.refresh()
        r = run("photogimp-split-shapes", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                             "drawables": [vl]})
        vls = [l for l in im.get_layers() if isinstance(l, Gimp.VectorLayer)]
        ok_ = r.index(0) == Gimp.PDBStatusType.SUCCESS and len(vls) == 2
        same = ok_ and all(l.get_enable_fill() for l in vls)
        report(ok_ and same, "Formes : séparer les formes", "%d calque(s) vectoriel(s)" % len(vls))
    except Exception as e:
        report(False, "Formes : séparer les formes", repr(e)[:160])

    # 3c. Remplir d'après le contenu (Resynthesizer) : un carré rouge sur un
    #     dégradé doit disparaître
    try:
        im = Gimp.Image.new(300, 200, Gimp.ImageBaseType.RGB)
        bg = Gimp.Layer.new(im, "Fond", 300, 200, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im.insert_layer(bg, None, 0)
        Gimp.context_set_foreground(color(0.2, 0.5, 0.3))
        Gimp.context_set_background(color(0.6, 0.8, 0.5))
        bg.edit_gradient_fill(Gimp.GradientType.LINEAR, 0, False, 1, 0, True, 0, 0, 300, 200)
        im.select_rectangle(Gimp.ChannelOps.REPLACE, 130, 80, 40, 40)
        Gimp.context_set_foreground(color(1.0, 0.0, 0.0))
        bg.edit_fill(Gimp.FillType.FOREGROUND)
        r = run("chopgimp-content-aware-fill", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                                  "drawables": [bg]})
        px = bg.get_pixel(150, 100).get_rgba()
        reddish = px[0] > 0.8 and px[1] < 0.2
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and not reddish,
               "Remplir d'après le contenu", "pixel central %.2f %.2f %.2f" % (px[0], px[1], px[2]))
    except Exception as e:
        report(False, "Remplir d'après le contenu", repr(e)[:160])

    # 3d. Effets de forme et style de calque (plug-in chopgimp_fx)
    for proc in ["chopgimp-fx-zigzag", "chopgimp-fx-wave", "chopgimp-fx-width",
                 "chopgimp-fx-stroke-outside", "chopgimp-layer-style", "chopgimp-fx-gradient-overlay"]:
        try:
            im = Gimp.Image.new(300, 200, Gimp.ImageBaseType.RGB)
            bg = Gimp.Layer.new(im, "Fond", 300, 200, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
            im.insert_layer(bg, None, 0)
            path = Gimp.Path.new(im, "Forme")
            im.insert_path(path, None, 0)
            path.bezier_stroke_new_ellipse(150, 100, 60, 40, 0)
            vl = Gimp.VectorLayer.new(im, path)
            im.insert_layer(vl, None, 0)
            vl.set_enable_fill(True); vl.set_enable_stroke(True); vl.set_stroke_width(4)
            vl.refresh()
            r = run(proc, **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im, "drawables": [vl]})
            report(r.index(0) == Gimp.PDBStatusType.SUCCESS, "Effets : " + proc)
        except Exception as e:
            report(False, "Effets : " + proc, repr(e)[:160])

    # 3e. Effets dynamiques : modifier / supprimer l'effet (parasite chopgimp-fx)
    def shape_image():
        im = Gimp.Image.new(300, 200, Gimp.ImageBaseType.RGB)
        bg = Gimp.Layer.new(im, "Fond", 300, 200, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im.insert_layer(bg, None, 0)
        path = Gimp.Path.new(im, "Forme")
        im.insert_path(path, None, 0)
        path.bezier_stroke_new_ellipse(150, 100, 60, 40, 0)
        vl = Gimp.VectorLayer.new(im, path)
        im.insert_layer(vl, None, 0)
        vl.set_enable_fill(True); vl.set_enable_stroke(True); vl.set_stroke_width(4)
        vl.refresh()
        return im, vl

    def nonint(proc, im, d, **kw):
        return run(proc, **dict({"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im, "drawables": [d]}, **kw))

    def fx_of(item):
        par = item.get_parasite("chopgimp-fx")
        return par is not None

    for proc in ["chopgimp-fx-zigzag", "chopgimp-fx-stroke-outside", "chopgimp-fx-arrows",
                 "chopgimp-fx-brush-stroke", "chopgimp-fx-gradient-overlay"]:
        name = "Effet dynamique : " + proc.replace("chopgimp-fx-", "")
        try:
            im, vl = shape_image()
            if proc == "chopgimp-fx-arrows":       # les flèches s'appliquent aux traits ouverts
                p2 = Gimp.Path.new(im, "Trait")
                im.insert_path(p2, None, 0)
                p2.stroke_new_from_points(Gimp.PathStrokeType.BEZIER,
                                          [20, 20, 20, 20, 20, 20, 250, 150, 250, 150, 250, 150], False)
                im.remove_layer(vl)
                vl = Gimp.VectorLayer.new(im, p2)
                im.insert_layer(vl, None, 0)
                vl.set_enable_stroke(True); vl.set_stroke_width(4); vl.refresh()
            im.select_rectangle(Gimp.ChannelOps.REPLACE, 10, 10, 50, 40)
            n0 = len(im.get_layers())
            r1 = nonint(proc, im, vl)
            res = im.get_selected_layers()[0]
            r2 = nonint("chopgimp-fx-edit", im, res)
            res2 = im.get_selected_layers()[0]
            kept = fx_of(res2)
            r3 = nonint("chopgimp-fx-remove", im, res2)
            back = im.get_selected_layers()[0]
            sel = Gimp.Selection.bounds(im)
            okk = (r1.index(0) == r2.index(0) == r3.index(0) == Gimp.PDBStatusType.SUCCESS and kept
                   and not fx_of(back) and len(im.get_layers()) == n0
                   and isinstance(back, Gimp.VectorLayer)
                   and sel[1] and (sel[2], sel[3], sel[4], sel[5]) == (10, 10, 60, 50))
            report(okk, name, "couches %d→%d, sélection %r" % (n0, len(im.get_layers()), tuple(sel)[1:]))
        except Exception as e:
            report(False, name, repr(e)[:160])

    try:
        im, vl = shape_image()
        nonint("chopgimp-layer-style", im, vl)
        has_style = vl.get_parasite("chopgimp-style") is not None and \
            any(f.get_name().startswith("Style : ") for f in (vl.get_filters() or []))
        nonint("chopgimp-fx-remove", im, vl)
        gone = not any(f.get_name().startswith("Style : ") for f in (vl.get_filters() or []))
        report(has_style and gone, "Style de calque mémorisé puis supprimé")
    except Exception as e:
        report(False, "Style de calque mémorisé puis supprimé", repr(e)[:160])

    try:
        sc = open(os.path.join(Gimp.sysconf_directory(), "shortcutsrc")).read()
        report('"tools-spot-heal" "j"' in sc or '(action "tools-spot-heal" "j")' in sc,
               "Correcteur localisé sur J", "")
    except Exception as e:
        report(False, "Correcteur localisé sur J", repr(e)[:160])

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

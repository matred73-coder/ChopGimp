"""
ChopGimp — test de fonctionnement exécuté DANS le paquet Flatpak :
  flatpak run --command=gimp-console-3.2 <app-id> -i --batch-interpreter=python-fu-eval \
      -b 'exec(open("tools/smoke_test.py").read())'
Résultats : <SMOKE_OUT> (une ligne « OK|ÉCHEC  test  détail » par test).
"""
import os
import traceback
import time

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

    # 3f. Outils vectoriels (moteur d'Inkscape, procédures chopgimp-path-*)
    def vrun(name, **kw):
        p = pdb.lookup_procedure(name)
        if p is None:
            return None
        c = p.create_config()
        for k, v in kw.items():
            if k == "paths":
                c.set_core_object_array(k, v)
            else:
                c.set_property(k, v)
        return p.run(c)

    def vinfo(path):
        r = vrun("chopgimp-path-info", path=path)
        return r.index(1), r.index(2)

    try:
        import math
        im = Gimp.Image.new(400, 400, Gimp.ImageBaseType.RGB)
        a = Gimp.Path.new(im, "a"); im.insert_path(a, None, 0); a.bezier_stroke_new_ellipse(150, 200, 80, 80, 0)
        b = Gimp.Path.new(im, "b"); im.insert_path(b, None, 0); b.bezier_stroke_new_ellipse(250, 200, 80, 80, 0)
        sq = Gimp.Path.new(im, "sq"); im.insert_path(sq, None, 0)
        sq.stroke_new_from_points(Gimp.PathStrokeType.BEZIER,
                                  [100, 100] * 3 + [200, 100] * 3 + [200, 200] * 3 + [100, 200] * 3, True)
        A = vinfo(a)[1]
        areas = {}
        for op, nm in enumerate(["union", "soustraction", "intersection", "exclusion"]):
            r = vrun("chopgimp-path-boolean", paths=[a, b], operation=op)
            p = r.index(1); im.insert_path(p, None, 0)
            areas[nm] = vinfo(p)[1]
        inter = areas["intersection"]
        okk = (abs(areas["union"] - (2 * A - inter)) < 0.01 * A and
               abs(areas["soustraction"] - (A - inter)) < 0.01 * A and
               abs(areas["exclusion"] - (2 * A - 2 * inter)) < 0.01 * A and inter > 0)
        report(okk, "Vectoriel : Pathfinder (aires)", " ".join("%s=%.0f" % kv for kv in areas.items()))

        r = vrun("chopgimp-path-divide", paths=[a, b])
        report(r.index(1) == 3, "Vectoriel : Diviser", "%d morceaux" % r.index(1))

        res = {}
        for d in (10, -10):
            p = vrun("chopgimp-path-offset", path=sq, distance=d, join=0).index(1); im.insert_path(p, None, 0)
            res[d] = vinfo(p)[1]
        report(abs(res[10] - 120 * 120) < 150 and abs(res[-10] - 80 * 80) < 0.04 * 6400,
               "Vectoriel : décaler ±10 px", "aires %.0f / %.0f" % (res[10], res[-10]))

        p = vrun("chopgimp-path-outline", path=sq, width=10, join=0, cap=0).index(1); im.insert_path(p, None, 0)
        report(abs(vinfo(p)[1] - (110 * 110 - 90 * 90)) < 150, "Vectoriel : vectoriser le contour",
               "aire %.0f" % vinfo(p)[1])

        p = vrun("chopgimp-path-round-corners", path=sq, radius=20, **{"selected-only": False}).index(1)
        im.insert_path(p, None, 0)
        expect = 100 * 100 - (4 - math.pi) * 20 * 20
        report(abs(vinfo(p)[1] - expect) < 100, "Vectoriel : arrondir les coins", "aire %.0f" % vinfo(p)[1])

        p = vrun("chopgimp-path-simplify", path=a, tolerance=2.0).index(1); im.insert_path(p, None, 0)
        report(abs(vinfo(p)[1] - A) < 0.02 * A, "Vectoriel : simplifier", "%r" % (vinfo(p),))

        # nœuds : tout sélectionner puis rendre angulaires (lignes droites)
        n = Gimp.Path.new(im, "n"); im.insert_path(n, None, 0); n.bezier_stroke_new_ellipse(200, 200, 50, 50, 0)
        vrun("chopgimp-path-nodes", path=n, operation=18, value=0.0)
        vrun("chopgimp-path-nodes", path=n, operation=0, value=0.0)
        report(abs(vinfo(n)[1] - 2 * 50 * 50) < 20, "Vectoriel : nœuds angulaires", "aire %.0f" % vinfo(n)[1])

        # effet vivant : le rendu suit le chemin source
        vl = Gimp.VectorLayer.new(im, sq)
        im.insert_layer(vl, None, 0)
        vl.set_enable_fill(True); vl.refresh()
        w0 = vl.get_width()
        vl.attach_parasite(Gimp.Parasite.new("chopgimp-lpe", 3, list(b"[0]\ntype=offset\ndistance=20\n")))
        vl.refresh()
        w1 = vl.get_width()
        report(w1 >= w0 + 39, "Vectoriel : effet vivant (décalage)", "largeur %d → %d" % (w0, w1))
        for spec in ["taper\nwidth=20", "powerstroke\nwidths=0:2,0.5:30,1:2", "zigzag\nsize=8\nridges=20",
                     "wave\nsize=6", "envelope\ntl-x=30", "bend\nangle=90", "twist", "pucker", "round\nradius=15"]:
            r = vrun("chopgimp-path-effects", path=sq, spec="[0]\ntype=" + spec + "\n")
            if r.index(0) != Gimp.PDBStatusType.SUCCESS or not r.index(1):
                report(False, "Vectoriel : effet " + spec.split("\n")[0])
                break
        else:
            report(True, "Vectoriel : 9 effets de chemin calculés")
    except Exception as e:
        report(False, "Vectoriel", repr(e)[:200])

    # 3g. Texte : balises ChopGimp (Pango) et vectorisation
    try:
        im = Gimp.Image.new(800, 300, Gimp.ImageBaseType.RGB)
        bg = Gimp.Layer.new(im, "Fond", 800, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im.insert_layer(bg, None, 0)
        font = Gimp.Font.get_by_name("Sans-serif") or Gimp.context_get_font()

        def width_of(markup):
            t = Gimp.TextLayer.new(im, "x", font, 40.0, Gimp.Unit.pixel())
            im.insert_layer(t, None, 0)
            t.set_markup(markup)
            w = t.get_width()
            im.remove_layer(t)
            return w

        plain = width_of("<markup>Bonjour Monde</markup>")
        caps = width_of('<markup><span text_transform="uppercase">Bonjour Monde</span></markup>')
        sup = width_of('<markup>Bonjour <span baseline_shift="superscript">'
                       '<span font_scale="superscript">Monde</span></span></markup>')
        report(caps > plain and sup < plain, "Texte : capitales et exposant (balises Pango)",
               "largeurs %d / %d / %d" % (plain, caps, sup))

        t = Gimp.TextLayer.new(im, "Abc", font, 80.0, Gimp.Unit.pixel())
        im.insert_layer(t, None, 0)
        t.set_color(color(0.8, 0.1, 0.1))
        r = run("chopgimp-text-outline", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                            "drawables": [t]})
        sel = im.get_selected_layers()
        vl = sel[0] if sel else None
        okk = (r.index(0) == Gimp.PDBStatusType.SUCCESS and isinstance(vl, Gimp.VectorLayer) and
               vl.get_fill_color().get_rgba()[0] > 0.7 and len(vl.get_path().get_strokes()) >= 4)
        report(okk, "Texte : vectoriser (Ctrl+Maj+O)",
               "%d contours" % (len(vl.get_path().get_strokes()) if vl else 0))

        t = Gimp.TextLayer.new(im, "Abc", font, 80.0, Gimp.Unit.pixel())
        im.insert_layer(t, None, 0)
        r = run("chopgimp-text-outline-letters", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                                    "drawables": [t]})
        grp = im.get_selected_layers()[0]
        n = len(grp.get_children()) if isinstance(grp, Gimp.GroupLayer) else 0
        report(n == 3, "Texte : vectoriser lettre par lettre", "%d lettres" % n)
    except Exception as e:
        report(False, "Texte", repr(e)[:200])

    # 3h. Texte : déformation, texte sur tracé / dans une forme, transformations
    try:
        im = Gimp.Image.new(1000, 700, Gimp.ImageBaseType.RGB)
        bg = Gimp.Layer.new(im, "Fond", 1000, 700, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im.insert_layer(bg, None, 0)
        font = Gimp.Font.get_by_name("Sans-serif") or Gimp.context_get_font()

        def fx(layer, spec):
            return run("chopgimp-text-fx-set", layer=layer, spec=spec, **{"push-undo": True})

        t = Gimp.TextLayer.new(im, "Bonjour ChopGimp", font, 60.0, Gimp.Unit.pixel())
        im.insert_layer(t, None, 0)
        t.set_offsets(100, 100)
        h0, off0 = t.get_height(), t.get_offsets()[1:]
        fx(t, "warp=arc;bend=50")
        h1 = t.get_height()
        okk = (h1 > h0 * 1.3 and isinstance(t, Gimp.TextLayer) and
               run("chopgimp-text-fx-get", layer=t).index(1).startswith("warp=arc"))
        fx(t, "")
        report(okk and t.get_height() == h0 and t.get_offsets()[1:] == off0,
               "Texte : déformation « arc » (texte modifiable, retour exact)",
               "hauteur %d → %d" % (h0, h1))

        styles = ["arc-lower", "arc-upper", "arch", "bulge", "shell-lower", "shell-upper", "flag",
                  "wave", "fish", "rise", "fisheye", "inflate", "squeeze", "twist"]
        bad = []
        for st in styles:
            fx(t, "warp=%s;bend=60;hdist=10;vdist=-10" % st)
            if t.get_width() < 50 or t.get_height() < 20:
                bad.append(st)
        fx(t, "")
        report(not bad, "Texte : 15 styles de déformation rendus", " ".join(bad))

        path = Gimp.Path.new(im, "courbe")
        im.insert_path(path, None, 0)
        sid = path.bezier_stroke_new_moveto(100, 600)
        path.bezier_stroke_cubicto(sid, 300, 300, 700, 300, 900, 600)
        fx(t, "path=%d;start=0;flip=0;shift=0" % path.get_tattoo())
        x, y = t.get_offsets()[1:]
        okk = t.get_height() > 150 and 50 < x < 200 and 250 < y < 450
        report(okk, "Texte : texte sur tracé", "%dx%d @ %d,%d" % (t.get_width(), t.get_height(), x, y))
        fx(t, "")

        ell = Gimp.Path.new(im, "forme")
        im.insert_path(ell, None, 0)
        ell.bezier_stroke_new_ellipse(500, 350, 250, 200, 0)
        t2 = Gimp.TextLayer.new(im, "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do "
                                    "eiusmod tempor incididunt ut labore et dolore magna aliqua.",
                                font, 24.0, Gimp.Unit.pixel())
        im.insert_layer(t2, None, 0)
        fx(t2, "shape=%d;inset=4" % ell.get_tattoo())
        x, y = t2.get_offsets()[1:]
        okk = t2.get_width() <= 500 and 250 <= x and x + t2.get_width() <= 760 and t2.get_height() > 60
        report(okk, "Texte : texte dans une forme",
               "%dx%d @ %d,%d" % (t2.get_width(), t2.get_height(), x, y))

        t3 = Gimp.TextLayer.new(im, "Rotation", font, 50.0, Gimp.Unit.pixel())
        im.insert_layer(t3, None, 0)
        t3.set_offsets(300, 300)
        w0, h0 = t3.get_width(), t3.get_height()
        t3.transform_rotate(0.6, True, 0, 0)
        okk = isinstance(t3, Gimp.TextLayer) and t3.get_text() == "Rotation" and t3.get_height() > h0 * 1.5
        t3.transform_scale(300, 300, 700, 500)
        report(okk and abs(t3.get_width() - 400) <= 8,
               "Texte : rotation / mise à l'échelle sans pixelliser",
               "%dx%d → %dx%d" % (w0, h0, t3.get_width(), t3.get_height()))

        fx(t, "warp=flag;bend=40")
        xcf = os.path.join(TMP, "texte-fx.xcf")
        os.makedirs(TMP, exist_ok=True)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, im, Gio.File.new_for_path(xcf), None)
        im2 = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(xcf))
        specs = [run("chopgimp-text-fx-get", layer=l).index(1)
                 for l in im2.get_layers() if isinstance(l, Gimp.TextLayer)]
        report(any(sp.startswith("warp=flag") for sp in specs) and
               any(sp.startswith("shape=") for sp in specs),
               "Texte : effets conservés dans le XCF", " | ".join(specs))
    except Exception as e:
        report(False, "Texte (effets)", repr(e)[:200])

    # 3 bis. Import PSD avancé (plug-in chopgimp_psd) sur le PSD de test
    try:
        import runpy
        repo = os.environ.get("SMOKE_REPO", os.path.expanduser("~/DOCKER/photogimp-pro"))
        psd_path = os.path.join(TMP, "test.psd")
        runpy.run_path(os.path.join(repo, "tools", "fixtures", "make_psd.py"))["write"](psd_path)
        im = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(psd_path))
        def walk_all(ls):
            for l in ls:
                yield l
                if isinstance(l, Gimp.GroupLayer) and not l.get_name().startswith("⟲"):
                    yield from walk_all(l.get_children())
        top = {l.get_name(): l for l in walk_all(im.get_layers())}
        texts = [l for l in top.values() if isinstance(l, Gimp.TextLayer)]
        report(len(texts) == 3, "PSD : 3 textes modifiables", ", ".join(sorted(l.get_name() for l in texts)))
        titre = top.get("Titre")
        report(isinstance(titre, Gimp.TextLayer) and "Bonjour" in (titre.get_markup() or "") and
               "DejaVu Sans Bold" in titre.get_font().get_name() and abs(titre.get_font_size()[0] - 48) < 0.5,
               "PSD : texte à 2 styles (police, taille, balises)",
               titre.get_font().get_name() if titre else "absent")
        para = top.get("Paragraphe")
        spec = run("chopgimp-text-fx-get", layer=para).index(1) if isinstance(para, Gimp.TextLayer) else ""
        report((spec or "").startswith("warp=arc"), "PSD : déformation Arc reprise", spec or "")
        rect = top.get("Rectangle")
        report(isinstance(rect, Gimp.VectorLayer) and rect.get_enable_stroke() and
               abs(rect.get_stroke_width() - 4) < 0.1, "PSD : forme → calque vectoriel avec contour",
               type(rect).__name__)
        photo = top.get("Photo masquée")
        report(photo is not None and photo.get_mask() is not None and
               any(p.get_name().startswith("Masque vectoriel") for p in im.get_paths()),
               "PSD : masque vectoriel → masque + chemin")
        fx = [f.get_name() for f in (top["Effets"].get_filters() or []) if f.get_name().startswith("Style : ")] if "Effets" in top else []
        report(len(fx) == 3, "PSD : effets lfx2 → styles ChopGimp", ", ".join(fx))
        orig = [l for l in im.get_layers() if l.get_name().startswith("⟲")]
        report(len(orig) == 1 and not orig[0].get_visible() and len(orig[0].get_children()) == 10,
               "PSD : originaux gardés dans un groupe masqué",
               str(len(orig[0].get_children())) if orig else "absent")
        ops = {n: [f.get_operation_name() for f in (l.get_filters() or [])] for n, l in top.items()}
        report("gimp:levels" in ops.get("◐ Niveaux", []) and "gimp:curves" in ops.get("◐ Courbes", []) and
               "gimp:hue-saturation" in ops.get("◐ Teinte", []),
               "PSD : réglages Niveaux, Courbes, Teinte → filtres modifiables")
        report("gimp:brightness-contrast" in ops.get("Effets", []),
               "PSD : réglage écrêté → filtre sur le calque de base")
        fill = top.get("Remplissage")
        report(isinstance(fill, Gimp.VectorLayer) and abs(fill.get_opacity() - 30.2) < 1,
               "PSD : calque de remplissage → calque vectoriel")
        logo = top.get("Logo")
        report(isinstance(logo, Gimp.LinkLayer) and logo.get_offsets()[1:] == (20, 520),
               "PSD : objet dynamique → calque lié placé",
               str(logo.get_offsets()[1:]) if logo else "absent")
        # aller-retour : export PSD (formes + textes modifiables) puis réimport
        out_psd = os.path.join(TMP, "aller-retour.psd")
        ep = pdb.lookup_procedure("file-psd-export")
        ecfg = ep.create_config()
        ecfg.set_property("run-mode", Gimp.RunMode.NONINTERACTIVE)
        ecfg.set_property("image", im)
        ecfg.set_property("file", Gio.File.new_for_path(out_psd))
        ecfg.set_property("editable-shapes", True)
        ecfg.set_property("editable-text", True)
        ep.run(ecfg)
        im2 = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(out_psd))
        all2 = {l.get_name(): l for l in walk_all(im2.get_layers())}
        report(isinstance(all2.get("Rectangle"), Gimp.VectorLayer) and
               all2["Rectangle"].get_enable_stroke(),
               "PSD : aller-retour, forme toujours vectorielle", type(all2.get("Rectangle")).__name__)
        report(isinstance(all2.get("Police absente"), Gimp.TextLayer) and
               all2["Police absente"].get_text() == "Police absente",
               "PSD : aller-retour, texte toujours modifiable", type(all2.get("Police absente")).__name__)
        par = im.get_parasite("chopgimp-psd-report")
        txt = bytes(b & 255 for b in par.get_data()).decode() if par else ""
        report("FooBarSans-Regular" in txt, "PSD : police absente signalée dans le rapport")
    except Exception as e:
        report(False, "Import PSD", repr(e)[:200])

    # 3 ter. Import vectoriel PDF / SVG / EPS (plug-in chopgimp_pdf)
    try:
        import runpy
        repo = os.environ.get("SMOKE_REPO", os.path.expanduser("~/DOCKER/photogimp-pro"))
        vdir = os.path.join(TMP, "vectoriel")
        runpy.run_path(os.path.join(repo, "tools", "fixtures", "make_vector.py"))["write"](vdir)
        runpy.run_path(os.path.join(repo, "tools", "fixtures", "make_pdf.py"))["write"](
            os.path.join(vdir, "test.pdf"))

        def flat(ls):
            for l in ls:
                yield l
                if isinstance(l, Gimp.GroupLayer):
                    yield from flat(l.get_children())

        def load_v(name):
            im = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(os.path.join(vdir, name)))
            return im, list(flat(im.get_layers()))

        def vxml(layer):
            # 3.27.2 (lot V4) : objets d'un calque vectoriel (XML du modèle)
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        def n_objects(layers):
            return sum(vxml(l).count("<path ") for l in layers if isinstance(l, Gimp.VectorLayer))

        im, ls = load_v("test.pdf")
        by = {l.get_name(): l for l in ls}
        vec = [l for l in ls if isinstance(l, Gimp.VectorLayer)]
        report(n_objects(vec) >= 3 and "Bleu" in by and by["Bleu"].get_visible() and
               "Vert" in by and not by["Vert"].get_visible(),
               "PDF : calques OCG, un calque vectoriel à objets par calque",
               "%d calques, %d objets" % (len(vec), n_objects(vec)))
        report(isinstance(by.get("Bonjour PDF"), Gimp.TextLayer), "PDF : texte modifiable")
        report(any(n.startswith("Image ") for n in by) and
               any('type="linear"' in vxml(l) for l in vec),
               "PDF : image placée et dégradé vectoriel")
        im, ls = load_v("test.svg")
        by = {l.get_name(): l for l in ls}
        report("Fond" in by and "Dessin" in by and "Caché" in by and not by["Caché"].get_visible() and
               isinstance(by.get("Salut SVG"), Gimp.TextLayer),
               "SVG : calques Inkscape et texte modifiable")
        im, ls = load_v("test.eps")
        by = {l.get_name(): l for l in ls}
        report(isinstance(by.get("Bonjour EPS"), Gimp.TextLayer) and n_objects(ls) >= 2,
               "EPS : formes vectorielles et texte (Ghostscript)")
        # aller-retour SVG : export (calques Inkscape, noms, masqués) puis réimport
        im, ls = load_v("test.svg")
        report(not any(isinstance(l, Gimp.VectorLayer) and "aa0000" in l.get_name() for l in ls),
               "SVG : texte sans doublon en tracés")
        out_svg = os.path.join(vdir, "aller-retour.svg")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, im, Gio.File.new_for_path(out_svg), None)
        txt = open(out_svg, encoding="utf-8").read()
        import re as _re
        report(not _re.search(r'="-?\d+,\d', txt) and 'inkscape:groupmode="layer"' in txt and
               'inkscape:label="Caché"' in txt and "<text" in txt,
               "SVG : export valide (nombres, calques Inkscape, calque masqué, texte)")
        im2 = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(out_svg))
        by2 = {l.get_name(): l for l in flat(im2.get_layers())}
        report("Fond" in by2 and "Caché" in by2 and not by2["Caché"].get_visible() and
               any(isinstance(l, Gimp.TextLayer) for l in by2.values()),
               "SVG : aller-retour (groupes, visibilité, texte)")
        # 3.27.2 (lot V4) : aller-retour des objets (groupes, découpes,
        # dégradés, transformations) : même arbre d'objets après réimport
        import sys as _sys
        _sys.path.insert(0, os.path.join(repo, "tools", "dev"))
        tsv = runpy.run_path(os.path.join(repo, "tools", "dev", "test_svg_vobjects.py"))
        with open(os.path.join(vdir, "objets.svg"), "w", encoding="utf-8") as f:
            f.write(tsv["TEST_SVG"])
        V = tsv["V"]

        def obj_sig(layers):
            out = []
            for l in layers:
                if isinstance(l, Gimp.VectorLayer):
                    out.append((l.get_name(), tuple(tsv["node_sig"](n) for n in V.from_xml(vxml(l)))))
            return out

        im, ls = load_v("objets.svg")
        sig1 = obj_sig(ls)
        dessin = dict(sig1).get("Dessin") or ()
        report(len(sig1) >= 2 and len(dessin) == 3 and dessin[0][0] == "G" and dessin[0][2],
               "SVG : objets, groupes et masque d'écrêtage dans un calque", "%d calques" % len(sig1))
        out2 = os.path.join(vdir, "objets-export.svg")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, im, Gio.File.new_for_path(out2), None)
        txt2 = open(out2, encoding="utf-8").read()
        report("<linearGradient" in txt2 and "<radialGradient" in txt2 and "clip-path=" in txt2 and
               'inkscape:label="Soleil"' in txt2,
               "SVG : export des objets (dégradés, découpes, noms)")
        im2, ls2 = load_v("objets-export.svg")
        sig2 = obj_sig(ls2)
        d = tsv["diff"](sig1, sig2)
        report(not d, "SVG : aller-retour des objets, même structure", "; ".join(d[:3]))
        res = run("file-chopgimp-svg-load-thumb", file=Gio.File.new_for_path(os.path.join(vdir, "test.svg")),
                  **{"thumb-size": 128})
        report(res is not None and res.index(0) == Gimp.PDBStatusType.SUCCESS and res.index(2) == 400,
               "SVG : vignette (fenêtre d'ouverture)")
    except Exception as e:
        report(False, "Import vectoriel", repr(e)[:200])

    # 3 quater. Objet dynamique : calques → XCF lié
    try:
        im = test_image()
        grp = [l for l in im.get_layers() if isinstance(l, Gimp.GroupLayer)][0]
        red = grp.get_children()[0]
        red.set_offsets(30, 40)
        r = run("chopgimp-smart-convert", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                             "drawables": [red]})
        links = [l for l in grp.get_children() if isinstance(l, Gimp.LinkLayer)]
        ok_ = (r.index(0) == Gimp.PDBStatusType.SUCCESS and len(links) == 1 and
               links[0].get_offsets()[1:] == (30, 40) and links[0].get_file().query_exists(None))
        report(ok_, "Objet dynamique : conversion en calque lié (XCF)",
               links[0].get_file().get_path() if links else str(r.index(0)))
    except Exception as e:
        report(False, "Objet dynamique", repr(e)[:200])

    # 3 quinquies. Base I : recadrage en perspective, redresser, Liquid Rescale
    try:
        def path_img(points):
            im = Gimp.Image.new(400, 300, Gimp.ImageBaseType.RGB)
            l = Gimp.Layer.new(im, "Fond", 400, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
            im.insert_layer(l, None, 0)
            l.fill(Gimp.FillType.WHITE)
            p = Gimp.Path.new(im, "Repères")
            flat = []
            for x, y in points:
                flat += [x, y, x, y, x, y]
            p.stroke_new_from_points(Gimp.PathStrokeType.BEZIER, flat, False)
            im.insert_path(p, None, 0)
            im.set_selected_paths([p])
            return im, l

        im, l = path_img([(50, 40), (350, 60), (330, 260), (70, 240)])
        r = run("chopgimp-perspective-crop", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                                "drawables": [l]})
        # côtés moyens : (300,7 + 260,8) / 2 ≈ 281 et (200,9 + 200,6) / 2 ≈ 201
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and abs(im.get_width() - 281) <= 2 and
               abs(im.get_height() - 201) <= 2, "Recadrage en perspective (4 points)",
               "%dx%d" % (im.get_width(), im.get_height()))
        im, l = path_img([(20, 100), (380, 130)])
        r = run("chopgimp-straighten", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                          "drawables": [l]})
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and 300 < im.get_width() < 400 and
               im.get_height() < 300, "Redresser (2 points)", "%dx%d" % (im.get_width(), im.get_height()))
        im, l = path_img([(0, 0), (1, 1)])
        r = run("chopgimp-liquid-rescale", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                              "drawables": [l], "width-factor": 0.5, "height-factor": 1.0,
                                              "protect-selection": False})
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and im.get_width() == 200 and l.get_width() == 200,
               "Mise à l'échelle selon le contenu (liblqr)", "%dx%d" % (im.get_width(), im.get_height()))
    except Exception as e:
        report(False, "Base I", repr(e)[:200])

    # 3 sexies. Base II : calques de remplissage, instantané
    try:
        im = test_image()

        def all_layers(ls):
            for l in ls:
                yield l
                if isinstance(l, Gimp.GroupLayer):
                    yield from all_layers(l.get_children())
        n0 = len(list(all_layers(im.get_layers())))
        r1 = run("chopgimp-fill-color", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                           "drawables": []})
        r2 = run("chopgimp-fill-pattern", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                             "drawables": []})
        kinds = [type(l).__name__ for l in all_layers(im.get_layers())]
        report(r1.index(0) == Gimp.PDBStatusType.SUCCESS and r2.index(0) == Gimp.PDBStatusType.SUCCESS and
               len(kinds) == n0 + 2 and "VectorLayer" in kinds,
               "Calques de remplissage (couleur unie, motif)", ", ".join(kinds))
        before = len(Gimp.get_images())
        r = run("chopgimp-snapshot-new", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                            "drawables": []})
        snaps = [i for i in Gimp.get_images() if i.get_parasite("chopgimp-snapshot-of")]
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and len(Gimp.get_images()) == before + 1 and
               snaps and len(snaps[0].get_layers()) == len(im.get_layers()),
               "Instantané (copie de l'image)")
    except Exception as e:
        report(False, "Base II", repr(e)[:200])

    # 3 septies. Base III : génération de ressources (manuelle et à l'enregistrement)
    try:
        im = test_image()
        red = [l for l in im.get_layers() if isinstance(l, Gimp.GroupLayer)][0].get_children()[0]
        red.set_name("logo.png, vignette.jpg 50%")
        xcf = os.path.join(TMP, "ressources.xcf")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, im, Gio.File.new_for_path(xcf), None)
        res_dir = os.path.join(TMP, "ressources-ressources")
        r = run("chopgimp-generate-assets", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                               "drawables": []})
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and
               os.path.exists(os.path.join(res_dir, "logo.png")) and
               os.path.exists(os.path.join(res_dir, "vignette.jpg")),
               "Génération de ressources (calques nommés comme des fichiers)")
        # (la génération à chaque enregistrement passe par l'enregistrement de
        # l'interface, Ctrl+S : vérifiée au banc graphique, pas ici)
    except Exception as e:
        report(False, "Base III", repr(e)[:200])

    # 3 octies. IA locale (modèles u2netp et super-résolution copiés par le lanceur)
    try:
        im = Gimp.Image.new(160, 120, Gimp.ImageBaseType.RGB)
        bg = Gimp.Layer.new(im, "Photo", 160, 120, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im.insert_layer(bg, None, 0)
        Gimp.context_set_foreground(color(0.2, 0.4, 0.9))
        bg.edit_fill(Gimp.FillType.FOREGROUND)
        im.select_ellipse(Gimp.ChannelOps.REPLACE, 50, 25, 60, 70)
        Gimp.context_set_foreground(color(0.95, 0.75, 0.6))
        bg.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(im)
        r = run("chopgimp-ia-remove-background", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                                    "drawables": [bg]})
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and bg.get_mask() is not None,
               "IA : supprimer l'arrière-plan (masque)", str(r.index(1)) if r.length() > 1 else "")
        r = run("chopgimp-ia-select-subject", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                                 "drawables": [bg]})
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and not Gimp.Selection.is_empty(im),
               "IA : sélection du sujet")
        before = {i.get_id() for i in Gimp.get_images()}
        r = run("chopgimp-ia-upscale", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                          "drawables": [bg], "factor": 2})
        new = [i for i in Gimp.get_images() if i.get_id() not in before]
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and new and
               (new[0].get_width(), new[0].get_height()) == (320, 240),
               "IA : agrandissement ×2 (super-résolution)",
               "%dx%d" % (new[0].get_width(), new[0].get_height()) if new else str(r.index(1)))
    except Exception as e:
        report(False, "IA locale", repr(e)[:200])

    # 3 nonies. Atelier / BD (plug-in chopgimp_atelier, valeurs par défaut)
    try:
        im = Gimp.Image.new(600, 400, Gimp.ImageBaseType.RGB)
        bg = Gimp.Layer.new(im, "Fond", 600, 400, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im.insert_layer(bg, None, 0)
        bg.fill(Gimp.FillType.WHITE)
        ink = Gimp.Layer.new(im, "Encrage", 600, 400, Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im.insert_layer(ink, None, 0)
        ink.fill(Gimp.FillType.TRANSPARENT)
        Gimp.context_set_foreground(color(0, 0, 0))
        for x, y, w, h in ((40, 40, 200, 150), (300, 60, 220, 260)):
            im.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, w, h)
            im.select_rectangle(Gimp.ChannelOps.SUBTRACT, x + 6, y + 6, w - 12, h - 12)
            ink.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(im)

        def at(proc, drawables=None):
            return run(proc, **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "image": im,
                                "drawables": drawables if drawables is not None else [ink]})

        def names():
            out = []
            def w_(ls):
                for l in ls:
                    out.append(l)
                    if isinstance(l, Gimp.GroupLayer):
                        w_(l.get_children())
            w_(im.get_layers())
            return out

        r = at("chopgimp-flats")
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and any(l.get_name() == "Aplats" for l in names()),
               "Atelier : aplats sous l'encrage", str(r.index(1)) if r.length() > 1 else "")
        at("chopgimp-sketch-layer")
        sk = [l for l in names() if l.get_parasite("chopgimp-sketch")]
        report(len(sk) == 1 and len(sk[0].get_filters() or []) == 1, "Atelier : calque de croquis bleu")
        at("chopgimp-comic-panels")
        cases = [l for l in names() if l.get_name().startswith("Case ")]
        report(len(cases) == 6 and all(isinstance(l, Gimp.VectorLayer) for l in cases),
               "Atelier : cases de BD (3 × 2)", str(len(cases)))
        r = at("chopgimp-comic-balloon")
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and any(l.get_name() == "Bulle" for l in names()) and
               any(isinstance(l, Gimp.TextLayer) for l in names()), "Atelier : bulle + texte")
        at("chopgimp-speed-lines")
        at("chopgimp-focus-lines")
        at("chopgimp-perspective-guides")
        nm = [l.get_name() for l in names()]
        report("Lignes de vitesse" in nm and "Lignes concentriques" in nm and
               any(n.startswith("⟂ Perspective") for n in nm),
               "Atelier : lignes de vitesse, concentriques, perspective")
        at("chopgimp-screentone", [bg])
        report(any(f.get_operation_name() == "gegl:newsprint" for f in (bg.get_filters() or [])),
               "Atelier : trame non destructive")
        case1 = [l for l in names() if l.get_name() == "Case 1"][0]
        _, cx, cy = case1.get_offsets()
        im.select_rectangle(Gimp.ChannelOps.REPLACE, cx, cy, 30, 30)
        r = at("chopgimp-vector-eraser", [case1])
        report(r.index(0) == Gimp.PDBStatusType.SUCCESS and
               len([l for l in names() if l.get_name() == "Case 1"]) == 1,
               "Atelier : gomme vectorielle",
               "%s n=%d %s" % (r.index(0), len([l for l in names() if l.get_name() == "Case 1"]),
                               str(r.index(1)) if r.length() > 1 else ""))
    except Exception as e:
        report(False, "Atelier", repr(e)[:200])

    # 3 decies. Filtre Contour (chopgimp:stroke), non destructif
    try:
        def contour_img(props):
            im = Gimp.Image.new(200, 200, Gimp.ImageBaseType.RGB)
            l = Gimp.Layer.new(im, "Objet", 200, 200, Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
            im.insert_layer(l, None, 0)
            l.fill(Gimp.FillType.TRANSPARENT)
            Gimp.context_set_foreground(color(1.0, 0.0, 0.0))
            im.select_rectangle(Gimp.ChannelOps.REPLACE, 50, 50, 100, 100)
            l.edit_fill(Gimp.FillType.FOREGROUND)
            Gimp.Selection.none(im)
            f = Gimp.DrawableFilter.new(l, "chopgimp:stroke", "Contour")
            cfg = f.get_config()
            for k, v in props.items():
                cfg.set_property(k, v)
            f.update()
            l.append_filter(f)
            l.merge_filters()
            return im, l

        def px(l, x, y):
            ok_, x0, y0 = l.get_offsets()
            return tuple(round(c * 255) for c in l.get_pixel(x - x0, y - y0).get_rgba_with_space(None))

        im, l = contour_img({"width": 6.0})
        out = px(l, 47, 100); inn = px(l, 53, 100); far = px(l, 30, 100)
        report(out[3] > 200 and out[0] < 60 and inn[0] > 200 and far[3] == 0,
               "Contour : extérieur noir autour de l'objet", "%s %s %s" % (out, inn, far))
        im.delete()
        im, l = contour_img({"width": 6.0, "position": 2})
        out = px(l, 47, 100); inn = px(l, 53, 100); mid = px(l, 100, 100)
        report(out[3] == 0 and inn[0] < 60 and inn[3] > 200 and mid[0] > 200,
               "Contour : intérieur", "%s %s %s" % (out, inn, mid))
        im.delete()
        im, l = contour_img({"width": 4.0, "dash-preset": 2})
        alphas = [px(l, 47, y)[3] for y in range(55, 145)]
        report(min(alphas) < 40 and max(alphas) > 200, "Contour : pointillés", str(alphas[:12]))
        im.delete()
    except Exception as e:
        report(False, "Contour", repr(e)[:200])

    # 3.27.3 (lot V5, V6 point 4) : Vectoriser, vectorisation dynamique
    try:
        def trace_xml(layer):
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        def trace(drawable, options, sel=False, live=True):
            r = run("chopgimp-image-trace", drawable=drawable, options=options,
                    **{"selection-only": sel, "live": live})
            ok = r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS
            return r.index(1) if ok else None

        def trace_cmd(layer, cmd):
            r = run("chopgimp-image-trace-command", layer=layer, command=cmd)
            return (r.index(1), r.index(2)) if r is not None else (False, "")

        # logo noir et blanc : un disque et un carré noirs sur blanc
        im = Gimp.Image.new(300, 200, Gimp.ImageBaseType.RGB)
        logo = Gimp.Layer.new(im, "Logo", 300, 200, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im.insert_layer(logo, None, 0)
        Gimp.context_set_background(color(1, 1, 1))
        logo.fill(Gimp.FillType.BACKGROUND)
        Gimp.context_set_foreground(color(0, 0, 0))
        im.select_ellipse(Gimp.ChannelOps.REPLACE, 20, 30, 120, 120)
        logo.edit_fill(Gimp.FillType.FOREGROUND)
        im.select_rectangle(Gimp.ChannelOps.REPLACE, 180, 50, 90, 90)
        logo.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(im)
        vl = trace(logo, "bw-logo")
        x = trace_xml(vl) if vl else ""
        report(vl is not None and isinstance(vl, Gimp.VectorLayer) and x.count("<path ") >= 2 and
               vl.get_parasite("chopgimp-trace") is not None,
               "Vectoriser : logo noir et blanc → calque vectoriel à objets, dynamique",
               "%s, %d objets" % (vl.get_name() if vl else "-", x.count("<path ")))
        # couleur : trois bandes de couleur → au moins 3 objets, groupés par couleur
        im2 = Gimp.Image.new(240, 120, Gimp.ImageBaseType.RGB)
        col = Gimp.Layer.new(im2, "Bandes", 240, 120, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im2.insert_layer(col, None, 0)
        for i, c in enumerate([(0.9, 0.1, 0.1), (0.1, 0.7, 0.2), (0.1, 0.2, 0.9)]):
            im2.select_rectangle(Gimp.ChannelOps.REPLACE, i * 80, 0, 80, 120)
            Gimp.context_set_foreground(color(*c))
            col.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(im2)
        cl = trace(col, "6-colors;ignore-white=0")
        cx = trace_xml(cl) if cl else ""
        report(cl is not None and cx.count("<path ") >= 3 and cx.count("<group ") >= 3,
               "Vectoriser : image en couleurs → objets groupés par couleur",
               "%d objets, %d groupes" % (cx.count("<path "), cx.count("<group ")))
        # sélection seulement : le carré seul
        im.select_rectangle(Gimp.ChannelOps.REPLACE, 170, 40, 110, 110)
        sl = trace(logo, "bw-logo", sel=True, live=False)
        sx = trace_xml(sl) if sl else ""
        Gimp.Selection.none(im)
        report(sl is not None and sx.count("<path ") == 1 and sl.get_parasite("chopgimp-trace") is None,
               "Vectoriser : sélection seulement, sans vectorisation dynamique",
               "%d objets" % sx.count("<path "))
        if vl:
            done, opts = trace_cmd(vl, "options")
            report(done and "threshold" in opts, "Vectorisation dynamique : options relues", opts[:120])
            done, ed = trace_cmd(vl, "edited")
            report(done and ed == "0", "Vectorisation dynamique : objets non modifiés", ed)
            # revectoriser avec d'autres réglages : même calque, parasite à jour
            done, _ = trace_cmd(vl, "retrace:noise=2")
            done2, opts2 = trace_cmd(vl, "options")
            report(done and "noise=2" in opts2.replace(" ", ""), "Vectorisation dynamique : revectoriser",
                   opts2[:120])
            # XCF : le parasite survit, les objets aussi
            xcf = os.path.join(TMP, "vectoriser.xcf")
            Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, im, Gio.File.new_for_path(xcf), None)
            imx = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(xcf))
            vx = [l for l in imx.get_layers() if isinstance(l, Gimp.VectorLayer) and
                  l.get_parasite("chopgimp-trace") is not None]
            okx = len(vx) == 1 and trace_xml(vx[0]).count("<path ") >= 2
            report(okx and trace_cmd(vx[0], "edited") == (True, "0"),
                   "Vectorisation dynamique : aller-retour XCF",
                   "%d calques dynamiques" % len(vx))
            # dupliquer garde la vectorisation dynamique
            dup = vl.copy()
            im.insert_layer(dup, None, 0)
            report(dup.get_parasite("chopgimp-trace") is not None,
                   "Vectorisation dynamique : gardée par la copie du calque")
            # décomposer : le parasite part, les objets restent
            n = trace_xml(vl).count("<path ")
            done, _ = trace_cmd(vl, "expand")
            report(done and vl.get_parasite("chopgimp-trace") is None and
                   trace_xml(vl).count("<path ") == n,
                   "Vectorisation dynamique : Décomposer", "%d objets" % n)
            imx.delete()
        im.delete()
        im2.delete()
    except Exception:
        report(False, "Vectoriser", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.27.5 : jointures, pixel art agrandi, allègement, vectorisation dynamique qui suit le calque
    try:
        import re, math

        def coords(layer):
            x = trace_xml(layer)
            nums = []
            for d in re.findall(r' d="([^"]*)"', x):
                nums += [float(v) for v in re.findall(r'-?[0-9.]+(?:e-?[0-9]+)?', d)]
            xs, ys = nums[0::2], nums[1::2]
            return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)

        def anchors(layer):
            return sum(d.count("C") + d.count("M") for d in re.findall(r' d="([^"]*)"', trace_xml(layer)))

        def near(a, b, tol=1.5):
            return all(abs(u - v) <= tol for u, v in zip(a, b))

        def pxa(l, x, y):
            ok_, x0, y0 = l.get_offsets()
            return round(l.get_pixel(x - x0, y - y0).get_rgba_with_space(None)[3] * 255)

        # jointures : un disque rouge sur fond bleu, en mode adjacent (pas de liseré transparent)
        Gimp.context_set_antialias(True)
        ims = Gimp.Image.new(200, 200, Gimp.ImageBaseType.RGB)
        ls_ = Gimp.Layer.new(ims, "Disque", 200, 200, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        ims.insert_layer(ls_, None, 0)
        Gimp.context_set_background(color(0.1, 0.2, 0.9)); ls_.fill(Gimp.FillType.BACKGROUND)
        ims.select_ellipse(Gimp.ChannelOps.REPLACE, 40, 40, 120, 120)
        Gimp.context_set_foreground(color(0.9, 0.1, 0.1)); ls_.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(ims)
        mins = {}
        for seams in (1, 0):
            v = trace(ls_, "6-colors;ignore-white=0;method=abutting;seams=%d" % seams, live=False)
            if v:
                mins[seams] = min(pxa(v, round(100 + 60 * math.cos(a / 57.3)), round(100 + 60 * math.sin(a / 57.3)))
                                  for a in range(0, 360, 3))
                ims.remove_layer(v)
        report(mins.get(1, 0) >= 250, "Vectoriser : pas de liseré entre formes adjacentes",
               "alpha min. sur le bord %s (sans « jointures » : %s)" % (mins.get(1), mins.get(0)))
        ims.delete()

        # pixel art agrandi 8× (1280 × 960 : plus d'1 Mpx) : tracé à sa vraie taille
        Gimp.context_set_antialias(False)
        Gimp.context_set_interpolation(Gimp.InterpolationType.NONE)
        imp = Gimp.Image.new(160, 120, Gimp.ImageBaseType.RGB)
        lp = Gimp.Layer.new(imp, "Pixel", 160, 120, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        imp.insert_layer(lp, None, 0)
        Gimp.context_set_background(color(1, 1, 1)); lp.fill(Gimp.FillType.BACKGROUND)
        for i, (c, r) in enumerate([((0.9, 0.2, 0.1), (10, 10, 40, 30)), ((0.1, 0.6, 0.2), (60, 20, 50, 50)),
                                    ((0.2, 0.2, 0.8), (30, 70, 90, 30))]):
            imp.select_ellipse(Gimp.ChannelOps.REPLACE, *r)
            Gimp.context_set_foreground(color(*c)); lp.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(imp)
        imp.scale(1280, 960)
        t0 = time.time()
        vp = trace(lp, "pixel-art", live=False)
        dt = time.time() - t0
        b = coords(vp) if vp else (0, 0, 0, 0)
        report(vp is not None and b[2] <= 1280.01 and b[3] <= 960.01 and b[2] > 1000,
               "Vectoriser : pixel art agrandi 8× tracé à sa taille d'origine",
               "%.1f s, %d objets, cadre %s" % (dt, trace_xml(vp).count("<path ") if vp else 0,
                                                 tuple(round(v) for v in b)))
        # une grande image qui n'est pas du pixel art : refus clair, qui propose potrace
        lp2 = Gimp.Layer.new(imp, "Dégradé", 1280, 960, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        imp.insert_layer(lp2, None, 0)
        Gimp.context_set_foreground(color(0, 0, 0)); Gimp.context_set_background(color(1, 1, 1))
        lp2.edit_gradient_fill(Gimp.GradientType.LINEAR, 0, False, 1, 0.0, True, 0, 0, 1280, 960)
        r = run("chopgimp-image-trace", drawable=lp2, options="pixel-art", **{"selection-only": False, "live": False})
        msg = r.index(1) if r is not None and r.index(0) != Gimp.PDBStatusType.SUCCESS else ""
        report(isinstance(msg, str) and "potrace" in msg, "Vectoriser : pixel art trop grand → message clair",
               str(msg)[:120])
        imp.delete()
        Gimp.context_set_antialias(True)
        Gimp.context_set_interpolation(Gimp.InterpolationType.CUBIC)

        # allègement : 1500 petites taches de couleur en haute fidélité
        import random
        random.seed(7)
        iml = Gimp.Image.new(1200, 900, Gimp.ImageBaseType.RGB)
        ll = Gimp.Layer.new(iml, "Taches", 1200, 900, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        iml.insert_layer(ll, None, 0)
        Gimp.context_set_background(color(0.5, 0.5, 0.5)); ll.fill(Gimp.FillType.BACKGROUND)
        for i in range(3500):
            iml.select_ellipse(Gimp.ChannelOps.REPLACE, random.randint(-10, 1190), random.randint(-10, 890),
                               random.randint(3, 40), random.randint(3, 40))
            Gimp.context_set_foreground(color(random.random(), random.random(), random.random()))
            ll.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(iml)
        res = {}
        for lighten in (0, 1):
            t0 = time.time()
            v = trace(ll, "photo-high;lighten=%d" % lighten, live=False)
            t1 = time.time()
            if v:
                v.transform_translate(3, 0)          # fluidité : un déplacement
                t2 = time.time()
                res[lighten] = (anchors(v), t1 - t0, t2 - t1)
                iml.remove_layer(v)
        a0, a1 = res.get(0, (0, 0, 0)), res.get(1, (0, 0, 0))
        report(a0[0] > 150000 and 0 < a1[0] < a0[0],
               "Vectoriser : « Alléger les résultats lourds »",
               "%d → %d points d'ancrage ; tracé %.1f → %.1f s ; déplacement %.2f → %.2f s" %
               (a0[0], a1[0], a0[1], a1[1], a0[2], a1[2]))
        iml.delete()

        # vectorisation dynamique : suit l'échelle, le déplacement, le retournement et le recadrage
        imt = Gimp.Image.new(300, 200, Gimp.ImageBaseType.RGB)
        lt = Gimp.Layer.new(imt, "Logo", 300, 200, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        imt.insert_layer(lt, None, 0)
        Gimp.context_set_background(color(1, 1, 1)); lt.fill(Gimp.FillType.BACKGROUND)
        Gimp.context_set_foreground(color(0, 0, 0))
        imt.select_ellipse(Gimp.ChannelOps.REPLACE, 20, 30, 120, 120); lt.edit_fill(Gimp.FillType.FOREGROUND)
        imt.select_rectangle(Gimp.ChannelOps.REPLACE, 180, 50, 90, 90); lt.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(imt)
        vt = trace(lt, "bw-logo")
        if vt:
            steps = []
            def check(name, expect):
                b1 = coords(vt)
                ed = trace_cmd(vt, "edited")[1]
                done, _ = trace_cmd(vt, "retrace")
                b2 = coords(vt)
                ed2 = trace_cmd(vt, "edited")[1]
                ok = near(b1, expect) and near(b2, expect) and ed == "0" and ed2 == "0" and done
                steps.append(ok)
                report(ok, "Vectorisation dynamique : suit « %s »" % name,
                       "attendu %s, objets %s, revectorisé %s, modifié %s/%s" %
                       (tuple(round(v) for v in expect), tuple(round(v) for v in b1),
                        tuple(round(v) for v in b2), ed, ed2))
            b0 = coords(vt)
            imt.scale(600, 400)
            check("Mettre l'image à l'échelle", tuple(v * 2 for v in b0))
            b0 = coords(vt)
            vt.transform_translate(10, 5)
            check("déplacer le calque", (b0[0] + 10, b0[1] + 5, b0[2] + 10, b0[3] + 5))
            b0 = coords(vt)
            imt.flip(Gimp.OrientationType.HORIZONTAL)
            check("Retourner l'image", (600 - b0[2], b0[1], 600 - b0[0], b0[3]))
            b0 = coords(vt)
            imt.crop(500, 380, 40, 10)
            check("Recadrer l'image", (b0[0] - 40, b0[1] - 10, b0[2] - 40, b0[3] - 10))
            # aller-retour XCF après transformations : toujours « non modifié »
            xcft = os.path.join(TMP, "vectoriser-transforme.xcf")
            Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, imt, Gio.File.new_for_path(xcft), None)
            imx2 = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(xcft))
            vx2 = [l for l in imx2.get_layers() if l.get_parasite("chopgimp-trace") is not None]
            report(len(vx2) == 1 and trace_cmd(vx2[0], "edited")[1] == "0" and
                   vx2[0].get_parasite("chopgimp-trace-matrix") is not None,
                   "Vectorisation dynamique : transformée, aller-retour XCF",
                   "modifié %s" % (trace_cmd(vx2[0], "edited")[1] if vx2 else "-"))
            imx2.delete()
            # en couleurs (couleurs non exactes en flottant), mise à l'échelle 3/4, XCF
            imc = Gimp.Image.new(240, 160, Gimp.ImageBaseType.RGB)
            lc = Gimp.Layer.new(imc, "Couleurs", 240, 160, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
            imc.insert_layer(lc, None, 0)
            Gimp.context_set_background(color(0.55, 0.62, 0.23)); lc.fill(Gimp.FillType.BACKGROUND)
            imc.select_ellipse(Gimp.ChannelOps.REPLACE, 30, 30, 100, 90)
            Gimp.context_set_foreground(color(0.31, 0.12, 0.67)); lc.edit_fill(Gimp.FillType.FOREGROUND)
            Gimp.Selection.none(imc)
            vc = trace(lc, "6-colors;ignore-white=0")
            imc.scale(180, 120)
            xcfc = os.path.join(TMP, "vectoriser-couleurs.xcf")
            Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, imc, Gio.File.new_for_path(xcfc), None)
            imx3 = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(xcfc))
            vx3 = [l for l in imx3.get_layers() if l.get_parasite("chopgimp-trace") is not None]
            report(vc is not None and len(vx3) == 1 and trace_cmd(vx3[0], "edited")[1] == "0",
                   "Vectorisation dynamique : couleurs, mise à l'échelle 3/4, aller-retour XCF",
                   "modifié %s" % (trace_cmd(vx3[0], "edited")[1] if vx3 else "-"))
            imx3.delete()
            imc.delete()
            # une vraie modification reste détectée
            x = trace_xml(vt)
            run("chopgimp-vobjects-set-xml", layer=vt, xml=x.replace('color="0 0 0 1"', 'color="1 0 0 1"', 1))
            report(trace_cmd(vt, "edited")[1] == "1", "Vectorisation dynamique : modification détectée après transformations")
        imt.delete()
    except Exception:
        report(False, "Vectoriser 3.27.5", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.27.6 : outil Largeur (profils asymétriques, enregistrés), Distorsion d'objets,
    # filet anti-jointures qui suit le fond, vectorisation dynamique déplacée par l'outil Chemin
    try:
        import re

        def alpha_sum(layer):
            buf = layer.get_buffer()
            rect = buf.get_extent()
            data = buf.get(rect, 1.0, "A u8", Gegl.AbyssPolicy.NONE)
            return sum(data) / 255.0

        def vxml(layer):
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        imw = Gimp.Image.new(400, 300, Gimp.ImageBaseType.RGB)
        bgw = Gimp.Layer.new(imw, "Fond", 400, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        imw.insert_layer(bgw, None, 0)
        pw = Gimp.Path.new(imw, "Deux")
        imw.insert_path(pw, None, 0)
        pw.bezier_stroke_new_ellipse(100, 150, 50, 40, 0)
        pw.bezier_stroke_new_ellipse(280, 150, 60, 50, 0)
        vw = Gimp.VectorLayer.new(imw, pw)
        imw.insert_layer(vw, None, 0)
        vw.set_enable_fill(False); vw.set_enable_stroke(True); vw.set_stroke_width(8)
        vw.refresh()
        imw.set_selected_layers([vw])

        def ocmd(c):
            r = run("chopgimp-vobjects-command", image=imw, command=c)
            return r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1)

        ocmd("split-new")
        ocmd("select-all")
        a_uni = alpha_sum(vw)
        ok_sym = ocmd("width-profile:0:1,0.5:3,1:1")
        a_sym = alpha_sum(vw)
        ok_asym = ocmd("width-profile:0:1,0.5:3/0.5,1:1")
        a_asym = alpha_sum(vw)
        x = vxml(vw)
        report(ok_sym and ok_asym and 'profile="0:1,0.5:3/0.5,1:1"' in x and a_uni < a_asym < a_sym,
               "Outil Largeur : profil asymétrique (un côté plus large)",
               "encre uniforme %d, asymétrique %d, symétrique %d" % (a_uni, a_asym, a_sym))
        ok_save = ocmd("save-profile:Test smoke")
        pf = os.path.join(Gimp.directory(), "chopgimp-width-profiles")
        txt = open(pf).read() if os.path.exists(pf) else ""
        report(ok_save and "Test smoke=0:1,0.5:3/0.5,1:1" in txt, "Outil Largeur : profil enregistré",
               txt.strip()[:80])
        ocmd("width-profile:uniform")

        # Déformation : les 15 styles, la distorsion reste modifiable et part dans le XML aplati
        styles = ["arc", "arc-lower", "arc-upper", "arch", "bulge", "shell-lower", "shell-upper", "flag",
                  "wave", "fish", "rise", "fisheye", "inflate", "squeeze", "twist"]
        b0 = (vw.get_offsets()[1:], vw.get_width(), vw.get_height())
        changed = []
        for st in styles:
            if ocmd("distort-warp:%s:60:0:0:0" % st):
                changed.append(alpha_sum(vw) != a_uni or
                               (vw.get_offsets()[1:], vw.get_width(), vw.get_height()) != b0)
            ocmd("distort-release")
        report(len(changed) == 15 and all(changed), "Distorsion : 15 déformations",
               "%d/%d appliquées et visibles" % (sum(changed), len(changed)))
        ocmd("distort-warp:arc:50:20:0:1")
        x = vxml(vw)
        report("type=distort" in x and "d-effective=" in x and "vertical=1" in x,
               "Distorsion : gardée dans les objets (modifiable), tracé aplati pour l'export")
        ocmd("distort-release")

        # Enveloppe à maille : un point tiré vers la gauche agrandit le calque
        w0, ox0 = vw.get_width(), vw.get_offsets()[1]
        ok_m = ocmd("distort-mesh:2:3") and ocmd("distort-mesh-point:0:-0.3:0")
        report(ok_m and vw.get_offsets()[1] < ox0 - 20, "Distorsion : enveloppe à maille, point déplacé",
               "x %d → %d" % (ox0, vw.get_offsets()[1]))
        ocmd("distort-release")
        # Distorsion libre : coin haut droit tiré vers la droite
        ok_f = ocmd("distort-free") and ocmd("distort-mesh-point:1:0.3:0")
        report(ok_f and vw.get_width() > w0 + 20, "Distorsion libre : 4 coins",
               "largeur %d → %d" % (w0, vw.get_width()))
        # XCF : la distorsion survit
        xcfw = os.path.join(TMP, "distorsion.xcf")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, imw, Gio.File.new_for_path(xcfw), None)
        imwx = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(xcfw))
        vwx = [l for l in imwx.get_layers() if isinstance(l, Gimp.VectorLayer)]
        report(len(vwx) == 1 and "type=distort" in vxml(vwx[0]) and vwx[0].get_width() == vw.get_width(),
               "Distorsion : aller-retour XCF", "largeur %s" % (vwx[0].get_width() if vwx else "-"))
        imwx.delete()
        # Décomposer : la forme distordue devient le tracé, plus d'effet
        wd = vw.get_width()
        ok_e = ocmd("distort-expand")
        x = vxml(vw)
        report(ok_e and "distort" not in x and abs(vw.get_width() - wd) <= 2 and x.count("<path ") == 2,
               "Distorsion : Décomposer", "largeur %d → %d" % (wd, vw.get_width()))
        # d'après l'objet du dessus : 2 objets → 1 objet dans l'enveloppe du second
        ocmd("select-all")
        ok_t = ocmd("distort-top")
        x = vxml(vw)
        report(ok_t and x.count("<path ") == 1 and "mode=mesh" in x,
               "Distorsion : créer d'après l'objet du dessus", "%d objet(s)" % x.count("<path "))
        imw.delete()

        # pixel art : le filet anti-jointures suit le fond
        imp = Gimp.Image.new(16, 16, Gimp.ImageBaseType.RGB)
        lp = Gimp.Layer.new(imp, "Pixels", 16, 16, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        imp.insert_layer(lp, None, 0)
        Gimp.context_set_background(color(1, 1, 1)); lp.fill(Gimp.FillType.BACKGROUND)
        imp.select_rectangle(Gimp.ChannelOps.REPLACE, 4, 4, 6, 6)
        Gimp.context_set_foreground(color(1, 0, 0)); lp.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(imp)
        r = run("chopgimp-image-trace", drawable=lp, options="pixel-art;ignore-white=0",
                **{"selection-only": False, "live": False})
        vp = r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else None
        x = vxml(vp) if vp else ""
        # le fond rouge seul passe au vert (comme dans le panneau Aspect)
        m = re.search(r'<fill type="color" color="1 0 0 1"/>', x)
        x2 = x[:m.start()] + '<fill type="color" color="0 1 0 1"/>' + x[m.end():] if m else x
        if vp:
            run("chopgimp-vobjects-set-xml", layer=vp, xml=x2)
        x3 = vxml(vp) if vp else ""
        report("follow-fill" in x and m is not None and
               re.search(r'<stroke type="color" color="0 1 0 1"[^>]*follow-fill', x3) is not None,
               "Vectoriser : le filet anti-jointures suit le fond", "%d objets" % x.count("<path "))
        imp.delete()

        # vectorisation dynamique : objets déplacés ensemble (outil Chemin), sans la matrice
        imv = Gimp.Image.new(300, 200, Gimp.ImageBaseType.RGB)
        lv = Gimp.Layer.new(imv, "Logo", 300, 200, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        imv.insert_layer(lv, None, 0)
        Gimp.context_set_background(color(1, 1, 1)); lv.fill(Gimp.FillType.BACKGROUND)
        Gimp.context_set_foreground(color(0, 0, 0))
        imv.select_ellipse(Gimp.ChannelOps.REPLACE, 20, 30, 120, 120); lv.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(imv)
        r = run("chopgimp-image-trace", drawable=lv, options="bw-logo", **{"selection-only": False, "live": True})
        vv = r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else None
        if vv:
            def box(layer):
                nums = []
                for d in re.findall(r' d="([^"]*)"', vxml(layer)):
                    nums += [float(v) for v in re.findall(r'-?[0-9.]+(?:e-?[0-9]+)?', d)]
                return (min(nums[0::2]), min(nums[1::2]), max(nums[0::2]), max(nums[1::2]))

            def shift(m):
                vals = [float(v) for v in re.findall(r'-?[0-9.]+(?:e-?[0-9]+)?', m.group(1))]
                out, k = [], 0
                def rep(mm):
                    nonlocal k
                    v = float(mm.group(0)) + (12 if k % 2 == 0 else 7)
                    k += 1
                    return repr(v)
                return ' d="%s"' % re.sub(r'-?[0-9.]+(?:e-?[0-9]+)?', rep, m.group(1))

            b1 = box(vv)
            run("chopgimp-vobjects-set-xml", layer=vv, xml=re.sub(r' d="([^"]*)"', shift, vxml(vv)))
            r1 = run("chopgimp-image-trace-command", layer=vv, command="edited")
            ed = r1.index(2) if r1 is not None else "?"
            run("chopgimp-image-trace-command", layer=vv, command="retrace")
            b2 = box(vv)
            okv = ed == "0" and all(abs(b2[i] - b1[i] - (12 if i % 2 == 0 else 7)) <= 1.5 for i in range(4))
            report(okv, "Vectorisation dynamique : suit un déplacement des objets (outil Chemin)",
                   "modifié %s, %s → %s" % (ed, tuple(round(v) for v in b1), tuple(round(v) for v in b2)))
        else:
            report(False, "Vectorisation dynamique : suit un déplacement des objets (outil Chemin)", "pas de tracé")
        imv.delete()
    except Exception:
        report(False, "3.27.6", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.28.1 : Peinture dynamique et Symboles
    try:
        import re

        def vxml2(layer):
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        def px(l, x, y):
            ok, x0, y0 = l.get_offsets()
            return tuple(round(c * 255) for c in l.get_pixel(x - x0, y - y0).get_rgba_with_space(None))

        iml = Gimp.Image.new(300, 300, Gimp.ImageBaseType.RGB)
        bgl = Gimp.Layer.new(iml, "Fond", 300, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        iml.insert_layer(bgl, None, 0)
        pl = Gimp.Path.new(iml, "Croix")
        iml.insert_path(pl, None, 0)
        s0 = pl.bezier_stroke_new_moveto(50, 50)
        for x, y in [(250, 50), (250, 250), (50, 250)]:
            pl.bezier_stroke_lineto(s0, x, y)
        pl.stroke_close(s0)
        s1 = pl.bezier_stroke_new_moveto(50, 150); pl.bezier_stroke_lineto(s1, 250, 150)
        s2 = pl.bezier_stroke_new_moveto(150, 50); pl.bezier_stroke_lineto(s2, 150, 250)
        vl2 = Gimp.VectorLayer.new(iml, pl)
        iml.insert_layer(vl2, None, 0)
        vl2.set_enable_fill(False); vl2.set_enable_stroke(True); vl2.set_stroke_width(2)
        vl2.refresh()
        iml.set_selected_layers([vl2])

        def lcmd(c):
            r = run("chopgimp-vobjects-command", image=iml, command=c)
            return r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1)

        lcmd("split-new"); lcmd("select-all")
        ok_mk = lcmd("livepaint-make")
        x = vxml2(vl2)
        nf = x.count('livepaint="face"')
        report(ok_mk and 'livepaint="group' in x and nf == 4 and x.count('livepaint="edge') >= 8,
               "Peinture dynamique : 4 zones et les segments d'un rectangle coupé par une croix",
               "%d zones, %d segments" % (nf, x.count('livepaint="edge')))
        ok_f = lcmd("livepaint-fill:100:100:#ff0000")
        p1 = px(vl2, 100, 100); p2 = px(vl2, 200, 100)
        report(ok_f and p1[:3] == (255, 0, 0) and p1[3] == 255 and p2[3] == 0,
               "Peinture dynamique : le pot remplit une seule zone", "%s / %s" % (p1, p2))
        ok_s = lcmd("livepaint-stroke:150:100:#0000ff")
        report(ok_s and 'color="0 0 1 1"' in vxml2(vl2), "Peinture dynamique : peindre un segment")

        # la ligne verticale bouge (-30 px) : les zones suivent, le rouge reste à sa zone
        x = vxml2(vl2)
        src = x.index('livepaint="sources"')
        # le sous-chemin vertical x = 150 passe à x = 120 (dans le groupe masqué des tracés)
        def mv(m):
            d = m.group(0)
            return re.sub(r'M 150 50 C 150 50 150 250 150 250', 'M 120 50 C 120 50 120 250 120 250', d)
        x2 = x[:src] + re.sub(r' d="[^"]*"', mv, x[src:])
        report(x2 != x, "Peinture dynamique : tracé vertical trouvé pour le déplacer")
        run("chopgimp-vobjects-set-xml", layer=vl2, xml=x2)
        x3 = vxml2(vl2)
        q1 = px(vl2, 80, 100); q2 = px(vl2, 135, 100)
        report(x3.count('livepaint="face"') == 4 and q1[:3] == (255, 0, 0) and q1[3] == 255 and q2[3] == 0,
               "Peinture dynamique : les zones suivent un tracé déplacé", "%s / %s" % (q1, q2))
        lcmd("livepaint-select:80:100")
        ok_g = lcmd("livepaint-gap:5")
        report(ok_g and "gap=5" in vxml2(vl2), "Peinture dynamique : options d'écarts")

        xcf = os.path.join(TMP, "peinture-dynamique.xcf")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, iml, Gio.File.new_for_path(xcf), None)
        imx = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(xcf))
        vx = [l for l in imx.get_layers() if l.is_vector_layer()]
        xx = vxml2(vx[0]) if vx else ""
        report(xx.count('livepaint="face"') == 4 and 'color="1 0 0 1"' in xx,
               "Peinture dynamique : aller-retour XCF")
        imx.delete()

        lcmd("livepaint-select:80:100")
        ok_e = lcmd("livepaint-expand")
        xe = vxml2(vl2)
        report(ok_e and "livepaint" not in xe and 'color="1 0 0 1"' in xe,
               "Peinture dynamique : décomposer", "%d objets" % xe.count("<path "))
        iml.delete()

        # Symboles
        ims = Gimp.Image.new(400, 300, Gimp.ImageBaseType.RGB)
        bgs = Gimp.Layer.new(ims, "Fond", 400, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        ims.insert_layer(bgs, None, 0)
        ps = Gimp.Path.new(ims, "Fleur")
        ims.insert_path(ps, None, 0)
        ps.bezier_stroke_new_ellipse(60, 60, 30, 20, 0)
        ps.bezier_stroke_new_ellipse(120, 60, 20, 30, 0)
        vs = Gimp.VectorLayer.new(ims, ps)
        ims.insert_layer(vs, None, 0)
        vs.set_enable_fill(True); vs.set_enable_stroke(False)
        vs.refresh()
        ims.set_selected_layers([vs])

        def scmd(c):
            r = run("chopgimp-vobjects-command", image=ims, command=c)
            return r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1)

        scmd("split-new"); scmd("select-all")
        ok_n = scmd("symbol-new:Fleur")
        par = ims.get_parasite("chopgimp-symbols")
        ptxt = bytes(par.get_data()).decode() if par else ""
        report(ok_n and 'name="Fleur"' in ptxt and 'symbol="s1"' in vxml2(vs),
               "Symboles : nouveau symbole (définition dans l'image, première occurrence)")
        ok_p = scmd("symbol-place:s1")
        xs = vxml2(vs)
        report(ok_p and xs.count('symbol="s1"') == 2, "Symboles : placer une occurrence",
               "%d occurrence(s)" % xs.count('symbol="s1"'))
        # modifier une occurrence hors de « Modifier le symbole » : elle seule quitte le symbole
        m = re.search(r'<fill type="color" color="[^"]*"', xs)
        xs_out = xs[:m.start()] + '<fill type="color" color="0 0 1 1"' + xs[m.end():] if m else xs
        run("chopgimp-vobjects-set-xml", layer=vs, xml=xs_out)
        xo = vxml2(vs)
        report(xo.count('symbol="s1"') == 1 and xo.count('color="0 0 1 1"') == 1,
               "Symboles : une occurrence modifiée hors du mode « Modifier le symbole » quitte le symbole",
               "%d occurrence(s)" % xo.count('symbol="s1"'))
        run("chopgimp-vobjects-set-xml", layer=vs, xml=xs)
        # dans « Modifier le symbole » (occurrence ouverte, ses objets sélectionnés) : un
        # alignement de ses objets change le symbole et l'autre occurrence suit
        par = ims.get_parasite("chopgimp-symbols")
        p_before = bytes(par.get_data()).decode() if par else ""
        ok_ed = scmd("symbol-edit:s1")
        ok_al = scmd("align-left")
        xs3 = vxml2(vs)
        par = ims.get_parasite("chopgimp-symbols")
        ptxt = bytes(par.get_data()).decode() if par else ""
        occs = re.findall(r'<group [^>]*symbol="s1"[^>]*>(.*?)</group>', xs3, re.S)
        occs = [re.sub(r' id="[0-9]+"', "", o) for o in occs]
        report(ok_ed and ok_al and len(occs) == 2 and occs[0] == occs[1] and ptxt != p_before,
               "Symboles : modifier le symbole met à jour toutes les occurrences",
               "%d occurrence(s), symbole %s" % (len(occs), "modifié" if ptxt != p_before else "inchangé"))
        xcf = os.path.join(TMP, "symboles.xcf")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, ims, Gio.File.new_for_path(xcf), None)
        imx = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(xcf))
        px2 = imx.get_parasite("chopgimp-symbols")
        vx = [l for l in imx.get_layers() if l.is_vector_layer()]
        report(px2 is not None and vx and vxml2(vx[0]).count('symbol="s1"') == 2,
               "Symboles : aller-retour XCF")
        imx.delete()
        run("chopgimp-vobjects-set-xml", layer=vs, xml=vxml2(vs))   # sort de l'occurrence ouverte
        scmd("select-all")
        ok_b = scmd("symbol-break")
        report(ok_b and vxml2(vs).count('symbol="s1"') == 0, "Symboles : rompre le lien")
        # import SVG : <symbol> / <use> → symbole et occurrences
        svgp = os.path.join(TMP, "symboles.svg")
        open(svgp, "w").write('<svg xmlns="http://www.w3.org/2000/svg" '
                              'xmlns:xlink="http://www.w3.org/1999/xlink" width="200" height="100">'
                              '<defs><symbol id="carre"><rect x="0" y="0" width="30" height="30" '
                              'fill="#00ff00"/></symbol></defs>'
                              '<use xlink:href="#carre" x="10" y="10"/>'
                              '<use xlink:href="#carre" x="120" y="40"/></svg>')
        imsv = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(svgp))
        psv = imsv.get_parasite("chopgimp-symbols")
        tsv = bytes(psv.get_data()).decode() if psv else ""
        vsv = [l for l in imsv.get_layers() if l.is_vector_layer()]
        nsv = sum(vxml2(l).count('symbol="svg-carre"') for l in vsv)
        report('id="svg-carre"' in tsv and nsv == 2, "Symboles : import SVG <symbol> / <use>",
               "%d occurrence(s)" % nsv)
        imsv.delete()
        ok_d = scmd("symbol-delete:s1")
        par = ims.get_parasite("chopgimp-symbols")
        ptxt = bytes(par.get_data()).decode() if par else ""
        report(ok_d and "<symbol " not in ptxt, "Symboles : supprimer")
        ims.delete()
    except Exception:
        report(False, "3.28.1", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.28.2 : petits défauts (contours à l'échelle, sélection d'objets
    # dans le XCF, convertir en maille, décomposer seulement la
    # distorsion, ombre en mode Produit pixellisée en calque)
    try:
        import re

        def vx3(layer):
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        im3 = Gimp.Image.new(300, 300, Gimp.ImageBaseType.RGB)
        bg3 = Gimp.Layer.new(im3, "Fond", 300, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im3.insert_layer(bg3, None, 0)
        p3 = Gimp.Path.new(im3, "Rect")
        im3.insert_path(p3, None, 0)
        s3 = p3.bezier_stroke_new_moveto(50, 50)
        for x, y in [(150, 50), (150, 150), (50, 150)]:
            p3.bezier_stroke_lineto(s3, x, y)
        p3.stroke_close(s3)
        vl3 = Gimp.VectorLayer.new(im3, p3)
        im3.insert_layer(vl3, None, 0)
        vl3.set_enable_fill(True); vl3.set_enable_stroke(True); vl3.set_stroke_width(4)
        vl3.refresh()
        im3.set_selected_layers([vl3])

        def c3(c):
            r = run("chopgimp-vobjects-command", image=im3, command=c)
            return r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1)

        c3("split-new"); c3("select-all")
        ws = lambda: [float(v) for v in re.findall(r'<stroke[^>]*?\swidth="([0-9.]+)"', vx3(vl3))]
        w0 = ws()
        c3("scale-strokes:0"); ok_sc = c3("scale-objects:2")
        w1 = ws()
        c3("scale-strokes:1"); c3("scale-objects:0.5")
        w2 = ws()
        report(ok_sc and w0 and w1 and abs(w1[0] - w0[0] / 2) < 1e-6 and abs(w2[0] - w1[0]) < 1e-6,
               "Contours à l'échelle : option décochée, épaisseur conservée",
               "%s → %s → %s" % (w0[:1], w1[:1], w2[:1]))

        # sélection d'objets gardée par le XCF
        x3p = os.path.join(TMP, "sel328.xcf")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, im3, Gio.File.new_for_path(x3p), None)
        im3b = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(x3p))
        lb = [l for l in im3b.get_layers() if l.is_vector_layer()][0]
        pb = lb.get_parasite("chopgimp-vobjects")
        tb = bytes(pb.get_data()).decode() if pb else ""
        msel = re.search(r'selection="([0-9 ]*)"', tb)
        report(bool(msel and msel.group(1).strip()), "Sélection d'objets gardée par le XCF",
               msel.group(0) if msel else "aucune")
        im3b.delete()

        # Déformation → Convertir en maille
        c3("select-all")
        ok_w = c3("distort-warp:arc:50")
        ok_m = c3("distort-to-mesh")
        xm = vx3(vl3)
        report(ok_w and ok_m and "mode=mesh" in xm and "mode=warp" not in xm,
               "Convertir la déformation en maille")

        # Décomposer : la distorsion seulement, les autres effets restent
        c3("distort-release")
        o_lpe = run("chopgimp-vobjects-command", image=im3, command="distort-warp:flag:40")
        xs = vx3(vl3)
        # un effet vivant ajouté à la main (zigzag) sous la distorsion
        xs2 = xs.replace("<lpe>", "<lpe>[9]\ntype=roughen\nsize=2\nseed=1\n", 1)
        ok_set = run("chopgimp-vobjects-set-xml", layer=vl3, xml=xs2) if xs2 != xs else None
        c3("select-all")
        ok_e = c3("distort-expand")
        xe = vx3(vl3)
        report(ok_e and "distort" not in xe and ("roughen" in xe or xs2 == xs),
               "Décomposer : seulement la distorsion",
               "effet restant : %s" % ("roughen" in xe))
        im3.delete()

        # Ombre portée en mode Produit : pixelliser → un calque en Produit
        im4 = Gimp.Image.new(200, 200, Gimp.ImageBaseType.RGB)
        b4 = Gimp.Layer.new(im4, "Fond", 200, 200, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im4.insert_layer(b4, None, 0)
        l4 = Gimp.Layer.new(im4, "Forme", 200, 200, Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im4.insert_layer(l4, None, 0)
        l4.fill(Gimp.FillType.TRANSPARENT)
        im4.select_rectangle(Gimp.ChannelOps.REPLACE, 60, 60, 60, 60)
        Gimp.context_set_foreground(Gegl.Color.new("red"))
        l4.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(im4)
        f4 = Gimp.DrawableFilter.new(l4, "gegl:dropshadow", "Ombre portée")
        cf = f4.get_config()
        cf.set_property("x", 10.0); cf.set_property("y", 10.0)
        try:
            cf.set_property("blend-mode", "multiply")
        except Exception:
            pass
        f4.set_blend_mode(Gimp.LayerMode.REPLACE)
        f4.update()
        l4.append_filter(f4)
        l4.merge_filters()
        modes = [(l.get_name(), l.get_mode()) for l in im4.get_layers()]
        report(len(modes) == 3 and any(m == Gimp.LayerMode.MULTIPLY for _, m in modes),
               "Pixelliser : l'ombre en Produit devient un calque en Produit",
               ", ".join("%s/%s" % (n, m.value_nick if hasattr(m, "value_nick") else m) for n, m in modes))
        im4.delete()
    except Exception:
        report(False, "3.28.2", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.28.3 : croix de la brosse, Sélection rapide, Lasso magnétique,
    # boîte à outils par familles
    try:
        try:
            v = Gimp.gimprc_query("brush-crosshair")
        except Exception as e:
            v = "erreur : %s" % e
        report(str(v).strip() in ("0", "always"),
               "Croix au centre de la brosse : Toujours par défaut", "valeur : %s" % v)
        # l'opération doit exister dans le cœur de GIMP (outil enregistré
        # seulement si gegl_has_operation) : un filtre inconnu est refusé
        imq = Gimp.Image.new(64, 64, Gimp.ImageBaseType.RGB)
        lq = Gimp.Layer.new(imq, "q", 64, 64, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        imq.insert_layer(lq, None, 0)
        try:
            fq = Gimp.DrawableFilter.new(lq, "gegl:paint-select", "test")
            okq = fq is not None
        except Exception as e:
            okq = False
        imq.delete()
        report(okq, "Sélection rapide : opération gegl:paint-select présente")
        rc = open(os.path.join(Gimp.sysconf_directory(), "toolrc")).read()
        order = [rc.find('"gimp-%s-tool"' % t) for t in
                 ("move", "magnetic-lasso", "paint-select", "paintbrush", "eraser",
                  "heal", "clone", "path", "shape", "live-paint-bucket", "width", "zoom")]
        report(all(p >= 0 for p in order) and order == sorted(order),
               "Boîte à outils par familles (Lasso magnétique, Sélection rapide, Gomme sous le pinceau…)",
               "positions : %s" % order)
        report('(active-tool "gimp-magnetic-lasso-tool")' in rc,
               "Lasso magnétique : outil affiché du groupe L")
    except Exception:
        report(False, "3.28.3", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.29.0 (vectoriel « complet », blocs 1 et 2) : angles dynamiques,
    # Ciseaux, Jonction, Cutter, objet clé, Aligner sur, Répéter la
    # transformation, Transformer chaque, panneau Transformation
    try:
        import re

        def vx9(layer):
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        im9 = Gimp.Image.new(320, 320, Gimp.ImageBaseType.RGB)
        b9 = Gimp.Layer.new(im9, "Fond", 320, 320, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im9.insert_layer(b9, None, 0)
        p9 = Gimp.Path.new(im9, "Formes")
        im9.insert_path(p9, None, 0)
        for pts9, closed in [([(50, 50), (150, 50), (150, 150), (50, 150)], True),
                             ([(200, 50), (280, 50), (280, 130), (200, 130)], True),
                             ([(20, 250), (100, 250)], False),
                             ([(103, 250), (180, 250)], False)]:
            st9 = p9.bezier_stroke_new_moveto(*pts9[0])
            for x, y in pts9[1:]:
                p9.bezier_stroke_lineto(st9, x, y)
            if closed:
                p9.stroke_close(st9)
        vl9 = Gimp.VectorLayer.new(im9, p9)
        im9.insert_layer(vl9, None, 0)
        vl9.set_enable_fill(True); vl9.set_enable_stroke(True); vl9.set_stroke_width(2)
        vl9.refresh()
        im9.set_selected_layers([vl9])

        def c9(c):
            r = run("chopgimp-vobjects-command", image=im9, command=c)
            return bool(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1))

        n9 = lambda: vx9(vl9).count("<path ")
        c9("split-new")
        n0 = n9()

        c9("select-all")
        ok_c = c9("corners:8:round")
        x_c = vx9(vl9)
        ok_c0 = c9("corners:0")
        report(ok_c and "type=corners" in x_c and "type=corners" not in vx9(vl9),
               "Angles dynamiques : ajoutés puis retirés", "%d objets" % n0)

        ok_cut = c9("cut-at:60:250")
        n_cut = n9()
        ok_join = c9("join-at:101.5:250:6")
        n_join = n9()
        report(ok_cut and n_cut == n0 + 1 and ok_join and n_join == n0,
               "Ciseaux puis Jonction", "%d → %d → %d objets" % (n0, n_cut, n_join))

        c9("select-none")
        ok_k = c9("knife:100:30:100:170")
        report(ok_k and n9() == n0 + 1, "Cutter : le carré tranché en deux", "%d objets" % n9())

        c9("select-all")
        ok_key = c9("key:0")
        ok_al = c9("align-left")
        ok_to = c9("align-to:artboard") and c9("key-none") and c9("align-top")
        c9("align-to:selection")
        report(ok_key and ok_al and ok_to, "Objet clé et « Aligner sur le plan de travail »")

        c9("select-all")
        n_sel = n9()
        ok_rec = c9("transform-record:1:0:0:1:10:0:1")
        ok_again = c9("transform-again")
        report(ok_rec and ok_again and n9() == 2 * n_sel,
               "Répéter la transformation (copie)", "%d → %d objets" % (n_sel, n9()))

        ok_each = c9("transform-each:150:150:0:0:30:0:0:4:1")
        report(ok_each and n9() > 2 * n_sel, "Transformer chaque (copie)", "%d objets" % n9())

        c9("select-all")
        ok_box = c9("box:0:10:10:120:120:15:0")
        ok_flip = c9("flip-h:4")
        report(ok_box and ok_flip, "Panneau Transformation : taille, angle, retournement")
        im9.delete()

        sysconf = Gimp.sysconf_directory()
        toolrc = os.path.join(sysconf, "toolrc")
        tr = open(toolrc).read() if os.path.exists(toolrc) else ""
        report(all(t in tr for t in ["gimp-curvature-tool", "gimp-vpencil-tool", "gimp-vsmooth-tool",
                                     "gimp-vscissors-tool", "gimp-vknife-tool", "gimp-vjoin-tool"]),
               "Outils Courbure, Crayon, Lissage, Ciseaux, Cutter, Jonction dans la boîte à outils")
    except Exception:
        report(False, "3.29.0", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.29.1 (vectoriel « complet », bloc 3 « couleur et matière ») :
    # Transition, filet de dégradé, dégradé libre, dégradé du contour,
    # masque d'opacité, motifs vectoriels
    try:
        def vx10(layer):
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        im10 = Gimp.Image.new(400, 300, Gimp.ImageBaseType.RGB)
        b10 = Gimp.Layer.new(im10, "Fond", 400, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im10.insert_layer(b10, None, 0)
        p10 = Gimp.Path.new(im10, "Formes")
        im10.insert_path(p10, None, 0)
        for pts10 in [[(20, 20), (80, 20), (80, 80), (20, 80)],
                      [(300, 20), (380, 20), (380, 100), (300, 100)],
                      [(20, 180), (140, 180), (140, 280), (20, 280)],
                      [(60, 200), (200, 200), (200, 260), (60, 260)]]:
            st10 = p10.bezier_stroke_new_moveto(*pts10[0])
            for x, y in pts10[1:]:
                p10.bezier_stroke_lineto(st10, x, y)
            p10.stroke_close(st10)
        vl10 = Gimp.VectorLayer.new(im10, p10)
        im10.insert_layer(vl10, None, 0)
        vl10.set_enable_fill(True); vl10.set_enable_stroke(True); vl10.set_stroke_width(2)
        vl10.refresh()
        im10.set_selected_layers([vl10])

        def c10(c):
            r = run("chopgimp-vobjects-command", image=im10, command=c)
            return bool(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1))

        c10("split-new")

        # Transition entre les quatre carrés (objets clés, dans l'ordre)
        ok_s = c10("select-at:50:50")
        c10("select-all")
        n_all = vx10(vl10).count("<path ")
        ok_b = c10("blend-make")
        x_b = vx10(vl10)
        ok_st = c10("blend-steps:5")
        x_s = vx10(vl10)
        report(ok_s and ok_b and 'blend="blend' in x_b and ok_st and
               x_s.count('blend="step"') == 5 * (n_all - 1),
               "Transition : étapes générées puis 5 étapes par paire",
               "%d objets clés, %d étapes" % (n_all, x_s.count('blend="step"')))
        ok_rv = c10("blend-reverse")
        ok_ex = c10("blend-expand")
        x_e = vx10(vl10)
        report(ok_rv and ok_ex and "blend=" not in x_e and x_e.count("<path ") == n_all + 5 * (n_all - 1),
               "Transition : inverser puis décomposer", "%d objets" % x_e.count("<path "))
        im10.delete()

        # Filet, dégradé libre, dégradé du contour, masque d'opacité, motif
        im11 = Gimp.Image.new(400, 300, Gimp.ImageBaseType.RGB)
        b11 = Gimp.Layer.new(im11, "Fond", 400, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im11.insert_layer(b11, None, 0)
        p11 = Gimp.Path.new(im11, "Formes")
        im11.insert_path(p11, None, 0)
        for pts11 in [[(20, 20), (120, 20), (120, 120), (20, 120)],
                      [(60, 60), (180, 60), (180, 180), (60, 180)],
                      [(250, 20), (380, 20), (380, 150), (250, 150)],
                      [(250, 200), (300, 200), (300, 250), (250, 250)]]:
            st11 = p11.bezier_stroke_new_moveto(*pts11[0])
            for x, y in pts11[1:]:
                p11.bezier_stroke_lineto(st11, x, y)
            p11.stroke_close(st11)
        vl11 = Gimp.VectorLayer.new(im11, p11)
        im11.insert_layer(vl11, None, 0)
        vl11.set_enable_fill(True); vl11.set_enable_stroke(True); vl11.set_stroke_width(3)
        vl11.refresh()
        im11.set_selected_layers([vl11])

        def c11(c):
            r = run("chopgimp-vobjects-command", image=im11, command=c)
            return bool(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1))

        c11("split-new")

        ok_sel = c11("select-at:300:80")
        ok_m = c11("mesh-make:2:3:1:0.8")
        ok_mi = c11("mesh-insert:0.5:0.5:#ff0000")
        x_m = vx10(vl11)
        report(ok_sel and ok_m and 'type="mesh"' in x_m and ok_mi and 'material="3 4;' in x_m,
               "Filet de dégradé : créé (2 × 3) puis une rangée et une colonne ajoutées")

        c11("select-at:275:225")
        ok_f = c11("freeform-make")
        ok_g = c11("stroke-gradient:1")
        x_f = vx10(vl11)
        report(ok_f and 'type="freeform"' in x_f and ok_g and 'stroke-gradient="1"' in x_f,
               "Dégradé libre et dégradé le long du contour")

        # masque d'opacité : les deux carrés qui se chevauchent
        c11("select-none")
        c11("select-all")
        ok_om = c11("opmask-make")
        x_o = vx10(vl11)
        ok_ot = c11("opmask-toggle:4")
        x_o2 = vx10(vl11)
        ok_or = c11("opmask-release")
        report(ok_om and 'opmask="3"' in x_o and ok_ot and 'opmask="7"' in x_o2 and ok_or and
               "opmask=" not in vx10(vl11),
               "Masque d'opacité : créé (découpe), inversé, libéré")

        # motif : le petit carré devient un motif, appliqué au grand
        c11("select-at:275:225")
        ok_pm = c11("pattern-make:Damier")
        c11("select-at:300:80")
        ok_pa = c11("pattern-apply:Damier")
        ok_pt = c11("pattern-type:hex")
        x_p = vx10(vl11)
        report(ok_pm and ok_pa and 'type="vpattern"' in x_p and ok_pt and "type=hex" in x_p,
               "Motif vectoriel : créé, appliqué, pavage hexagonal")

        # rendu : le calque n'est pas vide après tout ça
        vl11.refresh() if hasattr(vl11, "refresh") else None
        report(vl11.get_width() > 0 and vl11.get_height() > 0, "Rendu des matières (calque non vide)")
        im11.delete()

        # finition 3.29.1 : transition qui suit un tracé de base, Cutter
        # sur un tracé ouvert
        import re as re12
        im12 = Gimp.Image.new(400, 300, Gimp.ImageBaseType.RGB)
        b12 = Gimp.Layer.new(im12, "Fond", 400, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im12.insert_layer(b12, None, 0)
        p12 = Gimp.Path.new(im12, "Formes")
        im12.insert_path(p12, None, 0)
        for pts12, closed12 in [([(20, 100), (60, 100), (60, 140), (20, 140)], True),
                                ([(320, 100), (360, 100), (360, 140), (320, 140)], True),
                                ([(40, 120), (190, 20), (340, 120)], False)]:
            st12 = p12.bezier_stroke_new_moveto(*pts12[0])
            for x, y in pts12[1:]:
                p12.bezier_stroke_lineto(st12, x, y)
            if closed12:
                p12.stroke_close(st12)
        vl12 = Gimp.VectorLayer.new(im12, p12)
        im12.insert_layer(vl12, None, 0)
        vl12.set_enable_fill(True); vl12.set_enable_stroke(True); vl12.set_stroke_width(2)
        vl12.refresh()
        im12.set_selected_layers([vl12])

        def c12(c):
            r = run("chopgimp-vobjects-command", image=im12, command=c)
            return bool(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1))

        c12("split-new")
        ok12 = c12("select-at:25:105") and c12("select-add-at:355:105") and c12("blend-make")
        c12("blend-steps:3")
        ok12s = c12("select-at:25:105") and c12("select-add-at:190:20") and c12("blend-spine")
        x12 = vx10(vl12)
        ys12 = []
        for blk in re12.findall(r'blend="step"[^>]*d="([^"]*)"', x12):
            nums = [float(t) for t in re12.findall(r'-?[0-9.]+', blk)]
            ys12 += nums[1::2]
        report(ok12 and ok12s and "spine=" in x12 and ys12 and min(ys12) < 80,
               "Transition : remplacer le tracé de base (les étapes suivent la courbe)",
               "y min des étapes : %s" % (min(ys12) if ys12 else "—"))
        im12.delete()

        im13 = Gimp.Image.new(300, 300, Gimp.ImageBaseType.RGB)
        b13 = Gimp.Layer.new(im13, "Fond", 300, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im13.insert_layer(b13, None, 0)
        p13 = Gimp.Path.new(im13, "Trait")
        im13.insert_path(p13, None, 0)
        st13 = p13.bezier_stroke_new_moveto(20, 150)
        p13.bezier_stroke_lineto(st13, 280, 150)
        vl13 = Gimp.VectorLayer.new(im13, p13)
        im13.insert_layer(vl13, None, 0)
        vl13.set_enable_fill(False); vl13.set_enable_stroke(True); vl13.set_stroke_width(4)
        vl13.refresh()
        im13.set_selected_layers([vl13])
        run("chopgimp-vobjects-command", image=im13, command="split-new")
        run("chopgimp-vobjects-command", image=im13, command="select-all")
        r13 = run("chopgimp-vobjects-command", image=im13, command="knife:150:50:150:250")
        x13 = vx10(vl13)
        report(r13 is not None and r13.index(0) == Gimp.PDBStatusType.SUCCESS and
               x13.count("<path ") == 2,
               "Cutter : un tracé ouvert tranché en deux", "%d objets" % x13.count("<path "))
        im13.delete()

        sysconf = Gimp.sysconf_directory()
        toolrc = os.path.join(sysconf, "toolrc")
        tr = open(toolrc).read() if os.path.exists(toolrc) else ""
        report("gimp-vmesh-tool" in tr and "gimp-vblend-tool" in tr,
               "Outils Filet et Transition dans la boîte à outils")
    except Exception:
        report(False, "3.29.1", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.29.2 (vectoriel rapide) : glisser par caches, annulation par copie
    # de l'arbre, ouverture XCF sans rendu de l'ancien tracé ; le rendu
    # doit rester identique au pixel près
    try:
        import random as _r

        def px(layer):
            b = layer.get_buffer()
            e = b.get_extent()
            return (layer.get_offsets()[1:], e.width, e.height,
                    bytes(b.get(e, 1.0, "R'G'B'A u8", Gegl.AbyssPolicy.NONE)))

        def vx2(layer):
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        def vc2(image, c):
            r = run("chopgimp-vobjects-command", image=image, command=c)
            return r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1)

        imf = Gimp.Image.new(400, 400, Gimp.ImageBaseType.RGB)
        pf = Gimp.Path.new(imf, "Formes")
        imf.insert_path(pf, None, 0)
        rnd = _r.Random(3)
        for i in range(40):
            x, y = rnd.uniform(10, 300), rnd.uniform(10, 300)
            sid = pf.bezier_stroke_new_moveto(x, y)
            pf.bezier_stroke_lineto(sid, x + rnd.uniform(10, 80), y + rnd.uniform(-5, 5))
            pf.bezier_stroke_lineto(sid, x + rnd.uniform(0, 40), y + rnd.uniform(10, 80))
            pf.stroke_close(sid)
        vf = Gimp.VectorLayer.new(imf, pf)
        imf.insert_layer(vf, None, 0)
        vf.refresh()
        imf.set_selected_layers([vf])
        vc2(imf, "split-new")
        p0 = px(vf)
        vc2(imf, "select-all")
        moved = vc2(imf, "drag-sim:1.3:0.7:30")
        p1 = px(vf)
        x1 = vx2(vf)
        u = vc2(imf, "bench-undo")
        p2 = px(vf)
        report(u and p2 == p0, "3.29.2 annuler (copie de l'arbre) : pixels d'origine",
               "annulé=%s" % u)
        rr = vc2(imf, "bench-redo")
        p3 = px(vf)
        report(rr and p3 == p1, "3.29.2 rétablir : pixels après le glisser", "rétabli=%s" % rr)
        run("chopgimp-vobjects-set-xml", layer=vf, xml=x1)
        p1b = px(vf)
        report(moved and p1 == p1b and p1 != p0,
               "3.29.2 glisser par caches : rendu final identique à un rendu complet",
               "déplacé=%s identique=%s" % (moved, p1 == p1b))
        pathf = os.path.join(TMP, "perf-3292.xcf")
        os.makedirs(TMP, exist_ok=True)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, imf, Gio.File.new_for_path(pathf), None)
        imf2 = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(pathf))
        lf2 = [l for l in imf2.get_layers() if l.get_name() == vf.get_name()]
        report(bool(lf2) and px(lf2[0]) == p3 and vx2(lf2[0]).count("<path") == x1.count("<path"),
               "3.29.2 XCF rouvert sans rendu de l'ancien tracé : mêmes pixels, mêmes objets")
        imf2.delete()
        imf.delete()
    except Exception:
        report(False, "3.29.2", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.29.3 : nettoyage et sélection par couleur (Illustrator)
    try:
        im14 = Gimp.Image.new(300, 300, Gimp.ImageBaseType.RGB)
        b14 = Gimp.Layer.new(im14, "Fond", 300, 300, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
        im14.insert_layer(b14, None, 0)
        p14 = Gimp.Path.new(im14, "Formes")
        im14.insert_path(p14, None, 0)
        for x0, y0, w in ((20, 20, 80), (120, 20, 80), (20, 150, 80), (250, 250, 4)):
            st = p14.bezier_stroke_new_moveto(x0, y0)
            for x, y in ((x0 + w, y0), (x0 + w, y0 + w), (x0, y0 + w)):
                p14.bezier_stroke_lineto(st, x, y)
            p14.stroke_close(st)
        vl14 = Gimp.VectorLayer.new(im14, p14)
        im14.insert_layer(vl14, None, 0)
        vl14.set_enable_fill(True); vl14.set_enable_stroke(False)
        vl14.refresh()
        im14.set_selected_layers([vl14])
        run("chopgimp-vobjects-command", image=im14, command="split-new")

        def vx14():
            r = run("chopgimp-vobjects-get-xml", layer=vl14)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        n0 = vx14().count("<path ")
        r = run("chopgimp-vobjects-command", image=im14, command="delete-smaller:100")
        n1 = vx14().count("<path ")
        report(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and n0 == 4 and n1 == 3,
               "Supprimer les petits objets (côté < 10 px)", "%d → %d objets" % (n0, n1))
        run("chopgimp-vobjects-command", image=im14, command="select-at:60:60")
        r = run("chopgimp-vobjects-command", image=im14, command="select-same-fill")
        report(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS,
               "Sélectionner > Même couleur de fond")
        r = run("chopgimp-vobjects-command", image=im14, command="select-next-above")
        report(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS,
               "Objet suivant dessus (Ctrl+Alt+])")
        r = run("chopgimp-vobjects-command", image=im14, command="simplify:1.5")
        report(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and
               vx14().count("<path ") == 3, "Simplifier (sans perte d'objet)")
        r = run("chopgimp-vobjects-command", image=im14, command="fill-holes:100")
        report(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS,
               "Remplir les petits trous")
        # 3.29.3 (suite) : aperçu de Simplifier annulé, Couleurs du dessin
        import re
        x_before = vx14()
        r = run("chopgimp-vobjects-command", image=im14, command="simplify-preview:30")
        report(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and vx14() == x_before,
               "Simplifier : aperçu en direct puis Annuler (tracés d'origine rendus)")
        xr = re.sub(r'<fill type="color" color="[^"]*"', '<fill type="color" color="1 0 0 1"', vx14())
        run("chopgimp-vobjects-set-xml", layer=vl14, xml=xr)
        r = run("chopgimp-vobjects-command", image=im14, command="replace-color:ff0000ff:00ff00")
        xr2 = vx14()
        report(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1) and
               'color="0 1 0 1"' in xr2 and 'color="1 0 0 1"' not in xr2,
               "Couleurs du dessin : une couleur remplacée partout")
        r = run("chopgimp-vobjects-command", image=im14, command="merge-same-color")
        n2 = vx14().count("<path ")
        report(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and n2 == 1,
               "Fusionner les formes de même couleur", "%d objet(s)" % n2)
        im14.delete()

        # filet : tangentes (lignes courbes) et export SVG en <meshgradient>
        im15 = Gimp.Image.new(200, 200, Gimp.ImageBaseType.RGB)
        p15 = Gimp.Path.new(im15, "Carré")
        im15.insert_path(p15, None, 0)
        st = p15.bezier_stroke_new_moveto(20, 20)
        for x, y in ((180, 20), (180, 180), (20, 180)):
            p15.bezier_stroke_lineto(st, x, y)
        p15.stroke_close(st)
        st = p15.bezier_stroke_new_moveto(185, 185)
        for x, y in ((195, 185), (195, 195), (185, 195)):
            p15.bezier_stroke_lineto(st, x, y)
        p15.stroke_close(st)
        vl15 = Gimp.VectorLayer.new(im15, p15)
        im15.insert_layer(vl15, None, 0)
        vl15.set_enable_fill(True); vl15.set_enable_stroke(False)
        vl15.refresh()
        im15.set_selected_layers([vl15])

        def c15(c):
            r = run("chopgimp-vobjects-command", image=im15, command=c)
            return bool(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1))

        def px15():
            b = vl15.get_buffer()
            e = b.get_extent()
            return bytes(b.get(e, 1.0, "R'G'B'A u8", Gegl.AbyssPolicy.NONE))

        c15("split-new")
        c15("select-at:100:100")
        c15("mesh-make:2:2:1:0.9")
        x15 = run("chopgimp-vobjects-get-xml", layer=vl15).index(1)
        m15 = re.search(r'material="([^"]*)"', x15)
        ok_t = False
        if m15:
            nodes = m15.group(1).split(";")
            if len(nodes) == 10:
                # nœud central rouge : la courbure des lignes se voit
                nodes[5] = ",".join(nodes[5].split(",")[:2] + ["#ff0000ff"])
                x15a = x15.replace(m15.group(1), ";".join(nodes))
                run("chopgimp-vobjects-set-xml", layer=vl15, xml=x15a)
                q0 = px15()
                x15, m15 = x15a, re.search(r'material="([^"]*)"', x15a)
                nodes[5] = ",".join(nodes[5].split(",")[:3] + ["0.15", "0.1", "0", "0"])
                x15b = x15.replace(m15.group(1), ";".join(nodes))
                run("chopgimp-vobjects-set-xml", layer=vl15, xml=x15b)
                x15c = run("chopgimp-vobjects-get-xml", layer=vl15).index(1)
                ok_t = px15() != q0 and ",0.15,0.1,0,0" in x15c
        report(ok_t, "Filet : tangentes d'un nœud (lignes courbes, gardées dans le XML)")
        out15 = os.path.join(TMP, "filet-3293.svg")
        os.makedirs(TMP, exist_ok=True)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, im15, Gio.File.new_for_path(out15), None)
        t15 = open(out15, encoding="utf-8").read()
        report("<meshgradient" in t15 and t15.count("<meshpatch>") == 4 and "url(#" in t15,
               "Export SVG du filet en <meshgradient> (couleur de repli)",
               "%d meshpatch" % t15.count("<meshpatch>"))
        im15.delete()

        tr = open(os.path.join(Gimp.sysconf_directory(), "toolrc")).read()
        pos = [tr.find('"gimp-%s-tool"' % t) for t in ("direct-select", "path", "vpencil", "shape",
                                                       "shape-builder", "width", "vscissors", "vmesh", "text")]
        report(all(p >= 0 for p in pos) and pos == sorted(pos),
               "Boîte à outils : bloc vectoriel rangé par intention", "positions : %s" % pos)
    except Exception:
        report(False, "3.29.3", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.29.5 : finitions vectorielles (objet clé automatique, transitions
    # de groupes / orientées / tracé de base, dégradé libre en lignes,
    # dégradé en travers d'un contour à profil, peinture dynamique incrémentale)
    try:
        import re as re16

        def vx16(layer):
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        def scene16(w, h, shapes, fill=True, stroke=True, sw=2):
            im = Gimp.Image.new(w, h, Gimp.ImageBaseType.RGB)
            pa = Gimp.Path.new(im, "Formes")
            im.insert_path(pa, None, 0)
            for pts, closed in shapes:
                st = pa.bezier_stroke_new_moveto(*pts[0])
                for x, y in pts[1:]:
                    pa.bezier_stroke_lineto(st, x, y)
                if closed:
                    pa.stroke_close(st)
            vl = Gimp.VectorLayer.new(im, pa)
            im.insert_layer(vl, None, 0)
            vl.set_enable_fill(fill); vl.set_enable_stroke(stroke); vl.set_stroke_width(sw)
            vl.refresh()
            im.set_selected_layers([vl])
            def c(cmd):
                r = run("chopgimp-vobjects-command", image=im, command=cmd)
                return bool(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1))
            c("split-new")
            return im, vl, c

        def sq(x, y, s):
            return ([(x, y), (x + s, y), (x + s, y + s), (x, y + s)], True)

        def alpha16(layer, x, y):
            ox, oy = layer.get_offsets()[1:]
            if x < ox or y < oy or x >= ox + layer.get_width() or y >= oy + layer.get_height():
                return 0
            b = layer.get_buffer()
            return bytes(b.get(Gegl.Rectangle.new(x - ox, y - oy, 1, 1), 1.0,
                               "R'G'B'A u8", Gegl.AbyssPolicy.NONE))[3]

        def pixels16(layer):
            b = layer.get_buffer()
            return bytes(b.get(b.get_extent(), 1.0, "R'G'B'A u8", Gegl.AbyssPolicy.NONE))

        # objet clé automatique : « Aligner sur : l'objet clé » sans objet
        # clé = l'objet du dessus (ici le second carré, à x = 100)
        im, vl, c = scene16(300, 200, [sq(20, 20, 40), sq(100, 100, 60)])
        c("select-all"); c("key-none"); c("align-to:key")
        ok_al = c("align-left")
        c("align-to:selection")
        report(ok_al and alpha16(vl, 30, 40) == 0 and alpha16(vl, 110, 40) > 0,
               "Aligner sur l'objet clé sans objet clé : l'objet du dessus sert de clé",
               "alpha (30,40)=%d (110,40)=%d" % (alpha16(vl, 30, 40), alpha16(vl, 110, 40)))
        im.delete()

        # transition entre deux groupes (2 formes chacun) : étapes = groupes
        im, vl, c = scene16(400, 300, [sq(20, 20, 30), sq(60, 20, 30),
                                       sq(300, 200, 30), sq(340, 200, 30)])
        c("select-at:35:35"); c("select-add-at:75:35"); c("group")
        c("select-at:315:215"); c("select-add-at:355:215"); c("group")
        c("select-at:35:35"); c("select-add-at:315:215")
        ok_bm = c("blend-make")
        ok_bs = c("blend-steps:3")
        x = vx16(vl)
        steps = re16.findall(r'<group [^>]*blend="step"', x)
        report(ok_bm and ok_bs and len(steps) == 3 and x.count("<path ") == 4 + 3 * 2,
               "Transition : un groupe sert d'objet clé (étapes = groupes interpolés)",
               "%d étapes-groupes, %d tracés" % (len(steps), x.count("<path ")))
        im.delete()

        # tracé de base : les objets clés vont sur le tracé ; orienter le
        # long du tracé fait tourner les étapes
        im, vl, c = scene16(400, 300, [sq(20, 100, 40), sq(320, 100, 40),
                                       ([(100, 250), (200, 60), (300, 250)], False)])
        c("select-at:25:105"); c("select-add-at:355:105"); c("blend-make")
        c("blend-steps:3")
        c("select-at:25:105"); c("select-add-at:200:60")
        ok_sp = c("blend-spine")
        a_old, a_new = alpha16(vl, 40, 120), alpha16(vl, 100, 250)
        report(ok_sp and a_old == 0 and a_new > 0,
               "Transition : le tracé de base déplace les objets clés",
               "alpha ancien centre %d, début du tracé %d" % (a_old, a_new))
        c("select-at:100:250")
        x0 = vx16(vl)
        ok_or = c("blend-steps:3:1")
        x1 = vx16(vl)
        d0 = re16.findall(r'blend="step"[^>]*d="([^"]*)"', x0)
        d1 = re16.findall(r'blend="step"[^>]*d="([^"]*)"', x1)
        report(ok_or and "orient=path" in x1 and len(d1) == 3 and d0 != d1,
               "Transition : « orienter le long du tracé » fait tourner les étapes")
        im.delete()

        # dégradé libre : mode Lignes (couleurs le long de la ligne)
        im, vl, c = scene16(200, 200, [sq(20, 20, 160)], stroke=False)
        c("select-at:100:100"); c("freeform-make")
        x = vx16(vl)
        pts = "points;0.1,0.5,#ff0000ff;0.9,0.5,#0000ffff;0.5,0.15,#00ff00ff"
        xa = re16.sub(r'material="points[^"]*"', 'material="%s"' % pts, x)
        run("chopgimp-vobjects-set-xml", layer=vl, xml=xa)
        qa = pixels16(vl)
        xb = re16.sub(r'material="points[^"]*"', 'material="%s"' % pts.replace("#0000ffff", "#0000ffff,l"), x)
        run("chopgimp-vobjects-set-xml", layer=vl, xml=xb)
        qb = pixels16(vl)
        report("#0000ffff,l" in vx16(vl) and qa != qb,
               "Dégradé libre : mode Lignes (gardé dans le XML, rendu différent)")
        im.delete()

        # dégradé en travers d'un contour à profil : épaisseur locale
        im, vl, c = scene16(300, 120, [([(20, 60), (280, 60)], False)], fill=False, sw=40)
        c("select-all"); c("stroke-gradient:2"); c("width-profile:taper-end")
        x = vx16(vl)
        m = re16.search(r'<stroke ([^>]*?)/>', x)
        ok_x = False
        if m:
            attrs = re16.sub(r'(type|color)="[^"]*"\s*', '', m.group(1))
            xs = x.replace(m.group(0), '<stroke type="linear" x1="0" y1="0" x2="1" y2="0" %s>'
                           '<stop offset="0" color="0 0 0 1"/><stop offset="1" color="1 1 1 1"/>'
                           '</stroke>' % attrs)
            run("chopgimp-vobjects-set-xml", layer=vl, xml=xs)
            qa = pixels16(vl)
            os.environ["CHOPGIMP_NO_LOCAL_ACROSS"] = "1"
            run("chopgimp-vobjects-set-xml", layer=vl, xml=xs)
            qb = pixels16(vl)
            del os.environ["CHOPGIMP_NO_LOCAL_ACROSS"]
            ok_x = 'stroke-gradient="2"' in xs and qa != qb
        report(ok_x, "Dégradé en travers d'un contour à profil : il suit l'épaisseur locale")
        im.delete()

        # peinture dynamique : recalcul incrémental (zones retrouvées par
        # leur forme), couleurs gardées, plus rapide
        lines = [([(10 + 12 * i, 5), (10 + 12 * i, 395)], False) for i in range(30)] + \
                [([(5, 10 + 12 * i), (395, 10 + 12 * i)], False) for i in range(30)]
        im, vl, c = scene16(400, 400, lines, fill=False, sw=1)
        c("select-all")
        ok_lm = c("livepaint-make")
        c("livepaint-fill:16:16:#ff0000")
        t0 = time.time(); c("livepaint-gap:0.5"); t_inc = time.time() - t0
        x_inc = vx16(vl)
        os.environ["CHOPGIMP_LP_NO_INCREMENTAL"] = "1"
        t0 = time.time(); c("livepaint-gap:0.25"); t_full = time.time() - t0
        del os.environ["CHOPGIMP_LP_NO_INCREMENTAL"]
        report(ok_lm and x_inc.count('color="1 0 0 1"') >= 1 and t_inc < t_full,
               "Peinture dynamique : recalcul incrémental (couleur gardée, plus rapide)",
               "%.2f s au lieu de %.2f s, %d zones" % (t_inc, t_full, x_inc.count('livepaint="face"')))
        im.delete()
    except Exception:
        report(False, "3.29.5", traceback.format_exc().replace("\n", " | ")[:400])

    # 3.29.6 : performance complète (calques 16 / 32 bits en flottant,
    # rastérisation parallèle étendue, annulation partielle)
    try:
        import random as _r

        def vx17(layer):
            r = run("chopgimp-vobjects-get-xml", layer=layer)
            return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""

        def px17(layer):
            b = layer.get_buffer()
            e = b.get_extent()
            return (layer.get_offsets()[1:], e.width, e.height,
                    bytes(b.get(e, 1.0, "R'G'B'A u8", Gegl.AbyssPolicy.NONE)))

        def scene17(w, h, n, precision=None, closed=True, seed=5):
            if precision is None:
                im = Gimp.Image.new(w, h, Gimp.ImageBaseType.RGB)
            else:
                im = Gimp.Image.new_with_precision(w, h, Gimp.ImageBaseType.RGB, precision)
            pa = Gimp.Path.new(im, "Formes")
            im.insert_path(pa, None, 0)
            rnd = _r.Random(seed)
            for i in range(n):
                x, y = rnd.uniform(10, w - 90), rnd.uniform(10, h - 90)
                sid = pa.bezier_stroke_new_moveto(x, y)
                pa.bezier_stroke_lineto(sid, x + rnd.uniform(20, 80), y + rnd.uniform(-5, 5))
                pa.bezier_stroke_lineto(sid, x + rnd.uniform(0, 40), y + rnd.uniform(20, 80))
                if closed:
                    pa.stroke_close(sid)
            vl = Gimp.VectorLayer.new(im, pa)
            im.insert_layer(vl, None, 0)
            vl.set_enable_fill(closed); vl.set_enable_stroke(True); vl.set_stroke_width(3)
            vl.refresh()
            im.set_selected_layers([vl])
            def c(cmd):
                r = run("chopgimp-vobjects-command", image=im, command=cmd)
                return bool(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1))
            c("split-new")
            return im, vl, c

        # calque 16 bits : même rendu (à 1 près en 8 bits) que le calque 8 bits
        im8, v8, c8 = scene17(300, 300, 30)
        x8 = vx17(v8)
        im16, v16, c16 = scene17(300, 300, 30, Gimp.Precision.U16_NON_LINEAR)
        run("chopgimp-vobjects-set-xml", layer=v16, xml=x8)
        a, b = px17(v8), px17(v16)
        dmax = max((abs(p - q) for p, q in zip(a[3], b[3])), default=999) if a[:3] == b[:3] else 999
        report(dmax <= 1 and any(a[3][3::4]),
               "3.29.6 calque 16 bits (conversion en flottant) : même rendu que 8 bits",
               "écart max %d" % dmax)
        im16.delete()
        im32, v32, c32 = scene17(300, 300, 30, Gimp.Precision.FLOAT_LINEAR)
        run("chopgimp-vobjects-set-xml", layer=v32, xml=x8)
        b = px17(v32)
        dmax = max((abs(p - q) for p, q in zip(a[3], b[3])), default=999) if a[:3] == b[:3] else 999
        report(dmax <= 1, "3.29.6 calque 32 bits linéaire : même rendu que 8 bits",
               "écart max %d" % dmax)
        im32.delete()
        im8.delete()

        # rastérisation parallèle étendue : flèches + profil + dégradé libre
        # sur 30 objets ; deux rendus complets identiques, rien de vide
        im, vl, c = scene17(400, 400, 30, closed=False)
        c("select-all"); c("width-profile:taper-end")
        x = vx17(vl)
        xa = x.replace("<stroke ", '<stroke arrow-end="triangle" ') if 'arrow-end=' not in x else x
        run("chopgimp-vobjects-set-xml", layer=vl, xml=xa)
        q1 = px17(vl)
        run("chopgimp-vobjects-set-xml", layer=vl, xml=xa)
        q2 = px17(vl)
        report(q1 == q2 and any(q1[3][3::4]),
               "3.29.6 rastérisation parallèle (profils, flèches) : rendu stable",
               "%d x %d" % (q1[1], q1[2]))
        im.delete()
        im, vl, c = scene17(400, 400, 20)
        c("select-all"); ok_ff = c("freeform-make")
        q1 = px17(vl)
        run("chopgimp-vobjects-set-xml", layer=vl, xml=vx17(vl))
        q2 = px17(vl)
        report(ok_ff and q1 == q2,
               "3.29.6 rastérisation parallèle (dégradés libres) : identique à un rendu complet")
        im.delete()

        # annulation partielle : deux changements, annuler / rétablir ;
        # objets et pixels exacts à chaque étape
        im, vl, c = scene17(400, 400, 40)
        x0, p0 = vx17(vl), px17(vl)
        c("select-all"); c("drag-sim:5:3:4")
        x1, p1 = vx17(vl), px17(vl)
        c("select-all"); c("hide")
        x2, p2 = vx17(vl), px17(vl)
        u1 = c("bench-undo"); xu1, pu1 = vx17(vl), px17(vl)
        u2 = c("bench-undo"); xu2, pu2 = vx17(vl), px17(vl)
        r1 = c("bench-redo"); xr1, pr1 = vx17(vl), px17(vl)
        r2 = c("bench-redo"); xr2, pr2 = vx17(vl), px17(vl)
        ok = (u1 and u2 and r1 and r2 and x0 != x1 != x2 and
              xu1 == x1 and pu1 == p1 and xu2 == x0 and pu2 == p0 and
              xr1 == x1 and pr1 == p1 and xr2 == x2 and pr2 == p2)
        report(ok, "3.29.6 annulation partielle : annuler / rétablir exacts (objets et pixels)",
               "annulé %s %s, rétabli %s %s" % (u1, u2, r1, r2))
        # un nouveau changement après une annulation, puis annuler
        c("bench-undo"); c("bench-undo")
        c("select-all"); c("drag-sim:-7:2:3")
        x3 = vx17(vl)
        u3 = c("bench-undo")
        report(u3 and vx17(vl) == x0 and px17(vl) == p0 and x3 != x0,
               "3.29.6 annulation partielle : nouveau changement après annuler")
        im.delete()
    except Exception:
        report(False, "3.29.6", traceback.format_exc().replace("\n", " | ")[:400])

    # 4. Réglages d'usine présents (thème, icônes, menus, raccourcis)
    data = Gimp.data_directory()
    sysconf = Gimp.sysconf_directory()
    for label, path in [("Thème ChopGimp (sombre)", os.path.join(data, "themes", "ChopGimp", "gimp-dark.css")),
                        ("Thème ChopGimp (clair)", os.path.join(data, "themes", "ChopGimp", "gimp-light.css")),
                        ("Thème : palette Krita", os.path.join(data, "themes", "ChopGimp", "palette-krita.css")),
                        ("Ancien nom PS-Dark", os.path.join(data, "themes", "PS-Dark", "gimp-dark.css")),
                        ("Police Inter", "/app/share/fonts/chopgimp/Inter-Regular.ttf"),
                        ("Préréglage Aquarelle (texture de papier)",
                         os.path.join(data, "tool-presets", "PhotoGIMP", "Peinture-Aquarelle.gtp")),
                        ("Préréglage pinceau mélangeur",
                         os.path.join(data, "tool-presets", "PhotoGIMP", "Melangeur-Humide.gtp")),
                        ("Icônes PS-Line", os.path.join(data, "icons", "PS-Line", "index.theme")),
                        ("Menus Photoshop", os.path.join(data, "menus", "layers-menu.ui")),
                        ("Raccourcis d'usine", os.path.join(sysconf, "shortcutsrc")),
                        ("Options d'outils d'usine", os.path.join(sysconf, "tool-options", "gimp-move-tool"))]:
        report(os.path.exists(path), label, path)
except Exception:
    report(False, "Exception", traceback.format_exc().replace("\n", " | ")[:400])

open(OUT, "w").write("\n".join(results) + "\n")
pdb.lookup_procedure("gimp-quit").run(pdb.lookup_procedure("gimp-quit").create_config())

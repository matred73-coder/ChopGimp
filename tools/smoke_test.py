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

        im, ls = load_v("test.pdf")
        by = {l.get_name(): l for l in ls}
        vec = [l for l in ls if isinstance(l, Gimp.VectorLayer)]
        report(len(vec) >= 3 and "Bleu" in by and by["Bleu"].get_visible() and
               "Vert" in by and not by["Vert"].get_visible(),
               "PDF : calques OCG en groupes, formes vectorielles", "%d formes" % len(vec))
        report(isinstance(by.get("Bonjour PDF"), Gimp.TextLayer), "PDF : texte modifiable")
        report(any(n.startswith("Image ") for n in by) and any(n.startswith("Dégradé") for n in by),
               "PDF : image placée et dégradé en pixels")
        im, ls = load_v("test.svg")
        by = {l.get_name(): l for l in ls}
        report("Fond" in by and "Dessin" in by and "Caché" in by and not by["Caché"].get_visible() and
               isinstance(by.get("Salut SVG"), Gimp.TextLayer),
               "SVG : calques Inkscape et texte modifiable")
        im, ls = load_v("test.eps")
        by = {l.get_name(): l for l in ls}
        report(isinstance(by.get("Bonjour EPS"), Gimp.TextLayer) and
               len([l for l in ls if isinstance(l, Gimp.VectorLayer)]) >= 2,
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

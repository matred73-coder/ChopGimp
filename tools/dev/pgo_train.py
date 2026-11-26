# ChopGimp — entraînement PGO (optimisation guidée par profil)
#
# Exécuté par gimp-console instrumentée pendant « make build PGO=1 »
# (voir pgo_gimp() dans tools/make_manifest.py) :
#   gimp-console-3.2 -i --quit --batch-interpreter=python-fu-eval \
#     -b "exec(open('pgo_train.py').read())"
# Peut aussi se lancer sur ChopGimp installé pour vérifier qu'il tourne
# (PGO_DIR = dossier de travail, défaut /tmp).
#
# Travail représentatif des usages lents : grands calques en 8 bits non
# linéaires (et un passage en flottant), effets non destructifs (ombre
# portée, contour, flou), modes de fusion, peinture (pinceau, gomme,
# aérographe, doigt), transformations, sélection d'après l'alpha, rendu
# complet de l'image (aplatissement), enregistrement et ouverture XCF.
#
# gimp-console n'a pas d'affichage : le code de l'interface n'est pas
# entraîné, mais ce qui le fait ramer l'est par des appels équivalents :
#   - projection (rendu de l'image affichée) : copie du visible, vignettes,
#     pipette sur l'image fusionnée ; modes de fusion un par un, groupes ;
#   - contour de sélection (gimpboundary, fourmis) : tracé de la sélection,
#     sélection vers chemin, bordure, agrandir / réduire ;
#   - réglages (courbes, niveaux, teinte…) et filtres fusionnés
#     (gimp-drawable-merge-filters), masques, texte, remplissages.
#
# Banc de mesure : chaque étape écrit sa durée dans $PGO_DIR/pgo_train.log
# (« Δ s ») ; PGO_SIZE change la taille de l'image (défaut 3000).
import os
import time

from gi.repository import Gimp, Gio, Gegl

W = H = int(os.environ.get("PGO_SIZE", "3000"))
DIR = os.environ.get("PGO_DIR", "/tmp")
LOG = open(os.path.join(DIR, "pgo_train.log"), "w")
T0 = time.time()


def log(msg, dt=None):
    LOG.write("%6.1f s  %s%s\n" % (time.time() - T0, msg, "" if dt is None else "  Δ %.3f s" % dt))
    LOG.flush()


def step(name, fn, *args):
    t = time.time()
    try:
        fn(*args)
        log(name, time.time() - t)
    except Exception as e:          # une étape ratée ne doit pas arrêter l'entraînement
        log("%s : ÉCHEC %s" % (name, e))


def color(r, g, b, a=1.0):
    c = Gegl.Color.new("black")
    c.set_rgba(r, g, b, a)
    return c


def filt(drawable, op, merge=False, **props):
    f = Gimp.DrawableFilter.new(drawable, op, "")
    cfg = f.get_config()
    for k, v in props.items():
        cfg.set_property(k, v)
    f.update()
    if merge:
        drawable.merge_filter(f)
    else:
        drawable.append_filter(f)
    return f


def zigzag(x0, y0, w, h, n):
    pts = []
    for i in range(n + 1):
        pts += [x0 + w * i / n, y0 + (h if i % 2 else 0)]
    return pts


def build(img):
    bg = Gimp.Layer.new(img, "fond", W, H, Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    img.insert_layer(bg, None, 0)
    Gimp.context_set_foreground(color(0.9, 0.3, 0.1))
    Gimp.context_set_background(color(0.1, 0.2, 0.8))
    bg.edit_gradient_fill(Gimp.GradientType.LINEAR, 0, False, 1, 0, True, 0, 0, W, H)
    filt(bg, "gegl:noise-rgb", merge=True)
    layers = [bg]
    modes = [Gimp.LayerMode.NORMAL, Gimp.LayerMode.MULTIPLY, Gimp.LayerMode.SCREEN,
             Gimp.LayerMode.OVERLAY, Gimp.LayerMode.SOFTLIGHT]
    for i, mode in enumerate(modes):
        l = Gimp.Layer.new(img, "forme %d" % i, W - 200 * i, H - 150 * i,
                           Gimp.ImageType.RGBA_IMAGE, 90, mode)
        img.insert_layer(l, None, 0)
        l.set_offsets(100 * i, 75 * i)
        img.select_ellipse(Gimp.ChannelOps.REPLACE, 300 + 150 * i, 300 + 100 * i, 1600, 1400)
        Gimp.context_set_foreground(color(0.2 * i, 0.8 - 0.1 * i, 0.5))
        l.edit_fill(Gimp.FillType.FOREGROUND)
        Gimp.Selection.none(img)
        layers.append(l)
    return layers


def effects(layers):
    for i, l in enumerate(layers[1:]):
        filt(l, "gegl:dropshadow", x=20.0, y=20.0, radius=10.0 + 5 * i)
        if i % 2 == 0:
            filt(l, "chopgimp:stroke")
        if i == 3:
            filt(l, "gegl:gaussian-blur", std_dev_x=8.0, std_dev_y=8.0)


def render(img):
    dup = img.duplicate()
    dup.flatten()
    dup.delete()


def paint(img, layers):
    l = layers[2]
    img.set_selected_layers([l])
    for size in (20, 80, 250):
        Gimp.context_set_brush_size(size)
        Gimp.paintbrush_default(l, zigzag(200, 400, 2500, 2000, 40))
        Gimp.airbrush_default(l, zigzag(300, 300, 2000, 1500, 20))
        Gimp.eraser_default(l, zigzag(100, 1500, 2600, 800, 30))
        Gimp.smudge_default(l, zigzag(400, 800, 1500, 900, 15))
    Gimp.context_set_brush_size(40)
    Gimp.pencil(layers[0], zigzag(0, 0, W, H, 60))


def transform(img, layers):
    l = layers[3]
    l.scale(int(l.get_width() * 0.8), int(l.get_height() * 0.8), True)
    l.transform_rotate(0.3, True, 0, 0)
    img.select_item(Gimp.ChannelOps.REPLACE, layers[4])
    Gimp.Selection.grow(img, 20)
    Gimp.Selection.feather(img, 30)
    layers[0].edit_fill(Gimp.FillType.BACKGROUND)
    Gimp.Selection.none(img)


def xcf(img):
    f = Gio.File.new_for_path(os.path.join(DIR, "pgo_train.xcf"))
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, img, f, None)
    back = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, f)
    render(back)
    back.delete()
    os.unlink(f.get_path())


def float_pass(img):
    dup = img.duplicate()
    dup.convert_precision(Gimp.Precision.FLOAT_LINEAR)
    dup.flatten()
    dup.delete()


ALL_MODES = [getattr(Gimp.LayerMode, n) for n in (
    "NORMAL", "DISSOLVE", "MULTIPLY", "SCREEN", "OVERLAY", "SOFTLIGHT", "HARDLIGHT", "DODGE",
    "BURN", "DIFFERENCE", "ADDITION", "SUBTRACT", "DARKEN_ONLY", "LIGHTEN_ONLY",
    "LINEAR_LIGHT", "VIVID_LIGHT", "PIN_LIGHT", "HARD_MIX", "EXCLUSION", "LINEAR_BURN",
    "DIVIDE", "HSV_HUE", "HSV_SATURATION", "HSL_COLOR", "HSV_VALUE", "LCH_HUE", "LCH_COLOR",
    "LCH_LIGHTNESS", "LUMINANCE", "GRAIN_MERGE", "GRAIN_EXTRACT", "DARKER_COLOR",
    "LIGHTER_COLOR",)
             if hasattr(Gimp.LayerMode, n)]


def projection(img):
    """Rendu de la projection (ce que l'affichage demande) : copie du
    visible, vignettes de l'image et des calques, pipette fusionnée."""
    Gimp.edit_copy_visible(img)
    img.get_thumbnail(256, 256, Gimp.PixbufTransparency.KEEP_ALPHA)
    for l in img.get_layers():
        l.get_thumbnail(128, 128, Gimp.PixbufTransparency.KEEP_ALPHA)
    for i in range(20):
        img.pick_color([img.get_layers()[0]], 100 + i * 130, 200 + i * 120, True, True, 8.0)


def modes(img, layers):
    """Tous les modes de fusion, l'image étant recomposée à chaque fois."""
    l = layers[1]
    old = l.get_mode()
    for mode in ALL_MODES:
        try:
            l.set_mode(mode)
        except Exception:
            continue
        Gimp.edit_copy_visible(img)
    l.set_mode(old)


def groups(img, layers):
    """Groupe en passage (pass-through) et groupe isolé avec effet."""
    g = Gimp.GroupLayer.new(img, "groupe")
    img.insert_layer(g, None, 0)
    for i, src in enumerate(layers[1:3]):
        c = src.copy()
        img.insert_layer(c, g, 0)
        c.set_offsets(300 * i, 200 * i)
    g.set_mode(Gimp.LayerMode.PASS_THROUGH)
    Gimp.edit_copy_visible(img)
    g.set_mode(Gimp.LayerMode.NORMAL)
    filt(g, "gegl:dropshadow", x=15.0, y=15.0, radius=12.0)
    Gimp.edit_copy_visible(img)
    g.set_opacity(60.0)
    render(img)
    img.remove_layer(g)


def adjust(img):
    """Réglages appliqués aux pixels (opérations gimp:*)."""
    l = Gimp.Layer.new_from_visible(img, img, "réglages")
    img.insert_layer(l, None, 0)
    l.curves_spline(Gimp.HistogramChannel.VALUE, [0.0, 0.0, 0.3, 0.2, 0.7, 0.85, 1.0, 1.0])
    l.levels(Gimp.HistogramChannel.VALUE, 0.05, 0.95, True, 1.2, 0.0, 1.0, True)
    l.hue_saturation(Gimp.HueRange.ALL, 15.0, 0.0, 20.0, 0.0)
    l.brightness_contrast(0.1, 0.2)
    l.color_balance(Gimp.TransferMode.MIDTONES, True, 10.0, -5.0, 5.0)
    l.desaturate(Gimp.DesaturateMode.LUMINANCE)
    l.invert(False)
    l.posterize(8)
    l.histogram(Gimp.HistogramChannel.VALUE, 0.0, 1.0)
    l.threshold(Gimp.HistogramChannel.VALUE, 0.4, 1.0)
    img.remove_layer(l)


def merged_filters(img, layers):
    """Filtres non destructifs puis fusionnés (gimp-drawable-merge-filters),
    comme « Pixelliser le style de calque »."""
    l = layers[4].copy()
    img.insert_layer(l, None, 0)
    filt(l, "gegl:dropshadow", x=10.0, y=10.0, radius=20.0)
    filt(l, "chopgimp:stroke")
    filt(l, "gegl:inner-glow")
    filt(l, "gegl:bevel")
    filt(l, "gegl:unsharp-mask")
    filt(l, "gimp:curves")
    Gimp.edit_copy_visible(img)
    l.merge_filters()
    img.remove_layer(l)


def masks(img, layers):
    l = layers[2]
    m = l.create_mask(Gimp.AddMaskType.WHITE)
    l.add_mask(m)
    Gimp.context_set_foreground(color(0, 0, 0))
    Gimp.context_set_brush_size(150)
    Gimp.paintbrush_default(m, zigzag(200, 200, 2400, 2400, 20))
    m.edit_gradient_fill(Gimp.GradientType.RADIAL, 0, False, 1, 0, True, W / 2, H / 2, W, H)
    Gimp.edit_copy_visible(img)
    l.remove_mask(Gimp.MaskApplyMode.APPLY)


def selection(img, layers):
    """Sélections et leur contour (gimpboundary)."""
    l = layers[0]
    img.select_ellipse(Gimp.ChannelOps.REPLACE, 200, 200, W - 600, H - 700)
    img.select_rectangle(Gimp.ChannelOps.SUBTRACT, W / 3, H / 3, W / 4, H / 5)
    img.select_round_rectangle(Gimp.ChannelOps.ADD, 100, H / 2, W / 2, H / 3, 80, 80)
    img.select_polygon(Gimp.ChannelOps.INTERSECT, zigzag(0, 0, W, H, 25) + [W, H, 0, H])
    Gimp.context_set_brush_size(5)
    l.edit_stroke_selection()
    Gimp.Selection.border(img, 15)
    Gimp.Selection.grow(img, 10)
    Gimp.Selection.shrink(img, 5)
    Gimp.Selection.sharpen(img)
    Gimp.Selection.invert(img)
    Gimp.Selection.invert(img)
    proc = Gimp.get_pdb().lookup_procedure("plug-in-sel2path")
    if proc is not None:
        cfg = proc.create_config()
        cfg.set_property("image", img)
        proc.run(cfg)
    Gimp.Selection.none(img)
    for i, lay in enumerate(layers[1:]):
        img.select_item(Gimp.ChannelOps.REPLACE, lay)
        img.select_contiguous_color(Gimp.ChannelOps.ADD, l, 50 + 400 * i, 60 + 300 * i)
        Gimp.Selection.feather(img, 5.0)
        Gimp.Selection.bounds(img)
    img.select_color(Gimp.ChannelOps.REPLACE, l, color(0.5, 0.3, 0.4))
    Gimp.context_set_feather(False)
    Gimp.Selection.none(img)


def text(img):
    font = Gimp.Font.get_by_name("Sans-serif")
    t = Gimp.TextLayer.new(img, "ChopGimp — entraînement du profil " * 4, font, 140.0, Gimp.Unit.pixel())
    img.insert_layer(t, None, 0)
    t.set_offsets(100, 1200)
    filt(t, "gegl:dropshadow", x=8.0, y=8.0, radius=6.0)
    Gimp.edit_copy_visible(img)
    t.set_text("Autre texte, plus court")
    Gimp.edit_copy_visible(img)
    img.remove_layer(t)


def fills(img, layers):
    l = layers[0]
    for g in (Gimp.GradientType.RADIAL, Gimp.GradientType.CONICAL_SYMMETRIC, Gimp.GradientType.SPIRAL_CLOCKWISE,
              Gimp.GradientType.SHAPEBURST_DIMPLED):
        img.select_ellipse(Gimp.ChannelOps.REPLACE, 500, 500, 1500, 1200)
        l.edit_gradient_fill(g, 0, True, 3, 0.2, True, 800, 800, 1800, 1500)
    Gimp.Selection.none(img)
    l.edit_bucket_fill(Gimp.FillType.FOREGROUND, 1500, 1500)
    l.edit_fill(Gimp.FillType.PATTERN)


def scale(img):
    dup = img.duplicate()
    for interp in (Gimp.InterpolationType.CUBIC, Gimp.InterpolationType.LOHALO, Gimp.InterpolationType.NOHALO):
        Gimp.context_set_interpolation(interp)
        d = dup.duplicate()
        d.scale(W * 2 // 3, H * 2 // 3)
        d.delete()
    dup.get_layers()[0].transform_perspective(0, 0, W, 100, 50, H, W - 200, H - 50)
    dup.rotate(Gimp.RotationType.DEGREES90)
    dup.convert_precision(Gimp.Precision.U16_NON_LINEAR)
    dup.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
    dup.delete()


def vector():
    """4.0.0 : le vectoriel (bench_vector.py en plus court) : vectorisation
    d'une « photo » de taches, sélection, glisser, déplacement, annuler /
    rétablir, recoloration, rendu complet, XCF."""
    import random
    pdb = Gimp.get_pdb()

    def run(proc, **kw):
        p = pdb.lookup_procedure(proc)
        cfg = p.create_config()
        for k, v in kw.items():
            cfg.set_property(k, v)
        return p.run(cfg)

    def cmd(image, c):
        r = run("chopgimp-vobjects-command", image=image, command=c)
        return bool(r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1))

    N = 1200
    image = Gimp.Image.new(N, N, Gimp.ImageBaseType.RGB)
    src = Gimp.Layer.new(image, "Source", N, N, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
    image.insert_layer(src, None, 0)
    Gimp.context_set_background(color(1, 1, 1))
    src.fill(Gimp.FillType.BACKGROUND)
    rnd = random.Random(42)
    for _ in range(300):
        r = rnd.randint(8, 120)
        x, y = rnd.randint(-r, N), rnd.randint(-r, N)
        v = rnd.random()
        Gimp.context_set_foreground(color(v, v * rnd.random(), rnd.random() * 0.6))
        if rnd.random() < 0.5:
            image.select_ellipse(Gimp.ChannelOps.REPLACE, x, y, r * 2, r)
        else:
            image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, r, r * 2)
        src.edit_fill(Gimp.FillType.FOREGROUND)
    Gimp.Selection.none(image)
    res = run("chopgimp-image-trace", drawable=src, options="photo-high",
              **{"selection-only": False, "live": False})
    layer = res.index(1) if res is not None and res.index(0) == Gimp.PDBStatusType.SUCCESS else None
    if layer:
        image.set_selected_layers([layer])
        cmd(image, "select-at:600:600")
        cmd(image, "drag-sim:3:2:30")
        cmd(image, "transform-record:1:0:0:1:5:5")
        cmd(image, "transform-again")
        for _ in range(5):
            cmd(image, "bench-undo")
            cmd(image, "bench-redo")
        cmd(image, "select-all")
        run("chopgimp-vobjects-recolor", image=image, spec="hue=30")
        r = run("chopgimp-vobjects-get-xml", layer=layer)
        if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS:
            run("chopgimp-vobjects-set-xml", layer=layer, xml=r.index(1))
        path = os.path.join(DIR, "pgo-vector.xcf")
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.File.new_for_path(path), None)
        im2 = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(path))
        if im2:
            im2.delete()
    image.delete()


img = Gimp.Image.new(W, H, Gimp.ImageBaseType.RGB)
img.undo_disable()              # comme un script : l'historique n'est pas entraîné
layers = build(img)
log("construction")
step("vectoriel", vector)       # 4.0.0 : en tête, pour qu'il soit toujours entraîné
step("effets", effects, layers)
step("rendu 1", render, img)
step("projection", projection, img)
step("modes de fusion", modes, img, layers)
step("groupes", groups, img, layers)
step("réglages", adjust, img)
step("filtres fusionnés", merged_filters, img, layers)
step("masques", masks, img, layers)
step("sélections", selection, img, layers)
step("texte", text, img)
step("remplissages", fills, img, layers)
step("peinture", paint, img, layers)
step("rendu 2", render, img)
step("transformations", transform, img, layers)
step("rendu 3", render, img)
step("xcf", xcf, img)
step("échelle", scale, img)
step("flottant", float_pass, img)
img.delete()
log("fin")
LOG.close()

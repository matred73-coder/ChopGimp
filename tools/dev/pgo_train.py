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
import os
import time

from gi.repository import Gimp, Gio, Gegl

W = H = 3000
DIR = os.environ.get("PGO_DIR", "/tmp")
LOG = open(os.path.join(DIR, "pgo_train.log"), "w")
T0 = time.time()


def log(msg):
    LOG.write("%6.1f s  %s\n" % (time.time() - T0, msg))
    LOG.flush()


def step(name, fn, *args):
    try:
        fn(*args)
        log(name)
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


img = Gimp.Image.new(W, H, Gimp.ImageBaseType.RGB)
img.undo_disable()              # comme un script : l'historique n'est pas entraîné
layers = build(img)
log("construction")
step("effets", effects, layers)
step("rendu 1", render, img)
step("peinture", paint, img, layers)
step("rendu 2", render, img)
step("transformations", transform, img, layers)
step("rendu 3", render, img)
step("xcf", xcf, img)
step("flottant", float_pass, img)
img.delete()
log("fin")
LOG.close()

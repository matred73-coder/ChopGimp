"""
ChopGimp — banc de performance du vectoriel (3.29.2), exécuté DANS le
paquet par gimp-console (voir tools/dev/bench_vector.sh).

Cas mesurés :
  A. vectorisation lourde : image détaillée 2000 × 2000 (cercles et
     dégradés aléatoires, graine fixe), préréglage « Photo haute fidélité »
  B. 2 000 objets simples dans un calque vectoriel
  C. (3.99.0) le cas A dans une image 16 bits (calque vectoriel 16 bits)
Mesures ajoutées en 3.99.0 : annulation partielle (un seul objet déplacé
puis annulé), rafale de 40 annuler / rétablir (test de charge du rendu
parallèle et de l'annulation partielle : le rendu final doit être
identique au rendu de départ).
Pour chaque cas : get_xml / set_xml, sélection au clic, glisser simulé
(commande « drag-sim », temps par étape = image affichée pendant un
glisser), déplacement non interactif, recoloration, annuler / rétablir,
rendu complet, enregistrement / ouverture XCF.
Résultats : <BENCH_OUT> (lignes « clé<TAB>ms<TAB>détail »).
"""

import os
import random
import re
import time
import traceback

from gi.repository import Gimp, Gegl

OUT = os.environ.get("BENCH_OUT", "/tmp/chopgimp-bench-vector.txt")
TMP = os.environ.get("BENCH_TMP", "/tmp/chopgimp-bench-vector")
os.makedirs(TMP, exist_ok=True)
pdb = Gimp.get_pdb()
lines = []


def out(key, ms, detail=""):
    lines.append("%s\t%.1f\t%s" % (key, ms, detail))
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")


def run(proc, **kw):
    p = pdb.lookup_procedure(proc)
    if p is None:
        return None
    cfg = p.create_config()
    for k, v in kw.items():
        cfg.set_property(k, v)
    return p.run(cfg)


def timed(fn, repeat=1):
    best = None
    res = None
    for _ in range(repeat):
        t = time.perf_counter()
        res = fn()
        dt = (time.perf_counter() - t) * 1000.0
        best = dt if best is None else min(best, dt)
    return best, res


def color(r, g, b):
    c = Gegl.Color.new("black")
    c.set_rgba(r, g, b, 1.0)
    return c


def cmd(image, c):
    r = run("chopgimp-vobjects-command", image=image, command=c)
    return r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS and r.index(1)


def get_xml(layer):
    r = run("chopgimp-vobjects-get-xml", layer=layer)
    return r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else ""


def set_xml(layer, xml):
    run("chopgimp-vobjects-set-xml", layer=layer, xml=xml)


def measure(tag, image, layer, click):
    xml = get_xml(layer)
    out(tag + ".taille_xml_ko", len(xml) / 1024.0, "%d objets (balises path)" % xml.count("<path"))
    out(tag + ".get_xml", timed(lambda: get_xml(layer), 3)[0])
    out(tag + ".set_xml", timed(lambda: set_xml(layer, xml), 2)[0])

    # clic : sélection de l'objet sous le pointeur
    out(tag + ".clic", timed(lambda: cmd(image, "select-at:%d:%d" % click), 5)[0])

    # glisser simulé : 60 étapes de 3 px (une étape = une image)
    ms, ok = timed(lambda: cmd(image, "drag-sim:3:2:60"))
    if ok:
        out(tag + ".glisser_par_image", ms / 60.0, "60 étapes, fin de glisser comprise")
    else:
        out(tag + ".glisser_par_image", -1, "drag-sim absent (avant 3.29.2)")

    # déplacement non interactif (transform-again), puis annuler / rétablir
    cmd(image, "transform-record:1:0:0:1:5:5")
    out(tag + ".deplacement", timed(lambda: cmd(image, "transform-again"), 3)[0])
    ms, ok = timed(lambda: cmd(image, "bench-undo"))
    out(tag + ".annuler", ms if ok else -1, "" if ok else "bench-undo absent")
    ms, ok = timed(lambda: cmd(image, "bench-redo"))
    out(tag + ".retablir", ms if ok else -1, "" if ok else "bench-redo absent")

    # 3.99.0 : annulation partielle (un seul objet modifié) et rafale
    def pixels():
        b = layer.get_buffer()
        return hash(bytes(b.get(b.get_extent(), 1.0, "R'G'B'A u8", Gegl.AbyssPolicy.NONE)))
    if cmd(image, "select-at:%d:%d" % click):
        cmd(image, "transform-record:1:0:0:1:7:3")
        cmd(image, "transform-again")
        ms, ok = timed(lambda: cmd(image, "bench-undo"))
        out(tag + ".annuler_partiel", ms if ok else -1, "un objet déplacé")
        ms, ok = timed(lambda: cmd(image, "bench-redo"))
        out(tag + ".retablir_partiel", ms if ok else -1)
    ref = pixels()
    t = time.perf_counter()
    n_ok = 0
    for i in range(40):
        n_ok += bool(cmd(image, "bench-undo"))
        n_ok += bool(cmd(image, "bench-redo"))
    ms = (time.perf_counter() - t) * 1000.0
    out(tag + ".rafale_40_annuler_retablir", ms,
        "%d/80 réussis, rendu %s" % (n_ok, "identique" if pixels() == ref else "DIFFÉRENT"))

    # recoloration de tout le calque
    cmd(image, "select-all")
    out(tag + ".recolorer", timed(lambda: run("chopgimp-vobjects-recolor", image=image,
                                                 spec="hue=30"))[0])

    # rendu complet (set_xml du même contenu force un rendu de tout)
    out(tag + ".rendu_complet", timed(lambda: set_xml(layer, get_xml(layer)))[0])
    # 4.0.0 : mémoire du cœur (gimp-console, processus parent du greffon)
    # après le rendu complet : caches des objets compris
    try:
        rss = [l for l in open("/proc/%d/status" % os.getppid()) if l.startswith("VmRSS")][0]
        out(tag + ".memoire_mo", int(rss.split()[1]) / 1024.0, "RSS du cœur après rendu complet")
    except Exception:
        pass

    # XCF
    path = os.path.join(TMP, tag + ".xcf")
    from gi.repository import Gio
    gf = Gio.File.new_for_path(path)
    out(tag + ".xcf_enregistrer",
        timed(lambda: Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, gf, None))[0],
        "%d Ko" % (os.path.getsize(path) // 1024 if os.path.exists(path) else -1))
    ms, im2 = timed(lambda: Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, gf))
    out(tag + ".xcf_ouvrir", ms)
    if im2:
        im2.delete()


def case_trace(tag="A", precision=None):
    W = H = 2000
    image = Gimp.Image.new(W, H, Gimp.ImageBaseType.RGB)
    if precision is not None:
        image.convert_precision(precision)
    src = Gimp.Layer.new(image, "Source", W, H, Gimp.ImageType.RGB_IMAGE, 100,
                         Gimp.LayerMode.NORMAL)
    image.insert_layer(src, None, 0)
    Gimp.context_set_background(color(1, 1, 1))
    src.fill(Gimp.FillType.BACKGROUND)
    rnd = random.Random(42)
    for _ in range(700):
        r = rnd.randint(8, 160)
        x, y = rnd.randint(-r, W), rnd.randint(-r, H)
        v = rnd.random()
        Gimp.context_set_foreground(color(v, v * rnd.random(), rnd.random() * 0.6))
        if rnd.random() < 0.5:
            image.select_ellipse(Gimp.ChannelOps.REPLACE, x, y, r * 2, r)
        else:
            image.select_rectangle(Gimp.ChannelOps.REPLACE, x, y, r, r * 2)
        src.edit_fill(Gimp.FillType.FOREGROUND)
    Gimp.Selection.none(image)

    t = time.perf_counter()
    r = run("chopgimp-image-trace", drawable=src, options="photo-high",
            **{"selection-only": False, "live": True})
    ms = (time.perf_counter() - t) * 1000.0
    layer = r.index(1) if r is not None and r.index(0) == Gimp.PDBStatusType.SUCCESS else None
    xml = get_xml(layer) if layer else ""
    out(tag + ".vectoriser", ms, "%d objets, %d Ko de XML, %s" %
        (xml.count("<path"), len(xml) // 1024, image.get_precision().value_nick if layer else ""))
    if layer:
        image.undo_enable()
        measure(tag, image, layer, (1000, 1000))
    image.delete()


def case_simple():
    image = Gimp.Image.new(2000, 2000, Gimp.ImageBaseType.RGB)
    bg = Gimp.Layer.new(image, "Fond", 2000, 2000, Gimp.ImageType.RGB_IMAGE, 100,
                        Gimp.LayerMode.NORMAL)
    image.insert_layer(bg, None, 0)
    rnd = random.Random(7)
    p = Gimp.Path.new(image, "Formes")
    image.insert_path(p, None, 0)
    sid = p.bezier_stroke_new_moveto(10, 10)
    p.bezier_stroke_lineto(sid, 20, 10)
    p.bezier_stroke_lineto(sid, 20, 20)
    p.stroke_close(sid)
    vl = Gimp.VectorLayer.new(image, p)
    image.insert_layer(vl, None, 0)
    base = get_xml(vl)
    i0 = base.index("<path ")
    i1 = base.index("</path>", i0) + len("</path>") if "</path>" in base[i0:] else base.index("/>", i0) + 2
    tmpl = base[i0:i1]
    parts = []
    for i in range(2000):
        x, y = rnd.uniform(0, 1950), rnd.uniform(0, 1950)
        sz = rnd.uniform(8, 50)
        o = re.sub(r' id="\d+"', ' id="%d"' % (i + 1), tmpl, count=1)
        o = re.sub(r' d="[^"]*"', ' d="M %.1f %.1f L %.1f %.1f L %.1f %.1f Z"'
                   % (x, y, x + sz, y, x + sz / 2, y + sz), o, count=1)
        o = re.sub(r' color="[^"]*"', ' color="%.3f %.3f %.3f 1"'
                   % (rnd.random(), rnd.random(), rnd.random()), o, count=1)
        parts.append(o)
    xml = base[:i0] + "".join(parts) + base[i1:]
    xml = re.sub(r' next-id="\d+"', ' next-id="2001"', xml, count=1)
    xml = re.sub(r' selection="[^"]*"', ' selection=""', xml, count=1)
    t = time.perf_counter()
    set_xml(vl, xml)
    out("B.creer_2000", (time.perf_counter() - t) * 1000.0,
        "%d objets relus" % get_xml(vl).count("<path"))
    measure("B", image, vl, (1000, 1000))
    image.delete()


def case_trace16():
    case_trace("C", Gimp.Precision.U16_NON_LINEAR)


for case in (case_simple, case_trace, case_trace16):
    try:
        case()
    except Exception:
        out(case.__name__ + ".erreur", -1, traceback.format_exc().replace("\n", " | ")[:600])

out("fin", 0)

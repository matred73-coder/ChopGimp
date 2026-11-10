"""
PhotoGIMP Pro — banc de test des plug-ins (exécuté DANS gimp-console via
python-fu-eval). Pour chaque procédure : image de test neuve, exécution
non interactive avec les valeurs par défaut, journal JSON-lines.

Variables : PG_PROCS (fichier liste « plugin proc proc… »), PG_OUT (journal),
PG_SKIP (procédures à ne pas lancer : réseau, fichiers…).
"""
import json
import os
import sys
import time

from gi.repository import Gimp, Gegl

PROCS = os.environ["PG_PROCS"]
OUT = os.environ["PG_OUT"]
SKIP = set(os.environ.get("PG_SKIP", "").split())
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        try:
            done.add(json.loads(l)["proc"])
        except Exception:
            pass

pdb = Gimp.get_pdb()


def color(r, g, b):
    c = Gegl.Color.new("black")
    c.set_rgba(r, g, b, 1.0)
    return c


def test_image():
    img = Gimp.Image.new(640, 480, Gimp.ImageBaseType.RGB)
    bg = Gimp.Layer.new(img, "Arrière-plan", 640, 480, Gimp.ImageType.RGB_IMAGE, 100, Gimp.LayerMode.NORMAL)
    img.insert_layer(bg, None, 0)
    Gimp.context_set_foreground(color(0.2, 0.4, 0.8))
    Gimp.context_set_background(color(0.95, 0.9, 0.7))
    bg.edit_gradient_fill(Gimp.GradientType.LINEAR, 0, False, 1, 0, True, 0, 0, 640, 480)
    lay = Gimp.Layer.new(img, "Forme", 640, 480, Gimp.ImageType.RGBA_IMAGE, 100, Gimp.LayerMode.NORMAL)
    img.insert_layer(lay, None, 0)
    lay.fill(Gimp.FillType.TRANSPARENT)
    img.select_rectangle(Gimp.ChannelOps.REPLACE, 160, 120, 320, 240)
    Gimp.context_set_foreground(color(0.85, 0.2, 0.2))
    lay.edit_fill(Gimp.FillType.FOREGROUND)
    Gimp.Selection.none(img)
    img.select_ellipse(Gimp.ChannelOps.REPLACE, 100, 80, 300, 220)
    img.set_selected_layers([lay])
    return img, lay


def log(rec):
    with open(OUT, "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


for line in open(PROCS):
    parts = line.split()
    if not parts:
        continue
    plugin, procs = parts[0], parts[1:]
    for name in procs:
        if name in done:
            continue
        rec = {"plugin": plugin, "proc": name}
        if name in SKIP:
            rec["status"] = "SKIPPED"
            log(rec)
            continue
        log({"plugin": plugin, "proc": name, "status": "STARTED"})
        print("=== PROC %s" % name, file=sys.stderr, flush=True)
        try:
            proc = pdb.lookup_procedure(name)
            if proc is None:
                rec["status"] = "NOT_FOUND"
                log(rec)
                continue
            img, lay = test_image()
            n_before = len(img.get_layers())
            cfg = proc.create_config()
            args = [a.name for a in proc.get_arguments()]
            rec["args"] = args
            for a in args:
                if a == "run-mode":
                    cfg.set_property(a, Gimp.RunMode.NONINTERACTIVE)
                elif a == "image":
                    cfg.set_property(a, img)
                elif a == "drawables":
                    cfg.set_core_object_array(a, [lay])
                elif a == "drawable":
                    cfg.set_property(a, lay)
            t = time.time()
            res = proc.run(cfg)
            rec["time"] = round(time.time() - t, 2)
            st = res.index(0)
            rec["status"] = st.value_nick.upper() if hasattr(st, "value_nick") else str(st)
            if rec["status"] != "SUCCESS":
                try:
                    rec["error"] = res.index(1)
                except Exception:
                    pass
            try:
                rec["layers_delta"] = len(img.get_layers()) - n_before
                rec["image_count"] = len(Gimp.get_images())
            except Exception:
                pass
            for im in Gimp.get_images():
                im.delete()
        except Exception as e:
            rec["status"] = "EXCEPTION"
            rec["error"] = repr(e)[:400]
        log(rec)

pdb.lookup_procedure("gimp-quit").run(pdb.lookup_procedure("gimp-quit").create_config())

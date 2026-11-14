#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — IA locale (ONNX), exécutée hors ligne sur l'ordinateur.

Sélection > Sujet                     détourage automatique → sélection
Image > Supprimer l'arrière-plan      détourage → masque de calque (réversible)
Image > Agrandir (IA)…                ×2, ×3, ×4 : super-résolution (réseau
                                      « sub-pixel CNN », sur la luminance)
Filtres > Améliorer > Réduire le bruit…   filtre DCT de GEGL (pas de réseau)
Fichier > Modèles d'IA…               modèles installés, choix, suppression

Les modèles ne sont pas fournis avec ChopGimp : chacun est téléchargé à sa
première utilisation, après accord, dans <dossier GIMP>/ia-modeles/, puis
vérifié (SHA-256). Rien n'est envoyé : les images restent sur l'ordinateur.
"""
import hashlib
import json
import os
import sys
import urllib.request

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, GimpUi, Gegl, GLib, GObject, Gtk

MODELS = {
    "u2netp": ("Détourage rapide (U²-Net p)", 320, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225),
               "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx",
               "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8", 4574861),
    "silueta": ("Détourage équilibré (Silueta)", 320, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225),
                "https://github.com/danielgatis/rembg/releases/download/v0.0.0/silueta.onnx",
                "75da6c8d2f8096ec743d071951be73b4a8bc7b3e51d9a6625d63644f90ffeedb", 44173029),
    "isnet": ("Détourage précis (IS-Net)", 1024, (0.5, 0.5, 0.5), (1.0, 1.0, 1.0),
              "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
              "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a", 178648008),
    "superres": ("Super-résolution ×3 (sub-pixel CNN)", 224, None, None,
                 "https://github.com/onnx/models/raw/main/validated/vision/super_resolution/"
                 "sub_pixel_cnn_2016/model/super-resolution-10.onnx",
                 "85f36ff88cc504a24af5e0602148bc56a8aa09a58eca8c0da2756f3e8186035e", 240078),
}
SEG_MODELS = ("u2netp", "silueta", "isnet")

PROCS = {
    "chopgimp-ia-select-subject": ("Sujet (IA)", "<Image>/Select"),
    "chopgimp-ia-remove-background": ("Supprimer l'arrière-plan (IA)", "<Image>/Image"),
    "chopgimp-ia-upscale": ("Agrandir (IA)…", "<Image>/Image"),
    "chopgimp-ia-denoise": ("Réduire le bruit…", "<Image>/Filters/Enhance"),
    "chopgimp-ia-models": ("Modèles d'IA…", "<Image>/File"),
}


def ok(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def fail(procedure, msg):
    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                       GLib.Error.new_literal(GLib.quark_from_string("chopgimp"), msg, 0))


def models_dir():
    d = os.path.join(Gimp.directory(), "ia-modeles")
    os.makedirs(d, exist_ok=True)
    return d


def settings():
    try:
        with open(os.path.join(models_dir(), "reglages.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(s):
    with open(os.path.join(models_dir(), "reglages.json"), "w", encoding="utf-8") as f:
        json.dump(s, f)


def model_path(key):
    return os.path.join(models_dir(), key + ".onnx")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ask_download(key):
    label, _, _, _, url, _, size = MODELS[key]
    GimpUi.init("chopgimp_ia")
    dlg = Gtk.MessageDialog(message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE,
                            text="Télécharger le modèle « %s » ?" % label)
    dlg.format_secondary_text(
        "Taille : %.1f Mo, depuis %s.\n\nIl est téléchargé une seule fois, puis l'IA fonctionne "
        "hors ligne : vos images ne quittent jamais l'ordinateur." % (size / 1048576.0,
                                                                     url.split("/")[2]))
    dlg.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dlg.add_button("_Télécharger", Gtk.ResponseType.OK)
    resp = dlg.run()
    dlg.destroy()
    return resp == Gtk.ResponseType.OK


def ensure_model(key, interactive):
    """→ (chemin, message d'erreur)"""
    path = model_path(key)
    _, _, _, _, url, digest, size = MODELS[key]
    if os.path.exists(path) and os.path.getsize(path) == size:
        return path, None
    if not interactive and os.environ.get("CHOPGIMP_IA_ALLOW_DOWNLOAD") != "1":
        return None, "Modèle d'IA absent : lancez la commande depuis le menu pour le télécharger."
    if interactive and not ask_download(key):
        return None, "cancel"
    tmp = path + ".part"
    Gimp.progress_init("Téléchargement du modèle d'IA…")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChopGimp"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as out:
            done = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                Gimp.progress_update(min(1.0, done / float(size)))
    except OSError as e:
        try:                        # pas de fichier partiel laissé sur le disque
            os.unlink(tmp)
        except OSError:
            pass
        return None, "Téléchargement impossible : %s" % e
    finally:
        Gimp.progress_end()
    if sha256(tmp) != digest:
        os.unlink(tmp)
        return None, "Le modèle téléchargé est corrompu (empreinte SHA-256 différente)."
    os.replace(tmp, path)
    return path, None


def session(path):
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = max(1, (os.cpu_count() or 2) - 1)
    return ort.InferenceSession(path, opts, providers=["CPUExecutionProvider"])


# ─── pixels ↔ numpy, redimensionnement par GIMP (cubique) ───────────────

def read_rgb(drawable):
    import numpy as np
    w, h = drawable.get_width(), drawable.get_height()
    data = drawable.get_buffer().get(Gegl.Rectangle.new(0, 0, w, h), 1.0, "R'G'B'A u8",
                                     Gegl.AbyssPolicy.NONE)
    return np.frombuffer(data, np.uint8).reshape(h, w, 4)


def resized_rgb(image_or_layer, size):
    """Copie aplatie redimensionnée à size×size → tableau HxWx4."""
    if isinstance(image_or_layer, Gimp.Image):
        tmp = image_or_layer.duplicate()
        tmp.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
    else:
        layer = image_or_layer
        tmp = Gimp.Image.new(layer.get_width(), layer.get_height(), Gimp.ImageBaseType.RGB)
        copy = Gimp.Layer.new_from_drawable(layer, tmp)
        tmp.insert_layer(copy, None, 0)
        copy.set_offsets(0, 0)
    Gimp.context_push()
    Gimp.context_set_interpolation(Gimp.InterpolationType.CUBIC)
    tmp.scale(size, size)
    Gimp.context_pop()
    arr = read_rgb(tmp.get_layers()[0]).copy()
    tmp.delete()
    return arr


def gray_to_size(mask, w, h):
    """Masque (tableau 2D u8) → redimensionné à w×h (cubique) → octets."""
    import numpy as np
    sh, sw = mask.shape
    tmp = Gimp.Image.new(sw, sh, Gimp.ImageBaseType.GRAY)
    lay = Gimp.Layer.new(tmp, "m", sw, sh, Gimp.ImageType.GRAY_IMAGE, 100, Gimp.LayerMode.NORMAL)
    tmp.insert_layer(lay, None, 0)
    buf = lay.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, sw, sh), "Y' u8", np.ascontiguousarray(mask).tobytes())
    buf.flush()
    Gimp.context_push()
    Gimp.context_set_interpolation(Gimp.InterpolationType.CUBIC)
    tmp.scale(w, h)
    Gimp.context_pop()
    out = tmp.get_layers()[0].get_buffer().get(Gegl.Rectangle.new(0, 0, w, h), 1.0, "Y' u8",
                                               Gegl.AbyssPolicy.NONE)
    tmp.delete()
    return out


# ─── détourage ──────────────────────────────────────────────────────────

def seg_mask(source, w, h, key, interactive):
    """→ (octets du masque w×h, erreur)"""
    import numpy as np
    path, err = ensure_model(key, interactive)
    if err:
        return None, err
    _, size, mean, std, _, _, _ = MODELS[key]
    Gimp.progress_init("Détourage par l'IA…")
    rgb = resized_rgb(source, size)[:, :, :3].astype(np.float32) / 255.0
    x = (rgb - np.array(mean, np.float32)) / np.array(std, np.float32)
    x = np.ascontiguousarray(x.transpose(2, 0, 1)[None, ...])
    sess = session(path)
    pred = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    lo, hi = float(pred.min()), float(pred.max())
    pred = (pred - lo) / (hi - lo) if hi > lo else pred * 0
    mask = (np.clip(pred, 0, 1) * 255).astype(np.uint8)
    Gimp.progress_update(0.8)
    out = gray_to_size(mask, w, h)
    Gimp.progress_end()
    return out, None


def current_seg_model():
    k = settings().get("segmentation", "silueta")
    return k if k in SEG_MODELS else "silueta"


def select_subject(image, interactive):
    w, h = image.get_width(), image.get_height()
    data, err = seg_mask(image, w, h, current_seg_model(), interactive)
    if err:
        return err
    ch = Gimp.Channel.new(image, "Sujet", w, h, 100, Gegl.Color.new("black"))
    image.insert_channel(ch, None, 0)
    buf = ch.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, w, h), "Y u8", data)
    buf.flush()
    image.select_item(Gimp.ChannelOps.REPLACE, ch)
    image.remove_channel(ch)
    return None


IA_MASK_PARASITE = "chopgimp-ia-mask"


def remove_background(image, layer, interactive):
    import numpy as np
    w, h = layer.get_width(), layer.get_height()
    data, err = seg_mask(layer, w, h, current_seg_model(), interactive)
    if err:
        return err
    mask = layer.get_mask()
    if mask is not None and mask.get_parasite(IA_MASK_PARASITE) is not None:
        # masque posé par une précédente suppression : remplacé
        layer.remove_mask(Gimp.MaskApplyMode.DISCARD)
        mask = None
    if mask is not None:
        # masque de l'utilisateur : conservé, multiplié par le détourage
        cur = mask.get_buffer().get(Gegl.Rectangle.new(0, 0, w, h), 1.0, "Y u8",
                                    Gegl.AbyssPolicy.NONE)
        a = np.frombuffer(cur, np.uint8).astype(np.uint32)
        b = np.frombuffer(data, np.uint8).astype(np.uint32)
        data = ((a * b + 127) // 255).astype(np.uint8).tobytes()
    else:
        if not layer.has_alpha():
            layer.add_alpha()
        mask = layer.create_mask(Gimp.AddMaskType.WHITE)
        layer.add_mask(mask)
        # persistant + annulable : reconnu à la prochaine suppression
        mask.attach_parasite(Gimp.Parasite.new(IA_MASK_PARASITE, 3, [49]))
    buf = mask.get_buffer()
    buf.set(Gegl.Rectangle.new(0, 0, w, h), "Y u8", data)
    buf.flush()
    mask.update(0, 0, w, h)
    return None


# ─── super-résolution (luminance, par tuiles) ───────────────────────────

def upscale(image, factor, interactive):
    import numpy as np
    path, err = ensure_model("superres", interactive)
    if err:
        return None, err
    flat = image.duplicate()
    Gimp.progress_init("Agrandissement par l'IA…")
    try:
        flat.merge_visible_layers(Gimp.MergeType.CLIP_TO_IMAGE)
        # mémoire : images pleine taille en u8, calculs flottants par bandes
        src = read_rgb(flat.get_layers()[0])
        h, w = src.shape[:2]
        y = (0.299 * src[:, :, 0].astype(np.float32) + 0.587 * src[:, :, 1].astype(np.float32) +
             0.114 * src[:, :, 2].astype(np.float32)) / 255.0
        del src
        sess = session(path)
        name = sess.get_inputs()[0].name
        T, O, S = 224, 16, 3                         # tuile, recouvrement, facteur du réseau
        step = T - 2 * O
        out = np.zeros((h * S, w * S), np.uint8)     # luminance agrandie (u8)
        pad = np.pad(y, ((O, T + O), (O, T + O)), mode="reflect")
        del y
        tiles = [(ty, tx) for ty in range(0, h, step) for tx in range(0, w, step)]
        for i, (ty, tx) in enumerate(tiles):
            tile = pad[ty:ty + T, tx:tx + T][None, None].astype(np.float32)
            res = sess.run(None, {name: tile})[0][0, 0]
            hh, ww = min(step, h - ty), min(step, w - tx)
            out[ty * S:(ty + hh) * S, tx * S:(tx + ww) * S] = \
                (np.clip(res[O * S:(O + hh) * S, O * S:(O + ww) * S], 0, 1) * 255 + 0.5).astype(np.uint8)
            Gimp.progress_update(0.9 * (i + 1) / len(tiles))
        del pad
        # chrominance et alpha : agrandissement cubique de GIMP
        Gimp.context_push()
        Gimp.context_set_interpolation(Gimp.InterpolationType.CUBIC)
        flat.scale(w * S, h * S)
        Gimp.context_pop()
        lay = flat.get_layers()[0]
        big = read_rgb(lay)                          # u8, lecture seule
        if not lay.has_alpha():
            lay.add_alpha()
        buf = lay.get_buffer()
        W, H = w * S, h * S
        band = max(1, (8 << 20) // (W * 4))          # ~8 Mo de pixels par bande
        for r0 in range(0, H, band):
            r1 = min(H, r0 + band)
            bf = big[r0:r1].astype(np.float32) / 255.0
            yb = 0.299 * bf[:, :, 0] + 0.587 * bf[:, :, 1] + 0.114 * bf[:, :, 2]
            delta = out[r0:r1].astype(np.float32) / 255.0 - yb
            res = np.empty_like(bf)
            for c in range(3):
                res[:, :, c] = np.clip(bf[:, :, c] + delta, 0, 1)
            res[:, :, 3] = bf[:, :, 3]
            buf.set(Gegl.Rectangle.new(0, r0, W, r1 - r0), "R'G'B'A u8",
                    (res * 255 + 0.5).astype(np.uint8).tobytes())
        buf.flush()
        del big, out
        if factor != S:
            Gimp.context_push()
            Gimp.context_set_interpolation(Gimp.InterpolationType.LOHALO)
            flat.scale(w * factor, h * factor)
            Gimp.context_pop()
    except Exception:
        flat.delete()
        raise
    finally:
        Gimp.progress_end()
    return flat, None


def upscale_dialog():
    GimpUi.init("chopgimp_ia")
    dlg = GimpUi.Dialog(title="Agrandir (IA)", role="chopgimp-ia-upscale", modal=True)
    dlg.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dlg.add_button("_Agrandir", Gtk.ResponseType.OK)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=12)
    dlg.get_content_area().pack_start(box, True, True, 0)
    group, buttons = None, {}
    for f in (2, 3, 4):
        rb = Gtk.RadioButton.new_with_label_from_widget(group, "× %d" % f)
        group = group or rb
        box.pack_start(rb, False, False, 0)
        buttons[f] = rb
    buttons[2].set_active(True)
    box.pack_start(Gtk.Label(label="Le résultat s'ouvre dans une nouvelle image.", xalign=0), False, False, 6)
    dlg.show_all()
    resp = dlg.run()
    choice = next(f for f, rb in buttons.items() if rb.get_active())
    dlg.destroy()
    return choice if resp == Gtk.ResponseType.OK else None


# ─── gestion des modèles ────────────────────────────────────────────────

def models_dialog():
    GimpUi.init("chopgimp_ia")
    dlg = GimpUi.Dialog(title="Modèles d'IA", role="chopgimp-ia-models", modal=True)
    dlg.add_button("_Fermer", Gtk.ResponseType.CLOSE)
    grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=12)
    dlg.get_content_area().pack_start(grid, True, True, 0)
    grid.attach(Gtk.Label(label="Modèle de détourage utilisé :", xalign=0), 0, 0, 2, 1)
    combo = Gtk.ComboBoxText()
    for k in SEG_MODELS:
        combo.append(k, "%s — %.0f Mo" % (MODELS[k][0], MODELS[k][6] / 1048576.0))
    combo.set_active_id(current_seg_model())
    grid.attach(combo, 2, 0, 2, 1)
    row = 1
    for k, (label, _, _, _, _, _, size) in MODELS.items():
        present = os.path.exists(model_path(k))
        grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
        grid.attach(Gtk.Label(label="%.1f Mo" % (size / 1048576.0), xalign=1), 1, row, 1, 1)
        grid.attach(Gtk.Label(label="installé" if present else "à télécharger", xalign=0), 2, row, 1, 1)
        if present:
            b = Gtk.Button(label="Supprimer")
            b.connect("clicked", lambda btn, key=k: (os.unlink(model_path(key)), btn.set_sensitive(False)))
            grid.attach(b, 3, row, 1, 1)
        row += 1
    grid.attach(Gtk.Label(label="Dossier : " + models_dir(), xalign=0, selectable=True), 0, row, 4, 1)
    dlg.show_all()
    dlg.run()
    s = settings()
    s["segmentation"] = combo.get_active_id()
    save_settings(s)
    dlg.destroy()


class ChopGimpIA(Gimp.PlugIn):
    def do_query_procedures(self):
        return list(PROCS)

    def do_create_procedure(self, name):
        label, menu = PROCS[name]
        p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        p.set_image_types("RGB*, GRAY*")
        p.set_menu_label(label)
        p.add_menu_path(menu)
        p.set_documentation(label.rstrip("…"), __doc__.strip().split("\n")[0], name)
        p.set_attribution("ChopGimp", "ChopGimp", "2026")
        if name == "chopgimp-ia-upscale":
            p.add_int_argument("factor", "Facteur", "Facteur d'agrandissement", 2, 4, 2,
                               GObject.ParamFlags.READWRITE)
            # appel par script : la nouvelle image est renvoyée
            p.add_image_return_value("new-image", "Nouvelle image", "Image agrandie", True,
                                     GObject.ParamFlags.READWRITE)
        if name in ("chopgimp-ia-remove-background", "chopgimp-ia-denoise"):
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
        else:
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                   Gimp.ProcedureSensitivityMask.DRAWABLES |
                                   Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
        return p

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        interactive = run_mode == Gimp.RunMode.INTERACTIVE
        try:
            import numpy  # noqa: F401
            import onnxruntime  # noqa: F401
        except ImportError:
            if name not in ("chopgimp-ia-denoise", "chopgimp-ia-models"):
                return fail(procedure, "Le moteur d'IA (onnxruntime) est absent du paquet.")
        msg = None
        if name == "chopgimp-ia-models":
            models_dialog()
        elif name == "chopgimp-ia-select-subject":
            image.undo_group_start()
            try:
                msg = select_subject(image, interactive)
            finally:
                image.undo_group_end()
        elif name == "chopgimp-ia-remove-background":
            layers = [d for d in drawables if isinstance(d, Gimp.Layer) and not isinstance(d, Gimp.GroupLayer)]
            if len(layers) != 1:
                return fail(procedure, "Sélectionnez un seul calque de pixels.")
            image.undo_group_start()
            try:
                msg = remove_background(image, layers[0], interactive)
            finally:
                image.undo_group_end()
        elif name == "chopgimp-ia-upscale":
            factor = upscale_dialog() if interactive else config.get_property("factor")
            if factor is None:
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            big, msg = upscale(image, factor, interactive)
            if big is not None:
                big.undo_enable()
                if interactive:
                    Gimp.Display.new(big)
                Gimp.displays_flush()
                if not msg:
                    rv = procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())
                    rv.remove(1)
                    rv.insert(1, GObject.Value(Gimp.Image, big))
                    return rv
        else:   # réduire le bruit (filtre non destructif)
            for d in drawables:
                f = Gimp.DrawableFilter.new(d, "gegl:denoise-dct", "Réduction du bruit")
                cfg = f.get_config()
                try:
                    cfg.set_property("sigma", 8.0)
                except (TypeError, ValueError):
                    pass
                f.update()
                d.append_filter(f)
        Gimp.displays_flush()
        if msg == "cancel":
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        return fail(procedure, msg) if msg else ok(procedure)


if __name__ == "__main__":
    Gimp.main(ChopGimpIA.__gtype__, sys.argv)

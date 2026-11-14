#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — fonctions de base façon Photoshop (étape « Base I »).

Image > Recadrage en perspective…
    Les 4 points d'un tracé (outil Chemins) désignent un quadrilatère
    (document photographié de biais, façade…) : une homographie le redresse
    en rectangle, sur tous les calques, puis l'image est recadrée.
Image > Redresser…
    Les 2 extrémités d'un tracé indiquent une ligne qui devrait être
    horizontale (ou verticale) : l'image tourne, puis est recadrée sur le
    plus grand rectangle sans bord vide. (L'outil Mesure a aussi un bouton
    « Redresser ».)
Image > Mise à l'échelle selon le contenu…
    Liquid Rescale (liblqr) : retaille le calque en retirant ou en
    ajoutant les zones les moins importantes ; la sélection peut être
    protégée.
"""
import ctypes
import math
import sys

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, GimpUi, Gegl, GLib, GObject, Gtk

from chopgimp_common import ok, fail

try:                        # accélère la lecture/écriture des pixels (facultatif)
    import numpy as np
except Exception:
    np = None

MENU = "<Image>/Image"

PROCS = {
    "chopgimp-perspective-crop": "Recadrage en perspective…",
    "chopgimp-straighten": "Redresser…",
    "chopgimp-liquid-rescale": "Mise à l'échelle selon le contenu…",
}


def path_anchors(image):
    """Ancres du premier tracé du chemin sélectionné (ou du dernier chemin)."""
    paths = image.get_selected_paths() or image.get_paths()
    if not paths:
        return None
    path = paths[0]
    strokes = path.get_strokes()
    if not strokes:
        return None
    _, pts, _closed = path.stroke_get_points(strokes[0])
    return [(pts[i + 2], pts[i + 3]) for i in range(0, len(pts) - 5, 6)]


def top_layers(image):
    return list(image.get_layers())


# ─── recadrage en perspective ───────────────────────────────────────────

def order_quad(pts):
    """4 points → haut-gauche, haut-droite, bas-droite, bas-gauche."""
    cx = sum(p[0] for p in pts) / 4.0
    cy = sum(p[1] for p in pts) / 4.0
    pts = sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))   # sens horaire (y vers le bas)
    # commence au point le plus proche du coin haut-gauche
    start = min(range(4), key=lambda i: pts[i][0] + pts[i][1])
    return pts[start:] + pts[:start]


def homography(src, dst):
    """Matrice 3×3 qui envoie les 4 points src sur les 4 points dst."""
    a, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    n = 8
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):                         # Gauss avec pivot partiel
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            return None
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                for k in range(c, n + 1):
                    m[r][k] -= f * m[c][k]
    h = [m[i][n] / m[i][i] for i in range(n)]
    return [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]]


def perspective_crop(image):
    pts = path_anchors(image)
    if not pts or len(pts) < 4:
        return ("Tracez d'abord un chemin de 4 points (outil Chemins, B) sur les coins de la "
                "zone à redresser.")
    tl, tr, br, bl = order_quad(pts[:4])
    w = int(round((math.dist(tl, tr) + math.dist(bl, br)) / 2.0))
    h = int(round((math.dist(tl, bl) + math.dist(tr, br)) / 2.0))
    if w < 2 or h < 2:
        return "Le quadrilatère est trop petit."
    H = homography([tl, tr, br, bl], [(0, 0), (w, 0), (w, h), (0, h)])
    if H is None:
        return "Les 4 points sont alignés."
    Gimp.context_push()
    try:
        Gimp.context_set_interpolation(Gimp.InterpolationType.CUBIC)
        Gimp.context_set_transform_resize(Gimp.TransformResize.ADJUST)
        Gimp.context_set_transform_direction(Gimp.TransformDirection.FORWARD)
        for layer in top_layers(image):
            if layer.get_lock_position():
                continue
            layer.transform_matrix(H[0][0], H[0][1], H[0][2], H[1][0], H[1][1], H[1][2],
                                   H[2][0], H[2][1], H[2][2])
    finally:
        Gimp.context_pop()
    image.crop(w, h, 0, 0)
    return None


# ─── redresser ──────────────────────────────────────────────────────────

def inner_rect(w, h, angle):
    """Plus grand rectangle droit dans un rectangle w×h tourné de angle."""
    if w <= 0 or h <= 0:
        return 0, 0
    sin_a, cos_a = abs(math.sin(angle)), abs(math.cos(angle))
    long_side, short_side = (w, h) if w >= h else (h, w)
    if short_side <= 2.0 * sin_a * cos_a * long_side or abs(sin_a - cos_a) < 1e-10:
        x = 0.5 * short_side
        wr, hr = (x / sin_a, x / cos_a) if w >= h else (x / cos_a, x / sin_a)
    else:
        cos_2a = cos_a * cos_a - sin_a * sin_a
        wr, hr = (w * cos_a - h * sin_a) / cos_2a, (h * cos_a - w * sin_a) / cos_2a
    return int(wr), int(hr)


def straighten(image):
    pts = path_anchors(image)
    if not pts or len(pts) < 2:
        return ("Tracez d'abord un chemin de 2 points (outil Chemins, B) le long d'une ligne qui "
                "devrait être horizontale ou verticale.")
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    a = math.atan2(y1 - y0, x1 - x0)
    # vers l'horizontale ou la verticale la plus proche
    target = round(a / (math.pi / 2)) * (math.pi / 2)
    rot = target - a
    if abs(rot) < 1e-4:
        return None
    w, h = image.get_width(), image.get_height()
    cx, cy = w / 2.0, h / 2.0
    Gimp.context_push()
    try:
        Gimp.context_set_interpolation(Gimp.InterpolationType.CUBIC)
        Gimp.context_set_transform_resize(Gimp.TransformResize.ADJUST)
        for layer in top_layers(image):
            if not layer.get_lock_position():
                layer.transform_rotate(rot, False, cx, cy)
    finally:
        Gimp.context_pop()
    cw, ch = inner_rect(w, h, rot)
    image.crop(cw, ch, int(cx - cw / 2.0), int(cy - ch / 2.0))
    return None


# ─── mise à l'échelle selon le contenu (liblqr) ─────────────────────────

def lqr():
    for name in ("liblqr-1.so.0", "liblqr-1.so"):
        try:
            lib = ctypes.CDLL(name)
            break
        except OSError:
            lib = None
    if lib is None:
        return None, None
    glib = ctypes.CDLL("libglib-2.0.so.0")
    glib.g_malloc.restype = ctypes.c_void_p
    glib.g_malloc.argtypes = [ctypes.c_size_t]
    glib.g_free.argtypes = [ctypes.c_void_p]
    lib.lqr_carver_new.restype = ctypes.c_void_p
    lib.lqr_carver_new.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.lqr_carver_init.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_float]
    lib.lqr_carver_resize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    lib.lqr_carver_bias_add.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double), ctypes.c_int]
    lib.lqr_carver_scan_reset.argtypes = [ctypes.c_void_p]
    lib.lqr_carver_scan.restype = ctypes.c_int
    lib.lqr_carver_scan.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                                    ctypes.POINTER(ctypes.c_int),
                                    ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
    lib.lqr_carver_scan_by_row.restype = ctypes.c_int
    lib.lqr_carver_scan_by_row.argtypes = [ctypes.c_void_p]
    lib.lqr_carver_scan_line.restype = ctypes.c_int
    lib.lqr_carver_scan_line.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                                         ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
    lib.lqr_carver_destroy.argtypes = [ctypes.c_void_p]
    return lib, glib


def rescale_dialog(w, h, has_sel):
    GimpUi.init("chopgimp_base")
    dialog = GimpUi.Dialog(title="Mise à l'échelle selon le contenu", role="chopgimp-lqr", modal=True)
    dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("_OK", Gtk.ResponseType.OK)
    grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=12)
    dialog.get_content_area().pack_start(grid, True, True, 0)
    grid.attach(Gtk.Label(label="Largeur (%)", xalign=0), 0, 0, 1, 1)
    sw = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=75, lower=10, upper=200, step_increment=1))
    grid.attach(sw, 1, 0, 1, 1)
    grid.attach(Gtk.Label(label="Hauteur (%)", xalign=0), 0, 1, 1, 1)
    sh = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=100, lower=10, upper=200, step_increment=1))
    grid.attach(sh, 1, 1, 1, 1)
    protect = Gtk.CheckButton(label="Protéger la sélection (visages, sujet…)")
    protect.set_active(has_sel)
    protect.set_sensitive(has_sel)
    grid.attach(protect, 0, 2, 2, 1)
    grid.attach(Gtk.Label(label="Calque actif : %d × %d px" % (w, h), xalign=0), 0, 3, 2, 1)
    dialog.show_all()
    res = None
    if dialog.run() == Gtk.ResponseType.OK:
        res = (sw.get_value() / 100.0, sh.get_value() / 100.0, protect.get_active())
    dialog.destroy()
    return res


def read_carver(lib, carver, nw, nh):
    """Résultat de liblqr (RGBA 8 bits) lu ligne par ligne → octets nw×nh×4.
    Les « lignes » de liblqr sont des colonnes si le carver est transposé
    (lqr_carver_scan_by_row faux)."""
    by_row = bool(lib.lqr_carver_scan_by_row(carver))
    n = ctypes.c_int()
    px = ctypes.POINTER(ctypes.c_ubyte)()
    length = (nw if by_row else nh) * 4
    lib.lqr_carver_scan_reset(carver)
    if np is not None:
        out = np.zeros((nh, nw, 4), np.uint8)
        while lib.lqr_carver_scan_line(carver, ctypes.byref(n), ctypes.byref(px)):
            line = np.ctypeslib.as_array(px, shape=(length,)).reshape(-1, 4)
            if by_row:
                out[n.value] = line
            else:
                out[:, n.value] = line
        return out.tobytes()
    out = bytearray(nw * nh * 4)
    while lib.lqr_carver_scan_line(carver, ctypes.byref(n), ctypes.byref(px)):
        line = ctypes.string_at(px, length)
        if by_row:
            out[n.value * nw * 4:(n.value + 1) * nw * 4] = line
        else:
            for yy in range(nh):
                i = (yy * nw + n.value) * 4
                out[i:i + 4] = line[yy * 4:yy * 4 + 4]
    return bytes(out)


def liquid_rescale(image, layer, sx, sy, protect):
    lib, glib = lqr()
    if lib is None:
        return "La bibliothèque liblqr est absente du paquet."
    w, h = layer.get_width(), layer.get_height()
    nw, nh = max(1, int(round(w * sx))), max(1, int(round(h * sy)))
    if (nw, nh) == (w, h):
        return None
    if image.get_precision() not in (Gimp.Precision.U8_LINEAR, Gimp.Precision.U8_NON_LINEAR,
                                     Gimp.Precision.U8_PERCEPTUAL):
        # liblqr travaille ici en 8 bits : le calque perd sa précision
        Gimp.message("Mise à l'échelle selon le contenu : le calque est traité en 8 bits par "
                     "couche (la précision de l'image est supérieure).")
    if not layer.has_alpha():
        layer.add_alpha()
    buf = layer.get_buffer()
    data = buf.get(Gegl.Rectangle.new(0, 0, w, h), 1.0, "R'G'B'A u8", Gegl.AbyssPolicy.NONE)
    raw = glib.g_malloc(w * h * 4)                 # liblqr libère ce tampon (g_free)
    ctypes.memmove(raw, data, w * h * 4)
    carver = lib.lqr_carver_new(raw, w, h, 4)
    if not carver:
        glib.g_free(raw)                           # non repris par liblqr
        return "liblqr : création impossible"
    try:
        if lib.lqr_carver_init(carver, 1, 0.0) != 1:
            return "liblqr : initialisation impossible"
        if protect and not Gimp.Selection.is_empty(image):
            mask = image.get_selection()
            _, ox, oy = layer.get_offsets()
            mb = mask.get_buffer().get(Gegl.Rectangle.new(ox, oy, w, h), 1.0, "Y u8",
                                       Gegl.AbyssPolicy.NONE)
            if np is not None:
                bias_arr = np.where(np.frombuffer(mb, np.uint8) > 127, 1000.0, 0.0).astype(np.float64)
                bias = bias_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
            else:
                bias = (ctypes.c_double * (w * h))(*[1000.0 if v > 127 else 0.0 for v in mb])
            lib.lqr_carver_bias_add(carver, bias, 1)
        if lib.lqr_carver_resize(carver, nw, nh) != 1:      # LqrRetVal : LQR_ERROR 0, LQR_OK 1
            return "liblqr : redimensionnement impossible"
        out = read_carver(lib, carver, nw, nh)
    finally:
        lib.lqr_carver_destroy(carver)

    _, ox, oy = layer.get_offsets()
    full = (ox, oy, w, h) == (0, 0, image.get_width(), image.get_height())
    layer.resize(nw, nh, 0, 0)
    nb = layer.get_buffer()
    nb.set(Gegl.Rectangle.new(0, 0, nw, nh), "R'G'B'A u8", bytes(out))
    nb.flush()
    layer.update(0, 0, nw, nh)
    if full:                                       # calque à la taille de l'image : l'image suit
        image.resize(nw, nh, 0, 0)
    return None


class ChopGimpBase(Gimp.PlugIn):
    def do_query_procedures(self):
        return list(PROCS)

    def do_create_procedure(self, name):
        p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        p.set_image_types("*")
        p.set_menu_label(PROCS[name])
        p.add_menu_path(MENU)
        p.set_documentation(PROCS[name].rstrip("…"), __doc__.strip().split("\n")[0], name)
        p.set_attribution("ChopGimp", "ChopGimp", "2026")
        if name == "chopgimp-liquid-rescale":
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            p.add_double_argument("width-factor", "Largeur", "Facteur de largeur", 0.1, 2.0, 0.75,
                                  GObject.ParamFlags.READWRITE)
            p.add_double_argument("height-factor", "Hauteur", "Facteur de hauteur", 0.1, 2.0, 1.0,
                                  GObject.ParamFlags.READWRITE)
            p.add_boolean_argument("protect-selection", "Protéger", "Protéger la sélection", True,
                                   GObject.ParamFlags.READWRITE)
        else:
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                   Gimp.ProcedureSensitivityMask.DRAWABLES |
                                   Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
        return p

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        if name == "chopgimp-liquid-rescale":
            layers = [d for d in drawables if isinstance(d, Gimp.Layer)]
            if len(layers) != 1 or isinstance(layers[0], Gimp.GroupLayer):
                return fail(procedure, "Sélectionnez un seul calque de pixels.")
            layer = layers[0]
            sx, sy = config.get_property("width-factor"), config.get_property("height-factor")
            protect = config.get_property("protect-selection")
            if run_mode == Gimp.RunMode.INTERACTIVE:
                chosen = rescale_dialog(layer.get_width(), layer.get_height(),
                                        not Gimp.Selection.is_empty(image))
                if chosen is None:
                    return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
                sx, sy, protect = chosen
            Gimp.progress_init("Mise à l'échelle selon le contenu…")
            image.undo_group_start()
            try:
                msg = liquid_rescale(image, layer, sx, sy, protect)
            finally:
                image.undo_group_end()
        else:
            image.undo_group_start()
            try:
                msg = perspective_crop(image) if name == "chopgimp-perspective-crop" else straighten(image)
            finally:
                image.undo_group_end()
        Gimp.displays_flush()
        return fail(procedure, msg) if msg else ok(procedure)


if __name__ == "__main__":
    Gimp.main(ChopGimpBase.__gtype__, sys.argv)

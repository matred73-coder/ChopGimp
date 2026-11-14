#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — outils vectoriels avancés (moteur géométrique d'Inkscape, lib2geom).

  Calque > Pathfinder > Réunir, Soustraire, Intersection, Exclure, Diviser
  Calque > Contours   > Décaler, Vectoriser le contour, Simplifier,
                        Arrondir les coins, Inverser le sens, Fermer les chemins
  Calque > Nœuds      > types de nœuds, aligner, répartir, joindre, couper,
                        supprimer en gardant la forme, arrondir
  Calque > Effets de tracé > Effets vivants… (panneau, effets modifiables en
                        direct : le chemin reste éditable nœud par nœud)

Les calculs sont faits dans GIMP par les procédures chopgimp-path-*
(app/path/chopgimp-geom.cc) ; ce plug-in gère les calques et l'interface.
"""
import sys

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gimp, GimpUi, GLib, GObject, Gtk

AUTHOR = "ChopGimp"
YEAR = "2026"
LPE_PARASITE = "chopgimp-lpe"

PF = "<Image>/Layer/Pathfinder"
PF_L = "<Layers>/Layers Menu/Pathfinder"
CT = "<Image>/Layer/Contours"
CT_L = "<Layers>/Layers Menu/Contours"
ND = "<Image>/Layer/Nœuds"
TRACE = "<Image>/Layer/Effets de tracé"
TRACE_L = "<Layers>/Layers Menu/Effets de tracé"

def ok(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def fail(procedure, msg):
    return procedure.new_return_values(
        Gimp.PDBStatusType.EXECUTION_ERROR,
        GLib.Error.new_literal(GLib.quark_from_string("chopgimp"), msg, 0))


def call(name, **kw):
    # (Gimp.get_pdb() n'est valable qu'une fois le plug-in lancé)
    p = Gimp.get_pdb().lookup_procedure(name)
    if p is None:               # procédure absente (GIMP non recompilé ?)
        return None
    cfg = p.create_config()
    for k, v in kw.items():
        if k in ("paths",):
            cfg.set_core_object_array(k, v)
        else:
            cfg.set_property(k, v)
    res = p.run(cfg)
    if res.index(0) != Gimp.PDBStatusType.SUCCESS:
        return None
    return res


# ─── calques vectoriels ─────────────────────────────────────────────────

def copy_vector_style(src, dst):
    for getter, setter in [("get_enable_fill", "set_enable_fill"), ("get_fill_color", "set_fill_color"),
                           ("get_enable_stroke", "set_enable_stroke"), ("get_stroke_color", "set_stroke_color"),
                           ("get_stroke_width", "set_stroke_width"),
                           ("get_stroke_width_unit", "set_stroke_width_unit"),
                           ("get_stroke_cap_style", "set_stroke_cap_style"),
                           ("get_stroke_join_style", "set_stroke_join_style"),
                           ("get_stroke_miter_limit", "set_stroke_miter_limit"),
                           ("get_stroke_dash_pattern", "set_stroke_dash_pattern"),
                           ("get_stroke_dash_offset", "set_stroke_dash_offset")]:
        try:
            value = getattr(src, getter)()
            if getter == "get_stroke_dash_pattern" and isinstance(value, tuple):
                value = value[-1]          # (ok, tirets)
            getattr(dst, setter)(value)
        except Exception:
            pass
    dst.set_opacity(src.get_opacity())
    dst.set_mode(src.get_mode())


def new_layer_from_path(image, path, style, name=None, position_layer=None):
    """Calque vectoriel du chemin (déjà inséré dans l'image), au style de « style »."""
    path.set_name(name or style.get_name())
    layer = Gimp.VectorLayer.new(image, path)
    layer.set_name(name or style.get_name())
    copy_vector_style(style, layer)
    ref = position_layer or style
    image.insert_layer(layer, ref.get_parent(), image.get_item_position(ref))
    layer.refresh()
    return layer


def vector_layers(drawables):
    return [d for d in drawables if isinstance(d, Gimp.VectorLayer)]


def stack_order(image, layers):
    """Du haut vers le bas de la pile (même parent)."""
    return sorted(layers, key=lambda l: image.get_item_position(l))


def split_strokes(image, path):
    """Un chemin par sous-chemin (pour combiner les sous-chemins d'un calque)."""
    out = []
    for sid in path.get_strokes():
        t, pts, closed = path.stroke_get_points(sid)
        p = Gimp.Path.new(image, path.get_name())
        p.stroke_new_from_points(t, pts, True)
        image.insert_path(p, None, 0)
        out.append(p)
    return out


def remove_paths(image, paths):
    for p in paths:
        try:
            image.remove_path(p)
        except Exception:
            pass


def target_path(image, drawables):
    """Le chemin à modifier : celui du calque vectoriel sélectionné, sinon le
    chemin sélectionné dans le panneau Chemins."""
    vl = vector_layers(drawables)
    if vl:
        return vl[0].get_path(), vl[0]
    paths = image.get_selected_paths()
    return (paths[0], None) if paths else (None, None)


# ─── Pathfinder ─────────────────────────────────────────────────────────

PF_OPS = {"chopgimp-pathfinder-union": 0, "chopgimp-pathfinder-minus": 1,
          "chopgimp-pathfinder-intersect": 2, "chopgimp-pathfinder-exclude": 3,
          "chopgimp-pathfinder-divide": 4}


def pathfinder(image, drawables, op):
    layers = stack_order(image, vector_layers(drawables))
    temp = []
    if not layers:
        return "Sélectionnez les formes à combiner (calques vectoriels, Maj+clic dans le panneau Calques)."
    if len(layers) == 1:
        # les sous-chemins d'un même calque
        paths = split_strokes(image, layers[0].get_path())
        temp = paths
        if len(paths) < 2:
            remove_paths(image, temp)
            return "Sélectionnez au moins deux formes (ou un calque à plusieurs sous-chemins)."
        bottom_first = paths
    else:
        bottom_first = [l.get_path() for l in reversed(layers)]

    top, bottom = layers[0], layers[-1]

    if op == 4:
        res = call("chopgimp-path-divide", paths=bottom_first)
        n = res.index(1) if res else 0
        if n == 0:
            # rien à diviser (chemins ouverts, échec du calcul) : on ne
            # touche pas aux formes
            remove_paths(image, temp)
            return "Impossible de diviser ces formes (chemins fermés nécessaires)."
        pieces = image.get_paths()[:n]
        group = Gimp.GroupLayer.new(image, "Division")
        image.insert_layer(group, top.get_parent(), image.get_item_position(top))
        for i, piece in enumerate(pieces):
            style = owner_layer(image, piece, layers) if len(layers) > 1 else top
            nl = Gimp.VectorLayer.new(image, piece)
            nl.set_name("%s %d" % (style.get_name(), i + 1))
            copy_vector_style(style, nl)
            image.insert_layer(nl, group, i)
            nl.refresh()
        result = group
    else:
        # « Soustraire » : la forme du bas moins celles du dessus
        res = call("chopgimp-path-boolean", paths=bottom_first, operation=op)
        if not res or not res.index(1):
            remove_paths(image, temp)
            return "Le résultat est vide."
        path = res.index(1)
        image.insert_path(path, None, 0)
        style = bottom if op == 1 else top
        result = new_layer_from_path(image, path, style, style.get_name(), position_layer=top)

    for l in layers:
        image.remove_layer(l)
    remove_paths(image, temp)
    image.set_selected_layers([result])
    return None


def owner_layer(image, piece, layers):
    """Le calque le plus haut qui couvre l'essentiel du morceau (son style)."""
    info = call("chopgimp-path-info", path=piece)
    if info is None:
        return layers[0]
    area = max(1.0, info.index(2))
    for l in layers:
        res = call("chopgimp-path-boolean", paths=[piece, l.get_path()], operation=2)
        inter = res.index(1) if res else None
        if inter is None:
            continue
        image.insert_path(inter, None, 0)
        info = call("chopgimp-path-info", path=inter)
        image.remove_path(inter)
        if info is not None and info.index(2) > 0.5 * area:
            return l
    return layers[0]


# ─── Contours ───────────────────────────────────────────────────────────

JOINS = ["Angle", "Arrondi", "Biseau"]
CAPS = ["Plate", "Arrondie", "Carrée"]


def replace_layer_path(image, layer, path, name=None):
    image.insert_path(path, None, 0)
    nl = new_layer_from_path(image, path, layer, name or layer.get_name())
    image.remove_layer(layer)
    return nl


def contour(image, drawables, name, A):
    layers = vector_layers(drawables)
    if not layers:
        path, _ = target_path(image, drawables)
        if path is None:
            return "Sélectionnez une forme (calque vectoriel) ou un chemin."
        items = [(path, None)]
    else:
        items = [(l.get_path(), l) for l in layers]

    results, report = [], []
    for path, layer in items:
        if name == "chopgimp-contour-offset":
            res = call("chopgimp-path-offset", path=path, distance=A("distance"), join=int(A("join")))
        elif name == "chopgimp-contour-outline":
            width = layer.get_stroke_width() if layer and layer.get_enable_stroke() else A("width")
            res = call("chopgimp-path-outline", path=path, width=width, join=int(A("join")),
                       cap=int(A("cap")))
        elif name == "chopgimp-contour-simplify":
            info = call("chopgimp-path-info", path=path)
            before = info.index(1) if info else 0
            res = call("chopgimp-path-simplify", path=path, tolerance=A("tolerance"))
            if res and res.index(1) and info:
                # (le chemin résultat n'est inséré qu'une fois, plus bas)
                info = call("chopgimp-path-info", path=res.index(1))
                if info:
                    report.append("%d → %d nœuds" % (before, info.index(1)))
        elif name == "chopgimp-contour-round":
            res = call("chopgimp-path-round-corners", path=path, radius=A("radius"),
                       **{"selected-only": False})
        elif name == "chopgimp-contour-reverse":
            res = call("chopgimp-path-reverse", path=path)
        else:  # fermer
            res = None
            newp = Gimp.Path.new(image, path.get_name())
            for sid in path.get_strokes():
                t, pts, closed = path.stroke_get_points(sid)
                newp.stroke_new_from_points(t, pts, True)
            if layer:
                results.append(replace_layer_path(image, layer, newp))
            else:
                image.insert_path(newp, None, 0)
            continue

        if not res or not res.index(1):
            return "Le résultat est vide."
        newp = res.index(1)
        if layer:
            # lu avant de remplacer : l'ancien calque est retiré de l'image
            stroke_color = layer.get_stroke_color() if layer.get_enable_stroke() else None
            nl = replace_layer_path(image, layer, newp)
            if name == "chopgimp-contour-outline" and stroke_color is not None:
                # le contour devient une forme pleine de la couleur du contour
                nl.set_enable_fill(True)
                nl.set_fill_color(stroke_color)
                nl.set_enable_stroke(False)
                nl.refresh()
            results.append(nl)
        else:
            image.insert_path(newp, None, 0)

    if results:
        image.set_selected_layers(results)
    if report:
        Gimp.message("Simplifier : " + ", ".join(report))
    return None


# ─── Nœuds ──────────────────────────────────────────────────────────────

NODE_OPS = {
    "chopgimp-nodes-corner": 0, "chopgimp-nodes-smooth": 1, "chopgimp-nodes-symmetric": 2,
    "chopgimp-nodes-auto": 3, "chopgimp-nodes-line": 4, "chopgimp-nodes-curve": 5,
    "chopgimp-nodes-align-left": 6, "chopgimp-nodes-align-hcenter": 7,
    "chopgimp-nodes-align-right": 8, "chopgimp-nodes-align-top": 9,
    "chopgimp-nodes-align-vcenter": 10, "chopgimp-nodes-align-bottom": 11,
    "chopgimp-nodes-distribute-h": 12, "chopgimp-nodes-distribute-v": 13,
    "chopgimp-nodes-delete": 14, "chopgimp-nodes-join": 15, "chopgimp-nodes-break": 16,
    "chopgimp-nodes-round": 17, "chopgimp-nodes-select-all": 18,
}
NODE_LABELS = {
    "chopgimp-nodes-corner": "Nœud angulaire", "chopgimp-nodes-smooth": "Nœud doux",
    "chopgimp-nodes-symmetric": "Nœud symétrique", "chopgimp-nodes-auto": "Nœud automatique",
    "chopgimp-nodes-line": "Segments en lignes", "chopgimp-nodes-curve": "Segments en courbes",
    "chopgimp-nodes-align-left": "Aligner à gauche", "chopgimp-nodes-align-hcenter": "Aligner au centre (vertical)",
    "chopgimp-nodes-align-right": "Aligner à droite", "chopgimp-nodes-align-top": "Aligner en haut",
    "chopgimp-nodes-align-vcenter": "Aligner au centre (horizontal)", "chopgimp-nodes-align-bottom": "Aligner en bas",
    "chopgimp-nodes-distribute-h": "Répartir horizontalement", "chopgimp-nodes-distribute-v": "Répartir verticalement",
    "chopgimp-nodes-delete": "Supprimer en gardant la forme", "chopgimp-nodes-join": "Joindre deux extrémités",
    "chopgimp-nodes-break": "Couper aux nœuds", "chopgimp-nodes-round": "Arrondir les coins…",
    "chopgimp-nodes-select-all": "Sélectionner tous les nœuds",
}


def nodes(image, drawables, name, value):
    path, _ = target_path(image, drawables)
    if path is None:
        return "Sélectionnez une forme (calque vectoriel) ou un chemin."
    res = call("chopgimp-path-nodes", path=path, operation=NODE_OPS[name], value=float(value))
    if res and not res.index(1) and name != "chopgimp-nodes-select-all":
        Gimp.message("Sélectionnez d'abord des nœuds avec l'outil Sélection directe (A) : "
                     "clic, Maj+clic ou cadre.")
    return None


# ─── Effets vivants ─────────────────────────────────────────────────────
# (clé, libellé, [(paramètre, libellé, min, max, défaut)], forme pleine ?)
EFFECTS = [
    ("taper", "Effilé", [("width", "Épaisseur", 0.5, 500, 12), ("start", "Effilé au début (0-1)", 0, 1, 0.2),
                         ("end", "Effilé à la fin (0-1)", 0, 1, 0.2)], True),
    ("powerstroke", "Épaisseur variable", [("width", "Épaisseur", 0.5, 500, 12),
                                           ("widths", "Profil (position:épaisseur, …)", None, None,
                                            "0:2,0.5:24,1:2")], True),
    ("zigzag", "Zigzag", [("size", "Amplitude", 0, 500, 8), ("ridges", "Nombre de dents", 2, 400, 24),
                          ("smooth", "Vagues arrondies (0/1)", 0, 1, 0)], False),
    ("wave", "Ondulation", [("size", "Amplitude", 0, 500, 8), ("wavelength", "Longueur d'onde", 4, 2000, 60)], False),
    ("roughen", "Rugosité", [("size", "Amplitude", 0, 200, 4), ("detail", "Détail", 1, 100, 20),
                             ("seed", "Variante", 0, 99999, 1)], False),
    ("twist", "Torsion", [("angle", "Angle (°)", -720, 720, 90)], False),
    ("pucker", "Contracter / dilater", [("amount", "Contracter (−) / dilater (+) %", -100, 100, 30)], False),
    ("bend", "Courbure", [("angle", "Angle de l'arc (°)", -360, 360, 60)], False),
    ("envelope", "Enveloppe", [("tl-x", "Haut gauche x", -2000, 2000, 0), ("tl-y", "Haut gauche y", -2000, 2000, 0),
                               ("tr-x", "Haut droit x", -2000, 2000, 0), ("tr-y", "Haut droit y", -2000, 2000, 0),
                               ("br-x", "Bas droit x", -2000, 2000, 0), ("br-y", "Bas droit y", -2000, 2000, 0),
                               ("bl-x", "Bas gauche x", -2000, 2000, 0), ("bl-y", "Bas gauche y", -2000, 2000, 0)],
     False),
    ("pattern", "Motif le long du chemin", [("pattern-tattoo", "Motif (calque vectoriel)", "layer", None, 0),
                                            ("spacing", "Espacement", 0, 1000, 4),
                                            ("repeat", "Répéter (0/1)", 0, 1, 1)], False),
    ("along", "Suivre un chemin", [("spine-tattoo", "Chemin à suivre (calque vectoriel)", "layer", None, 0)],
     False),
    ("offset", "Décalage", [("distance", "Distance (px, − pour rétrécir)", -500, 500, 6)], False),
    ("round", "Coins arrondis", [("radius", "Rayon", 0, 1000, 12)], False),
]
EFFECT_BY_KEY = {e[0]: e for e in EFFECTS}


def read_lpe(layer):
    par = layer.get_parasite(LPE_PARASITE)
    if par is None:
        return []
    kf = GLib.KeyFile.new()
    try:
        # get_data() renvoie des octets signés (-128..127)
        raw = bytes(b & 0xff for b in par.get_data())
        kf.load_from_data(raw.decode("utf-8"), -1, GLib.KeyFileFlags.NONE)
    except Exception:
        return []
    out = []
    groups = sorted(kf.get_groups()[0], key=lambda g: int(g) if g.isdigit() else 0)
    for g in groups:
        e = {k: kf.get_value(g, k) for k in kf.get_keys(g)[0]}
        if "type" in e and e["type"] in EFFECT_BY_KEY:
            out.append(e)
    return out


def write_lpe(layer, effects):
    if not effects:
        try:
            layer.detach_parasite(LPE_PARASITE)
        except Exception:
            pass
    else:
        text = ""
        for i, e in enumerate(effects):
            text += "[%d]\n" % i + "".join("%s=%s\n" % (k, v) for k, v in e.items())
        # 1 = persistant (dans le XCF), 2 = annulable
        raw = [b - 256 if b > 127 else b for b in text.encode("utf-8")]   # octets signés
        layer.attach_parasite(Gimp.Parasite.new(LPE_PARASITE, 3, raw))
    layer.refresh()
    Gimp.displays_flush()


def effects_dialog(image, layer):
    GimpUi.init("chopgimp_vector")
    original = read_lpe(layer)
    effects = [dict(e) for e in original]
    # réglages de fond / contour que « Ajouter l'effet » peut modifier
    style = (layer.get_enable_fill(), layer.get_fill_color(), layer.get_enable_stroke())
    others = [l for l in walk_layers(image.get_layers())
              if isinstance(l, Gimp.VectorLayer) and l != layer]

    dialog = GimpUi.Dialog(title="Effets vivants — " + layer.get_name(), role="chopgimp-lpe", modal=True)
    dialog.add_button("_Annuler", Gtk.ResponseType.CANCEL)
    dialog.add_button("_OK", Gtk.ResponseType.OK)
    dialog.set_default_size(520, 420)
    box = dialog.get_content_area()

    intro = Gtk.Label(label="Les effets s'appliquent au rendu : le chemin reste modifiable nœud par nœud "
                            "(outil Sélection directe, A) et l'effet suit en direct.", wrap=True, xalign=0,
                      margin=8)
    box.pack_start(intro, False, False, 0)

    add_row = Gtk.Box(spacing=6, margin=8)
    combo = Gtk.ComboBoxText()
    for key, label, _, _ in EFFECTS:
        combo.append(key, label)
    combo.set_active(0)
    add_btn = Gtk.Button(label="Ajouter l'effet")
    add_row.pack_start(combo, True, True, 0)
    add_row.pack_start(add_btn, False, False, 0)
    box.pack_start(add_row, False, False, 0)

    scroller = Gtk.ScrolledWindow(vexpand=True)
    listbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=8)
    scroller.add(listbox)
    box.pack_start(scroller, True, True, 0)

    pending = [0]

    def apply_now():
        pending[0] = 0
        write_lpe(layer, effects)
        return False

    def changed(*_):
        if pending[0]:
            GLib.source_remove(pending[0])
        pending[0] = GLib.timeout_add(150, apply_now)

    def rebuild():
        for child in listbox.get_children():
            listbox.remove(child)
        for idx, e in enumerate(effects):
            key, label, params, _ = EFFECT_BY_KEY[e["type"]]
            frame = Gtk.Frame()
            inner = Gtk.Grid(column_spacing=8, row_spacing=4, margin=6)
            frame.add(inner)
            on = Gtk.CheckButton(label=label)
            on.set_active(e.get("enabled", "1") != "0")
            on.connect("toggled", lambda w, e=e: (e.__setitem__("enabled", "1" if w.get_active() else "0"),
                                                  changed()))
            inner.attach(on, 0, 0, 2, 1)
            tools = Gtk.Box(spacing=2)
            for icon, tip, fn in [("go-up-symbolic", "Monter", lambda i=idx: move(i, -1)),
                                  ("go-down-symbolic", "Descendre", lambda i=idx: move(i, 1)),
                                  ("edit-delete-symbolic", "Supprimer l'effet", lambda i=idx: remove(i))]:
                b = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.MENU)
                b.set_tooltip_text(tip)
                b.connect("clicked", lambda w, fn=fn: fn())
                tools.pack_start(b, False, False, 0)
            inner.attach(tools, 2, 0, 1, 1)
            for row, (pk, plabel, lo, hi, default) in enumerate(params, start=1):
                inner.attach(Gtk.Label(label=plabel, xalign=0), 0, row, 1, 1)
                value = e.get(pk, str(default))
                if lo == "layer":
                    w = Gtk.ComboBoxText()
                    w.append("0", "(choisir un calque)")
                    for l in others:
                        w.append(str(l.get_tattoo()), l.get_name())
                    if not w.set_active_id(str(value)):
                        w.set_active(0)
                    w.connect("changed", lambda w, e=e, pk=pk: (e.__setitem__(pk, w.get_active_id() or "0"),
                                                                changed()))
                elif lo is None:
                    w = Gtk.Entry(text=str(value), hexpand=True)
                    w.connect("changed", lambda w, e=e, pk=pk: (e.__setitem__(pk, w.get_text()), changed()))
                else:
                    adj = Gtk.Adjustment(value=float(value), lower=lo, upper=hi,
                                         step_increment=0.05 if hi <= 1 else 1)
                    w = Gtk.SpinButton(adjustment=adj, digits=2 if hi <= 1 else 0, hexpand=True)
                    w.connect("value-changed",
                              lambda w, e=e, pk=pk: (e.__setitem__(pk, "%g" % w.get_value()), changed()))
                inner.attach(w, 1, row, 2, 1)
            listbox.pack_start(frame, False, False, 0)
        listbox.show_all()

    def move(i, d):
        j = i + d
        if 0 <= j < len(effects):
            effects[i], effects[j] = effects[j], effects[i]
            rebuild()
            changed()

    def remove(i):
        del effects[i]
        rebuild()
        changed()

    def add(_):
        key = combo.get_active_id()
        _, _, params, shape = EFFECT_BY_KEY[key]
        e = {"type": key, "enabled": "1"}
        for pk, _, lo, hi, default in params:
            e[pk] = str(default)
        if shape and layer.get_enable_stroke() and not layer.get_enable_fill():
            # un tracé à épaisseur variable devient une forme pleine
            layer.set_enable_fill(True)
            layer.set_fill_color(layer.get_stroke_color())
            layer.set_enable_stroke(False)
            if "width" in e:
                e["width"] = "%g" % max(1.0, layer.get_stroke_width() * 3)
        effects.append(e)
        rebuild()
        changed()

    add_btn.connect("clicked", add)
    rebuild()
    dialog.show_all()
    resp = dialog.run()
    if pending[0]:
        GLib.source_remove(pending[0])
    if resp != Gtk.ResponseType.OK:
        layer.set_enable_fill(style[0])
        layer.set_fill_color(style[1])
        layer.set_enable_stroke(style[2])
    write_lpe(layer, effects if resp == Gtk.ResponseType.OK else original)
    dialog.destroy()


def walk_layers(layers):
    for l in layers:
        yield l
        if isinstance(l, Gimp.GroupLayer):
            yield from walk_layers(l.get_children())


# ─── Déclaration des procédures ─────────────────────────────────────────

PROCS = {}
for name, op in PF_OPS.items():
    PROCS[name] = ({0: "Réunir", 1: "Soustraire la forme du dessus", 2: "Intersection",
                    3: "Exclure le chevauchement", 4: "Diviser"}[op], [PF, PF_L], [])
PROCS.update({
    "chopgimp-contour-offset": ("Décaler…", [CT, CT_L],
                                [("double", "distance", "Distance (px, − pour rétrécir)", -2000, 2000, 6),
                                 ("choice", "join", "Jointure", JOINS, None, 1)]),
    "chopgimp-contour-outline": ("Vectoriser le contour…", [CT, CT_L],
                                 [("double", "width", "Épaisseur (si le calque n'a pas de contour)", 0.1, 2000, 4),
                                  ("choice", "join", "Jointure", JOINS, None, 0),
                                  ("choice", "cap", "Extrémités", CAPS, None, 0)]),
    "chopgimp-contour-simplify": ("Simplifier…", [CT, CT_L],
                                  [("double", "tolerance", "Tolérance (px)", 0.1, 100, 2)]),
    "chopgimp-contour-round": ("Arrondir les coins…", [CT, CT_L],
                               [("double", "radius", "Rayon (px)", 0, 2000, 12)]),
    "chopgimp-contour-reverse": ("Inverser le sens", [CT, CT_L], []),
    "chopgimp-contour-close": ("Fermer les chemins", [CT, CT_L], []),
    "chopgimp-path-effects-dialog": ("Effets vivants…", [TRACE, TRACE_L], []),
})
for name, label in NODE_LABELS.items():
    args = [("double", "radius", "Rayon (px)", 0, 2000, 12)] if name == "chopgimp-nodes-round" else []
    PROCS[name] = (label, [ND], args)


class ChopGimpVector(Gimp.PlugIn):

    def do_query_procedures(self):
        return list(PROCS)

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        label, paths, args = PROCS[name]
        p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        p.set_image_types("*")
        p.set_attribution(AUTHOR, AUTHOR, YEAR)
        p.set_menu_label(label)
        for path in paths:
            p.add_menu_path(path)
        p.set_documentation(label.rstrip("…"), label.rstrip("…"), name)
        p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                               Gimp.ProcedureSensitivityMask.DRAWABLES |
                               Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
        for kind, key, nick, lo, hi, default in args:
            if kind == "double":
                p.add_double_argument(key, nick, nick, lo, hi, default, GObject.ParamFlags.READWRITE)
            elif kind == "choice":
                ch = Gimp.Choice.new()
                for i, l in enumerate(lo):
                    ch.add(str(i), i, l, "")
                p.add_choice_argument(key, nick, nick, ch, str(default), GObject.ParamFlags.READWRITE)
        return p

    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        args = PROCS[name][2]

        if run_mode == Gimp.RunMode.INTERACTIVE and args:
            GimpUi.init("chopgimp_vector")
            dialog = GimpUi.ProcedureDialog.new(procedure, config, PROCS[name][0].rstrip("…"))
            dialog.fill(None)
            if not dialog.run():
                dialog.destroy()
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            dialog.destroy()

        def A(k):
            v = config.get_property(k)
            return int(v) if isinstance(v, str) and v.isdigit() else v

        image.undo_group_start()
        try:
            if name in PF_OPS:
                msg = pathfinder(image, drawables, PF_OPS[name])
            elif name.startswith("chopgimp-contour-"):
                msg = contour(image, drawables, name, A)
            elif name in NODE_OPS:
                msg = nodes(image, drawables, name, A("radius") if args else 0)
            elif name == "chopgimp-path-effects-dialog":
                layers = vector_layers(drawables)
                if not layers:
                    msg = "Sélectionnez une forme (calque vectoriel)."
                elif run_mode != Gimp.RunMode.INTERACTIVE:
                    msg = None
                else:
                    effects_dialog(image, layers[0])
                    msg = None
            else:
                msg = "Procédure inconnue."
        finally:
            image.undo_group_end()
            Gimp.displays_flush()

        return fail(procedure, msg) if msg else ok(procedure)


if __name__ == "__main__":
    Gimp.main(ChopGimpVector.__gtype__, sys.argv)

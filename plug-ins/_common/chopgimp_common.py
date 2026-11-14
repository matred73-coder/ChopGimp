# -*- coding: utf-8 -*-
"""
ChopGimp — fonctions communes aux plug-ins (plug-ins/_common).

Ce n'est pas un plug-in : tools/install_data.sh copie ce fichier dans le
dossier de chaque plug-in installé, à côté de son script. Le dossier du
plug-in étant dans sys.path quand GIMP le lance, on l'importe simplement :

    from chopgimp_common import ok, fail, srgb, …

  ok / fail                 valeurs de retour d'une procédure
  srgb                      couleur sRGB (0..1) → Gegl.Color
  pdb_run / pdb_call        lancer une procédure de la PDB
  walk_layers               tous les calques, groupes compris
  parasite_*                parasites (texte, JSON) lus et écrits
  copy_vector_style         style complet d'un calque vectoriel
  remove_layer_and_paths    retirer un calque sans laisser de chemin orphelin
"""
import json

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, Gegl, GLib


# ─── retour des procédures ──────────────────────────────────────────────

def ok(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def fail(procedure, msg):
    return procedure.new_return_values(
        Gimp.PDBStatusType.EXECUTION_ERROR,
        GLib.Error.new_literal(GLib.quark_from_string("chopgimp"), msg, 0))


# ─── couleurs ───────────────────────────────────────────────────────────

def srgb(r, g, b, a=1.0):
    """Couleur sRGB (0..1, comme Gdk.RGBA ou Photoshop) → Gegl.Color.
    set_rgba() seul attendrait du RGB linéaire et éclaircirait la couleur :
    on précise l'espace (None = sRGB, valeurs non linéaires)."""
    c = Gegl.Color.new("black")
    c.set_rgba_with_space(r, g, b, a, None)
    return c


# ─── PDB ────────────────────────────────────────────────────────────────

def pdb_run(name, **kw):
    """Lance la procédure name (les listes vont dans des tableaux d'objets,
    ex. paths=[…]). → résultat brut, ou None si la procédure est absente.
    (Gimp.get_pdb() n'est valable qu'une fois le plug-in lancé.)"""
    proc = Gimp.get_pdb().lookup_procedure(name)
    if proc is None:
        return None
    cfg = proc.create_config()
    for k, v in kw.items():
        if isinstance(v, (list, tuple)):
            cfg.set_core_object_array(k, v)
        else:
            cfg.set_property(k, v)
    return proc.run(cfg)


def pdb_call(name, **kw):
    """Comme pdb_run, mais None aussi quand la procédure échoue."""
    res = pdb_run(name, **kw)
    if res is None or res.index(0) != Gimp.PDBStatusType.SUCCESS:
        return None
    return res


# ─── calques ────────────────────────────────────────────────────────────

def walk_layers(layers):
    """Chaque calque, puis le contenu des groupes (profondeur d'abord)."""
    for l in layers:
        yield l
        if isinstance(l, Gimp.GroupLayer):
            yield from walk_layers(l.get_children())


# ─── parasites ──────────────────────────────────────────────────────────
# Les données d'un parasite sont des octets SIGNÉS pour PyGObject
# (-128..127). Lecture : on accepte aussi des octets 0..255 (anciens
# parasites de chopgimp_fx) — sur le disque, ce sont les mêmes octets.

def parasite_encode(data):
    """str ou bytes → liste d'octets signés pour Gimp.Parasite.new."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return [b - 256 if b > 127 else b for b in data]


def parasite_decode(par):
    """Gimp.Parasite → bytes."""
    return bytes(b & 255 for b in par.get_data())


def get_parasite_text(item, name):
    """Texte UTF-8 du parasite name de item, ou None."""
    try:
        par = item.get_parasite(name)
    except Exception:
        par = None
    if par is None:
        return None
    try:
        return parasite_decode(par).decode("utf-8")
    except ValueError:
        return None


def set_parasite_text(item, name, text, flags=Gimp.PARASITE_PERSISTENT):
    # flags : 1 = persistant (enregistré dans le XCF), 2 = annulable
    item.attach_parasite(Gimp.Parasite.new(name, flags, parasite_encode(text)))


def get_parasite_json(item, name, default=None):
    text = get_parasite_text(item, name)
    if text is None:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


def set_parasite_json(item, name, data, flags=Gimp.PARASITE_PERSISTENT):
    set_parasite_text(item, name, json.dumps(data), flags)


# ─── calques vectoriels ─────────────────────────────────────────────────

_VECTOR_STYLE = [("get_enable_fill", "set_enable_fill"), ("get_fill_color", "set_fill_color"),
                 ("get_enable_stroke", "set_enable_stroke"), ("get_stroke_color", "set_stroke_color"),
                 ("get_stroke_width", "set_stroke_width"),
                 ("get_stroke_width_unit", "set_stroke_width_unit"),
                 ("get_stroke_cap_style", "set_stroke_cap_style"),
                 ("get_stroke_join_style", "set_stroke_join_style"),
                 ("get_stroke_miter_limit", "set_stroke_miter_limit"),
                 ("get_stroke_dash_pattern", "set_stroke_dash_pattern"),
                 ("get_stroke_dash_offset", "set_stroke_dash_offset")]


def copy_vector_style(src, dst):
    """Fond, contour (couleur, épaisseur, extrémités, angles, tirets),
    opacité et mode de src vers dst (calques vectoriels)."""
    for getter, setter in _VECTOR_STYLE:
        try:
            value = getattr(src, getter)()
            if getter == "get_stroke_dash_pattern" and isinstance(value, tuple):
                value = value[-1]          # (ok, tirets)
            getattr(dst, setter)(value)
        except Exception:
            pass
    dst.set_opacity(src.get_opacity())
    dst.set_mode(src.get_mode())


def vector_paths(layer):
    """Chemins des calques vectoriels de layer (et de ses enfants)."""
    out = []
    if isinstance(layer, Gimp.VectorLayer):
        p = layer.get_path()
        if p is not None:
            out.append(p)
    if isinstance(layer, Gimp.GroupLayer):
        for c in layer.get_children():
            out += vector_paths(c)
    return out


def remove_unused_paths(image, paths):
    """Supprime ces chemins s'ils ne servent plus à aucun calque vectoriel."""
    if not paths:
        return
    used = set()
    for l in image.get_layers():
        used.update(p.get_id() for p in vector_paths(l))
    for p in paths:
        try:
            if p is not None and p.is_valid() and p.get_id() not in used:
                image.remove_path(p)
                used.add(p.get_id())
        except Exception:
            pass


def remove_layer_and_paths(image, layer):
    """Retire le calque et les chemins de ses calques vectoriels : GIMP les
    laisse dans l'image (chemins orphelins), sauf s'ils servent encore à un
    autre calque vectoriel."""
    paths = vector_paths(layer)
    image.remove_layer(layer)
    remove_unused_paths(image, paths)

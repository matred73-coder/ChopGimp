#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp — import PSD avancé (étape « PSD I »).

Remplace l'ouverture des .psd / .psb (priorité plus forte que file-psd-load) :

1. l'import de GIMP charge les pixels, groupes, masques, modes ;
2. psdparse relit la section « calques » du fichier ;
3. chaque calque est retrouvé par son identifiant Photoshop (tatouage) ;
4. il est remplacé par son équivalent modifiable :
     texte (TySh)          → calque de texte (styles, transformation, déformation)
     forme (vmsk + vscg)   → calque vectoriel (fond, contour)
     masque vectoriel      → masque de calque + chemin du même nom
     effets (lfx2)         → styles de calque ChopGimp
   L'original pixellisé est rangé, masqué, dans le groupe « ⟲ Originaux » :
   le résultat n'est jamais moins bon que l'import d'origine.
5. un rapport liste ce qui est repris, approximé ou ignoré ; les polices
   absentes peuvent être remplacées (correspondance mémorisée).
"""
import hashlib
import json
import math
import os
import re
import subprocess
import sys

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, GimpUi, Gegl, Gio, GLib, GObject, Gtk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import psdparse  # noqa: E402

PROC = "file-chopgimp-psd-load"
PROC_THUMB = "file-chopgimp-psd-load-thumb"
ORIGINALS = "⟲ Originaux (pixels Photoshop)"
SETTINGS = "chopgimp-psd.json"
DEFAULT_FONT = "Sans-serif"


# ─── réglages mémorisés (correspondance des polices, rapport) ───────────

def settings_path():
    return os.path.join(Gimp.directory(), SETTINGS)


def settings_load():
    try:
        with open(settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def settings_save(data):
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


# ─── styles de calque (module du plug-in chopgimp_fx) ───────────────────

def fx_module():
    for path in (os.path.join(os.path.dirname(HERE), "chopgimp_fx"),
                 os.path.join(sys.prefix, "lib", "gimp", "3.0", "plug-ins", "chopgimp_fx"),
                 "/app/lib/gimp/3.0/plug-ins/chopgimp_fx"):
        if os.path.isfile(os.path.join(path, "chopgimp_fx.py")):
            if path not in sys.path:
                sys.path.insert(0, path)
            break
    try:
        import chopgimp_fx
        return chopgimp_fx
    except Exception:          # plug-in absent ou incompatible : pas d'effets
        return None


def gegl_color(rgb, a=1.0):
    """Couleur Photoshop (sRGB, 0..1) → Gegl.Color. set_rgba() attend du
    RGB linéaire : on précise l'espace (None = sRGB, valeurs non linéaires)."""
    c = Gegl.Color.new("black")
    c.set_rgba_with_space(rgb[0], rgb[1], rgb[2], a, None)
    return c


# ─── polices ────────────────────────────────────────────────────────────

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


class Fonts:
    """Retrouve une police installée à partir d'un nom PostScript."""

    STRIP = ("mt", "ps", "std", "pro", "lt", "com")
    REGULAR = ("", "regular", "book", "roman", "normal")

    def __init__(self, memory):
        self.memory = memory                 # nom PS → nom de police choisi
        self.index = {}
        for f in Gimp.fonts_get_list("") or []:
            name = f.get_name()
            self.index.setdefault(norm(name), name)
        self.ps = {}
        try:   # nom PostScript → « famille style » selon fontconfig
            out = subprocess.run(["fc-list", "--format", "%{postscriptname}\t%{family[0]}\t%{style[0]}\n"],
                                 capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                p = line.split("\t")
                if len(p) == 3 and p[0]:
                    self.ps.setdefault(p[0], (p[1], p[2]))
        except (OSError, subprocess.SubprocessError):
            pass
        self.cache = {}

    def lookup(self, psname):
        """→ (nom de police, trouvée ?)"""
        if psname in self.cache:
            return self.cache[psname]
        res = self._lookup(psname)
        self.cache[psname] = res
        return res

    def _find(self, *names):
        for n in names:
            k = norm(n)
            if k in self.index:
                return self.index[k]
        return None

    def _lookup(self, psname):
        if psname in self.memory:
            chosen = self.memory[psname]
            hit = self._find(chosen)
            if hit or Gimp.Font.get_by_name(chosen):    # alias (Sans-serif…) compris
                return hit or chosen, True
        if psname in self.ps:
            fam, style = self.ps[psname]
            hit = self._find(fam + " " + style, *(fam + " " + r for r in self.REGULAR)
                             if norm(style) in self.REGULAR else ())
            if hit:
                return hit, True
        fam, _, style = psname.partition("-")
        cands = [psname, fam + style]
        for suffix in self.STRIP:
            if norm(fam).endswith(suffix):
                cands.append(norm(fam)[:-len(suffix)] + style)
        if norm(style) in self.REGULAR:
            cands += [fam + r for r in self.REGULAR]
        hit = self._find(*cands)
        if hit:
            return hit, True
        return DEFAULT_FONT, False


# ─── rapport ────────────────────────────────────────────────────────────

class Report:
    def __init__(self):
        self.done, self.approx, self.ignored = [], [], []
        self.missing = {}            # nom PS → calques

    def ok(self, layer, what):
        self.done.append("%s — %s" % (layer, what))

    def approximate(self, layer, what):
        self.approx.append("%s — %s" % (layer, what))

    def ignore(self, layer, what):
        self.ignored.append("%s — %s" % (layer, what))

    def text(self):
        out = []
        for title, items in (("Repris", self.done), ("Approximé", self.approx), ("Ignoré", self.ignored)):
            if items:
                out.append("%s (%d) :" % (title, len(items)))
                out += ["  • " + s for s in items]
        if self.missing:
            out.append("Polices absentes :")
            out += ["  • %s (%s)" % (k, ", ".join(v)) for k, v in self.missing.items()]
        return "\n".join(out)


# ─── conversion des textes ──────────────────────────────────────────────

def hex_color(c):
    return "#%02x%02x%02x" % tuple(int(round(max(0.0, min(1.0, v)) * 255)) for v in c[:3])


def esc(s):
    return GLib.markup_escape_text(s, -1)


def text_runs(t):
    """Découpe le texte selon les longueurs des styles : [(texte, style)]."""
    out, pos = [], 0
    for n, st in t.runs:
        out.append((t.text[pos:pos + n], st))
        pos += n
    if pos < len(t.text):
        out.append((t.text[pos:], t.runs[-1][1] if t.runs else {}))
    return out


def clean(s):
    return s.replace("\r", "\n").replace("\x03", "\n")


def build_text(image, L, t, fonts, report, res):
    xx, xy, yx, yy, tx, ty = t.transform
    s = math.hypot(yx, yy) or 1.0
    runs = [(clean(txt), st) for txt, st in text_runs(t)]
    # le dernier retour (fin de paragraphe) n'est pas du texte
    while runs and runs[-1][0].endswith("\n"):
        txt, st = runs[-1]
        runs[-1] = (txt[:-1], st)
        if not runs[-1][0]:
            runs.pop()
    if not runs:
        return None
    base = runs[0][1]

    def font_of(st):
        name, found = fonts.lookup(st.get("font", ""))
        if not found and st.get("font"):
            report.missing.setdefault(st["font"], [])
            if L.name not in report.missing[st["font"]]:
                report.missing[st["font"]].append(L.name)
        return name

    def px(st):
        return st.get("size", 12.0) * s

    font = Gimp.Font.get_by_name(font_of(base)) or Gimp.Font.get_by_name(DEFAULT_FONT)
    plain = "".join(r[0] for r in runs)
    layer = Gimp.TextLayer.new(image, plain, font, px(base), Gimp.Unit.pixel())
    layer.set_name(L.name)
    image.insert_layer(layer, L.gimp.get_parent(), image.get_item_position(L.gimp))
    layer.set_color(gegl_color(base.get("color", (0, 0, 0))))
    layer.set_justification({1: Gimp.TextJustification.RIGHT, 2: Gimp.TextJustification.CENTER}
                            .get(t.justification, Gimp.TextJustification.FILL
                                 if t.justification >= 3 else Gimp.TextJustification.LEFT))
    layer.set_letter_spacing(base.get("tracking", 0.0) / 1000.0 * px(base))
    if not base.get("autoleading", True) and base.get("leading"):
        layer.set_line_spacing(base["leading"] * s - 1.17 * px(base))
    if t.vertical:
        layer.set_base_direction(Gimp.TextDirection.TTB_RTL)
        report.approximate(L.name, "texte vertical (sens d'écriture approché)")

    # plusieurs styles : balises Pango, une propriété par <span> (format GIMP)
    def differs(st, key, default=None):
        return st.get(key, default) != base.get(key, default)

    if len(runs) > 1 or base.get("bold") or base.get("italic") or base.get("underline") or base.get("strike"):
        parts = []
        for txt, st in runs:
            m = esc(txt)
            if differs(st, "font"):
                m = '<span font="%s">%s</span>' % (esc(font_of(st)), m)
            if differs(st, "size"):
                m = '<span size="%d">%s</span>' % (round(px(st) * 72.0 / res * 1024), m)
            if differs(st, "color"):
                m = '<span foreground="%s">%s</span>' % (hex_color(st.get("color", (0, 0, 0))), m)
            if differs(st, "tracking", 0.0):
                m = '<span letter_spacing="%d">%s</span>' % (
                    round(st.get("tracking", 0.0) / 1000.0 * px(st) * 72.0 / res * 1024), m)
            if st.get("baseline"):
                m = '<span rise="%d">%s</span>' % (round(st["baseline"] * s * 72.0 / res * 1024), m)
            for flag, tag in (("bold", "b"), ("italic", "i"), ("underline", "u"), ("strike", "s")):
                if st.get(flag):
                    m = "<%s>%s</%s>" % (tag, m, tag)
            parts.append(m)
        layer.set_markup("<markup>%s</markup>" % "".join(parts))


    # cadre de paragraphe, sinon texte de point placé d'après ses limites
    if t.box:
        bl, bt, br, bb = t.box
        layer.resize((br - bl) * s, (bb - bt) * s)
        ox, oy = bl * s, bt * s
    else:
        bl, bt, br, bb = t.bounds or (0.0, -px(base), 0.0, 0.0)
        w = layer.get_width()
        if t.justification == 2:
            ox = (bl + br) / 2.0 * s - w / 2.0
        elif t.justification == 1:
            ox = br * s - w
        else:
            ox = bl * s
        oy = bt * s
    layer.set_offsets(int(round(tx + ox)), int(round(ty + oy)))

    # rotation / inclinaison / étirement : transformation modifiable
    a, b, c, d = xx / s, yx / s, xy / s, yy / s
    if max(abs(a - 1), abs(b), abs(c), abs(d - 1)) > 1e-3:
        # x' = a x + b y + e autour de l'origine du texte (tx, ty)
        e = tx - a * tx - b * ty
        f = ty - c * tx - d * ty
        layer.transform_matrix(a, b, e, c, d, f, 0.0, 0.0, 1.0)
        what = "rotation" if abs(a * d - b * c - 1) < 1e-2 and abs(a - d) < 1e-2 else "transformation"
        report.ok(L.name, "texte modifiable (%s)" % what)
    else:
        report.ok(L.name, "texte modifiable")

    if t.warp:
        style, bend, hd, vd, vertical = t.warp
        spec = "warp=%s;bend=%g;hdist=%g;vdist=%g" % (style, bend, hd, vd)
        pdb_run("chopgimp-text-fx-set", layer=layer, spec=spec, push_undo=False)
        if vertical:
            report.approximate(L.name, "déformation verticale traitée comme horizontale")
    return layer


# ─── conversion des formes et masques vectoriels ────────────────────────

def make_path(image, name, subs):
    path = Gimp.Path.new(image, name)
    for closed, pts in subs:
        if not pts:
            continue
        flat = []
        for cin, anchor, cout in pts:
            flat += [cin[0], cin[1], anchor[0], anchor[1], cout[0], cout[1]]
        path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER, flat, closed)
    image.insert_path(path, None, -1)
    return path


CAPS = {"butt": Gimp.CapStyle.BUTT, "round": Gimp.CapStyle.ROUND, "square": Gimp.CapStyle.SQUARE}
JOINS = {"miter": Gimp.JoinStyle.MITER, "round": Gimp.JoinStyle.ROUND, "bevel": Gimp.JoinStyle.BEVEL}


def build_shape(image, L, sh, report):
    if sh.fill_kind in ("gradient", "pattern") and not (sh.stroke and sh.stroke["enabled"]):
        make_path(image, L.name, sh.paths)
        report.approximate(L.name, "forme à fond %s : pixels gardés, chemin ajouté"
                           % ("dégradé" if sh.fill_kind == "gradient" else "motif"))
        return None
    path = make_path(image, L.name, sh.paths)
    vl = Gimp.VectorLayer.new(image, path)
    vl.set_name(L.name)
    fill = sh.fill_enabled and sh.fill_kind == "solid" and sh.fill is not None
    vl.set_enable_fill(fill)
    if fill:
        vl.set_fill_color(gegl_color(sh.fill))
    st = sh.stroke
    if st and st["enabled"] and st["color"] is not None and st["width"] > 0:
        vl.set_enable_stroke(True)
        vl.set_stroke_color(gegl_color(st["color"], st["opacity"]))
        vl.set_stroke_width(st["width"])
        vl.set_stroke_cap_style(CAPS[st["cap"]])
        vl.set_stroke_join_style(JOINS[st["join"]])
        if st["dashes"]:
            vl.set_stroke_dash_pattern(st["dashes"])
        if st["align"] != "center":
            report.approximate(L.name, "contour %s centré sur le tracé"
                               % ("intérieur" if st["align"] == "inside" else "extérieur"))
    else:
        vl.set_enable_stroke(False)
        if st and st["enabled"]:
            report.approximate(L.name, "contour en dégradé ou motif ignoré")
    if sh.fill_kind in ("gradient", "pattern"):
        report.approximate(L.name, "fond en dégradé ou motif remplacé par aucun fond")
    image.insert_layer(vl, L.gimp.get_parent(), image.get_item_position(L.gimp))
    vl.refresh()
    report.ok(L.name, "forme vectorielle modifiable")
    return vl


def apply_vector_mask(image, L, sh, report):
    """Masque vectoriel d'un calque de pixels → masque de calque."""
    layer = L.gimp
    path = make_path(image, "Masque vectoriel — " + L.name, sh.paths)
    mask = layer.get_mask()
    if mask is None:
        mask = layer.create_mask(Gimp.AddMaskType.WHITE)
        layer.add_mask(mask)
    image.select_item(Gimp.ChannelOps.REPLACE, path)
    try:
        if not sh.inverted:
            Gimp.Selection.invert(image)
        if not Gimp.Selection.is_empty(image):
            Gimp.context_push()
            try:
                Gimp.context_set_foreground(gegl_color((0, 0, 0)))
                mask.edit_fill(Gimp.FillType.FOREGROUND)
            finally:
                Gimp.context_pop()
    finally:
        Gimp.Selection.none(image)
    report.ok(L.name, "masque vectoriel (masque de calque + chemin)")


# ─── effets (lfx2) ──────────────────────────────────────────────────────

def _first(fx, key, multi):
    if multi in fx and isinstance(fx[multi], list):
        on = [e for e in fx[multi] if isinstance(e, dict) and e.get("enab", True)]
        return on[0] if on else None, len(on)
    e = fx.get(key)
    if isinstance(e, dict) and e.get("enab", True):
        return e, 1
    return None, 0


def apply_effects(image, L, layer, fx, psd, report):
    mod = fx_module()
    if mod is None:
        report.ignore(L.name, "effets (plug-in de styles absent)")
        return
    if not fx.get("masterFXSwitch", True):
        return
    scale = float(fx.get("Scl ", 100.0)) / 100.0
    chosen = {}
    done = []

    def num(e, k, default=0.0):
        try:
            return float(e.get(k, default))
        except (TypeError, ValueError):
            return default

    def angle(e):
        return float(psd.global_angle) if e.get("uglg", False) else num(e, "lagl", 120.0)

    def color(e, default=(0, 0, 0)):
        return gegl_color(psdparse._color(e) or default)

    def opacity(e):
        return num(e, "Opct", 75.0) / 100.0

    for key, multi, style, label in (("DrSh", "dropShadowMulti", "drop-shadow", "ombre portée"),
                                     ("IrSh", "innerShadowMulti", "inner-shadow", "ombre interne")):
        e, n = _first(fx, key, multi)
        if e:
            chosen[style] = ({"dist": num(e, "Dstn") * scale, "radius": num(e, "blur") * scale / 2.0,
                              "angle": angle(e)}, color(e), opacity(e))
            done.append(label + (" (%d, seule la 1re)" % n if n > 1 else ""))

    e, _ = _first(fx, "OrGl", "outerGlowMulti")
    if e:
        chosen["outer-glow"] = ({"radius": num(e, "blur") * scale / 2.0}, color(e, (1, 0.93, 0.6)), opacity(e))
        done.append("lueur externe")
    e, _ = _first(fx, "IrGl", "innerGlowMulti")
    if e:
        chosen["inner-glow"] = ({"radius": num(e, "blur") * scale / 2.0}, color(e, (1, 1, 0.75)), opacity(e))
        done.append("lueur interne")
    e, _ = _first(fx, "ebbl", "bevelEmbossMulti")
    if e:
        chosen["bevel"] = ({"radius": max(1.0, num(e, "blur", 5.0) * scale),
                            "depth": max(1, min(100, int(num(e, "srgR", 100.0) / 5.0))),
                            "angle": angle(e)}, color((), (1, 1, 1)), 1.0)
        done.append("biseau")
    e, _ = _first(fx, "SoFi", "solidFillMulti")
    if e:
        chosen["overlay"] = ({}, color(e), opacity(e))
        done.append("incrustation couleur")
    e, _ = _first(fx, "FrFX", "frameFXMulti")
    if e:
        if str(e.get("PntT", "SClr")) != "SClr":
            report.approximate(L.name, "contour en dégradé ou motif rendu en couleur unie")
        if str(e.get("Styl", "OutF")) != "OutF":
            report.approximate(L.name, "contour intérieur ou centré rendu à l'extérieur")
        chosen["stroke"] = ({"size": num(e, "Sz  ", 3.0) * scale}, color(e), opacity(e))
        done.append("contour")

    # les anciens effets (lrFX) éventuellement posés par l'import de GIMP
    # font doublon avec les effets modernes : on les retire
    if chosen:
        for f in list(layer.get_filters() or []):
            f.delete()
        mod.apply_styles(layer, chosen)
        mod.parasite_set(layer, mod.STYLE_PARASITE, mod.style_to_json(chosen))
        report.ok(L.name, "effets : " + ", ".join(done))

    e, _ = _first(fx, "GrFl", "gradientFillMulti")
    if e:
        grad = e.get("Grad", {})
        stops = [s for s in (grad.get("Clrs", []) if isinstance(grad, dict) else []) if isinstance(s, dict)]
        c1 = psdparse._color(stops[0]) if stops else None
        c2 = psdparse._color(stops[-1]) if stops else None
        if c1 and c2:
            mod.gradient_overlay(image, layer, num(e, "Angl", 90.0), bool(e.get("Rvrs", False)),
                                 gegl_color(c1), gegl_color(c2))
            report.ok(L.name, "incrustation de dégradé (calque écrêté)")
            if len(stops) > 2:
                report.approximate(L.name, "dégradé à %d couleurs ramené à 2" % len(stops))
        else:
            report.ignore(L.name, "incrustation de dégradé illisible")
    for key, label in (("ChFX", "satin"), ("patternFill", "incrustation de motif")):
        e = fx.get(key)
        if isinstance(e, dict) and e.get("enab", False):
            report.ignore(L.name, label)


# ─── calques de réglage → filtres modifiables ───────────────────────────

ADJ_PREFIX = "◐ "


def new_filter(drawable, op, name, props):
    f = Gimp.DrawableFilter.new(drawable, op, name)
    cfg = f.get_config()
    for k, v in props.items():
        try:
            cfg.set_property(k, v)
        except (TypeError, ValueError):
            pass
    f.update()
    drawable.append_filter(f)
    return f


def gimp_curve(points):
    c = Gimp.Curve.new()
    c.set_curve_type(Gimp.CurveType.SMOOTH)
    c.clear_points()
    for x, y in sorted(points):
        c.add_point(max(0.0, min(1.0, x / 255.0)), max(0.0, min(1.0, y / 255.0)))
    return c


CHANNELS = [Gimp.HistogramChannel.VALUE, Gimp.HistogramChannel.RED,
            Gimp.HistogramChannel.GREEN, Gimp.HistogramChannel.BLUE]


def adjustment_filters(target, adj, name):
    """Pose le réglage Photoshop comme filtre(s) non destructif(s) sur target.
    → (nombre de filtres, texte d'approximation ou None)."""
    k = adj["kind"]
    n, approx = 0, None
    if k == "levels":
        for ch, (ilo, ihi, olo, ohi, g) in zip(CHANNELS, adj["records"]):
            if (ilo, ihi, olo, ohi, round(g, 2)) == (0, 255, 0, 255, 1.0):
                continue
            new_filter(target, "gimp:levels", name, {
                "channel": ch, "low-input": ilo / 255.0, "high-input": ihi / 255.0,
                "gamma": max(0.1, min(10.0, g)), "low-output": olo / 255.0, "high-output": ohi / 255.0})
            n += 1
    elif k == "curves":
        for ch, pts in sorted(adj["curves"].items()):
            if len(pts) < 2 or all(a == b for a, b in pts):
                continue
            new_filter(target, "gimp:curves", name, {"channel": CHANNELS[ch], "curve": gimp_curve(pts)})
            n += 1
    elif k == "brightness":
        new_filter(target, "gimp:brightness-contrast", name, {
            "brightness": max(-1.0, min(1.0, adj["brightness"] / 150.0)),
            "contrast": max(-1.0, min(1.0, adj["contrast"] / 100.0))})
        n = 1
        approx = "luminosité/contraste : échelle de GIMP, rendu proche"
    elif k == "hue-saturation":
        new_filter(target, "gimp:hue-saturation", name, {
            "hue": adj["hue"] / 180.0, "saturation": adj["saturation"] / 100.0,
            "lightness": adj["lightness"] / 100.0})
        n = 1
    elif k == "colorize":
        new_filter(target, "gimp:colorize", name, {
            "hue": (adj["hue"] % 360) / 360.0, "saturation": adj["saturation"] / 100.0,
            "lightness": adj["lightness"] / 100.0})
        n = 1
    elif k == "color-balance":
        for rng, vals in ((Gimp.TransferMode.SHADOWS, adj["shadows"]),
                          (Gimp.TransferMode.MIDTONES, adj["midtones"]),
                          (Gimp.TransferMode.HIGHLIGHTS, adj["highlights"])):
            if any(vals):
                new_filter(target, "gimp:color-balance", name, {
                    "range": rng, "cyan-red": vals[0] / 100.0, "magenta-green": vals[1] / 100.0,
                    "yellow-blue": vals[2] / 100.0, "preserve-luminosity": adj["preserve"]})
                n += 1
    elif k == "invert":
        new_filter(target, "gegl:invert-gamma", name, {})
        n = 1
    elif k == "posterize":
        new_filter(target, "gimp:posterize", name, {"levels": max(2, adj["levels"])})
        n = 1
    elif k == "threshold":
        new_filter(target, "gimp:threshold", name, {"low": adj["level"] / 255.0, "high": 1.0})
        n = 1
    elif k == "exposure":
        new_filter(target, "gegl:exposure", name, {"exposure": adj["exposure"],
                                                   "black-level": adj["offset"]})
        n = 1
        if abs(adj["gamma"] - 1.0) > 1e-3:
            new_filter(target, "gimp:levels", name, {"gamma": 1.0 / max(0.1, adj["gamma"])})
            n = 2
    elif k == "black-white":
        tot = adj["red"] + adj["green"] + adj["blue"] or 1.0
        new_filter(target, "gegl:mono-mixer", name, {
            "red": adj["red"] / tot, "green": adj["green"] / tot, "blue": adj["blue"] / tot,
            "preserve-luminosity": False})
        n = 1
        approx = "noir et blanc : 3 couleurs sur 6 (jaune, cyan, magenta ignorés)"
        if adj["tint"]:
            approx += ", teinte ignorée"
    elif k == "channel-mixer":
        rows = adj["rows"]
        if adj["mono"]:
            r = rows[0]
            new_filter(target, "gegl:mono-mixer", name, {"red": r[0] / 100.0, "green": r[1] / 100.0,
                                                         "blue": r[2] / 100.0})
        else:
            props = {}
            for i, out in enumerate("rgb"):
                for j, inn in enumerate("rgb"):
                    props["%s%s-gain" % (out, inn)] = rows[i][j] / 100.0
            new_filter(target, "gegl:channel-mixer", name, props)
        n = 1
    elif k == "vibrance":
        new_filter(target, "gegl:saturation", name, {
            "scale": max(0.0, 1.0 + (adj["vibrance"] * 0.5 + adj["saturation"]) / 100.0)})
        n = 1
        approx = "vibrance rendue par une saturation"
    return n, approx


def build_adjustment(image, L, adj, report):
    """Un calque de réglage Photoshop agit sur ce qui est dessous :
    écrêté → filtre sur le calque de base ; sinon groupe « ◐ » qui contient
    les calques du dessous (comme Calque > Nouveau calque de réglage)."""
    name = L.name
    if adj is None or adj["kind"] == "unsupported":
        report.ignore(name, "réglage %s non repris" % (adj or {}).get("key", "?"))
        return None
    layer = L.gimp
    parent = layer.get_parent()
    sibs = list(parent.get_children() if parent else image.get_layers())
    idx = sibs.index(layer)
    below = sibs[idx + 1:]
    if L.clipping and below:
        target = below[0]
        created = None
    else:
        if not below:
            report.ignore(name, "réglage sans rien en dessous")
            return None
        created = Gimp.GroupLayer.new(image, ADJ_PREFIX + name)
        image.insert_layer(created, parent, image.get_item_position(below[0]))
        for l in below:
            image.reorder_item(l, created, len(created.get_children()))
        target = created
    n, approx = adjustment_filters(target, adj, name)
    if n == 0:
        report.ok(name, "réglage neutre (aucun effet)")
    else:
        for f in target.get_filters() or []:
            if f.get_name() == name:
                f.set_opacity(L.opacity / 255.0)
                f.set_visible(L.visible)
        report.ok(name, "réglage modifiable (%s)" % adj["kind"])
    if approx:
        report.approximate(name, approx)
    if layer.get_mask() is not None:
        report.approximate(name, "masque du réglage non repris (le réglage agit partout)")
    return created


# ─── calque de remplissage couleur → calque vectoriel ───────────────────

def build_fill(image, L, report):
    sh = L.shape()
    if sh is not None and sh.paths:
        return None                     # forme : traitée par build_shape
    data = L.blocks.get("SoCo")
    if data is None:
        report.approximate(L.name, "remplissage %s : pixels gardés"
                           % ("dégradé" if "GdFl" in L.blocks else "motif"))
        return None
    try:
        rgb = psdparse._color(psdparse.descriptor_block(data, 0))
    except psdparse.PARSE_ERRORS:
        rgb = None
    if rgb is None:
        return None
    w, h = image.get_width(), image.get_height()
    path = Gimp.Path.new(image, L.name)
    path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER,
                                [0, 0, 0, 0, 0, 0, w, 0, w, 0, w, 0, w, h, w, h, w, h, 0, h, 0, h, 0, h],
                                True)
    image.insert_path(path, None, -1)
    vl = Gimp.VectorLayer.new(image, path)
    vl.set_name(L.name)
    vl.set_enable_fill(True)
    vl.set_fill_color(gegl_color(rgb))
    vl.set_enable_stroke(False)
    image.insert_layer(vl, L.gimp.get_parent(), image.get_item_position(L.gimp))
    vl.refresh()
    report.ok(L.name, "calque de remplissage couleur modifiable")
    return vl


# ─── objets dynamiques → calques liés ───────────────────────────────────

def build_smart(image, L, so, files, cache_dir, report):
    entry = files.get(so["uid"])
    if entry is None:
        report.ignore(L.name, "objet dynamique lié à un fichier externe (pixels gardés)")
        return None
    fname, data = entry
    safe = re.sub(r"[^\w.\- ]", "_", fname or "objet") or "objet"
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, "%s_%s" % (re.sub(r"\W", "", so["uid"])[:12], safe))
    with open(path, "wb") as f:
        f.write(data)
    try:
        ll = Gimp.LinkLayer.new(image, Gio.File.new_for_path(path))
        err = None
    except Exception as e:
        ll, err = None, e
    if ll is None:
        # pas de calque lié : le fichier extrait ne sert à rien
        try:
            os.remove(path)
        except OSError:
            pass
        report.ignore(L.name, "objet dynamique illisible%s" % (" (%s)" % err if err else ""))
        return None
    ll.set_name(L.name)
    image.insert_layer(ll, L.gimp.get_parent(), image.get_item_position(L.gimp))
    c = so["corners"]
    if len(c) == 8:
        ll.transform_perspective(c[0], c[1], c[2], c[3], c[6], c[7], c[4], c[5])
    report.ok(L.name, "objet dynamique → calque lié (%s, extrait dans le cache)" % fname)
    return ll


# ─── assemblage ─────────────────────────────────────────────────────────

def pdb_run(name, **kw):
    proc = Gimp.get_pdb().lookup_procedure(name)
    if proc is None:
        return None
    cfg = proc.create_config()
    for k, v in kw.items():
        cfg.set_property(k, v)
    return proc.run(cfg)


def walk(layers):
    for l in layers:
        yield l
        if isinstance(l, Gimp.GroupLayer):
            yield from walk(l.get_children())


def copy_props(src, dst):
    dst.set_opacity(src.get_opacity())
    dst.set_mode(src.get_mode())
    dst.set_visible(src.get_visible())
    try:
        dst.set_lock_position(src.get_lock_position())
    except Exception:
        pass


class Originals:
    """Groupe masqué où sont rangés les calques remplacés."""

    def __init__(self, image):
        self.image = image
        self.group = None

    def keep(self, layer, new):
        if self.group is None:
            self.group = Gimp.GroupLayer.new(self.image, ORIGINALS)
            self.image.insert_layer(self.group, None, 0)
            self.group.set_visible(False)
        # le masque de calque et l'écrêtage restent sur la version modifiable
        mask = layer.get_mask()
        if mask is not None and new.get_mask() is None:
            nm = new.create_mask(Gimp.AddMaskType.WHITE)
            new.add_mask(nm)
            self.image.select_item(Gimp.ChannelOps.REPLACE, mask)
            try:
                Gimp.Selection.invert(self.image)
                if not Gimp.Selection.is_empty(self.image):
                    Gimp.context_push()
                    try:
                        Gimp.context_set_foreground(gegl_color((0, 0, 0)))
                        nm.edit_fill(Gimp.FillType.FOREGROUND)
                    finally:
                        Gimp.context_pop()
            finally:
                Gimp.Selection.none(self.image)
        self.stash(layer)

    def stash(self, layer):
        if self.group is None:
            self.group = Gimp.GroupLayer.new(self.image, ORIGINALS)
            self.image.insert_layer(self.group, None, 0)
            self.group.set_visible(False)
        self.image.reorder_item(layer, self.group, 0)
        layer.set_visible(True)
        layer.set_name("⟲ " + layer.get_name())


def convert(image, path, run_mode, report):
    psd = psdparse.parse(path)
    # identifiant Photoshop → calque GIMP ; l'import de GIMP donne parfois
    # le même identifiant au groupe d'écrêtage qu'il crée : le vrai calque
    # l'emporte sur le groupe
    by_id = {}
    for lay in walk(image.get_layers()):
        t = lay.get_tattoo()
        if t not in by_id or (isinstance(by_id[t], Gimp.GroupLayer) and
                              not isinstance(lay, Gimp.GroupLayer)):
            by_id[t] = lay

    res = image.get_resolution()[2] if hasattr(image, "get_resolution") else 72.0
    todo, adjustments = [], []
    for L in psd.layers:
        if L.section in (1, 2, 3) or L.id not in by_id:
            continue
        L.gimp = by_id[L.id]
        try:                        # un calque malformé ne bloque pas les autres
            adj = L.adjustment()
            if adj is not None:
                adjustments.append((L, adj))
                continue
            t = L.text() if "TySh" in L.blocks else None
            sh = L.shape() if ("vmsk" in L.blocks or "vsms" in L.blocks) else None
            so = L.smart_object()
            fill = any(k in L.blocks for k in ("SoCo", "GdFl", "PtFl")) and not (sh and sh.is_shape)
            fx = L.effects()
        except Exception as e:
            report.ignore(L.name, "informations illisibles (%s)" % e)
            continue
        if t or sh or fx or so or fill:
            todo.append((L, t, sh, fx, so, fill))
    if not todo and not adjustments:
        return psd

    settings = settings_load()
    fonts = Fonts(settings.get("fonts", {}))

    # polices absentes : choix d'un remplacement avant de construire
    if run_mode == Gimp.RunMode.INTERACTIVE:
        missing = []
        for L, t, *_ in todo:
            for _, st in (t.runs if t else []):
                ps = st.get("font")
                if ps and ps not in missing and not fonts.lookup(ps)[1]:
                    missing.append(ps)
        if missing:
            chosen, remember = missing_fonts_dialog(missing)
            for ps, name in chosen.items():
                fonts.cache[ps] = (name, True)
                report.approximate(ps, "police remplacée par « %s »" % name)
            if remember and chosen:
                settings.setdefault("fonts", {}).update(chosen)
                settings_save(settings)

    keep = Originals(image)
    files = None
    # dossier propre au fichier : deux PSD de même nom ne se mélangent pas
    digest = hashlib.sha1(os.path.abspath(path).encode("utf-8", "surrogateescape")).hexdigest()[:8]
    cache_dir = os.path.join(Gimp.directory(), "psd-objets",
                             "%s_%s" % (re.sub(r"[^\w.\- ]", "_", os.path.basename(path)), digest))
    for L, t, sh, fx, so, fill in todo:
        new = None
        try:
            if t:
                new = build_text(image, L, t, fonts, report, res)
            elif so:
                if files is None:
                    files = psdparse.linked_files(psd)
                new = build_smart(image, L, so, files, cache_dir, report)
            elif sh and sh.is_shape:
                new = build_shape(image, L, sh, report)
            elif fill:
                new = build_fill(image, L, report)
            if sh and not sh.is_shape:
                apply_vector_mask(image, L, sh, report)
        except Exception as e:      # un calque raté ne bloque pas les autres
            report.ignore(L.name, "conversion impossible (%s)" % e)
            new = None
        target = new or L.gimp
        if new is not None:
            copy_props(L.gimp, new)
            keep.keep(L.gimp, new)
            new.set_name(L.name)
        if fx:
            try:
                apply_effects(image, L, target, fx, psd, report)
            except Exception as e:
                report.ignore(L.name, "effets (%s)" % e)

    # réglages en dernier, du bas vers le haut : chacun regroupe ce qui est
    # en dessous de lui (y compris les réglages déjà convertis)
    for L, adj in adjustments:
        try:
            build_adjustment(image, L, adj, report)
            keep.stash(L.gimp)
        except Exception as e:
            report.ignore(L.name, "réglage (%s)" % e)
    return psd


# ─── fenêtres ───────────────────────────────────────────────────────────

def missing_fonts_dialog(missing):
    GimpUi.init("chopgimp_psd")
    dialog = GimpUi.Dialog(title="Polices absentes", role="chopgimp-psd-fonts", modal=True)
    dialog.add_button("_Ignorer", Gtk.ResponseType.CANCEL)
    dialog.add_button("_Remplacer", Gtk.ResponseType.OK)
    box = dialog.get_content_area()
    grid = Gtk.Grid(column_spacing=12, row_spacing=6, margin=12)
    box.pack_start(grid, True, True, 0)
    grid.attach(Gtk.Label(label="Ces polices du fichier ne sont pas installées.\n"
                                "Choisissez une police de remplacement pour chacune :",
                          xalign=0), 0, 0, 2, 1)
    choosers = {}
    for i, ps in enumerate(missing, 1):
        grid.attach(Gtk.Label(label=ps, xalign=0), 0, i, 1, 1)
        ch = GimpUi.FontChooser.new(None, None, Gimp.Font.get_by_name(DEFAULT_FONT))
        grid.attach(ch, 1, i, 1, 1)
        choosers[ps] = ch
    remember = Gtk.CheckButton(label="Mémoriser ces correspondances")
    remember.set_active(True)
    grid.attach(remember, 0, len(missing) + 1, 2, 1)
    dialog.show_all()
    chosen = {}
    if dialog.run() == Gtk.ResponseType.OK:
        for ps, ch in choosers.items():
            f = ch.get_resource()
            if f is not None:
                chosen[ps] = f.get_name()
    rem = remember.get_active()
    dialog.destroy()
    return chosen, rem


def report_dialog(report, settings):
    GimpUi.init("chopgimp_psd")
    dialog = GimpUi.Dialog(title="Import PSD — rapport", role="chopgimp-psd-report", modal=True)
    dialog.add_button("_Fermer", Gtk.ResponseType.CLOSE)
    box = dialog.get_content_area()
    view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD, margin=12)
    view.get_buffer().set_text(report.text())
    sw = Gtk.ScrolledWindow(min_content_height=260, min_content_width=480)
    sw.add(view)
    box.pack_start(sw, True, True, 0)
    quiet = Gtk.CheckButton(label="Ne plus afficher ce rapport (sauf polices absentes)", margin=12)
    box.pack_start(quiet, False, False, 0)
    dialog.show_all()
    dialog.run()
    if quiet.get_active():
        settings["quiet"] = True
        settings_save(settings)
    dialog.destroy()


# ─── procédure de chargement ────────────────────────────────────────────

def load(procedure, run_mode, file, metadata, flags, config, data):
    res = pdb_run("file-psd-load", **{"run-mode": Gimp.RunMode.NONINTERACTIVE, "file": file})
    if res is None or res.index(0) != Gimp.PDBStatusType.SUCCESS:
        err = res.index(1) if res is not None and res.length() > 1 else None
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error(str(err or "Import PSD impossible")))
    image = res.index(1)
    report = Report()
    path = file.get_path()
    if path and os.environ.get("CHOPGIMP_PSD_PLAIN") != "1":
        image.undo_disable()
        Gimp.context_push()
        try:
            convert(image, path, run_mode, report)
        except Exception as e:       # analyse impossible : on garde l'import GIMP
            report.ignore(os.path.basename(path), "analyse PSD impossible (%s)" % e)
        finally:
            Gimp.context_pop()
            image.undo_enable()
    # rapport : parasite de l'image (tests, scripts) + fenêtre
    text = report.text()
    if text:
        data = [b - 256 if b > 127 else b for b in text.encode("utf-8")]   # octets signés
        image.attach_parasite(Gimp.Parasite.new("chopgimp-psd-report", 0, data))
    if run_mode == Gimp.RunMode.INTERACTIVE and (report.approx or report.ignored or report.missing):
        settings = settings_load()
        if not settings.get("quiet") or report.missing:
            report_dialog(report, settings)
    return Gimp.ValueArray.new_from_values([
        GObject.Value(Gimp.PDBStatusType, Gimp.PDBStatusType.SUCCESS),
        GObject.Value(Gimp.Image, image),
    ]), flags


def thumbnail(procedure, file, size, config, data):
    """Vignette : celle de l'import de GIMP (image composite du PSD)."""
    res = pdb_run("file-psd-load-thumb", file=file, **{"thumb-size": size})
    if res is None or res.index(0) != Gimp.PDBStatusType.SUCCESS:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error("Vignette PSD impossible"))
    return res


class ChopGimpPSD(Gimp.PlugIn):
    def do_query_procedures(self):
        return [PROC_THUMB, PROC]

    def do_create_procedure(self, name):
        if name == PROC_THUMB:
            procedure = Gimp.ThumbnailProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, thumbnail, None)
            procedure.set_documentation("Vignette d'un PSD/PSB", "Délègue à file-psd-load-thumb.", name)
            procedure.set_attribution("ChopGimp", "ChopGimp", "2026")
            return procedure
        procedure = Gimp.LoadProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, load, None)
        procedure.set_menu_label("Photoshop (calques modifiables)")
        procedure.set_documentation("Ouvre un PSD/PSB en gardant textes, formes et effets modifiables",
                                    "Import de GIMP, puis reconstruction des textes, formes vectorielles, "
                                    "masques vectoriels et styles de calque d'après le fichier.", name)
        procedure.set_attribution("ChopGimp", "ChopGimp", "2026")
        procedure.set_mime_types("image/x-psd")
        procedure.set_extensions("psd,psb")
        procedure.set_magics("0,string,8BPS")
        procedure.set_priority(-1)
        procedure.set_thumbnail_loader(PROC_THUMB)
        return procedure


if __name__ == "__main__":
    Gimp.main(ChopGimpPSD.__gtype__, sys.argv)

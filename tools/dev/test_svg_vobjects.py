#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChopGimp 3.27.2 (lot V4) — aller-retour SVG des objets vectoriels, sans GIMP.

  SVG (groupes, dégradés, découpes, transformations, calques, texte)
    → plug-ins/chopgimp_pdf/vobjects.py (import : plan + XML du modèle)
    → plug-ins/common/file-svg-vobjects.h (export, compilé seul dans le SDK
      flatpak, comme file-svg.c l'appelle)
    → réimport → même structure (calques, objets, groupes, découpes,
      dégradés, noms, transformations, géométrie).

Format 2 du modèle (3.27.2) : pile « Aspect » (plusieurs fonds / contours,
opacité, mode, masqué, couleur globale, profil de largeur, pointes de
flèche) : import (fill-opacity, stroke-opacity, marqueurs), export
(<g chopgimp:aspect>, <marker>, contour à profil en tracé plein, nuancier
Inkscape) et aller-retour.

Usage : python3 tools/dev/test_svg_vobjects.py [-v]
"""
import math
import os
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "plug-ins", "chopgimp_pdf"))
import vobjects as V  # noqa: E402

HEADER = os.path.join(ROOT, "build", "gimp-src", "plug-ins", "common", "file-svg-vobjects.h")
VERBOSE = "-v" in sys.argv

TEST_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="400" height="300" viewBox="0 0 200 150">
  <style>.bleu { fill: #2050c0; stroke: #000; stroke-width: 2 } #etoile { fill-rule: evenodd }</style>
  <defs>
    <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ff0000"/>
      <stop offset="1" stop-color="#0000ff" stop-opacity="0.5"/>
    </linearGradient>
    <linearGradient id="lgu" gradientUnits="userSpaceOnUse" x1="20" y1="0" x2="60" y2="0"
                    gradientTransform="rotate(30 40 40)" xlink:href="#lg"/>
    <radialGradient id="rg" cx="0.5" cy="0.5" r="0.5" fx="0.3" fy="0.3">
      <stop offset="0%" style="stop-color:white"/>
      <stop offset="100%" style="stop-color:rgb(0,128,0)"/>
    </radialGradient>
    <clipPath id="clipRond"><circle id="rond" cx="50" cy="50" r="30"/></clipPath>
    <clipPath id="clipRect"><rect x="120" y="10" width="40" height="40" transform="rotate(10 140 30)"/></clipPath>
    <path id="motif" d="M0 0 L10 0 L5 8 Z"/>
  </defs>
  <g inkscape:groupmode="layer" inkscape:label="Fond" id="layer1">
    <rect id="ciel" x="0" y="0" width="200" height="150" fill="url(#lg)"/>
    <rect inkscape:label="Bande" x="10" y="100" width="180" height="20" rx="5"
          style="fill:url(#lgu);stroke:#333;stroke-width:1.5;stroke-dasharray:4 2"/>
  </g>
  <g inkscape:groupmode="layer" inkscape:label="Dessin" transform="translate(5,0)">
    <g id="soleil" inkscape:label="Soleil" clip-path="url(#clipRond)" opacity="0.8">
      <circle cx="50" cy="50" r="40" fill="url(#rg)"/>
      <path class="bleu" d="M20 20 h60 v60 h-60 z" transform="rotate(45 50 50)"/>
    </g>
    <path id="etoile" inkscape:label="Étoile" clip-path="url(#clipRect)"
          d="M140 5 L150 45 L115 20 H165 L130 45 Z" fill="#e0a000" stroke="none"
          transform="scale(1.1) translate(-10,-2)" style="mix-blend-mode:multiply"/>
    <g inkscape:label="Clones">
      <use xlink:href="#motif" x="20" y="130" fill="purple"/>
      <use xlink:href="#motif" x="40" y="130" fill="teal" transform="skewX(10)"/>
      <ellipse cx="100" cy="135" rx="15" ry="5" fill="none" stroke="#c00" stroke-width="3"
               stroke-linecap="round" display="none"/>
      <polygon points="150,140 160,125 170,140" fill="rgba(0,0,0,0.5)"/>
      <path d="M175 125 a10 5 30 1 1 10 10 q5 5 10 0 t10 0" fill="none" stroke="black"/>
    </g>
  </g>
  <g inkscape:groupmode="layer" inkscape:label="Textes">
    <path inkscape:label="Souligné" d="M10 145 H90" stroke="#000"/>
    <text x="10" y="140" style="font-size:12px;font-family:Sans;fill:#123456">Bonjour</text>
  </g>
</svg>
"""


# ─── export (comme svg_export_layers de file-svg.c) ─────────────────────

HARNESS = r"""
#include <stdio.h>
#include <stdlib.h>
#include "file-svg-vobjects.h"
int main (int argc, char **argv)
{
  gchar   *xml = NULL;
  GString *s   = g_string_new (NULL);
  gboolean ok;
  if (! g_file_get_contents (argv[1], &xml, NULL, NULL)) return 2;
  ok = svg_vobjects_write (xml, argv[2], atoi (argv[3]), g_ascii_strtod (argv[4], NULL),
                           atoi (argv[5]), atoi (argv[6]), s, argv[7]);
  fputs (s->str, stdout);
  return ok ? 0 : 3;
}
"""


def build_harness(tmp):
    src = os.path.join(tmp, "harness.c")
    exe = os.path.join(tmp, "harness")
    with open(src, "w") as f:
        f.write(HARNESS)
    cmd = "gcc -Wall -Wno-unused-function -O1 -I%s %s -o %s $(pkg-config --cflags --libs glib-2.0) -lm" % (
        shlex.quote(os.path.dirname(HEADER)), shlex.quote(src), shlex.quote(exe))
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    runner = []
    if r.returncode != 0:
        # pas de GLib de développement sur l'hôte : le SDK flatpak
        runner = ["flatpak", "run", "--filesystem=%s" % tmp, "--filesystem=%s" % os.path.dirname(HEADER),
                  "--command=bash", "org.gnome.Sdk//51", "-c"]
        r = subprocess.run(runner + [cmd], capture_output=True, text=True)
    if r.returncode != 0 or r.stderr.strip():
        print(r.stdout + r.stderr)
    if r.returncode != 0:
        raise SystemExit("compilation du banc impossible")
    return exe, runner


def run_harness(h, xml, name, lid, opacity, hidden, spacing, tmp):
    exe, runner = h
    path = os.path.join(tmp, "layer%d.xml" % lid)
    with open(path, "w") as f:
        f.write(xml)
    args = [exe, path, name, str(lid), repr(opacity), str(int(hidden)), "0", spacing]
    if runner:
        r = subprocess.run(runner + [" ".join(shlex.quote(a) for a in args)], capture_output=True, text=True)
    else:
        r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode not in (0, 3):
        raise SystemExit("banc : erreur %d\n%s" % (r.returncode, r.stderr))
    return r.stdout if r.returncode == 0 else None, r.stderr


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def export_plan(items, h, tmp, w, hgt):
    """Le document SVG qu'écrirait file-svg.c pour les calques du plan."""
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
           '<svg xmlns="http://www.w3.org/2000/svg" xmlns:svg="http://www.w3.org/2000/svg"\n'
           '     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"\n'
           '     xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"\n'
           '     xmlns:chopgimp="http://chopgimp.org/namespaces/chopgimp"\n'
           '     version="1.1" width="%sin" height="%sin" viewBox="0 0 %d %d">\n  <defs>\n  </defs>\n'
           % ("%.10g" % (w / 96.0), "%.10g" % (hgt / 96.0), w, hgt)]
    ids = [0]

    def walk(items, spacing):
        for it in items:          # du bas vers le haut, comme file-svg.c
            sp = spacing + "  "
            hidden = not it.get("visible", True)
            if it["kind"] == "group":
                out.append('%s<g id="group%d" opacity="%s" inkscape:label="%s" inkscape:groupmode="layer"%s>\n'
                           % (sp, ids[0], repr(it["opacity"]), esc(it["name"]),
                              ' style="display:none"' if hidden else ""))
                ids[0] += 1
                walk(it["items"], sp)
                out.append("%s</g>\n" % sp)
            elif it["kind"] == "vector":
                xml = V.to_xml(it["nodes"])
                ids[0] += 1
                frag, err = run_harness(h, xml, it["name"], ids[0], it["opacity"], hidden, sp, tmp)
                if err.strip():
                    raise SystemExit("banc : " + err)
                assert frag is not None, "objets non exportés : %s" % it["name"]
                # inkscape:label sur le premier élément, comme file-svg.c
                i = frag.index("<g ") + 2
                out.append(frag[:i] + ' inkscape:label="%s"' % esc(it["name"]) + frag[i:])
            elif it["kind"] == "text":
                r, g, b, _ = it["rgba"]
                out.append('%s<text inkscape:label="%s" x="%r" y="%r" style="font-size:%rpx;'
                           'font-family:%s;fill:#%02x%02x%02x">%s</text>\n'
                           % (sp, esc(it["name"]), it["x"], it["y"], it["size"], esc(it["family"]),
                              int(r * 255 + .5), int(g * 255 + .5), int(b * 255 + .5), esc(it["text"])))
    walk(items, "")
    out.append("</svg>\n")
    return "".join(out)


# ─── comparaison ────────────────────────────────────────────────────────

def r6(v):
    return round(v, 2) + 0.0


def paint_sig(p, kind="fill"):
    """Peinture d'un fond / contour (format 2). Une couleur : alpha × opacité
    (fill-opacity les confond) ; la couleur globale n'est pas relue."""
    t = p.get("type", "none")
    op = p.get("opacity", 1.0)
    s = [kind, t]
    if t == "color":
        c = p["rgba"]
        s.append(tuple(round(v, 2) for v in c[:3]) + (round(c[3] * op, 2),))
    elif t in ("linear", "radial"):
        s.append(tuple(round(p[k], 3) for k in ("x1", "y1", "x2", "y2", "r")))
        s.append(tuple((round(o, 3), tuple(round(v, 2) for v in c)) for o, c in p["stops"]))
        s.append(round(op, 3))
    s.append((p.get("mode", "normal"), p.get("visible", True)))
    if kind == "stroke" and t != "none":
        s.append((round(p["width"], 3), p.get("cap") if not p.get("profile") else None,
                  p.get("join") if not p.get("profile") else None,
                  round(p.get("miter", 4), 3) if not p.get("profile") else None,
                  tuple(round(v, 3) for v in p.get("dash") or ()), p.get("align", "center"),
                  p.get("profile"), p.get("arrow_start"), p.get("arrow_end"),
                  round(p.get("arrow_scale", 1.0), 2) if p.get("arrow_start") or p.get("arrow_end") else None))
    return tuple(s)


def stack_sig(n):
    return tuple(paint_sig(e, k) for k, e in V.entries_of(n) if e.get("type", "none") != "none")


def node_sig(n, m=None):
    """Structure + monde (transformations appliquées) d'un objet."""
    wm = V.compose(n.transform, m)
    if n.kind == "group":
        return ("G", n.name, n.clip, round(n.opacity, 3), n.mode, n.visible,
                tuple(node_sig(c, wm) for c in n.children))
    b = V.bbox(V.tf_subpaths(n.subpaths, wm))
    return ("P", n.name, round(n.opacity, 3), n.mode, n.visible, n.nonzero,
            len(n.subpaths), tuple(len(k) for _, k in n.subpaths),
            tuple(r6(v) for v in b) if b else None, stack_sig(n))


def plan_sig(items):
    out = []
    for it in items:
        if it["kind"] == "group":
            out.append(("group", it["name"], it["visible"], round(it["opacity"], 3), plan_sig(it["items"])))
        elif it["kind"] == "vector":
            out.append(("vector", it["name"], it["visible"], round(it["opacity"], 3),
                        tuple(node_sig(n) for n in it["nodes"])))
        elif it["kind"] == "text":
            out.append(("text", it["text"], round(it["x"], 1), round(it["y"], 1), round(it["size"], 2)))
        else:
            out.append((it["kind"], it["name"]))
    return out


def diff(a, b, path="", out=None):
    out = [] if out is None else out
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            out.append("%s : longueurs %d ≠ %d" % (path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, "%s/%d" % (path, i), out)
    elif a != b:
        out.append("%s : %r ≠ %r" % (path, a, b))
    return out


def dump(items, indent=""):
    for it in items:
        print("%s%s « %s »%s" % (indent, it["kind"], it.get("name", ""), "" if it.get("visible", True) else " (masqué)"))
        if it["kind"] == "group":
            dump(it["items"], indent + "  ")
        elif it["kind"] == "vector":
            def nd(n, ind):
                extra = []
                if n.clip:
                    extra.append("découpe")
                if n.kind == "path":
                    extra.append(n.fill["type"])
                    if n.stroke["type"] != "none":
                        extra.append("contour " + n.stroke["type"])
                if not n.visible:
                    extra.append("masqué")
                if n.mode != "normal":
                    extra.append(n.mode)
                print("%s%s « %s » %s" % (ind, n.kind, n.name, ", ".join(extra)))
                for c in n.children:
                    nd(c, ind + "  ")
            for n in it["nodes"]:
                nd(n, indent + "  ")


def import_svg(text, name):
    """Comme import_svg() de chopgimp_pdf.py : taille en pixels entiers."""
    root = ET.fromstring(text)
    w0, h0 = V.image_size(V.parse_length(root.get("width"), 0, 0), V.parse_length(root.get("height"), 0, 0))
    imp = V.SvgImport(root, V.svg_base_matrix(root, w0, h0), name)
    return imp.plan(), imp.stats, (w0, h0)


# ─── tests ──────────────────────────────────────────────────────────────

def check(cond, msg, failures):
    print(("  ok    " if cond else "  ÉCHEC ") + msg)
    if not cond:
        failures.append(msg)


V2_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="200" height="100" viewBox="0 0 200 100">
  <defs>
    <marker id="Arrow1Lend" inkscape:stockid="Arrow1Lend" orient="auto" refX="0" refY="0"
            style="overflow:visible">
      <path transform="scale(0.8) rotate(180) translate(12.5,0)" style="fill-rule:evenodd;stroke:#000;stroke-width:1pt"
            d="M 0,0 5,-5 -12.5,0 5,5 Z"/>
    </marker>
    <marker id="ArrowWide" orient="auto-start-reverse" markerWidth="1" markerHeight="1"
            viewBox="0 0 1 1" style="overflow:visible">
      <path style="fill:none;stroke:context-stroke;stroke-width:1" d="M 3,-3 0,0 3,3"
            transform="rotate(180) scale(0.7)"/>
    </marker>
    <marker id="Dot" orient="auto" style="overflow:visible"><circle r="2" cx="0" cy="0"/></marker>
    <marker id="Fancy" orient="auto" style="overflow:visible">
      <path d="M0 0 L2 1 L4 0 L2 3 Z"/><path d="M0 0 L1 1"/>
    </marker>
  </defs>
  <path id="trait" d="M10 10 H190" style="fill:none;stroke:#ff0000;stroke-width:2;stroke-opacity:0.5;
        marker-end:url(#Arrow1Lend);marker-start:url(#Dot)"/>
  <path id="fleche" d="M10 30 H190" style="fill:none;stroke:#00f;stroke-width:3;marker-end:url(#ArrowWide)"/>
  <path id="bizarre" d="M10 50 H190" style="fill:none;stroke:#000;marker-end:url(#Fancy);marker-mid:url(#Dot)"/>
  <rect id="carre" x="10" y="60" width="30" height="30" fill="#0f0" fill-opacity="0.25" stroke="none"/>
</svg>
"""


def test_v2_import(failures):
    print("Import SVG, format 2 (opacités, marqueurs)")
    plan, stats, _ = import_svg(V2_SVG, "v2.svg")
    nodes = {n.name: n for n in plan[0]["nodes"]}
    t, f, b, c = nodes["trait"], nodes["fleche"], nodes["bizarre"], nodes["carre"]
    check(c.fill["rgba"] == (0.0, 1.0, 0.0, 1.0) and abs(c.fill["opacity"] - 0.25) < 1e-9 and
          abs(t.stroke["opacity"] - 0.5) < 1e-9 and t.stroke["rgba"][3] == 1.0,
          "fill-opacity / stroke-opacity → opacité du fond / du contour", failures)
    check(t.stroke.get("arrow_end") == "triangle" and t.stroke.get("arrow_start") == "circle" and
          f.stroke.get("arrow_end") == "arrow",
          "marqueurs simples → pointes (dard Arrow1, rond, chevron ArrowWide) : %s %s %s"
          % (t.stroke.get("arrow_start"), t.stroke.get("arrow_end"), f.stroke.get("arrow_end")), failures)
    # Arrow1Lend : 17.5 × 0.8 = 14 unités × épaisseur 2 = 28 px = 4 × 2 × 3.5
    check(abs(t.stroke.get("arrow_scale", 1) - 3.5) < 0.01, "taille de la pointe → arrow-scale (%r)"
          % t.stroke.get("arrow_scale"), failures)
    check(not b.stroke.get("arrow_end") and stats["markers"] == 2,
          "marqueur complexe et marker-mid ignorés et signalés (%d)" % stats["markers"], failures)
    x = V.to_xml(plan[0]["nodes"])
    check('version="2"' in x and 'arrow-end="triangle"' in x and 'arrow-start="circle"' in x and
          'opacity="0.25"' in x and 'arrow-scale="3.5"' in x,
          "XML du modèle en version 2 (opacity, arrow-start / -end / -scale)", failures)


def v2_nodes():
    """Objets du format 2 : tout ce que la pile « Aspect » sait dire."""
    line = [(False, [((0, 0), (0, 0), (0, 0)), ((30, 0), (60, 10), (60, 10)), ((90, 20), (100, 50), (100, 50))])]
    sq = [(True, [((0, 0), (0, 0), (0, 0)), ((40, 0), (40, 0), (40, 0)), ((40, 40), (40, 40), (40, 40)),
                  ((0, 40), (0, 40), (0, 40))])]
    a = V.path_node("Pile", sq)
    a.transform = V.Matrix(1, 0, 0, 1, 20, 20)
    grad = {"type": "linear", "x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 0.0, "r": 0.5,
            "stops": [(0.0, (1.0, 1.0, 1.0, 1.0)), (1.0, (0.0, 0.0, 1.0, 0.5))]}
    a.entries = [
        {"kind": "stroke", "type": "color", "rgba": (0, 0, 0, 1), "width": 8.0, "cap": "round",
         "join": "round", "miter": 4.0, "align": "outside", "global": "Encre"},
        {"kind": "fill", "type": "color", "rgba": (1, 0, 0, 1), "opacity": 0.5, "global": "Rouge"},
        dict(grad, kind="fill", mode="multiply", opacity=0.75),
        {"kind": "fill", "type": "color", "rgba": (0, 1, 0, 1), "visible": False},
        {"kind": "stroke", "type": "color", "rgba": (1, 1, 0, 1), "width": 2.0, "cap": "butt",
         "join": "miter", "miter": 4.0, "align": "center", "dash": [2.0, 1.0], "dash_offset": 0.0},
    ]
    a.fill, a.stroke = a.entries[1], a.entries[-1]
    b = V.path_node("Flèche", line, None, {"type": "color", "rgba": (0, 0, 1, 1), "width": 3.0,
                                           "cap": "butt", "join": "miter", "miter": 4.0, "align": "center",
                                           "arrow_start": "circle", "arrow_end": "triangle",
                                           "arrow_scale": 1.5, "opacity": 0.8})
    b.transform = V.Matrix(1, 0, 0, 1, 100, 20)
    c = V.path_node("Profil", line)
    c.transform = V.Matrix(1, 0, 0, 1, 220, 20)
    c.entries = [{"kind": "fill", "type": "color", "rgba": (0.9, 0.9, 0.9, 1)},
                 {"kind": "stroke", "type": "color", "rgba": (0.2, 0.1, 0, 1), "width": 10.0, "cap": "butt",
                  "join": "miter", "miter": 4.0, "align": "center", "profile": "lens", "arrow_end": "arrow"}]
    c.fill, c.stroke = c.entries[0], c.entries[1]
    d = V.path_node("Contour simple", sq, None, {"type": "color", "rgba": (0, 0, 0, 1), "width": 1.0,
                                                 "cap": "butt", "join": "miter", "miter": 4.0,
                                                 "align": "center", "arrow_end": "triangle"})
    d.transform = V.Matrix(1, 0, 0, 1, 340, 20)
    return [a, b, c, d]


def test_v2(harness, tmp, failures):
    print("Format 2 : pile « Aspect » → SVG → réimport")
    nodes = v2_nodes()
    xml = V.to_xml(nodes)
    back = V.from_xml(xml)
    check([stack_sig(n) for n in nodes] == [stack_sig(n) for n in back] and
          back[0].entries[1].get("global") == "Rouge" and back[2].stroke.get("profile") == "lens",
          "XML du modèle (format 2) : écriture / lecture sans perte", failures)
    frag, err = run_harness(harness, xml, "Calque", 7, 1.0, False, "", tmp)
    if VERBOSE:
        print(frag)
    ns = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
          'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" '
          'xmlns:chopgimp="http://chopgimp.org/namespaces/chopgimp" width="480" height="100" viewBox="0 0 480 100">')
    try:
        el = ET.fromstring(ns + frag + "</svg>")
    except (ET.ParseError, TypeError) as e:
        check(False, "export du format 2 bien formé (%s)" % e, failures)
        return
    SV = "{http://www.w3.org/2000/svg}"
    CH = "{http://chopgimp.org/namespaces/chopgimp}"
    by = {e.get("id"): e for e in el.iter()}
    pile = by.get("vl7-o1")
    kids = list(pile) if pile is not None else []
    check(not err.strip() and pile is not None and len(kids) == 5 and
          "display:none" in kids[3].get("style") and "mix-blend-mode:multiply" in kids[2].get("style") and
          "fill-opacity:0.75" in kids[2].get("style") and kids[0].get(CH + "stroke-align") == "outside",
          "pile : fond masqué (display:none), mode, opacité d'un dégradé en fill-opacity", failures)
    markers = [e for e in el.iter(SV + "marker")]
    fl = by.get("vl7-o2")
    st = fl.get("style") if fl is not None else ""
    check(fl is not None and fl.tag == SV + "path" and "marker-start:url(#" in st and "marker-end:url(#" in st
          and {m.get(CH + "arrow") for m in markers} >= {"circle", "triangle"} and "stroke-opacity:0.8" in st,
          "pointes de flèche → <marker> sur un <path> simple", failures)
    tri = [m for m in markers if m.get(CH + "arrow") == "triangle" and m.get(CH + "arrow-scale") == "1.5"]
    # triangle : pointe au bout, longueur 4 × 3 × 1.5 = 18, largeur 18
    ok = False
    if tri:
        pts = [float(v) for v in tri[0][0].get("d").replace("M", " ").replace("L", " ").replace("Z", " ").split()]
        xs, ys = pts[0::2], pts[1::2]
        ok = (max(xs) == 0 and min(xs) == -18 and max(ys) - min(ys) == 18 and
              tri[0].get("markerUnits") == "userSpaceOnUse" and "fill-opacity:0.8" in tri[0][0].get("style"))
    check(ok, "marqueur triangle aux dimensions du modèle (userSpaceOnUse)", failures)
    prof = [e for e in el.iter(SV + "path") if e.get(CH + "profile") == "lens"]
    ok = False
    if prof:
        sub = V.parse_d(prof[0].get("d"))
        pts = [k[1] for k in sub[0][1]] if sub else []
        if len(pts) % 2:
            pts.append(pts[0])           # dernier point = premier, fondu dans Z
        half = len(pts) // 2
        # côté gauche puis côté droit à rebours : largeur = distance des paires
        widths = [math.hypot(pts[i][0] - pts[-1 - i][0], pts[i][1] - pts[-1 - i][1]) for i in range(half)]
        # fuseau : nul aux bouts, 10 (l'épaisseur) au milieu
        ok = (len(sub) == 1 and sub[0][0] and "stroke:none" in prof[0].get("style") and
              widths[0] < 0.01 and widths[-1] < 0.01 and abs(max(widths) - 10) < 0.2 and
              abs(widths[half // 2] - 10) < 1.0 and
              prof[0].get(CH + "d") == by["vl7-o3"][0].get("d"))
    check(ok, "profil de largeur → contour plein (fuseau)", failures)
    simple = by.get("vl7-o4")
    check(simple is not None and "marker" not in (simple.get("style") or ""),
          "pas de pointe sur un tracé fermé (comme le modèle)", failures)
    # réimport : même pile (la couleur globale devient une couleur simple ;
    # une pointe sur un tracé fermé, que le modèle ne dessine pas, se perd)
    del nodes[3].stroke["arrow_end"]
    plan, stats, _ = import_svg('<?xml version="1.0"?>' + ns + frag + "</svg>", "v2.svg")
    back = plan[0]["nodes"]
    d = diff([node_sig(n) for n in nodes], [node_sig(n) for n in back])
    for line in d[:10]:
        print("        " + line)
    check(not d and stats["markers"] == 0,
          "aller-retour du format 2 : pile, opacités, modes, masqués, profil, pointes", failures)


def main():
    failures = []
    plan1, stats, (w, h) = import_svg(TEST_SVG, "test.svg")
    if VERBOSE:
        dump(plan1)
        print(stats)

    print("Import SVG → objets")
    kinds = [(it["kind"], it["name"]) for it in plan1]
    check(kinds == [("vector", "Fond"), ("vector", "Dessin"), ("group", "Textes")],
          "un calque vectoriel par calque Inkscape, groupe si texte : %s" % kinds, failures)
    fond, dessin = plan1[0]["nodes"], plan1[1]["nodes"]
    check(len(fond) == 2 and fond[0].name == "ciel" and fond[1].name == "Bande",
          "un objet par élément, noms (id / inkscape:label)", failures)
    check(fond[0].fill["type"] == "linear" and len(fond[0].fill["stops"]) == 2 and
          abs(fond[0].fill["stops"][1][1][3] - 0.5) < 1e-6, "dégradé linéaire vectoriel (arrêts, opacité)", failures)
    check(fond[1].fill["type"] == "linear" and fond[1].stroke.get("dash") == [4 / 1.5, 2 / 1.5],
          "dégradé userSpaceOnUse + gradientTransform converti, pointillés en largeurs", failures)
    # valeur du dégradé userSpaceOnUse + rotate(30 40 40), de x=20 à x=60,
    # en quelques points de la bande : modèle (unités de la boîte) = SVG
    bande = fond[1]
    G = V.svg_matrix("rotate(30 40 40)")
    to_units, _ = V.bbox_units(bande.subpaths)
    f = bande.fill
    ok = True
    for px, py in ((10, 100), (50, 110), (190, 120), (100, 105)):
        qx, qy = G.invert().apply(px, py)
        t_svg = (qx - 20) / 40.0
        ux, uy = to_units.apply(px, py)
        dx, dy = f["x2"] - f["x1"], f["y2"] - f["y1"]
        t_mod = ((ux - f["x1"]) * dx + (uy - f["y1"]) * dy) / (dx * dx + dy * dy)
        ok = ok and abs(t_svg - t_mod) < 1e-6
    check(ok, "dégradé converti : même valeur qu'en SVG en tout point", failures)
    soleil = dessin[0]
    check(soleil.kind == "group" and soleil.name == "Soleil" and soleil.clip and
          len(soleil.children) == 3 and soleil.children[-1].name == "rond",
          "clip-path sur <g> → groupe masque d'écrêtage (forme de découpe au-dessus)", failures)
    check(abs(soleil.opacity - 0.8) < 1e-9 and soleil.children[0].fill["type"] == "radial",
          "opacité de groupe, dégradé radial", failures)
    etoile = dessin[1]
    check(etoile.kind == "group" and etoile.clip and etoile.children[0].name == "Étoile" and
          not etoile.children[0].nonzero and etoile.mode == "multiply",
          "clip-path sur un tracé → groupe masque ; evenodd (CSS #id), mix-blend-mode", failures)
    clones = dessin[2]
    check(clones.kind == "group" and len(clones.children) == 5 and clones.children[0].kind == "group"
          and not clones.children[2].visible, "<use> → groupe, objet masqué conservé", failures)
    m = soleil.transform
    check(m is not None and abs(m.xx - 2) < 1e-9 and abs(m.x0 - 10) < 1e-9,
          "transformations : viewBox × calque × objet", failures)
    poly = clones.children[3]
    check(poly.fill["rgba"][3] == 0.5 and poly.fill.get("opacity", 1.0) == 1.0,
          "rgba(…, 0.5) : alpha de la couleur", failures)
    check(V.image_size(400.00032, 300.0) == (400, 300) and V.image_size(400.2, 299.5) == (401, 300),
          "taille de l'image : « 4.16667in » → 400 px, pas 401 (demi-pixel de décalage)", failures)

    print("Export SVG (file-svg-vobjects.h) → réimport")
    with tempfile.TemporaryDirectory(prefix="chopgimp-vobj-") as tmp:
        harness = build_harness(tmp)
        svg2 = export_plan(plan1, harness, tmp, w, h)
        if VERBOSE:
            print(svg2)
        try:
            ET.fromstring(svg2)
            check(True, "SVG exporté bien formé", failures)
        except ET.ParseError as e:
            check(False, "SVG exporté bien formé (%s)" % e, failures)
            raise SystemExit(1)
        plan2, _, _ = import_svg(svg2, "test.svg")
        d = diff(plan_sig(plan1), plan_sig(plan2))
        for line in d[:20]:
            print("        " + line)
        check(not d, "même structure après aller-retour (calques, objets, groupes, découpes, "
                     "dégradés, noms, transformations, boîtes)", failures)
        check(w == 400 and h == 300 and 'width="4.166666667in"' in svg2,
              "taille exportée en pouces à 10 chiffres, relue 400 × 300", failures)
        svg3 = export_plan(plan2, harness, tmp, w, h)
        plan3, _, _ = import_svg(svg3, "test.svg")
        check(not diff(plan_sig(plan2), plan_sig(plan3)), "second aller-retour identique", failures)

        # format version 2 (pile « Aspect », éléments inconnus ignorés)
        v2 = ('<chopgimp-vobjects version="2" next-id="9" options-style="x" legacy="0" selection="1">\n'
              '<group id="0" name="">\n'
              '<path id="1" name="Aspect" opacity="1" mode="normal" visible="1" locked="0" '
              'fill-rule="nonzero" antialias="1" d="M0 0 C0 0 10 0 10 0 C10 0 10 10 10 10 Z">\n'
              '<stroke type="color" color="0 0 0 1" width="6" align="center" cap="round" join="round" '
              'miter="4" global="noir"/>\n'
              '<fill type="color" color="1 0 0 1" opacity="0.5"/>\n'
              '<fill type="linear" x1="0" y1="0" x2="1" y2="0" r="0.5" mode="multiply">'
              '<stop offset="0" color="1 1 1 1"/><stop offset="1" color="0 0 1 1"/></fill>\n'
              '<future-thing a="1"><fill type="color" color="0 1 0 1"/></future-thing>\n'
              '<lpe>[effet]\nx=1</lpe>\n'
              '</path>\n'
              '<path id="2" name="Simple" opacity="1" mode="normal" visible="1" locked="1" '
              'fill-rule="evenodd" antialias="1" d="M0 0 C0 0 5 5 5 5">\n'
              '<fill type="color" color="0 1 0 1" opacity="0.5"/>\n'
              '<stroke type="none" width="1"/>\n'
              '</path>\n</group>\n</chopgimp-vobjects>\n')
        frag, err = run_harness(harness, v2, "Calque", 9, 1.0, False, "", tmp)
        ok = frag is not None and not err.strip()
        if ok:
            el = ET.fromstring('<svg xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
                               'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" '
                               'xmlns:chopgimp="http://chopgimp.org/namespaces/chopgimp">' + frag + '</svg>')
            g = [e for e in el.iter() if e.get("id") == "vl9-o1"]
            paths = list(g[0]) if g else []
            simple = [e for e in el.iter() if e.get("id") == "vl9-o2"]
            sw = [e for e in el.iter() if e.get("{http://www.inkscape.org/namespaces/inkscape}swatch") == "solid"]
            ok = (g and g[0].tag == "g" and len(paths) == 3 and
                  g[0].get("{http://chopgimp.org/namespaces/chopgimp}aspect") == "1" and
                  len(sw) == 1 and "stroke:url(#%s)" % sw[0].get("id") in paths[0].get("style") and
                  "stop-color:#000000" in ET.tostring(sw[0], encoding="unicode") and
                  "fill-opacity:0.5" in paths[1].get("style") and
                  "mix-blend-mode:multiply" in paths[2].get("style") and
                  simple and "fill-opacity:0.5" in simple[0].get("style") and
                  "fill-rule:evenodd" in simple[0].get("style") and
                  simple[0].get("{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}insensitive") == "true")
        if VERBOSE:
            print(frag)
        check(ok, "export du format 2 : pile « Aspect » → <g> d'un <path> par fond / contour, "
                  "couleur globale → nuancier Inkscape, éléments inconnus ignorés", failures)

        test_v2(harness, tmp, failures)

        # XML du modèle relu tel quel (format du parasite)
        x1 = V.to_xml(dessin)
        back = V.from_xml(x1)
        check(not diff([node_sig(n) for n in dessin], [node_sig(n) for n in back]),
              "XML du modèle : écriture / lecture sans perte", failures)

    test_v2_import(failures)

    # PDF : objets de cairoscript
    print("PDF (cairoscript) → objets")
    try:
        import cairo
        import cairoscript
        path = os.path.join(tempfile.gettempdir(), "chopgimp-vobj-test.cs")
        dev = cairo.ScriptDevice(path)
        surf = cairo.ScriptSurface(dev, cairo.Content.COLOR_ALPHA, 200, 200)
        cr = cairo.Context(surf)
        cr.rectangle(0, 0, 200, 200)
        cr.clip()                                  # page entière : ignorée
        g = cairo.LinearGradient(0, 0, 100, 0)
        g.add_color_stop_rgb(0, 1, 0, 0)
        g.add_color_stop_rgb(1, 0, 0, 1)
        cr.rectangle(0, 0, 100, 50)
        cr.set_source(g)
        cr.fill()
        cr.save()
        cr.arc(100, 100, 40, 0, 2 * math.pi)
        cr.clip()
        cr.set_source_rgb(0, 1, 0)
        cr.rectangle(50, 50, 60, 60)
        cr.fill()
        cr.set_source_rgb(0, 0, 1)
        cr.rectangle(90, 90, 60, 60)
        cr.fill()
        cr.restore()
        cr.set_source_rgb(0, 0, 0)
        cr.move_to(0, 190)
        cr.line_to(200, 190)
        cr.stroke()
        surf.finish()
        dev.finish()
        objs, _ = cairoscript.parse(open(path, "rb").read())
        os.unlink(path)
        st = {}
        nodes = V.pdf_nodes(objs, st)
        if VERBOSE:
            dump([{"kind": "vector", "name": "PDF", "nodes": nodes}])
        check(len(nodes) == 3 and nodes[0].fill["type"] == "linear" and nodes[1].clip and
              len(nodes[1].children) == 3 and nodes[2].stroke["type"] == "color",
              "un objet par élément, découpe → groupe de masque, dégradé vectoriel", failures)
        merged = V.merge_similar(V.from_xml(V.to_xml(nodes)))
        check(len(merged) == 3, "option « Fusionner » sans effet sur des styles différents", failures)
    except ImportError:
        print("  (pycairo absent : test PDF sauté)")

    print("%d échec(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

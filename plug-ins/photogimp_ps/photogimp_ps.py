#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PhotoGIMP Pro — fonctions de calques façon Photoshop (GIMP 3.2).

  Calque > Créer / annuler le masque d'écrêtage      (Ctrl+Alt+G)
  Calque > Style de calque > Contour / Lueur externe / Ombre interne / Effacer
  Calque > Nouveau calque de réglage > Courbes, Niveaux, Teinte/Saturation…
  Calque > Fusionner sur un nouveau calque           (Ctrl+Maj+Alt+E)

Les styles et réglages sont des FILTRES NON DESTRUCTIFS de GIMP : ils restent
modifiables via l'icône « fx » du calque dans le panneau Calques.
"""
import sys

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gimp, Gegl, GLib

AUTHOR = "PhotoGIMP Pro"
YEAR = "2026"

# ── Styles de calque (gegl:dropshadow détourné, comme le font les pros GIMP) ──
STYLES = {
    "photogimp-style-stroke": ("Contour", "gegl:dropshadow",
                               {"x": 0.0, "y": 0.0, "radius": 0.0, "grow-radius": 3,
                                "opacity": 1.0}, (0.0, 0.0, 0.0)),
    "photogimp-style-outer-glow": ("Lueur externe", "gegl:dropshadow",
                                   {"x": 0.0, "y": 0.0, "radius": 18.0, "grow-radius": 2,
                                    "opacity": 1.0}, (1.0, 0.93, 0.6)),
    "photogimp-style-inner-shadow": ("Ombre interne", "gegl:inner-glow",
                                     {"x": 4.0, "y": 4.0, "radius": 8.0, "grow-radius": 2,
                                      "opacity": 0.75},
                                     (0.0, 0.0, 0.0)),
}

# effet correspondant dans la fenêtre Style de calque (plug-in chopgimp_fx)
STYLE_KEYS = {"photogimp-style-stroke": "stroke",
              "photogimp-style-outer-glow": "outer-glow",
              "photogimp-style-inner-shadow": "inner-shadow"}

# ── Calques de réglage : (libellé, opération GEGL) ──
ADJUST = {
    "photogimp-adj-brightness-contrast": ("Luminosité/Contraste…", "gimp:brightness-contrast"),
    "photogimp-adj-levels": ("Niveaux…", "gimp:levels"),
    "photogimp-adj-curves": ("Courbes…", "gimp:curves"),
    "photogimp-adj-exposure": ("Exposition…", "gegl:exposure"),
    "photogimp-adj-hue-saturation": ("Teinte/Saturation…", "gimp:hue-saturation"),
    "photogimp-adj-color-balance": ("Balance des couleurs…", "gimp:color-balance"),
    "photogimp-adj-black-white": ("Noir et blanc…", "gegl:mono-mixer"),
    "photogimp-adj-channel-mixer": ("Mélangeur de couches…", "gegl:channel-mixer"),
    "photogimp-adj-invert": ("Négatif", "gegl:invert-gamma"),
    "photogimp-adj-posterize": ("Isohélie…", "gimp:posterize"),
    "photogimp-adj-threshold": ("Seuil…", "gimp:threshold"),
}

OTHER = {
    "photogimp-clipping-toggle": "Créer / annuler le masque d'écrêtage",
    "photogimp-style-clear": "Effacer le style de calque",
    "photogimp-stamp-visible": "Fusionner sur un nouveau calque",
    "photogimp-split-shapes": "Séparer les formes",
}

CLIP_GROUP_PREFIX = "⧉ "     # préfixe des groupes d'écrêtage créés par PhotoGIMP
ADJ_PREFIX = "◐ "            # préfixe des groupes « calque de réglage »


def ok(procedure):
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def fail(procedure, msg):
    return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error.new_literal(
        GLib.quark_from_string("photogimp"), msg, 0))


def gegl_color(rgb):
    c = Gegl.Color.new("black")
    # valeurs sRGB (set_rgba les interpréterait en linéaire)
    c.set_rgba_with_space(rgb[0], rgb[1], rgb[2], 1.0, None)
    return c


def remove_orphan_path(image, path):
    """Supprime le chemin d'un calque vectoriel retiré (GIMP le laisse dans
    l'image), sauf s'il sert encore à un autre calque vectoriel."""
    if path is None or not path.is_valid():
        return
    def walk(ls):
        for l in ls:
            if isinstance(l, Gimp.VectorLayer):
                p = l.get_path()
                if p is not None and p.get_id() == path.get_id():
                    return True
            if isinstance(l, Gimp.GroupLayer) and walk(l.get_children()):
                return True
        return False
    try:
        if not walk(image.get_layers()):
            image.remove_path(path)
    except Exception:
        pass


def siblings(layer):
    parent = layer.get_parent()
    return list(parent.get_children()) if parent else list(layer.get_image().get_layers())


def add_filter(drawable, op, name, props, color=None):
    f = Gimp.DrawableFilter.new(drawable, op, name)
    cfg = f.get_config()
    for k, v in props.items():
        try:
            cfg.set_property(k, v)
        except Exception:
            pass
    if color is not None:
        # gegl:dropshadow → « color », gegl:inner-glow → « value »
        for prop in ("color", "value"):
            try:
                cfg.set_property(prop, gegl_color(color))
                break
            except Exception:
                pass
    # les effets se superposent au calque (sinon « Remplacer » efface le contenu)
    f.set_blend_mode(Gimp.LayerMode.NORMAL)
    f.update()
    drawable.append_filter(f)
    return f


class PhotoGimpPS(Gimp.PlugIn):

    def do_query_procedures(self):
        return list(STYLES) + list(ADJUST) + list(OTHER)

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        p = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        p.set_image_types("*")
        p.set_attribution(AUTHOR, AUTHOR, YEAR)
        if name in STYLES:
            label = STYLES[name][0] + "…"
            paths = ["<Image>/Layer/Style de calque", "<Layers>/Layers Menu/Style de calque"]
            doc = "Ajoute le style « %s » (filtre non destructif, modifiable via fx)" % STYLES[name][0]
        elif name in ADJUST:
            label = ADJUST[name][0]
            # le menu « Nouveau calque de réglage » est fourni par ChopGimp
            # (actions layers-adjustment-*, avec la vraie fenêtre de réglage) :
            # ces procédures restent disponibles pour les scripts
            paths = []
            doc = "Calque de réglage %s appliqué aux calques situés dessous" % label
        else:
            label = OTHER[name]
            paths = {"photogimp-clipping-toggle": ["<Image>/Layer", "<Layers>/Layers Menu"],
                     "photogimp-style-clear": ["<Image>/Layer/Style de calque",
                                               "<Layers>/Layers Menu/Style de calque"],
                     "photogimp-stamp-visible": ["<Image>/Layer"],
                     "photogimp-split-shapes": ["<Image>/Layer", "<Layers>/Layers Menu"]}[name]
            doc = label
        p.set_menu_label(label)
        for path in paths:
            p.add_menu_path(path)
        p.set_documentation(doc, doc, name)
        if name == "photogimp-stamp-visible":
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        else:
            p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                   Gimp.ProcedureSensitivityMask.DRAWABLES)
        return p

    # ── exécution ────────────────────────────────────────────────────
    def run(self, procedure, run_mode, image, drawables, config, data):
        name = procedure.get_name()
        layers = [d for d in drawables if isinstance(d, Gimp.Layer)]
        # depuis un menu : la fenêtre Style de calque, l'effet déjà coché
        # (Contour…, Lueur externe…, Ombre interne… ont des réglages)
        if name in STYLES and run_mode == Gimp.RunMode.INTERACTIVE and layers:
            proc = Gimp.get_pdb().lookup_procedure("chopgimp-layer-style")
            if proc is not None:
                cfg = proc.create_config()
                cfg.set_property("run-mode", Gimp.RunMode.INTERACTIVE)
                cfg.set_property("image", image)
                cfg.set_core_object_array("drawables", layers[:1])
                cfg.set_property("effect", STYLE_KEYS[name])
                res = proc.run(cfg)
                return procedure.new_return_values(res.index(0), GLib.Error())
        image.undo_group_start()
        try:
            if name in STYLES:
                if not layers:
                    return fail(procedure, "Sélectionnez un calque.")
                label, op, props, color = STYLES[name]
                for l in layers:
                    add_filter(l, op, label, props, color)
            elif name == "photogimp-style-clear":
                # seulement les filtres de style (pas le flou, les courbes…
                # posés par l'utilisateur)
                labels = {v[0] for v in STYLES.values()}
                for l in layers:
                    for f in list(l.get_filters() or []):
                        n = f.get_name() or ""
                        if n in labels or n.startswith("Style : "):
                            f.delete()
                    try:
                        l.detach_parasite("chopgimp-style")
                    except Exception:
                        pass
            elif name in ADJUST:
                if not layers:
                    return fail(procedure, "Sélectionnez un calque.")
                self.adjustment_layer(image, layers[0], *ADJUST[name])
            elif name == "photogimp-clipping-toggle":
                if not layers:
                    return fail(procedure, "Sélectionnez un calque.")
                msg = self.clipping_toggle(image, layers[0])
                if msg:
                    return fail(procedure, msg)
            elif name == "photogimp-stamp-visible":
                self.stamp_visible(image)
            elif name == "photogimp-split-shapes":
                msg = self.split_shapes(image, layers)
                if msg:
                    return fail(procedure, msg)
        finally:
            image.undo_group_end()
            Gimp.displays_flush()
        return ok(procedure)

    # Masque d'écrêtage Photoshop : le calque n'apparaît que là où le calque
    # du dessous est opaque. GIMP : groupe {base + calque} et mode de
    # composition « Écrêter à l'arrière-plan » sur le calque écrêté.
    def clipping_toggle(self, image, layer):
        parent = layer.get_parent()
        if (parent and parent.get_name().startswith(CLIP_GROUP_PREFIX) and
                layer.get_composite_mode() != Gimp.LayerCompositeMode.CLIP_TO_BACKDROP):
            # C'est la base : défaire tout l'écrêtage (sinon les calques
            # écrêtés n'auraient plus rien sur quoi s'afficher)
            gparent = parent.get_parent()
            pos = image.get_item_position(parent)
            for c in reversed(list(parent.get_children())):
                c.set_composite_mode(Gimp.LayerCompositeMode.AUTO)
                image.reorder_item(c, gparent, pos + 1)
            image.remove_layer(parent)
            return None
        if parent and parent.get_name().startswith(CLIP_GROUP_PREFIX):
            # Annuler : sortir le calque du groupe, défaire le groupe s'il ne reste que la base
            layer.set_composite_mode(Gimp.LayerCompositeMode.AUTO)
            gparent = parent.get_parent()
            pos = image.get_item_position(parent)
            image.reorder_item(layer, gparent, pos)
            rest = list(parent.get_children())
            clipped = [c for c in rest if c.get_composite_mode() == Gimp.LayerCompositeMode.CLIP_TO_BACKDROP]
            if not clipped:
                pos = image.get_item_position(parent)
                for c in reversed(rest):
                    image.reorder_item(c, gparent, pos + 1)
                image.remove_layer(parent)
            return None
        sibs = siblings(layer)
        idx = sibs.index(layer)
        if idx + 1 >= len(sibs):
            return "Il n'y a pas de calque en dessous pour l'écrêtage."
        base = sibs[idx + 1]
        if base.get_name().startswith(CLIP_GROUP_PREFIX) and base.is_group():
            # Empiler sur un groupe d'écrêtage existant (plusieurs calques écrêtés)
            image.reorder_item(layer, base, 0)
        else:
            pos = image.get_item_position(base)
            group = Gimp.GroupLayer.new(image, CLIP_GROUP_PREFIX + base.get_name())
            image.insert_layer(group, parent, pos)
            image.reorder_item(base, group, 0)
            image.reorder_item(layer, group, 0)
        layer.set_composite_mode(Gimp.LayerCompositeMode.CLIP_TO_BACKDROP)
        image.set_selected_layers([layer])
        return None

    # Calque de réglage : regroupe les calques SOUS le calque actif (même
    # niveau) et applique le réglage au groupe → même rendu que Photoshop.
    def adjustment_layer(self, image, layer, label, op):
        parent = layer.get_parent()
        sibs = siblings(layer)
        idx = sibs.index(layer)
        below = sibs[idx:]
        title = ADJ_PREFIX + label.rstrip("…")
        pos = image.get_item_position(below[0])
        group = Gimp.GroupLayer.new(image, title)
        image.insert_layer(group, parent, pos)
        for l in below:
            image.reorder_item(l, group, len(group.get_children()))
        add_filter(group, op, label.rstrip("…"), {})
        image.set_selected_layers([group])

    # Un calque vectoriel qui contient plusieurs formes (sous-chemins) devient
    # un calque vectoriel par forme, avec le même style de départ : chaque
    # forme peut ensuite recevoir sa propre couleur de fond et de contour.
    def split_shapes(self, image, layers):
        vlayers = [l for l in layers if isinstance(l, Gimp.VectorLayer)]
        if not vlayers:
            return "Sélectionnez un calque vectoriel (forme)."
        for layer in vlayers:
            path = layer.get_path()
            strokes = list(path.get_strokes())
            if len(strokes) < 2:
                continue
            parent = layer.get_parent()
            pos = image.get_item_position(layer)
            new_layers = []
            for n, sid in enumerate(strokes, 1):
                ptype, points, closed = path.stroke_get_points(sid)
                new_path = Gimp.Path.new(image, "%s — forme %d" % (layer.get_name(), n))
                image.insert_path(new_path, None, 0)
                new_path.stroke_new_from_points(ptype, points, closed)
                nl = Gimp.VectorLayer.new(image, new_path)
                nl.set_name("%s — forme %d" % (layer.get_name(), n))
                self.copy_vector_style(layer, nl)
                image.insert_layer(nl, parent, pos)
                nl.refresh()
                new_layers.append(nl)
            image.remove_layer(layer)
            remove_orphan_path(image, path)
            image.set_selected_layers(new_layers)
        return None

    @staticmethod
    def copy_vector_style(src, dst):
        dst.set_enable_fill(src.get_enable_fill())
        dst.set_fill_color(src.get_fill_color())
        dst.set_enable_stroke(src.get_enable_stroke())
        dst.set_stroke_color(src.get_stroke_color())
        dst.set_stroke_width(src.get_stroke_width())
        dst.set_stroke_width_unit(src.get_stroke_width_unit())
        dst.set_stroke_cap_style(src.get_stroke_cap_style())
        dst.set_stroke_join_style(src.get_stroke_join_style())
        dst.set_stroke_miter_limit(src.get_stroke_miter_limit())
        try:
            dst.set_stroke_dash_pattern(src.get_stroke_dash_pattern())
            dst.set_stroke_dash_offset(src.get_stroke_dash_offset())
        except Exception:
            pass

    # Ctrl+Maj+Alt+E : copie fusionnée du visible dans un nouveau calque en haut
    def stamp_visible(self, image):
        layer = Gimp.Layer.new_from_visible(image, image, "Fusion (visible)")
        image.insert_layer(layer, None, 0)
        image.set_selected_layers([layer])


if __name__ == "__main__":
    Gimp.main(PhotoGimpPS.__gtype__, sys.argv)

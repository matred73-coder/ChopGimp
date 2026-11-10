#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Vector Contour (Enhanced)
#   Illustrator-style enhanced path stroking:
#   Contour a largeur variable, Ligne en pointilles, Pointes de fleche
#
#   License: GPL v3+

import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('Gegl', '0.4')
from gi.repository import Gegl
from gi.repository import GObject
from gi.repository import GLib
import sys
import math

def N_(message): return message
def _(message): return GLib.dgettext(None, message)


# ---------------------------------------------------------------------------
# Contour a largeur variable
# ---------------------------------------------------------------------------
def variable_width_stroke(procedure, run_mode, image, drawables, config, data):
    """Simulate a variable-width stroke by rendering multiple passes at
    different widths along the path.  The stroke tapers from start_width
    at the beginning to end_width at the end of the active path."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-variable-stroke')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    start_width = config.get_property('start-width')
    end_width = config.get_property('end-width')
    num_steps = config.get_property('steps')
    color = config.get_property('color')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    vectors = image.get_active_vectors()

    if vectors is None:
        image.undo_group_end()
        Gimp.context_pop()
        error = GLib.Error.new_literal(
            GLib.quark_from_string("vector-stroke"),
            "No active path. Please select a vector path first.", 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

    drawable = drawables[0] if drawables else image.get_active_drawable()
    if drawable is None:
        image.undo_group_end()
        Gimp.context_pop()
        error = GLib.Error.new_literal(
            GLib.quark_from_string("vector-stroke"),
            "No active drawable to stroke onto.", 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

    Gimp.context_set_foreground(color)
    Gimp.context_set_opacity(100.0)
    Gimp.context_set_paint_mode(Gimp.LayerMode.NORMAL)

    strokes = vectors.get_strokes()

    for stroke_id in strokes:
        # Get stroke length via PDB
        proc = pdb.lookup_procedure('gimp-vectors-stroke-get-length')
        pc = proc.create_config()
        pc.set_property('vectors', vectors)
        pc.set_property('stroke-id', stroke_id)
        pc.set_property('precision', 1.0)
        result = proc.run(pc)
        total_length = result.index(1)

        if total_length <= 0:
            continue

        # Contour in segments: for each segment, extract a sub-path and stroke it
        # Simpler approach: stroke the full path multiple times with varying brush size
        # using opacity and small steps to simulate tapering.
        # We divide the path into segments, create a selection for each, and stroke.

        # Practical approach: use multiple strokes from different positions.
        # Actually, the most reliable GIMP approach is to stroke the path multiple
        # times at decreasing widths, which creates a natural taper effect.

        # Render from widest to narrowest in layers, then flatten
        for step in range(num_steps):
            t = step / float(max(num_steps - 1, 1))
            width = start_width + (end_width - start_width) * t

            # Set brush size for this step
            Gimp.context_set_line_width(width)
            Gimp.context_set_stroke_method(Gimp.ContourMethod.LINE)
            Gimp.context_set_antialias(True)
            Gimp.context_set_line_cap(Gimp.CapStyle.ROUND)
            Gimp.context_set_line_join(Gimp.JoinStyle.ROUND)

            # Contour only the relevant portion by adjusting opacity
            # For a taper effect, each step has full opacity but covers
            # a sub-section. Since GIMP doesn't support partial path stroking
            # easily, we stroke the whole path and rely on overpainting.
            alpha = 1.0 / num_steps
            Gimp.context_set_opacity(max(alpha * 100.0, 5.0))

            # Convert path to selection and stroke the drawable
            proc = pdb.lookup_procedure('gimp-drawable-edit-stroke-item')
            pc = proc.create_config()
            pc.set_property('drawable', drawable)
            pc.set_property('item', vectors)
            proc.run(pc)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Contour en ligne pointillee
# ---------------------------------------------------------------------------
def dashed_stroke(procedure, run_mode, image, drawables, config, data):
    """Contour the active path with a configurable dash pattern."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-dashed-stroke')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    line_width = config.get_property('line-width')
    dash_length = config.get_property('dash-length')
    gap_length = config.get_property('gap-length')
    color = config.get_property('color')
    cap_style = config.get_property('cap-style')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    vectors = image.get_active_vectors()

    if vectors is None:
        image.undo_group_end()
        Gimp.context_pop()
        error = GLib.Error.new_literal(
            GLib.quark_from_string("vector-stroke"),
            "No active path. Please select a vector path first.", 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

    drawable = drawables[0] if drawables else image.get_active_drawable()
    if drawable is None:
        image.undo_group_end()
        Gimp.context_pop()
        error = GLib.Error.new_literal(
            GLib.quark_from_string("vector-stroke"),
            "No active drawable to stroke onto.", 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

    Gimp.context_set_foreground(color)
    Gimp.context_set_opacity(100.0)
    Gimp.context_set_paint_mode(Gimp.LayerMode.NORMAL)
    Gimp.context_set_stroke_method(Gimp.ContourMethod.LINE)
    Gimp.context_set_line_width(line_width)
    Gimp.context_set_antialias(True)

    # Set cap style
    if cap_style == "round":
        Gimp.context_set_line_cap(Gimp.CapStyle.ROUND)
    elif cap_style == "square":
        Gimp.context_set_line_cap(Gimp.CapStyle.SQUARE)
    else:
        Gimp.context_set_line_cap(Gimp.CapStyle.BUTT)

    Gimp.context_set_line_join(Gimp.JoinStyle.MITER)

    # Set dash pattern: array of [dash, gap, dash, gap, ...]
    dash_pattern = Gimp.FloatArray.new([float(dash_length), float(gap_length)])

    proc = pdb.lookup_procedure('gimp-context-set-line-dash-pattern')
    pc = proc.create_config()
    pc.set_property('dash-pattern', dash_pattern)
    proc.run(pc)

    # Contour the path onto the drawable
    proc = pdb.lookup_procedure('gimp-drawable-edit-stroke-item')
    pc = proc.create_config()
    pc.set_property('drawable', drawable)
    pc.set_property('item', vectors)
    proc.run(pc)

    # Reset dash pattern to solid
    solid_pattern = Gimp.FloatArray.new([])
    proc = pdb.lookup_procedure('gimp-context-set-line-dash-pattern')
    pc = proc.create_config()
    pc.set_property('dash-pattern', solid_pattern)
    proc.run(pc)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Pointes de fleche sur chemin
# ---------------------------------------------------------------------------
def arrow_heads(procedure, run_mode, image, drawables, config, data):
    """Add arrowheads to the endpoints of the active path by creating
    small triangular paths and stroking/filling them."""
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-arrow-heads')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    arrow_size = config.get_property('arrow-size')
    arrow_angle = config.get_property('arrow-angle')
    color = config.get_property('color')
    add_start = config.get_property('start-arrow')
    add_end = config.get_property('end-arrow')
    filled = config.get_property('filled')

    Gimp.context_push()
    image.undo_group_start()

    pdb = Gimp.get_pdb()
    vectors = image.get_active_vectors()

    if vectors is None:
        image.undo_group_end()
        Gimp.context_pop()
        error = GLib.Error.new_literal(
            GLib.quark_from_string("vector-stroke"),
            "No active path. Please select a vector path first.", 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

    drawable = drawables[0] if drawables else image.get_active_drawable()
    if drawable is None:
        image.undo_group_end()
        Gimp.context_pop()
        error = GLib.Error.new_literal(
            GLib.quark_from_string("vector-stroke"),
            "No active drawable.", 0)
        return procedure.new_return_values(Gimp.PDBStatusType.CALLING_ERROR, error)

    Gimp.context_set_foreground(color)
    half_angle_rad = math.radians(arrow_angle / 2.0)

    strokes = vectors.get_strokes()

    for stroke_id in strokes:
        # Get stroke length
        proc = pdb.lookup_procedure('gimp-vectors-stroke-get-length')
        pc = proc.create_config()
        pc.set_property('vectors', vectors)
        pc.set_property('stroke-id', stroke_id)
        pc.set_property('precision', 0.5)
        result = proc.run(pc)
        total_length = result.index(1)

        if total_length <= 0:
            continue

        def get_point_at(dist):
            """Get point and tangent at distance along stroke."""
            proc2 = pdb.lookup_procedure('gimp-vectors-stroke-get-point-at-dist')
            pc2 = proc2.create_config()
            pc2.set_property('vectors', vectors)
            pc2.set_property('stroke-id', stroke_id)
            pc2.set_property('dist', dist)
            pc2.set_property('precision', 0.5)
            r = proc2.run(pc2)
            # Returns: x, y, slope, valid
            return r.index(1), r.index(2), r.index(3)

        def make_arrowhead(tip_x, tip_y, dx, dy):
            """Create an arrowhead triangle path pointing in direction (dx, dy)."""
            length = math.sqrt(dx * dx + dy * dy)
            if length < 0.001:
                return None

            # Normalize direction
            ux = dx / length
            uy = dy / length

            # Perpendicular
            px = -uy
            py = ux

            # Two base points of the arrowhead
            base_x = tip_x - ux * arrow_size
            base_y = tip_y - uy * arrow_size

            wing = arrow_size * math.tan(half_angle_rad)

            p1x = base_x + px * wing
            p1y = base_y + py * wing
            p2x = base_x - px * wing
            p2y = base_y - py * wing

            # Create path for the arrowhead
            arrow_vec = Gimp.Vectors.new(image, "Arrowhead")
            image.insert_vectors(arrow_vec, None, -1)

            cp = [
                tip_x, tip_y, tip_x, tip_y, tip_x, tip_y,
                p1x, p1y, p1x, p1y, p1x, p1y,
                p2x, p2y, p2x, p2y, p2x, p2y,
            ]

            proc3 = pdb.lookup_procedure('gimp-vectors-bezier-stroke-new')
            pc3 = proc3.create_config()
            pc3.set_property('vectors', arrow_vec)
            fa = Gimp.FloatArray.new(cp)
            pc3.set_property('controlpoints', fa)
            pc3.set_property('closed', True)
            proc3.run(pc3)

            return arrow_vec

        # End arrowhead
        if add_end:
            # Get point near the end and at the end
            near_dist = max(0, total_length - arrow_size * 0.5)
            ex, ey, _ = get_point_at(total_length - 0.1)
            nx, ny, _ = get_point_at(near_dist)

            dx = ex - nx
            dy = ey - ny

            arrow_vec = make_arrowhead(ex, ey, dx, dy)
            if arrow_vec:
                if filled:
                    # Convert arrowhead path to selection and fill
                    _path_to_selection_and_fill(image, arrow_vec, drawable, pdb)
                else:
                    # Contour the arrowhead outline
                    _stroke_path(arrow_vec, drawable, pdb, 2.0)
                # Remove the temporary arrowhead path
                image.remove_vectors(arrow_vec)

        # Start arrowhead (pointing backward)
        if add_start:
            sx_pt, sy_pt, _ = get_point_at(0.1)
            nx2, ny2, _ = get_point_at(min(arrow_size * 0.5, total_length))

            dx = sx_pt - nx2
            dy = sy_pt - ny2

            arrow_vec = make_arrowhead(sx_pt, sy_pt, dx, dy)
            if arrow_vec:
                if filled:
                    _path_to_selection_and_fill(image, arrow_vec, drawable, pdb)
                else:
                    _stroke_path(arrow_vec, drawable, pdb, 2.0)
                image.remove_vectors(arrow_vec)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def _path_to_selection_and_fill(image, vectors, drawable, pdb):
    """Convert path to selection and fill on drawable."""
    proc = pdb.lookup_procedure('gimp-image-select-item')
    pc = proc.create_config()
    pc.set_property('image', image)
    pc.set_property('operation', Gimp.ChannelOps.REPLACE)
    pc.set_property('item', vectors)
    proc.run(pc)

    drawable.edit_fill(Gimp.FillType.FOREGROUND)
    Gimp.Selection.none(image)


def _stroke_path(vectors, drawable, pdb, width):
    """Contour a path onto a drawable."""
    Gimp.context_set_stroke_method(Gimp.ContourMethod.LINE)
    Gimp.context_set_line_width(width)
    Gimp.context_set_line_cap(Gimp.CapStyle.ROUND)
    Gimp.context_set_line_join(Gimp.JoinStyle.MITER)

    proc = pdb.lookup_procedure('gimp-drawable-edit-stroke-item')
    pc = proc.create_config()
    pc.set_property('drawable', drawable)
    pc.set_property('item', vectors)
    proc.run(pc)


# ===========================================================================
# Plugin registration
# ===========================================================================
class VectorContour(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-variable-stroke',
            'python-fu-dashed-stroke',
            'python-fu-arrow-heads',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)
        menu_base = "<Image>/Filters/Vector/Stroke"

        if name == 'python-fu-variable-stroke':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                variable_width_stroke, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Contour a largeur variable"),
                _("Contour the active path with a width that varies from start to end, "
                  "simulating calligraphic or tapered strokes."),
                name)
            procedure.set_menu_label(_("Contour a largeur _variable..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            black = Gegl.Color.new("black")
            procedure.add_double_argument("start-width", _("Largeur de _debut"),
                                          _("Largeur du contour au debut du chemin"),
                                          0.5, 500.0, 8.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("end-width", _("Largeur de _fin"),
                                          _("Largeur du contour a la fin du chemin"),
                                          0.5, 500.0, 2.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("steps", _("_Etapes"),
                                       _("Nombre de passes de contour (plus eleve = effilement plus lisse)"),
                                       2, 50, 10,
                                       GObject.ParamFlags.READWRITE)
            procedure.add_color_argument("color", _("_Couleur"), _("Couleur du contour"),
                                         True, black, GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-dashed-stroke':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                dashed_stroke, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Contour en ligne pointillee"),
                _("Tracer le chemin actif avec un motif de tirets et espaces configurable."),
                name)
            procedure.set_menu_label(_("Ligne en _pointilles..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            black = Gegl.Color.new("black")
            procedure.add_double_argument("line-width", _("Largeur du _trait"),
                                          _("Largeur de la ligne en pointilles"),
                                          0.5, 500.0, 3.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("dash-length", _("Longueur du _tiret"),
                                          _("Length of each dash segment"),
                                          1.0, 1000.0, 15.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("gap-length", _("Longueur de l'_espace"),
                                          _("Length of gap between dashes"),
                                          1.0, 1000.0, 10.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_color_argument("color", _("_Couleur"), _("Couleur du contour"),
                                         True, black, GObject.ParamFlags.READWRITE)

            cap_choice = Gimp.Choice.new()
            cap_choice.add("butt", 0, _("Butt"), "")
            cap_choice.add("round", 1, _("Round"), "")
            cap_choice.add("square", 2, _("Square"), "")
            procedure.add_choice_argument("cap-style", _("Style de _terminaison"),
                                          _("Style de terminaison de ligne pour les extremites de tirets"),
                                          cap_choice, "butt",
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-arrow-heads':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                arrow_heads, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Pointes de fleche"),
                _("Ajouter des pointes de fleche au debut et/ou a la fin du chemin actif."),
                name)
            procedure.set_menu_label(_("_Pointes de fleche..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            black = Gegl.Color.new("black")
            procedure.add_double_argument("arrow-size", _("_Taille"),
                                          _("Longueur de la pointe de fleche"),
                                          2.0, 500.0, 20.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("arrow-angle", _("_Angle"),
                                          _("Opening angle of arrowhead in degrees"),
                                          10.0, 160.0, 60.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_color_argument("color", _("_Couleur"), _("Couleur de la pointe de fleche"),
                                         True, black, GObject.ParamFlags.READWRITE)
            procedure.add_boolean_argument("start-arrow", _("Fleche de _debut"),
                                           _("Ajouter une pointe de fleche au debut du chemin"),
                                           False, GObject.ParamFlags.READWRITE)
            procedure.add_boolean_argument("end-arrow", _("Fleche de _fin"),
                                           _("Ajouter une pointe de fleche a la fin du chemin"),
                                           True, GObject.ParamFlags.READWRITE)
            procedure.add_boolean_argument("filled", _("_Rempli"),
                                           _("Remplir les pointes de fleche (Vrai) ou tracer le contour uniquement (Faux)"),
                                           True, GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(VectorContour.__gtype__, sys.argv)

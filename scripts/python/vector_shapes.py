#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Vector Shapes
#   Create vector paths for common shapes (Rectangle, Ellipse, Polygon,
#   Star, Arrow, Spiral) — Illustrator-style vector tools.
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
# Chemin Rectangle
# ---------------------------------------------------------------------------
def shape_rectangle(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-shape-rectangle')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    x = config.get_property('x')
    y = config.get_property('y')
    w = config.get_property('width')
    h = config.get_property('height')
    r = config.get_property('corner-radius')

    Gimp.context_push()
    image.undo_group_start()

    vectors = Gimp.Vectors.new(image, "Rectangle")
    image.insert_vectors(vectors, None, -1)

    if r <= 0:
        # Simple rectangle: 4 corners, straight lines (anchors with equal handles)
        coords = [
            x,     y,      x,     y,      x,     y,
            x + w, y,      x + w, y,      x + w, y,
            x + w, y + h,  x + w, y + h,  x + w, y + h,
            x,     y + h,  x,     y + h,  x,     y + h,
        ]
        vectors.bezier_stroke_new_moveto(coords[0], coords[1])
        stroke_id = vectors.get_strokes()[0]
        pdb = Gimp.get_pdb()

        # Build full control-point array for a closed rectangular bezier stroke
        # Each anchor: (handle_left_x, handle_left_y, anchor_x, anchor_y, handle_right_x, handle_right_y)
        # For straight lines, handles = anchor position
        controlpoints = [
            x, y, x, y, x, y,
            x + w, y, x + w, y, x + w, y,
            x + w, y + h, x + w, y + h, x + w, y + h,
            x, y + h, x, y + h, x, y + h,
        ]
        # Remove auto-created stroke, re-create with full coords
        vectors.remove_stroke(stroke_id)
        vectors.bezier_stroke_new_ellipse(0, 0, 0, 0)  # dummy removed below
        for sid in vectors.get_strokes():
            vectors.remove_stroke(sid)

        # Use the PDB to add a bezier stroke with explicit control points
        proc = pdb.lookup_procedure('gimp-vectors-bezier-stroke-new')
        pc = proc.create_config()
        pc.set_property('vectors', vectors)
        fa = Gimp.FloatArray.new(controlpoints)
        pc.set_property('controlpoints', fa)
        pc.set_property('closed', True)
        proc.run(pc)
    else:
        # Rounded rectangle: use bezier curves at corners
        # Clamp radius
        r = min(r, w / 2.0, h / 2.0)
        # Kappa for circular arc approximation
        k = 0.5522847498 * r

        controlpoints = [
            # Top-left corner (from left side coming down to top side going right)
            x, y + r - k,          x, y + r,          x, y + r,         # left handle, anchor (start of top-left arc)
            # Actually, let's build it systematically:
            # Start at top-left, after the corner radius, going clockwise
        ]
        # Rebuild properly: start at (x + r, y) going right along top edge
        # CW: top-right corner, right edge, bottom-right corner, bottom edge, bottom-left corner, left edge, back to start
        cp = []

        def add_point(hlx, hly, ax, ay, hrx, hry):
            cp.extend([hlx, hly, ax, ay, hrx, hry])

        # Top edge: from (x+r, y) to (x+w-r, y) -- straight
        add_point(x + r, y, x + r, y, x + r, y)                       # P0: top-left after radius
        add_point(x + w - r, y, x + w - r, y, x + w - r, y)           # P1: top-right before radius

        # Top-right corner arc
        add_point(x + w - r + k, y, x + w, y + r, x + w, y + r)       # P2: top-right arc to right edge start
        # WRONG: bezier needs anchor + 2 handles per point. Let me redo this properly.

        # Clear and restart with the correct cubic bezier approach
        cp = []
        # For a rounded rect, we need 8 anchor points (2 per corner) with appropriate handles
        # Going clockwise from top-left corner

        # Point 1: Start of top edge (after top-left radius)
        cp.extend([x + r, y, x + r, y, x + w - r, y])  # handle_left = anchor, handle_right points toward next
        # WAIT: GIMP bezier format is: handle_left_x, handle_left_y, anchor_x, anchor_y, handle_right_x, handle_right_y
        # per control point. Let me be precise.

        cp = []
        # 8 points for rounded rectangle, clockwise from top-left post-radius

        # 1. Top-left -> start of top straight edge
        cp.extend([x, y + r - k,  x, y + r,  x, y + r])  # Will be point 8 actually... Let me think linearly.

        # Let me just go point by point around the shape:
        # Format per point: [handle_in_x, handle_in_y, anchor_x, anchor_y, handle_out_x, handle_out_y]

        points = [
            # Top edge start (after TL corner)
            (x + r,     y,         x + r,     y,         x + w - r, y),
            # Top edge end (before TR corner) -- NOTE: for a straight segment, handle_out of prev = anchor of prev, handle_in of next = anchor of next
            # Actually for a straight line between two points, the handles lie on the line.
            # Let me use the simplified approach: just 4 arcs with straight segments between.

            # TR corner approach: anchor at (x+w-r, y), handle_out toward corner
            (x + w - r, y,         x + w - r, y,         x + w - r + k, y),
            # TR corner: anchor at (x+w, y+r), handle_in from corner
            (x + w,     y + r - k, x + w,     y + r,     x + w,     y + r),

            # Right edge
            (x + w,     y + r,     x + w,     y + h - r, x + w,     y + h - r),
            # BR corner approach
            (x + w,     y + h - r, x + w,     y + h - r, x + w,     y + h - r + k),
            # BR corner
            (x + w - r + k, y + h, x + w - r, y + h,     x + w - r, y + h),

            # Bottom edge (right to left)
            (x + w - r, y + h,     x + r,     y + h,     x + r,     y + h),
            # BL corner approach
            (x + r,     y + h,     x + r,     y + h,     x + r - k, y + h),
            # BL corner
            (x,         y + h - r + k, x, y + h - r,     x,         y + h - r),

            # Left edge (bottom to top)
            (x,         y + h - r, x,         y + r,     x,         y + r),
            # TL corner approach
            (x,         y + r,     x,         y + r,     x,         y + r - k),
            # TL corner -- connects back to first point
            (x + r - k, y,         x + r,     y,         x + r,     y),
        ]
        # This has redundant straight-edge points. Simplify to 8 points (the canonical rounded rect).
        cp = []
        points = []
        # 8-point rounded rectangle (2 points per corner, the arc endpoints)
        # For straight segments, handles coincide with anchors.
        # For arc segments, handles are offset by kappa.

        def pt(hlx, hly, ax, ay, hrx, hry):
            points.append((hlx, hly, ax, ay, hrx, hry))

        # Going clockwise from top-left corner
        pt(x + r - k, y,           x + r,   y,       x + r,   y)         # 0: TL arc end / top edge start
        pt(x + w - r, y,           x + w-r, y,       x + w-r+k, y)       # 1: top edge end / TR arc start
        pt(x + w,     y + r - k,   x + w,   y + r,   x + w,   y + r)     # 2: TR arc end / right edge start
        pt(x + w,     y + h - r,   x + w,   y+h-r,   x + w,   y+h-r+k)  # 3: right edge end / BR arc start
        pt(x + w-r+k, y + h,       x + w-r, y + h,   x + w-r, y + h)    # 4: BR arc end / bottom edge start
        pt(x + r,     y + h,       x + r,   y + h,   x + r-k, y + h)    # 5: bottom edge end / BL arc start
        pt(x,         y + h-r+k,   x,       y+h-r,   x,       y+h-r)    # 6: BL arc end / left edge start
        pt(x,         y + r,       x,       y + r,   x,       y + r-k)   # 7: left edge end / TL arc start

        for p in points:
            cp.extend(p)

        pdb = Gimp.get_pdb()
        proc = pdb.lookup_procedure('gimp-vectors-bezier-stroke-new')
        pc = proc.create_config()
        pc.set_property('vectors', vectors)
        fa = Gimp.FloatArray.new(cp)
        pc.set_property('controlpoints', fa)
        pc.set_property('closed', True)
        proc.run(pc)

    image.set_active_vectors(vectors)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Chemin Ellipse
# ---------------------------------------------------------------------------
def shape_ellipse(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-shape-ellipse')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    cx = config.get_property('center-x')
    cy = config.get_property('center-y')
    rx = config.get_property('radius-x')
    ry = config.get_property('radius-y')

    Gimp.context_push()
    image.undo_group_start()

    vectors = Gimp.Vectors.new(image, "Ellipse")
    image.insert_vectors(vectors, None, -1)

    # Use the built-in ellipse stroke helper
    pdb = Gimp.get_pdb()
    proc = pdb.lookup_procedure('gimp-vectors-bezier-stroke-new-ellipse')
    pc = proc.create_config()
    pc.set_property('vectors', vectors)
    pc.set_property('x0', float(cx))
    pc.set_property('y0', float(cy))
    pc.set_property('radius-x', float(rx))
    pc.set_property('radius-y', float(ry))
    pc.set_property('angle', 0.0)
    proc.run(pc)

    image.set_active_vectors(vectors)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Chemin Polygone
# ---------------------------------------------------------------------------
def shape_polygon(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-shape-polygon')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    cx = config.get_property('center-x')
    cy = config.get_property('center-y')
    radius = config.get_property('radius')
    sides = config.get_property('num-sides')

    Gimp.context_push()
    image.undo_group_start()

    vectors = Gimp.Vectors.new(image, "Polygon (%d sides)" % sides)
    image.insert_vectors(vectors, None, -1)

    # Build polygon vertices — straight-line bezier (handles = anchors)
    cp = []
    for i in range(sides):
        angle = -math.pi / 2.0 + (2.0 * math.pi * i / sides)
        ax = cx + radius * math.cos(angle)
        ay = cy + radius * math.sin(angle)
        # handle_left = anchor = handle_right for straight segments
        cp.extend([ax, ay, ax, ay, ax, ay])

    pdb = Gimp.get_pdb()
    proc = pdb.lookup_procedure('gimp-vectors-bezier-stroke-new')
    pc = proc.create_config()
    pc.set_property('vectors', vectors)
    fa = Gimp.FloatArray.new(cp)
    pc.set_property('controlpoints', fa)
    pc.set_property('closed', True)
    proc.run(pc)

    image.set_active_vectors(vectors)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Chemin Etoile
# ---------------------------------------------------------------------------
def shape_star(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-shape-star')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    cx = config.get_property('center-x')
    cy = config.get_property('center-y')
    outer_r = config.get_property('outer-radius')
    inner_r = config.get_property('inner-radius')
    points = config.get_property('num-points')

    Gimp.context_push()
    image.undo_group_start()

    vectors = Gimp.Vectors.new(image, "Star (%d points)" % points)
    image.insert_vectors(vectors, None, -1)

    # Alternating outer/inner vertices
    cp = []
    total_verts = points * 2
    for i in range(total_verts):
        angle = -math.pi / 2.0 + (2.0 * math.pi * i / total_verts)
        r = outer_r if (i % 2 == 0) else inner_r
        ax = cx + r * math.cos(angle)
        ay = cy + r * math.sin(angle)
        cp.extend([ax, ay, ax, ay, ax, ay])

    pdb = Gimp.get_pdb()
    proc = pdb.lookup_procedure('gimp-vectors-bezier-stroke-new')
    pc = proc.create_config()
    pc.set_property('vectors', vectors)
    fa = Gimp.FloatArray.new(cp)
    pc.set_property('controlpoints', fa)
    pc.set_property('closed', True)
    proc.run(pc)

    image.set_active_vectors(vectors)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Chemin Fleche
# ---------------------------------------------------------------------------
def shape_arrow(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-shape-arrow')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    sx = config.get_property('start-x')
    sy = config.get_property('start-y')
    ex = config.get_property('end-x')
    ey = config.get_property('end-y')
    head = config.get_property('head-size')
    shaft_w = config.get_property('shaft-width')

    Gimp.context_push()
    image.undo_group_start()

    vectors = Gimp.Vectors.new(image, "Arrow")
    image.insert_vectors(vectors, None, -1)

    # Calculate arrow geometry
    dx = ex - sx
    dy = ey - sy
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1.0:
        length = 1.0

    # Unit vectors: along arrow and perpendicular
    ux = dx / length
    uy = dy / length
    px = -uy  # perpendicular
    py = ux

    half_shaft = shaft_w / 2.0

    # Arrow as closed polygon path:
    # 7 vertices: shaft (4 corners of the rectangle) + arrowhead (3 triangle points)
    # Going clockwise:
    #   P0: start left
    #   P1: base of head left (shaft)
    #   P2: base of head left (wide, arrowhead)
    #   P3: tip
    #   P4: base of head right (wide, arrowhead)
    #   P5: base of head right (shaft)
    #   P6: start right

    head_base_x = ex - ux * head
    head_base_y = ey - uy * head

    verts = [
        (sx + px * half_shaft,           sy + py * half_shaft),           # P0
        (head_base_x + px * half_shaft,  head_base_y + py * half_shaft),  # P1
        (head_base_x + px * head * 0.5,  head_base_y + py * head * 0.5), # P2
        (ex,                              ey),                             # P3 (tip)
        (head_base_x - px * head * 0.5,  head_base_y - py * head * 0.5), # P4
        (head_base_x - px * half_shaft,  head_base_y - py * half_shaft),  # P5
        (sx - px * half_shaft,           sy - py * half_shaft),           # P6
    ]

    cp = []
    for vx, vy in verts:
        cp.extend([vx, vy, vx, vy, vx, vy])

    pdb = Gimp.get_pdb()
    proc = pdb.lookup_procedure('gimp-vectors-bezier-stroke-new')
    pc = proc.create_config()
    pc.set_property('vectors', vectors)
    fa = Gimp.FloatArray.new(cp)
    pc.set_property('controlpoints', fa)
    pc.set_property('closed', True)
    proc.run(pc)

    image.set_active_vectors(vectors)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ---------------------------------------------------------------------------
# Chemin Spirale
# ---------------------------------------------------------------------------
def shape_spiral(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version('GimpUi', '3.0')
        from gi.repository import GimpUi
        GimpUi.init('python-fu-shape-spiral')
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    cx = config.get_property('center-x')
    cy = config.get_property('center-y')
    turns = config.get_property('turns')
    start_r = config.get_property('start-radius')
    end_r = config.get_property('end-radius')

    Gimp.context_push()
    image.undo_group_start()

    vectors = Gimp.Vectors.new(image, "Spiral (%.1f turns)" % turns)
    image.insert_vectors(vectors, None, -1)

    # Generate spiral as a series of bezier segments
    # Use ~8 segments per full turn for smooth curves
    segs_per_turn = 8
    total_segs = max(int(turns * segs_per_turn), 1)
    total_angle = turns * 2.0 * math.pi

    cp = []
    for i in range(total_segs + 1):
        t = i / float(total_segs)
        angle = t * total_angle
        r = start_r + (end_r - start_r) * t

        ax = cx + r * math.cos(angle)
        ay = cy + r * math.sin(angle)

        # Calculate tangent direction for bezier handles
        # dr/dt and dangle/dt
        dangle = total_angle / total_segs
        dr = (end_r - start_r) / total_segs

        # Tangent vector at this point
        tx = -r * math.sin(angle) + (end_r - start_r) / total_angle * math.cos(angle) if total_angle > 0 else 0
        ty = r * math.cos(angle) + (end_r - start_r) / total_angle * math.sin(angle) if total_angle > 0 else 0

        # Scale tangent for bezier handle length (~1/3 of segment)
        handle_scale = total_angle / (total_segs * 3.0)

        hlx = ax - tx * handle_scale
        hly = ay - ty * handle_scale
        hrx = ax + tx * handle_scale
        hry = ay + ty * handle_scale

        cp.extend([hlx, hly, ax, ay, hrx, hry])

    pdb = Gimp.get_pdb()
    proc = pdb.lookup_procedure('gimp-vectors-bezier-stroke-new')
    pc = proc.create_config()
    pc.set_property('vectors', vectors)
    fa = Gimp.FloatArray.new(cp)
    pc.set_property('controlpoints', fa)
    pc.set_property('closed', False)
    proc.run(pc)

    image.set_active_vectors(vectors)
    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


# ===========================================================================
# Plugin registration
# ===========================================================================
class VectorShapes(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-shape-rectangle',
            'python-fu-shape-ellipse',
            'python-fu-shape-polygon',
            'python-fu-shape-star',
            'python-fu-shape-arrow',
            'python-fu-shape-spiral',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)
        menu_base = "<Image>/Filters/Vector/Shapes"

        if name == 'python-fu-shape-rectangle':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                shape_rectangle, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Chemin Rectangle"),
                _("Creer un chemin vectoriel rectangle avec des coins arrondis optionnels."),
                name)
            procedure.set_menu_label(_("_Rectangle..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("x", _("_X"), _("Coordonnee X du coin superieur gauche"),
                                          -10000.0, 100000.0, 50.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("y", _("_Y"), _("Coordonnee Y du coin superieur gauche"),
                                          -10000.0, 100000.0, 50.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("width", _("_Largeur"), _("Largeur du rectangle"),
                                          1.0, 100000.0, 400.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("height", _("_Hauteur"), _("Hauteur du rectangle"),
                                          1.0, 100000.0, 300.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("corner-radius", _("Rayon des _coins"),
                                          _("Rayon d'arrondi des coins (0 = coins vifs)"),
                                          0.0, 10000.0, 0.0,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-shape-ellipse':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                shape_ellipse, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Chemin Ellipse"),
                _("Creer un chemin vectoriel ellipse a partir du centre et des rayons."),
                name)
            procedure.set_menu_label(_("_Ellipse..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("center-x", _("Centre _X"), _("Coordonnee X du centre"),
                                          -10000.0, 100000.0, 250.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("center-y", _("Centre _Y"), _("Coordonnee Y du centre"),
                                          -10000.0, 100000.0, 200.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("radius-x", _("Rayon _X"), _("Rayon horizontal"),
                                          1.0, 100000.0, 200.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("radius-y", _("Rayon _Y"), _("Rayon vertical"),
                                          1.0, 100000.0, 150.0,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-shape-polygon':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                shape_polygon, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Chemin Polygone"),
                _("Creer un chemin vectoriel polygone regulier (triangle, pentagone, hexagone, etc)."),
                name)
            procedure.set_menu_label(_("_Polygone..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("center-x", _("Centre _X"), _("Coordonnee X du centre"),
                                          -10000.0, 100000.0, 250.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("center-y", _("Centre _Y"), _("Coordonnee Y du centre"),
                                          -10000.0, 100000.0, 250.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("radius", _("_Rayon"), _("Distance du centre au sommet"),
                                          1.0, 100000.0, 150.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("num-sides", _("_Cotes"), _("Nombre de cotes (3=triangle, 5=pentagone, 6=hexagone, etc)"),
                                       3, 100, 6,
                                       GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-shape-star':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                shape_star, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Chemin Etoile"),
                _("Creer un chemin vectoriel etoile avec pointes et rayons configurables."),
                name)
            procedure.set_menu_label(_("_Etoile..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("center-x", _("Centre _X"), _("Coordonnee X du centre"),
                                          -10000.0, 100000.0, 250.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("center-y", _("Centre _Y"), _("Coordonnee Y du centre"),
                                          -10000.0, 100000.0, 250.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("outer-radius", _("Rayon _exterieur"),
                                          _("Distance du centre aux pointes exterieures"),
                                          1.0, 100000.0, 150.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("inner-radius", _("Rayon _interieur"),
                                          _("Distance du centre aux creux interieurs"),
                                          1.0, 100000.0, 60.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_int_argument("num-points", _("_Pointes"), _("Nombre de pointes de l'etoile"),
                                       3, 100, 5,
                                       GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-shape-arrow':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                shape_arrow, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Chemin Fleche"),
                _("Creer un chemin vectoriel fleche du point de depart au point d'arrivee."),
                name)
            procedure.set_menu_label(_("_Fleche..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("start-x", _("Debut _X"), _("X de debut de la fleche"),
                                          -10000.0, 100000.0, 50.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("start-y", _("Debut _Y"), _("Y de debut de la fleche"),
                                          -10000.0, 100000.0, 250.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("end-x", _("Fin _X"), _("X de fin de la fleche (pointe)"),
                                          -10000.0, 100000.0, 450.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("end-y", _("Fin _Y"), _("Y de fin de la fleche (pointe)"),
                                          -10000.0, 100000.0, 250.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("head-size", _("Taille de la _pointe"),
                                          _("Length of arrowhead"),
                                          1.0, 10000.0, 40.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("shaft-width", _("Largeur du _corps"),
                                          _("Largeur du corps de la fleche"),
                                          1.0, 10000.0, 20.0,
                                          GObject.ParamFlags.READWRITE)

        elif name == 'python-fu-shape-spiral':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                shape_spiral, None)
            procedure.set_image_types("*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE)
            procedure.set_documentation(
                _("Chemin Spirale"),
                _("Creer un chemin vectoriel spirale (spirale d'Archimede)."),
                name)
            procedure.set_menu_label(_("S_pirale..."))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path(menu_base)

            procedure.add_double_argument("center-x", _("Centre _X"), _("Coordonnee X du centre"),
                                          -10000.0, 100000.0, 250.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("center-y", _("Centre _Y"), _("Coordonnee Y du centre"),
                                          -10000.0, 100000.0, 250.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("turns", _("_Tours"), _("Nombre de tours de la spirale"),
                                          0.25, 50.0, 3.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("start-radius", _("Rayon de _depart"),
                                          _("Rayon au centre de la spirale"),
                                          0.0, 100000.0, 10.0,
                                          GObject.ParamFlags.READWRITE)
            procedure.add_double_argument("end-radius", _("Rayon de _fin"),
                                          _("Rayon au bord exterieur de la spirale"),
                                          1.0, 100000.0, 200.0,
                                          GObject.ParamFlags.READWRITE)

        else:
            return None

        return procedure


Gimp.main(VectorShapes.__gtype__, sys.argv)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#   PhotoGIMP Pro — Histogram Live
#   Enhanced histogram display with R/G/B curves and statistics
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


HIST_WIDTH = 400
HIST_HEIGHT = 300
GRAPH_X = 40       # left margin for labels
GRAPH_Y = 10       # top margin
GRAPH_W = 256      # one pixel per histogram bin
GRAPH_H = 200      # graph drawing height
STATS_Y = GRAPH_Y + GRAPH_H + 20  # Y position for stats text


def _compute_channel_histogram(drawable, channel):
    """Compute histogram for a channel and return (values, mean, stddev, min, max, clip_low, clip_high)."""
    pdb = Gimp.get_pdb()
    values = []
    total_pixels = 0
    weighted_sum = 0
    min_val = 255
    max_val = 0
    clip_low = 0
    clip_high = 0

    for i in range(256):
        result = pdb.run_procedure('gimp-drawable-histogram', [
            GObject.Value(Gimp.Drawable, drawable),
            GObject.Value(Gimp.HistogramChannel, channel),
            GObject.Value(GObject.TYPE_DOUBLE, float(i)),
            GObject.Value(GObject.TYPE_DOUBLE, float(i)),
        ])
        # Returns: mean, std_dev, median, pixels, count, percentile
        count = result.index(5) if result else 0.0
        count = max(0, int(count))
        values.append(count)
        total_pixels += count
        weighted_sum += i * count
        if count > 0:
            if i < min_val:
                min_val = i
            if i > max_val:
                max_val = i

    # Clipping warnings
    clip_low = values[0]
    clip_high = values[255]

    # Stats
    if total_pixels > 0:
        mean = weighted_sum / total_pixels
        variance_sum = sum((i - mean) ** 2 * values[i] for i in range(256))
        stddev = math.sqrt(variance_sum / total_pixels)
    else:
        mean = 0
        stddev = 0
        min_val = 0
        max_val = 0

    return values, mean, stddev, min_val, max_val, clip_low, clip_high


def _draw_curve(hist_drawable, values, color_r, color_g, color_b, max_count):
    """Draw a histogram curve on the histogram image layer."""
    pdb = Gimp.get_pdb()

    # Set foreground color for drawing
    color = Gimp.RGB()
    color.set(color_r, color_g, color_b)
    Gimp.context_set_foreground(color)
    Gimp.context_set_brush_size(1.5)
    Gimp.context_set_opacity(70.0)

    if max_count == 0:
        return

    # Draw the curve as a series of pencil strokes
    for i in range(GRAPH_W - 1):
        val1 = values[i] if i < len(values) else 0
        val2 = values[i + 1] if (i + 1) < len(values) else 0

        # Normalize to graph height (log scale for better visibility)
        h1 = int((math.log(val1 + 1) / math.log(max_count + 1)) * GRAPH_H) if val1 > 0 else 0
        h2 = int((math.log(val2 + 1) / math.log(max_count + 1)) * GRAPH_H) if val2 > 0 else 0

        x1 = GRAPH_X + i
        y1 = GRAPH_Y + GRAPH_H - h1
        x2 = GRAPH_X + i + 1
        y2 = GRAPH_Y + GRAPH_H - h2

        # Draw line segment using pencil
        strokes = [float(x1), float(y1), float(x2), float(y2)]
        pdb.run_procedure('gimp-pencil', [
            GObject.Value(Gimp.Drawable, hist_drawable),
            GObject.Value(Gimp.ObjectArray, Gimp.ObjectArray.new(GObject.TYPE_DOUBLE, strokes, False)),
        ])


def histogram_live(procedure, run_mode, image, drawables, config, data):
    """Compute and display detailed histogram for the current drawable."""
    if not drawables:
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                           GLib.Error.new_literal(GLib.quark_from_string("histogram"),
                                                                  "Aucun calque actif.", 0))

    drawable = drawables[0]
    pdb = Gimp.get_pdb()

    Gimp.context_push()

    # Compute histograms for each channel
    is_rgb = drawable.is_rgb()

    channels = {}
    if is_rgb:
        channels['R'] = _compute_channel_histogram(drawable, Gimp.HistogramChannel.RED)
        channels['G'] = _compute_channel_histogram(drawable, Gimp.HistogramChannel.GREEN)
        channels['B'] = _compute_channel_histogram(drawable, Gimp.HistogramChannel.BLUE)
    channels['L'] = _compute_channel_histogram(drawable, Gimp.HistogramChannel.VALUE)

    # Find max count across all channels for normalization
    max_count = 1
    for ch_data in channels.values():
        ch_max = max(ch_data[0]) if ch_data[0] else 1
        if ch_max > max_count:
            max_count = ch_max

    # Create new image for the histogram display
    hist_image = Gimp.Image.new(HIST_WIDTH, HIST_HEIGHT, Gimp.ImageBaseType.RGB)

    # Background layer
    bg_layer = Gimp.Layer.new(hist_image, "Fond",
                              HIST_WIDTH, HIST_HEIGHT,
                              Gimp.ImageType.RGB_IMAGE, 100.0,
                              Gimp.LayerMode.NORMAL)
    hist_image.insert_layer(bg_layer, None, 0)

    # Fill background with dark gray
    color_bg = Gimp.RGB()
    color_bg.set(0.15, 0.15, 0.15)
    Gimp.context_set_foreground(color_bg)
    pdb.run_procedure('gimp-drawable-edit-fill', [
        GObject.Value(Gimp.Drawable, bg_layer),
        GObject.Value(Gimp.FillType, Gimp.FillType.FOREGROUND),
    ])

    # Draw graph border
    color_border = Gimp.RGB()
    color_border.set(0.4, 0.4, 0.4)
    Gimp.context_set_foreground(color_border)
    Gimp.context_set_brush_size(1.0)
    Gimp.context_set_opacity(100.0)

    # Draw border lines
    border_strokes = [
        float(GRAPH_X), float(GRAPH_Y),
        float(GRAPH_X + GRAPH_W), float(GRAPH_Y),
        float(GRAPH_X + GRAPH_W), float(GRAPH_Y + GRAPH_H),
        float(GRAPH_X), float(GRAPH_Y + GRAPH_H),
        float(GRAPH_X), float(GRAPH_Y),
    ]
    pdb.run_procedure('gimp-pencil', [
        GObject.Value(Gimp.Drawable, bg_layer),
        GObject.Value(Gimp.ObjectArray, Gimp.ObjectArray.new(GObject.TYPE_DOUBLE, border_strokes, False)),
    ])

    # Draw curves layer
    curves_layer = Gimp.Layer.new(hist_image, "Courbes",
                                  HIST_WIDTH, HIST_HEIGHT,
                                  Gimp.ImageType.RGBA_IMAGE, 100.0,
                                  Gimp.LayerMode.NORMAL)
    hist_image.insert_layer(curves_layer, None, 0)

    if is_rgb:
        _draw_curve(curves_layer, channels['R'][0], 1.0, 0.2, 0.2, max_count)
        _draw_curve(curves_layer, channels['G'][0], 0.2, 1.0, 0.2, max_count)
        _draw_curve(curves_layer, channels['B'][0], 0.3, 0.3, 1.0, max_count)

    # Luminosity in white
    _draw_curve(curves_layer, channels['L'][0], 0.8, 0.8, 0.8, max_count)

    # Add stats as a text annotation via floating text layer
    stats_layer = Gimp.Layer.new(hist_image, "Statistiques",
                                 HIST_WIDTH, HIST_HEIGHT,
                                 Gimp.ImageType.RGBA_IMAGE, 100.0,
                                 Gimp.LayerMode.NORMAL)
    hist_image.insert_layer(stats_layer, None, 0)

    # Draw stats text using gimp-text-fontname
    stats_lines = []
    for ch_name, ch_data in channels.items():
        values, mean, stddev, min_v, max_v, clip_lo, clip_hi = ch_data
        line = f"{ch_name}: min={min_v} max={max_v} moy={mean:.1f} σ={stddev:.1f} écrêt.=[{clip_lo},{clip_hi}]"
        stats_lines.append(line)

    stats_text = "\n".join(stats_lines)

    color_text = Gimp.RGB()
    color_text.set(0.9, 0.9, 0.9)
    Gimp.context_set_foreground(color_text)

    text_layer = pdb.run_procedure('gimp-text-fontname', [
        GObject.Value(Gimp.Image, hist_image),
        GObject.Value(Gimp.Drawable, stats_layer),
        GObject.Value(GObject.TYPE_DOUBLE, 10.0),
        GObject.Value(GObject.TYPE_DOUBLE, float(STATS_Y)),
        GObject.Value(GObject.TYPE_STRING, stats_text),
        GObject.Value(GObject.TYPE_INT, 0),
        GObject.Value(GObject.TYPE_BOOLEAN, True),
        GObject.Value(GObject.TYPE_DOUBLE, 11.0),
        GObject.Value(GObject.TYPE_STRING, "Sans"),
    ])

    # Flatten and display
    hist_image.flatten()
    hist_image.set_name("Histogramme détaillé")
    display = Gimp.Display.new(hist_image)

    Gimp.displays_flush()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class HistogramLive(Gimp.PlugIn):

    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return [
            'python-fu-histogram-live',
        ]

    def do_create_procedure(self, name):
        Gegl.init(None)

        if name == 'python-fu-histogram-live':
            procedure = Gimp.ImageProcedure.new(self, name,
                                                Gimp.PDBProcType.PLUGIN,
                                                histogram_live, None)
            procedure.set_image_types("RGB*, GRAY*")
            procedure.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                           Gimp.ProcedureSensitivityMask.DRAWABLES)
            procedure.set_documentation(
                _("Detailed Histogram"),
                _("Calculer et afficher un histogramme détaillé R/V/B/L avec statistiques et avertissements d'écrêtage."),
                name)
            procedure.set_menu_label(_("_Histogramme détaillé"))
            procedure.set_attribution("PhotoGIMP Pro", "GPL v3+", "2026")
            procedure.add_menu_path("<Image>/Windows")

        else:
            return None

        return procedure


Gimp.main(HistogramLive.__gtype__, sys.argv)

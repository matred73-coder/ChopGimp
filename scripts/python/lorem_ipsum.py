#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#   PhotoGIMP Pro — Lorem Ipsum Generator
#   Insert placeholder text as a text layer
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp
gi.require_version('GimpUi', '3.0')
from gi.repository import GimpUi
from gi.repository import GObject, GLib
import sys

LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, "
    "quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. "
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu "
    "fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in "
    "culpa qui officia deserunt mollit anim id est laborum.\n\n"
    "Curabitur pretium tincidunt lacus. Nulla gravida orci a odio. Nullam varius, "
    "turpis et commodo pharetra, est eros bibendum elit, nec luctus magna felis "
    "sollicitudin mauris. Integer in mauris eu nibh euismod gravida. Duis ac tellus "
    "et risus vulputate vehicula. Donec lobortis risus a elit. Etiam tempor. Ut "
    "ullamcorper, ligula ut dictum pharetra, nisi nunc fringilla magna, in commodo "
    "elit erat nec turpis. Ut pharetra augue nec augue.\n\n"
    "Praesent dapibus, neque id cursus faucibus, tortor neque egestas augue, eu "
    "vulputate magna eros eu erat. Aliquam erat volutpat. Nam dui mi, tincidunt "
    "quis, accumsan porttitor, facilisis luctus, metus. Phasellus ultrices nulla "
    "quis nibh. Quisque a lectus. Donec consectetuer ligula vulputate sem tristique "
    "cursus. Nam nulla quam, gravida non, commodo a, sodales sit amet, nisi."
)

def lorem_run(procedure, run_mode, image, drawables, config, data):
    if run_mode == Gimp.RunMode.INTERACTIVE:
        GimpUi.init("lorem_ipsum")
        dialog = GimpUi.ProcedureDialog.new(procedure, config, "Lorem Ipsum")
        dialog.fill(None)
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    paragraphs = int(config.get_property("paragraphs"))
    font_size = config.get_property("font-size")

    Gimp.context_push()
    image.undo_group_start()

    parts = LOREM.split("\n\n")
    text = "\n\n".join(parts[:min(paragraphs, len(parts))])
    if paragraphs > len(parts):
        for i in range(paragraphs - len(parts)):
            text += "\n\n" + parts[i % len(parts)]

    layer = Gimp.TextLayer.new(image, text, Gimp.context_get_font(), font_size, Gimp.Unit.pixel())
    image.insert_layer(layer, None, -1)

    Gimp.displays_flush()
    image.undo_group_end()
    Gimp.context_pop()
    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class LoremIpsum(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["photogimp-lorem-ipsum"]

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, lorem_run, None)
        procedure.set_menu_label("Lorem Ipsum...")
        procedure.set_icon_name("gimp-text-layer")
        procedure.add_menu_path("<Image>/Filters/Design/")
        procedure.set_documentation("Insert Lorem Ipsum text", "Creates a text layer with placeholder text", name)
        procedure.set_attribution("PhotoGIMP Pro", "PhotoGIMP Pro", "2026")
        procedure.add_int_argument("paragraphs", "Paragraphes", "Nombre de paragraphes", 1, 10, 3, GObject.ParamFlags.READWRITE)
        procedure.add_double_argument("font-size", "Taille de police", "Taille en pixels", 8.0, 200.0, 24.0, GObject.ParamFlags.READWRITE)
        return procedure

Gimp.main(LoremIpsum.__gtype__, sys.argv)

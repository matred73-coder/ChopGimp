#!/usr/bin/env python3
"""Extrait les actions GIMP et leurs raccourcis par défaut depuis les sources
(app/actions/*.c et app/tools/*.c) → JSON {action: [accels]}.
Usage : extract_default_shortcuts.py <gimp-src>/app > defaults.json"""
import re, sys, os, json, glob
app = sys.argv[1]
acts = {}
entry = re.compile(r'\{\s*"([a-z0-9][a-z0-9-]+)"\s*,[^{};]*?\{\s*((?:"[^"]*"\s*,\s*)*)NULL\s*\}', re.S)
for f in glob.glob(os.path.join(app, 'actions', '*.c')):
    src = open(f, encoding='utf-8', errors='ignore').read()
    for m in entry.finditer(src):
        acts[m.group(1)] = re.findall(r'"([^"]*)"', m.group(2))
tool = re.compile(r'"gimp-([a-z0-9-]+)-tool"\s*,.*?N_\("[^"]*"\)\s*,\s*("([^"]*)"|NULL)', re.S)
for f in glob.glob(os.path.join(app, 'tools', 'gimp*tool.c')):
    src = open(f, encoding='utf-8', errors='ignore').read()
    i = src.find('_tool_register')
    if i < 0:
        continue
    m = tool.search(src, i)
    if m:
        acts['tools-' + m.group(1)] = [m.group(3)] if m.group(3) else []
json.dump(acts, sys.stdout, indent=0, sort_keys=True)

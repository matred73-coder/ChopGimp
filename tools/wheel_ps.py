#!/usr/bin/env python3
"""Molette façon Photoshop dans un controllerrc : Alt+molette = zoom,
Ctrl+molette = défilement horizontal. Usage : wheel_ps.py <controllerrc>"""
import re
import sys

p = sys.argv[1]
s = open(p).read()
PS = {"scroll-up-alt": "view-zoom-in", "scroll-down-alt": "view-zoom-out",
      "scroll-up-primary": "view-scroll-left", "scroll-down-primary": "view-scroll-right"}
m = re.search(r'\(GimpControllerInfo "Main Mouse Wheel".*?\(mapping(.*?)\)\)\n', s, re.S)
if not m:
    sys.exit("bloc « Main Mouse Wheel » introuvable dans " + p)
body = m.group(1)
for k in PS:
    body = re.sub(r'\n\s*\(map "%s" "[^"]*"\)' % re.escape(k), "", body)
body += "".join('\n        (map "%s" "%s")' % kv for kv in PS.items())
open(p, "w").write(s[:m.start(1)] + body + s[m.end(1):])

#!/usr/bin/env python3
"""Regroupement de la série de patchs GIMP en thèmes (docs/dev/PATCHS.md).

Reconstruit dans build/gimp-src une branche thématique (par défaut
photogimp-v2) depuis GIMP_3_2_8, à partir de l'arbre final de la branche
source (par défaut photogimp-legacy) : chaque fichier appartient à un seul
thème, un commit par thème. Le commit de l'icône Windows (ancien 0045) reste
seul, tel quel. Vérifie à la fin que les deux arbres sont identiques.

  tools/dev/regroup_patches.py [--source BRANCHE] [--target BRANCHE] [--tsv FICHIER]

Ne sert qu'une fois (4.2.1) ou pour refaire le regroupement : ensuite, un
correctif est un commit « fixup » sur le thème concerné (voir PATCHS.md).
"""
import argparse
import collections
import os
import subprocess
import sys

BASE = "GIMP_3_2_8"
WINDOWS_ICON = 45          # ancien patch gardé tel quel (sous-module gimp-data)

# (thème, titre, anciens patchs) — ordre d'application
THEMES = [
    ("T01", "socle : identité, configuration, journal de session, rapport de plantage",
     [1, 10, 11, 13, 20, 30, 47, 74, 76]),
    ("T02", "Windows : build, installateur, instances, orthographe", [43, 44, 46, 134, 135]),
    ("T03", "gestes Photoshop des outils de base", [2, 3, 4, 5, 6, 8, 14, 91, 92, 98, 99, 100]),
    ("T04", "barre d'options", [9, 18, 19, 21, 22, 23, 25, 31, 32, 108, 109, 114, 173]),
    ("T05", "contrôles de transformation", [16, 17, 35, 36, 40, 75]),
    ("T06", "outils raster ajoutés", [15, 26, 29, 41, 86, 87, 142, 143, 157]),
    ("T07", "panneaux, docks et vignettes de calques",
     [7, 37, 38, 42, 48, 49, 50, 51, 52, 53, 54, 55, 116, 117, 174]),
    ("T08", "apparence : curseurs, thèmes, onglets, espaces de travail",
     [63, 64, 71, 72, 112, 168, 171]),
    ("T09", "texte", [65, 66, 67, 68, 73, 90]),
    ("T10", "styles de calque et filtres", [39, 94, 95, 101, 113, 115]),
    ("T11", "performance du rendu", [96, 97, 102, 103, 104, 105, 106, 107, 110, 111]),
    ("T12", "lib2geom, outil Forme, Pathfinder, Concepteur de formes",
     [24, 28, 33, 34, 56, 57, 58, 59, 60, 61, 62, 69]),
    ("T13", "objets vectoriels : modèle, outils, panneaux, SVG, sélection, copier-coller",
     [118, 119, 120, 121, 122, 123, 124, 125, 126, 144, 158, 178, 179, 181, 182]),
    ("T14", "vectoriser", [127, 128, 129, 130, 131, 132, 133, 137]),
    ("T15", "outils vectoriels avancés", [138, 140, 141, 146, 147, 149, 153, 154, 155, 156]),
    ("T16", "performance vectorielle et allègement 4.1", [148, 150, 151, 152, 159, 170, 175, 176]),
    ("T17", "Pinceau goutte, formes de pinceau, répétitions", [160, 161, 177]),
    ("T18", "plans de travail et grille de perspective", [162, 166, 167, 169]),
    ("T19", "fichiers : PSD, PDF, SVG, Importer", [79, 80, 81, 163, 172]),
    ("T20", "CMJN façon Photoshop", [180]),
    ("T21", "fonctions Photoshop diverses", [77, 78, 82, 83, 84, 85, 88, 89, 93, 136]),
    ("T22", "menus, Satin / Incrustation de motif, traductions", [12, 27, 139, 145, 164]),
]
# correctifs transverses (revue 3.24, compilation 3.99.0) : pas de thème,
# leurs lignes vont au propriétaire de chaque fichier
TRANSVERSE = [70, 165]
# fichiers dont le thème est imposé (sinon : créateur, puis plus de lignes)
FORCED = {
    "app/chopgimp-crash.c": "T01", "app/chopgimp-crash.h": "T01",
    "app/widgets/gimpcriticaldialog.c": "T01", "app/widgets/gimpcriticaldialog.h": "T01",
}


def git(*args, check=True):
    r = subprocess.run(["git", "-C", SRC] + list(args), capture_output=True, text=True)
    if check and r.returncode:
        sys.exit("git %s : %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def main():
    global SRC
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(os.path.dirname(__file__), "..", "..", "build", "gimp-src"))
    ap.add_argument("--source", default="photogimp-legacy")
    ap.add_argument("--target", default="photogimp-v2")
    ap.add_argument("--tsv", default=None)
    a = ap.parse_args()
    SRC = os.path.abspath(a.src)

    commits = git("rev-list", "--reverse", "%s..%s" % (BASE, a.source)).split()
    theme_of = {}
    for t, _, nums in THEMES:
        for n in nums:
            theme_of[n] = t
    known = set(theme_of) | set(TRANSVERSE) | {WINDOWS_ICON}
    missing = [i for i in range(1, len(commits) + 1) if i not in known]
    if missing:
        sys.exit("commits sans thème : %s" % missing)

    weight = collections.defaultdict(collections.Counter)
    creator = {}
    icon_files = set()
    for i, c in enumerate(commits, 1):
        for line in git("show", "--format=", "--numstat", "--no-renames", c).splitlines():
            add, dele, path = line.split("\t")
            if i == WINDOWS_ICON:
                icon_files.add(path)
                continue
            if i in theme_of:
                n = (int(add) if add != "-" else 1) + (int(dele) if dele != "-" else 1)
                weight[path][theme_of[i]] += n
        for line in git("show", "--format=", "--name-status", "--no-renames", c).splitlines():
            st, path = line.split("\t", 1)
            if st == "A" and path not in creator and i in theme_of:
                creator[path] = theme_of[i]

    final = git("diff", "--name-only", "--no-renames", BASE, a.source).split()
    owner = {}
    for f in final:
        if f in icon_files:
            owner[f] = "ICON"
        elif f in FORCED:
            owner[f] = FORCED[f]
        elif f.startswith("po") and f.endswith(".po"):
            owner[f] = "T22"
        elif f in creator:
            owner[f] = creator[f]
        elif weight[f]:
            owner[f] = weight[f].most_common(1)[0][0]
        else:
            owner[f] = "T01"
    if icon_files & set(f for f in final if owner[f] != "ICON"):
        sys.exit("fichiers de l'icône Windows touchés ailleurs")

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8") as out:
            out.write("fichier\tthème\n")
            for f in sorted(final):
                out.write("%s\t%s\n" % (f, owner[f]))

    if git("status", "--porcelain", "--untracked-files=no").strip():
        sys.exit("build/gimp-src a des modifications non commitées")
    git("checkout", "-q", "-B", a.target, BASE)
    env_date = git("log", "-1", "--format=%ad", "--date=iso-strict", a.source).strip()
    order = [("ICON", None)] + [(t, title) for t, title, _ in THEMES]
    # l'icône Windows (ancien 0045) en tête de T02 : juste avant T02
    order = [o for o in order if o[0] != "ICON"]
    i02 = [o[0] for o in order].index("T02")
    order.insert(i02, ("ICON", None))
    for t, title in order:
        files = sorted(f for f in final if owner[f] == t)
        if not files:
            continue
        if t == "ICON":
            git("cherry-pick", "--allow-empty", commits[WINDOWS_ICON - 1])
            continue
        for k in range(0, len(files), 200):
            git("checkout", a.source, "--", *files[k:k + 200])
        git("add", "--", *files)
        msg = "ChopGimp %s: %s\n\nAnciens patchs : %s." % (
            t, title, ", ".join("%04d" % n for n in next(x[2] for x in THEMES if x[0] == t)))
        subprocess.run(["git", "-C", SRC, "commit", "-q", "-m", msg],
                       env=dict(os.environ, GIT_AUTHOR_DATE=env_date, GIT_COMMITTER_DATE=env_date),
                       check=True)
    diff = git("diff", "--stat", a.target, a.source)
    print("%d fichiers, %d commits ; diff %s..%s : %s" % (
        len(final), int(git("rev-list", "--count", "%s..%s" % (BASE, a.target))),
        a.target, a.source, "VIDE" if not diff.strip() else diff))
    return 0 if not diff.strip() else 1


if __name__ == "__main__":
    sys.exit(main())

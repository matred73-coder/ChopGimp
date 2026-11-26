#!/usr/bin/env python3
"""
ChopGimp 3.31.0 (lot 4b) — vérification de l'export PSD par un lecteur
indépendant : psd-tools (hors du paquet Flatpak).

Lit le PSD écrit par le test de fonctionnement (tools/smoke_test.py,
« psd-tools.psd ») et écrit une ligne « OK|ÉCHEC  test  détail » par test,
comme le test de fonctionnement (tools/dev/smoke.sh les ajoute au résultat).

    python3 check_psd_tools.py <fichier.psd>

psd-tools : `pip install psd-tools` (tools/dev/smoke.sh l'installe dans un
environnement virtuel de $CHOPGIMP_DEV).
"""
import sys
import traceback


def main(path):
    out = []

    def report(ok, name, detail=""):
        out.append("%s  %s  %s" % ("OK    " if ok else "ÉCHEC ", name, detail))

    try:
        from psd_tools import PSDImage
        psd = PSDImage.open(path)
        by = {layer.name: layer for layer in psd.descendants()}

        forme = by.get("Forme")
        kinds = sorted(type(e).__name__ for e in (forme.effects if forme is not None else []))
        report(forme is not None and "DropShadow" in kinds and "Stroke" in kinds,
               "psd-tools : styles de calque (lfx2) lus", ", ".join(kinds))
        if forme is not None and forme.effects:
            ds = [e for e in forme.effects if type(e).__name__ == "DropShadow"]
            report(bool(ds) and ds[0].enabled and abs(ds[0].distance - 8.485) < 0.1
                   and str(ds[0].blend_mode).endswith("MULTIPLY"),
                   "psd-tools : ombre portée (distance, mode)",
                   "%.3f %s" % (ds[0].distance, ds[0].blend_mode) if ds else "")

        titre = by.get("Titre")
        report(titre is not None and titre.kind == "type" and "Titre ChopGimp" in titre.text,
               "psd-tools : calque de texte (TySh, EngineData)",
               repr(titre.text) if titre is not None and titre.kind == "type" else "")

        ell = by.get("Ellipse")
        report(ell is not None and ell.kind == "shape" and ell.has_vector_mask(),
               "psd-tools : calque de forme (vmsk + vscg)", ell.kind if ell is not None else "")

        flou = by.get("Flou")
        orig = [n for n in by if "original" in n]
        report(flou is not None and orig and not by[orig[0]].visible,
               "psd-tools : filtre fusionné, original masqué gardé", ", ".join(orig))

        img = psd.composite()
        report(img is not None and img.size == (600, 400), "psd-tools : image composite",
               "%dx%d" % img.size if img is not None else "")
    except Exception:
        report(False, "psd-tools", traceback.format_exc().replace("\n", " | ")[:400])

    print("\n".join(out))
    return all(line.startswith("OK") for line in out)


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1]) else 1)

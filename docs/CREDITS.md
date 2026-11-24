# Crédits

ChopGimp est un logiciel libre (GPL-3.0-ou-ultérieure) fondé sur :

- **GIMP 3.2.8** — https://www.gimp.org (GPL-3.0-ou-ultérieure).
- **Resynthesizer 3.0.1** (Lloyd Konneker) — Correcteur localisé, Remplir d'après le contenu (GPL-3.0).
- **lib2geom 1.4** (projet Inkscape) — moteur géométrique des outils vectoriels :
  Pathfinder, Bâtisseur de formes, décalages, simplification, effets de chemin
  (LGPL-2.1 / MPL-1.1). https://gitlab.com/inkscape/lib2geom
- **Inkscape 1.4** — code de contour / décalage repris de `src/helper/geom-pathstroke.cpp`
  (Liam P. White, Tavmjong Bah, Alexander Brock ; GPL-2.0-ou-ultérieure), dans
  `app/path/chopgimp-inkscape-pathstroke.cc`. https://inkscape.org
- **boost**, **GSL**, **double-conversion** — dépendances de lib2geom.
- **Dictionnaire orthographique français « classique »** (Olivier R., Dicollecte /
  Grammalecte ; MPL-2.0), dans `data/hunspell/`, et **Hunspell** (bibliothèque
  du runtime GNOME) pour la vérification d'orthographe des textes.

- **potrace 1.16** (Peter Selinger ; GPL-2.0-ou-ultérieure) — moteur principal de
  Vectoriser (module Flatpak `potrace`, bibliothèque seule). https://potrace.sourceforge.net
- **autotrace** (tracé central) et **libdepixelize** (Kopf-Lischinski, pixel art),
  repris des sources d'Inkscape (GPL-2.0-ou-ultérieure / LGPL), dans
  `app/path/trace/autotrace` et `app/path/trace/depixelize`.
- **liblqr** (Carlo Baldassi ; LGPL-3.0) — mise à l'échelle selon le contenu.
- **onnxruntime**, **numpy** (MIT / BSD) — IA locale ; modèles téléchargés à part,
  chacun sous sa propre licence.
- **mimalloc** (Microsoft ; MIT) — allocateur mémoire.

Icônes, thème, outils et plug-ins ChopGimp : originaux, GPL-3.0-ou-ultérieure.

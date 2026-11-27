# Plan de regroupement des patchs GIMP — ChopGimp 4.1 (proposition, non appliquée)

État de départ : 173 patchs `patches/gimp-3.2.8/0001…0173` (4.0.1), plus le 0174 de la 4.0.2
(panneau Calques) et les commits 4.1.0 de la branche `next-4.1` (interrupteurs retirés,
code mort, `chopgimp-vutil.c`). Les patchs babl (2) et GEGL (7) ne changent pas.

Objectif : **21 patchs thématiques**, chacun nommé `NN-ChopGimp-<thème>.patch`, appliqués
dans l'ordre ci-dessous. Une seule série, toujours appliquée en entier : un thème n'a pas à
compiler seul, mais l'ordre doit respecter les dépendances (socle → interface → vectoriel).

## Thèmes et ordre

| # | Thème | Patchs actuels | Lignes ± |
|---|---|---|---|
| T01 | Socle : identité, configuration, journal de session, rapport de plantage | 0001, 0010, 0011, 0013, 0020, 0030, 0047, 0074, 0076 | 1 029 |
| T02 | Windows : build, installateur, instances, orthographe | 0043, 0044, 0045, 0046, 0134, 0135 | 177 |
| T03 | Gestes Photoshop des outils de base (modificateurs, Alt, Ctrl, chiffres, Espace) | 0002, 0003, 0004, 0005, 0006, 0008, 0014, 0091, 0092, 0098, 0099, 0100 | 636 |
| T04 | Barre d'options | 0009, 0018, 0019, 0021, 0022, 0023, 0025, 0031, 0032, 0108, 0109, 0114, 0173 | 4 107 |
| T05 | Contrôles de transformation | 0016, 0017, 0035, 0036, 0040, 0075 | 650 |
| T06 | Outils raster ajoutés : stylet, Main / Rotation, Correcteur localisé, stabilisateur, papier, Lasso magnétique, Sélection rapide | 0015, 0026, 0029, 0041, 0086, 0087, 0142, 0143, 0157 | 2 647 |
| T07 | Panneaux, docks et vignettes de calques (+ 4.0.2 : panneau Calques) | 0007, 0037, 0038, 0042, 0048, 0049, 0050, 0051, 0052, 0053, 0054, 0055, 0116, 0117 | 3 718 |
| T08 | Apparence : curseurs, thèmes, curseurs de valeur, onglets, espaces de travail | 0063, 0064, 0071, 0072, 0112, 0168, 0171 | 2 446 |
| T09 | Texte | 0065, 0066, 0067, 0068, 0073, 0090 | 6 264 |
| T10 | Styles de calque et filtres | 0039, 0094, 0095, 0101, 0113, 0115 | 4 773 |
| T11 | Performance du rendu : projection, cache XCF des effets, fil de rendu, styles fusionnés, brouillons | 0096, 0097, 0102, 0103, 0104, 0105, 0106, 0107, 0110, 0111 | 20 208 |
| T12 | Moteur lib2geom, outil Forme, Pathfinder, Concepteur de formes | 0024, 0028, 0033, 0034, 0056, 0057, 0058, 0059, 0060, 0061, 0062, 0069 | 6 710 |
| T13 | Objets vectoriels : modèle, outils V / A, panneaux Objets / Aspect / Couleurs globales, SVG | 0118, 0119, 0120, 0121, 0122, 0123, 0124, 0125, 0126, 0144, 0158 | 24 797 |
| T14 | Vectoriser | 0127, 0128, 0129, 0130, 0131, 0132, 0133, 0137 | 19 292 |
| T15 | Outils vectoriels avancés : Largeur, Peinture dynamique, 3.29.0 / 3.29.1 / 3.29.3 / 3.29.5 | 0138, 0140, 0141, 0146, 0147, 0149, 0153, 0154, 0155, 0156 | 26 379 |
| T16 | Performance vectorielle : 3.29.2, 3.29.4, 3.29.6, 4.0.0 (+ 4.1.0 : interrupteurs retirés) | 0148, 0150, 0151, 0152, 0159, 0170 | 2 045 |
| T17 | Pinceau goutte, formes de pinceau, répétitions (3.30.0) (+ 4.1.0 : chopgimp-vutil.c) | 0160, 0161 | 6 725 |
| T18 | Plans de travail et grille de perspective (3.31.0 lot 4a) | 0162, 0166, 0167, 0169 | 7 745 |
| T19 | Fichiers : PSD, PDF, SVG, Importer | 0079, 0080, 0081, 0163, 0172 | 6 629 |
| T20 | Fonctions Photoshop diverses : alignement, repères commentés, calques de réglage, actions, croquis, accueil, dialogues | 0077, 0078, 0082, 0083, 0084, 0085, 0088, 0089, 0093, 0136 | 3 517 |
| T21 | Menus, Satin / Incrustation de motif et traductions (lot 5) | 0012, 0027, 0139, 0145, 0164 | 2 186 |
| T22 | Correctifs transverses de fin de cycle (revue 3.24, compilation 3.99.0) : à répartir dans leurs thèmes | 0070, 0165 | 572 |

Total : 153 252 lignes ±, 173 patchs.

T22 n'est pas un patch final : 0070 (fin de la revue 3.24) et 0165 (correctifs de
compilation 3.99.0) touchent des fichiers de plusieurs thèmes ; leurs morceaux vont dans le
thème qui possède chaque fichier (voir la méthode). On arrive donc à **21 patchs**.

Rattachements à valider :
- 0164 (lot 5 : Satin, Incrustation de motif, menus sans doublon, icônes) est rangé en T21 ;
  sa partie Satin / Incrustation pourrait aller en T10.
- 0158 (Redéfinir les couleurs, 3.29.5) est en T13 avec les autres couleurs des objets.
- 0141 (petits défauts 3.28.2) touche aussi les effets « dessous » : la part
  `gimpdrawable-filters.c` irait en T10 si le fichier lui appartient.
- 0168 (libellés des onglets de documents) est rangé en T08 (onglets façon Photoshop).

## Méthode proposée : un propriétaire par fichier

Rejouer les 173 commits par `git rebase -i` (squash / fixup) provoquerait des conflits en
cascade : `gimpoptionsbar.c`, `chopgimp-vobject.c`, `gimplayertreeview.c`, les `meson.build`
et les `.po` sont modifiés par des dizaines de patchs de thèmes différents.

À la place, à partir de l'arbre final (branche `next-4.1` rebasée sur la 4.0.2) :

1. `git diff --stat GIMP_3_2_8 next-4.1` : liste des ~480 fichiers touchés.
2. Chaque fichier reçoit **un** thème propriétaire : celui du patch qui l'a créé (fichiers
   `chopgimp-*`), sinon celui qui le modifie le plus (calcul automatique par
   `git log --numstat`, puis relecture de la table produite, à garder dans
   `docs/dev/patchs-4.1-fichiers.tsv`).
3. Fichiers partagés par nature (`meson.build`, `po/fr.po`, `app/actions/*-actions.c`,
   `menus/*.ui`, `gimpoptionsbar.c`) : un patch du thème qui les modifie le plus ; les
   `.po` vont dans T21 (traductions) en fin de série.
4. Construction : branche `themes-4.1` depuis `GIMP_3_2_8`, puis pour chaque thème dans
   l'ordre `git checkout next-4.1 -- <ses fichiers>` et un commit ; à la fin
   `git diff themes-4.1 next-4.1` doit être **vide** (contrôle d'identité de l'arbre).
5. `make patches` réécrit en conséquence : export de la série `themes-4.1`, et non plus
   ajout incrémental (le Makefile compte aujourd'hui les commits de `photogimp`).

Points d'attention :
- **0045** (icône Windows) modifie le sous-module `gimp-data` : il ne se régénère pas depuis
  gimp-src (voir le commentaire du Makefile) ; le garder tel quel, en tête de T02.
- L'historique fin (un commit par version) est perdu dans les patchs : garder la branche
  `photogimp` et une étiquette `chopgimp-4.0.2` dans `build/gimp-src`, et `docs/SUIVI.md`
  reste la référence version par version.
- Après regroupement, un nouveau correctif = un commit sur le thème concerné
  (`git commit --fixup` puis `rebase --autosquash` sur `themes-4.1`), et le patch du thème
  est réexporté : la série reste à ~21 fichiers.
- Vérifications : arbre identique (étape 4), `make manifest`, compilation complète,
  `tools/smoke_test.py`.

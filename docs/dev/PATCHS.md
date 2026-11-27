# Organisation des patchs GIMP (depuis la 4.2.1)

Les modifications de GIMP 3.2.8 forment **23 patchs** dans `patches/gimp-3.2.8/` : 22 thèmes
et le patch de l'icône Windows, gardé tel quel. Ils remplacent les 182 patchs « un par commit »
de la 4.2.0 et de la 4.2.1 (plan appliqué : `archive/PLAN-PATCHS-4.1.md`, adapté). La série
s'applique toujours en entier et dans l'ordre. Un thème seul n'a pas à compiler.

## Les thèmes

| N° | Thème | Anciens patchs |
|---|---|---|
| 0001 | T01 Socle : identité, configuration, journal de session, rapport de plantage | 0001, 0010, 0011, 0013, 0020, 0030, 0047, 0074, 0076 (+ rapport de plantage 4.2.1) |
| 0002 | Icône Windows (ancien 0045, **tel quel**) | 0045 |
| 0003 | T02 Windows : build, installateur, instances, orthographe | 0043, 0044, 0046, 0134, 0135 |
| 0004 | T03 Gestes Photoshop des outils de base | 0002–0006, 0008, 0014, 0091, 0092, 0098–0100 |
| 0005 | T04 Barre d'options | 0009, 0018, 0019, 0021–0023, 0025, 0031, 0032, 0108, 0109, 0114, 0173 |
| 0006 | T05 Contrôles de transformation | 0016, 0017, 0035, 0036, 0040, 0075 |
| 0007 | T06 Outils raster ajoutés | 0015, 0026, 0029, 0041, 0086, 0087, 0142, 0143, 0157 |
| 0008 | T07 Panneaux, docks, vignettes de calques | 0007, 0037, 0038, 0042, 0048–0055, 0116, 0117, 0174 |
| 0009 | T08 Apparence | 0063, 0064, 0071, 0072, 0112, 0168, 0171 |
| 0010 | T09 Texte | 0065–0068, 0073, 0090 |
| 0011 | T10 Styles de calque et filtres | 0039, 0094, 0095, 0101, 0113, 0115 |
| 0012 | T11 Performance du rendu | 0096, 0097, 0102–0107, 0110, 0111 |
| 0013 | T12 lib2geom, outil Forme, Pathfinder, Concepteur de formes | 0024, 0028, 0033, 0034, 0056–0062, 0069 |
| 0014 | T13 Objets vectoriels | 0118–0126, 0144, 0158, 0178, 0179, 0181, 0182 (4.2.1) |
| 0015 | T14 Vectoriser | 0127–0133, 0137 |
| 0016 | T15 Outils vectoriels avancés | 0138, 0140, 0141, 0146, 0147, 0149, 0153–0156 |
| 0017 | T16 Performance vectorielle, allègement 4.1 | 0148, 0150–0152, 0159, 0170, 0175, 0176 |
| 0018 | T17 Pinceau goutte, formes de pinceau, répétitions | 0160, 0161, 0177 |
| 0019 | T18 Plans de travail, grille de perspective | 0162, 0166, 0167, 0169 |
| 0020 | T19 Fichiers : PSD, PDF, SVG, Importer | 0079–0081, 0163, 0172 |
| 0021 | T20 CMJN façon Photoshop | 0180 |
| 0022 | T21 Fonctions Photoshop diverses | 0077, 0078, 0082–0085, 0088, 0089, 0093, 0136 |
| 0023 | T22 Menus, Satin / Incrustation de motif, traductions | 0012, 0027, 0139, 0145, 0164 |

0070 (fin de la revue 3.24) et 0165 (correctifs de compilation 3.99.0) n'ont pas de thème :
leurs lignes sont allées au thème propriétaire de chaque fichier.

## Un fichier, un thème

Chaque fichier modifié appartient à **un seul** thème (`patchs-4.2-fichiers.tsv`, 491
fichiers). Règles, dans l'ordre :

1. les deux fichiers de l'icône Windows → le patch de l'icône ;
2. fichiers imposés (rapport de plantage : `chopgimp-crash.*`, `gimpcriticaldialog.*`) → T01 ;
3. traductions `po*/*.po` → T22 ;
4. fichier créé par la série → thème du patch qui l'a créé ;
5. sinon → thème qui l'a le plus modifié (lignes ajoutées et retirées).

## Branches de `build/gimp-src`

- `photogimp-v2` : la série thématique (23 commits sur `GIMP_3_2_8`), d'où `make patches`
  exporte ;
- `photogimp-legacy` : l'ancienne branche (un commit par patch, jusqu'à la 4.2.1). L'ancienne
  série reste aussi dans les étiquettes `v4.2.0` et antérieures du projet.

Contrôle d'identité à la construction : `git diff photogimp-v2 photogimp-legacy` est vide, et
les deux branches ont le même arbre (`git rev-parse <branche>^{tree}`).

## Faire une modification

1. Dans `build/gimp-src`, sur `photogimp-v2` : modifier, puis
   `git commit --fixup=<commit du thème>` (voir `git log --oneline GIMP_3_2_8..`) ;
2. `git rebase -i --autosquash GIMP_3_2_8` ;
3. `make patches` : réexporte toute la série (`--zero-commit` : seuls les patchs modifiés
   changent) et remet le patch de l'icône Windows tel quel ;
4. `make manifest`, compilation, `tools/dev/smoke.sh`.

Un fichier nouveau va dans le thème de la fonction. Si une modification touche plusieurs
thèmes, un fixup par thème.

`tools/dev/regroup_patches.py` refait le regroupement à partir d'une branche « un commit par
patch » (`--source`, par défaut `photogimp-legacy`) et vérifie l'identité des arbres.

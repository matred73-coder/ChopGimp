# Vectoriel rapide — mesures et suite (3.29.2)

Banc : `tools/dev/bench_vector.sh` (gimp-console, PDB). Cas A : image 2000 × 2000
vectorisée en « Photo haute fidélité » (3 595 objets, 4,3 Mo de XML). Cas B :
2 000 triangles dans un calque. Temps en ms (meilleur de quelques essais).

| Mesure | A avant (3.29.1) | A après | B avant | B après |
|---|---|---|---|---|
| Ouverture du XCF | 22 458 | **1 016 – 1 347** | 5 807 | **270 – 357** |
| Glisser, par image (drag-sim) | — | 286 – 344 | — | **0,5 – 0,9** |
| Déplacement non interactif | 492 | 345 – 392 | 23 | 16 – 20 |
| Annuler / rétablir | (XML : écrire + relire) | 335 – 479 | — | 150 – 196 |
| Rendu complet | 1 135 | 917 – 1 067 | 325 | 286 – 295 |
| Recolorer tout | 699 | 678 | 279 | 214 – 242 |
| Clic (sélection) | 3,1 | 2,7 – 3,0 | 0,2 | 0,2 |

## Fait en 3.29.2
- **Ouverture XCF ×17 à ×22** : GIMP redessinait d'abord tout l'ancien tracé
  (un seul tracé géant, fond + contour, ~90 % du temps) avant le rendu par objets.
  Sauté quand le calque a ses objets (`CHOPGIMP_NO_FAST_LOAD=1` pour revenir).
- **Glisser interactif** (`chopgimp_vlayer_begin/end_interactive`, outil V) :
  les rendus en cache et les boîtes se décalent au lieu d'être recalculés ;
  pas d'ancien tracé réécrit, pas de réindexation, panneaux prévenus une fois à
  la fin ; rendu exact au relâchement (seuls les objets décalés d'une fraction
  de pixel sont redessinés). « Sprite » : reste du calque et objets déplacés
  faits une fois, chaque image ne fait que copier / coller
  (`CHOPGIMP_NO_FAST_DRAG=1`, `CHOPGIMP_NO_DRAG_SPRITE=1`).
- **Calque qui s'agrandit** : les pixels inchangés sont recopiés, seule la zone
  touchée est redessinée ; marge d'agrandissement pendant un glisser.
- **Annulation** : copie de l'arbre d'objets (mêmes ids, rendus en cache
  partagés) au lieu d'écrire puis relire tout le XML ; rétablir = échange
  (`CHOPGIMP_NO_FAST_UNDO=1`).
- Rendu identique au pixel près vérifié par 4 tests (glisser, annuler,
  rétablir, XCF rouvert).

## Reste (par impact)
1. **Conversion de pixels** (cause n° 1 du glisser lourd, mesurée à l'échantillonneur) :
   `gegl_buffer_set` de cairo-ARGB32 vers le format du calque passe par la
   conversion de **référence** de babl (gamma par pixel). Ajouter une conversion
   directe (patch babl, comme ceux de la 3.25.1) ou rendre dans le format natif :
   gain attendu ×10 sur le glisser et le rendu complet.
2. Recoloration et rendu complet : rasteriser les objets en parallèle (fils).
3. Annulation : n'enregistrer que les objets modifiés (au lieu de tout l'arbre),
   et ancien tracé réécrit paresseusement.
4. Mesure au banc graphique (temps par image réel, liste Objets, repères).

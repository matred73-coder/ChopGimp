# Vectoriel rapide — mesures et suite (3.29.2, 3.29.4, 3.29.6)

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
  Sauté quand le calque a ses objets (`CHOPGIMP_NO_FAST_LOAD=1`, retiré en 4.1.0).
- **Glisser interactif** (`chopgimp_vlayer_begin/end_interactive`, outil V) :
  les rendus en cache et les boîtes se décalent au lieu d'être recalculés ;
  pas d'ancien tracé réécrit, pas de réindexation, panneaux prévenus une fois à
  la fin ; rendu exact au relâchement (seuls les objets décalés d'une fraction
  de pixel sont redessinés). « Sprite » : reste du calque et objets déplacés
  faits une fois, chaque image ne fait que copier / coller
  (`CHOPGIMP_NO_FAST_DRAG=1`, `CHOPGIMP_NO_DRAG_SPRITE=1`, retirés en 4.1.0).
- **Calque qui s'agrandit** : les pixels inchangés sont recopiés, seule la zone
  touchée est redessinée ; marge d'agrandissement pendant un glisser.
- **Annulation** : copie de l'arbre d'objets (mêmes ids, rendus en cache
  partagés) au lieu d'écrire puis relire tout le XML ; rétablir = échange
  (`CHOPGIMP_NO_FAST_UNDO=1`, retiré en 4.1.0).
- Rendu identique au pixel près vérifié par 4 tests (glisser, annuler,
  rétablir, XCF rouvert).

## Fait en 3.29.4
Cas A : glisser **373,5 → 13,7 ms** par image (sous les 33 ms d'une image à
30 i/s), recolorer 799 → 266, rendu complet 1 197 → 648, annuler 383 → 136.
Cas B : recolorer 414 → 60, rendu complet 582 → 159 (« avant » = mêmes binaires,
`CHOPGIMP_NO_FAST_BABL=1 CHOPGIMP_NO_PAR_RENDER=1`, interrupteurs retirés en 4.1.0 ; tableau complet : SUIVI 3.29.4).
- **Conversion de pixels** : dépremultiplication maison (table, en parallèle)
  vers R'G'B'A u8, **calques 8 bits seulement** ; 16 / 32 bits : babl comme avant.
- **Rastérisation en parallèle** des objets sans cache (fils de GEGL).

## Fait en 3.29.6 (non compilé, mesures au lot 6)
- **Calques 16 / 32 bits** : dépremultiplication en R'G'B'A flottant, en
  parallèle, puis chemins rapides de babl (`CHOPGIMP_NO_FAST_FLOAT=1`).
- **Rastérisation parallèle étendue** à tous les objets : filets, dégradés
  libres, motifs, flèches, dégradés de contour, profils de largeur (contours
  des profils et cellules des motifs préparés sur le fil principal ;
  `CHOPGIMP_NO_PAR_RENDER_EXT=1`).
- **Annulation partielle** : seules les feuilles changées sont copiées ; les
  autres sont partagées entre instantanés et échangées à l'annulation
  (`CHOPGIMP_NO_PARTIAL_UNDO=1`). Ancien tracé réécrit paresseusement après
  annuler / rétablir (`CHOPGIMP_NO_LAZY_LEGACY=1`).

## Reste
- Mesure au banc graphique (temps par image réel, liste Objets, repères) et
  test de charge de la rastérisation parallèle : lot 6.

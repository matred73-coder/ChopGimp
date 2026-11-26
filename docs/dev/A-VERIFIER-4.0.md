# Points à vérifier à la compilation de la 4.0.0 (lot 6)

## Lot 1 (3.29.5, commit 5ced593, patchs 0153-0158)
- Outil Dégradé sur calque vectoriel (dégradé libre) : initialisation, « preserve » pendant le glisser, dessin des points.
- Banc graphique : poignées d'angles en Sélection directe (A), nouveau sous-tracé en sélection multi-objets, lasso magnétique rapide.
- Temps du test Peinture dynamique incrémentale ; bench_vector.sh sans régression.
- Mises en page Redéfinir / groupe du panneau Aspect (jamais vues à l'écran).

## Lot 2 (3.29.6, patch 0159)
- Compilation de l'ensemble (`chopgimp-vobject.c`, `chopgimp-vmaterial.c/.h`, champ `rev` ajouté à `ChopGimpVObject`).
- Annulation partielle : l'invariant « tout changement d'une feuille passe par `vobj_drop_cache` / `vobj_shift` » (qui changent la révision). Une modification en place sans invalidation (nom, verrou… sont comparés ; tracé et style ne le sont que par la révision) donnerait une feuille partagée fausse → tester `CHOPGIMP_NO_PARTIAL_UNDO=1` en cas de doute ; vérifier renommer / verrouiller / symboles / peinture dynamique / transitions puis annuler.
- Annulation partielle : un objet tenu par un panneau ou un outil pendant annuler / rétablir (référence en plus) ; mémoire d'annulation affichée.
- Ancien tracé paresseux : un groupe d'annulation qui restaure aussi le tracé du calque (options) — ordre d'écriture ; transformer le calque, outil Chemins sur le tracé du calque, script qui annule puis lit le tracé.
- Rastérisation parallèle étendue : test de charge (TSan ou boucle de rendus de motifs vectoriels imbriqués, profils, flèches) ; `gimp_stroke_interpolate` et `gegl_color_get_pixel` sur des objets partagés depuis plusieurs fils ; motif bitmap (`gimp_temp_buf_create_buffer`) depuis les fils.
- 16 / 32 bits : écart ≤ 1 avec le 8 bits sur les bords semi-transparents ; calques linéaires et en demi-flottant ; mémoire du tampon flottant (bande de 4 Mpx = 64 Mo).

## Lot 3 (3.30.0, patchs 0160 et 0161)
- Compilation : `chopgimp-vrepeat.c/.h`, `chopgimp-vbrush.c/.h` (app/path), `chopgimp-blobtool.c/.h` (app/tools), dialogues dans `chopgimp-material-dialogs.c`, actions `layers-vobjects-repeat-*` / `-brush-*`, commandes PDB.
- Champ `blend` réutilisé pour toutes les specs dynamiques (« repeat … » / « rinst », « brush … » / « bpart ») : vérifier qu'aucun code de la Transition ne prend une répétition ou une forme pour une transition (préfixes) ; annuler / rétablir et annulation partielle (clé de forme remplacée par une copie quand son contour réapparaît).
- Hook des objets : formes puis répétitions rafraîchies après les transitions ; une forme dans la source d'une répétition, une répétition imbriquée ; coût de la signature (XML de la source) à chaque changement sur de gros calques.
- `hit_rec` : les parties verrouillées « bpart » / « rinst » sont touchées ; vérifier Déplacement, rectangle de sélection, outil Objets entré dans le groupe (une partie verrouillée ne doit pas être déplacée seule), Sélection directe redirigée vers le tracé.
- Calligraphique : contour rond de lib2geom dans l'espace de la plume (arrondi 1 % = plume très plate) ; Art / Motif : courbes réajustées (tolérance 0,15 px), angles vifs du tracé (normales moyennées), tracés fermés.
- Pinceau goutte : aperçu rempli recalculé à chaque mouvement (fluidité au-delà de quelques centaines de points), couleur du contour des options (fond sans contour) — non testable par la PDB, à voir au banc graphique ; nouveau calque : style posé sur l'objet n° 1 (le calque n'est plus « legacy ») ; fusion d'objets dans des groupes différents, objets à effets vivants non fusionnés.
- Options : barre d'options (`blob-size`, `@fill-opacity` sur les options du Pinceau goutte) ; icônes `chopgimp-tool-vblob`, `chopgimp-repeat-*` (générées par `icons/build_icons.py`).
- Menus (build_menus.py) : nouvelle section Répétition / Formes de pinceau du menu Vecteur, mnémoniques en double éventuels.
- Tests smoke 3.30.0 : positions des pixels (instance radiale à (200,180), plume de 20 px), couleur de fond du calque de test pour le Pinceau goutte.
- Patch 0161 : compilation de `chopgimp-brushes-panel.c` (app/dialogs), des API ajoutées à `chopgimp-vbrush.c/.h` (bibliothèque, tuiles, variations) et `chopgimp-vrepeat.c/.h` (poignées), de `chopgimp-material-dialogs.h` qui inclut maintenant `path/chopgimp-vbrush.h`.
- Calligraphique « Pression » : la pression est-elle gardée dans les points des tracés (Crayon vectoriel, Plume, import SVG la perdent sans doute : valeur par défaut 1 = base + variation) ; enveloppe des plumes sur les virages serrés (auto-intersections de la bande, union avec les bouts) ; tracés fermés (deux anneaux, règle non nulle).
- Motif : détection des angles (virage > 30° entre deux points de l'interpolation à 0,25 px), orientation extérieur / intérieur selon le sens du tracé et « retourner », tuile d'angle centrée sur le sommet (Illustrator la cale sur les côtés), tracés fermés avec angles (pièces sur la boucle), début / fin plus longs que le tracé.
- Panneau Formes : fusion de la bibliothèque de l'image à son affichage seulement (une image ouverte panneau fermé n'enrichit la bibliothèque qu'à son prochain affichage) ; fichier `chopgimp-brushes` écrit à chaque changement ; aperçus (illustration ou plume) ; « Modifier » met à jour les tracés de l'image active seulement ; les tracés gardent leur spec quand la forme est supprimée.
- Poignées des répétitions (outil Déplacement) : priorité sur les poignées du cadre et les angles dynamiques, rayon (la source est déplacée, le centre reste), nombre d'instances (angle vers la 2e instance), colonnes / rangées (coin bas droit), axe du miroir (déplacer, tourner) ; groupe transformé (matrice monde) ; annuler pendant le glisser (Échap).

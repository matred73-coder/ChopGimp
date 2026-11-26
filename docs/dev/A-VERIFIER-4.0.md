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

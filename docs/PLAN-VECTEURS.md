# ChopGimp — vrais objets vectoriels et Vectoriser (3.27.x)

> **Action à la validation de ce plan (demande du 2026-11-19 : « sauve tout ça en MD »)** : copier ce fichier dans le projet, `/home/dsi/DOCKER/photogimp-pro/docs/PLAN-VECTEURS.md`, le commiter et le pousser. **Ne rien coder ni compiler** : l'utilisateur a choisi « Plus tard » pour ce chantier.
>
> **En attente, à reprendre sur demande :**
> - **3.26.1, écrite mais non compilée** (commits dans `build/gimp-src` : 7f2bb25, f12846d, 1a16451, 190c14f, 31a226f, 9cf1b46, 3bcdab3 ; patch GEGL 0007 ; CSS et greffons non commités) :
>   - cache des effets qui survit aux mises à jour ;
>   - « Aide » et unités ;
>   - rendu en arrière-plan allégé ;
>   - curseurs façon Photoshop ;
>   - mode de fusion de l'ombre portée et de la lueur externe ;
>   - fenêtres de filtres et Style de calque unifié ;
>   - panneaux modernisés ;
>   - finitions.
> - **Compilation optimisée de GIMP (LTO et PGO)** : `make build LTO=all PGO=1`, environ 1 h, à lancer quand la machine est libre.
> - **Windows** : compilation automatique sur GitHub ou guide mis à jour (choix de l'utilisateur en attente).
> - **Modernisation restante** : boîte à outils et icônes, barre d'état, onglets, accueil, styles d'interface (lots D, E, F de l'ancien plan).
> - **Pipette sur le calque avec effets** : à faire seulement si l'utilisateur le veut.

## Contexte

L'utilisateur trouve la gestion vectorielle poussive :
- dans un calque vectoriel, on ne peut pas déplacer, recolorer ou modifier le contour d'un élément séparément ;
- les outils sont pauvres comparés à Illustrator ou Inkscape ;
- il manque **Vectoriser**, la Vectorisation dynamique d'Illustrator.

**Ses choix :**
- **tout dans ChopGimp**, sans aller-retour avec Inkscape ;
- Vectoriser avec **toutes les options d'Illustrator**.

**Ce que le code montre** (exploration) :
- un `GimpVectorLayer` = **un seul `GimpPath`** (plusieurs sous-tracés), avec **un seul fond et un seul contour** (`app/path/gimpvectorlayeroptions.c`) ;
- les sous-tracés n'ont ni nom, ni couleur, ni position propres ;
- l'import PDF/AI/SVG (`plug-ins/chopgimp_pdf/chopgimp_pdf.py`, `merge_runs`) et les opérations booléennes **regroupent** volontairement les objets dans un seul calque ;
- le rendu passe par `gimp_drawable_fill_path` / `gimp_drawable_stroke_path` (`GimpScanConvert`, cairo) et redessine tout le calque ;
- **aucune vectorisation d'image** n'existe. Les sources d'Inkscape sont présentes dans `build/inkscape/src/trace/` (potrace, autotrace, depixelize), mais libpotrace n'est pas dans le paquet.

**Briques réutilisables :**
- `app/path/chopgimp-geom.cc` (lib2geom : booléens, contours, décalage, simplification, effets vivants) ;
- les outils Forme, Bâtisseur de formes et Sélection directe (`app/tools/chopgimp-shapetool.c`, `chopgimp-shapebuildertool.c`) ;
- le greffon `chopgimp_vector` (Pathfinder, Nœuds, Effets vivants) ;
- `GimpFillOptions` et `GimpStrokeOptions` ;
- la propriété XCF `PROP_VECTOR_LAYER`.

**Règle :** améliorer l'existant plutôt que créer un mécanisme parallèle. Le calque vectoriel de GIMP **devient** multi-objets ; les anciens calques sont lus comme un calque à un seul objet.

## Lot V1 — Modèle multi-objets (3.27.0)

- **`GimpVectorLayer` contient une liste d'objets**, dans de nouveaux fichiers `app/path/chopgimp-vobject.c/.h`. Chaque objet porte :
  - un nom ;
  - son tracé (lib2geom `PathVector`, sérialisé en données de chemin SVG) ;
  - un fond : aucun, couleur, dégradé linéaire ou radial, motif ;
  - un contour : couleur, épaisseur, alignement intérieur/centre/extérieur, tirets, extrémités, jointures ;
  - une opacité, un mode de fusion, une transformation (matrice), un état visible et un état verrouillé ;
  - des **groupes d'objets** imbriqués.
- **Rendu cairo direct** des objets dans le tampon du calque, avec un cache par objet et un redessin limité à la zone modifiée. Les effets vivants (`chopgimp-lpe`) s'appliquent par objet.
- **Enregistrement :** les objets sont stockés dans le XCF sous forme de parasite `chopgimp-vobjects` (XML type SVG). Un GIMP standard voit le calque rendu en pixels, et rien ne se perd. Les anciens fichiers s'ouvrent à l'identique : le tracé, le fond et le contour actuels deviennent l'objet n° 1.
- **Commandes :**
  - « Fusionner en un calque vectoriel » : plusieurs calques vectoriels deviennent les objets d'un seul calque ;
  - « Dissocier » : chaque objet devient son propre calque ;
  - « Décomposer les sous-tracés en objets » : rend éditables un par un les fichiers importés et les résultats booléens existants.
- Une étape d'annulation par action sur les objets.

## Lot V2 — Outils façon Illustrator (3.27.0)

- **Sélection (V) en mode objets** sur un calque vectoriel :
  - clic sur un objet, Maj+clic pour en ajouter, rectangle de sélection ;
  - cadre de transformation pour déplacer, redimensionner (Maj : proportions) et faire pivoter ;
  - Alt+glisser duplique ;
  - double-clic pour entrer dans un groupe, Échap pour en sortir.
- **Sélection directe (A)** : modifie les nœuds de l'objet cliqué seulement.
- **Les outils Forme, Plume, Crayon et Texte vectorisé** ajoutent un objet au calque vectoriel actif, au lieu de créer un nouveau calque (option dans la barre d'options).
- **Bâtisseur de formes et Pathfinder** travaillent sur les objets sélectionnés du calque.
- **Commandes Objet**, dans un nouveau menu Objet de premier niveau ajouté (les menus existants ne sont pas renommés) :
  - Grouper / Dissocier (Ctrl+G / Maj+Ctrl+G) ;
  - Premier plan / Arrière-plan / Avancer / Reculer (Ctrl+] [) ;
  - Verrouiller / Masquer ;
  - Aligner et répartir sur la sélection ou le calque ;
  - Masque d'écrêtage ;
  - Pipette de style : copier fond et contour d'un objet à l'autre.
- **Barre d'options en mode objet :** fond, contour, épaisseur, opacité, X/Y/L/H, rotation — avec les champs compacts de la 3.26.

## Lot V3 — Panneaux (3.27.1)

- **Objets dans le panneau Calques** : les objets du calque vectoriel actif s'affichent dépliables sous le calque, avec œil, verrou, renommage, réorganisation par glisser et groupes. C'est le même principe que la bande fx de la 3.26.1.
- **Panneau Aspect** (fond et contour de l'objet) : couleur, dégradé (outil Dégradé applicable sur l'objet, avec poignées sur le canevas), motif, opacité.
- **Panneau Contour** : épaisseur, alignement, tirets, extrémités et jointures, profils de largeur (réutilise `taper` et `powerstroke`).

## Lot V4 — Import et export avec objets (3.27.1)

- **Import PDF, AI, SVG et EPS** (`chopgimp_pdf.py`) : un objet par élément, au lieu de `merge_runs`. Les groupes SVG et PDF sont conservés, de même que les masques d'écrêtage et les dégradés vectoriels. Il n'y a plus de plafond à 1 500 objets, puisque tout reste dans un seul calque.
- **Export SVG** : un `<path>` par objet, des `<g>` pour les groupes, les dégradés, les noms.

## Lot V5 — Vectoriser (Vectorisation dynamique) (3.27.2)

- **Moteurs :**
  - **potrace** : libpotrace ajouté au paquet via `tools/make_manifest.py`. Il prend en charge le noir et blanc, et la couleur ou les gris par passes multiples, en reprenant la logique d'Inkscape (`build/inkscape/src/trace/potrace/`) ;
  - **autotrace** pour le **tracé central** des croquis et dessins au trait (`build/inkscape/src/3rdparty/autotrace`) ;
  - **depixelize** pour le pixel art.
- **Commande :** Calque > **Vectoriser…**, avec un aperçu en direct sur le canevas. Vues : résultat, contours, contours + source.
- **Préréglages Illustrator :**
  - Photo haute fidélité, Photo basse fidélité ;
  - 3 couleurs, 6 couleurs, 16 couleurs ;
  - Nuances de gris ;
  - Logo noir et blanc ;
  - Croquis, Silhouettes, Dessin au trait, Dessin technique.
- **Options avancées comme Illustrator :**
  - mode : couleur, gris, noir et blanc ;
  - palette : automatique, limitée, ou issue du nuancier ;
  - nombre de couleurs, seuil, précision des chemins, angles, bruit (pixels ignorés) ;
  - méthode : adjacent ou superposé ;
  - remplissages et/ou contours, avec l'épaisseur maximale du trait ;
  - arrondir les courbes en lignes droites ;
  - ignorer le blanc.
- **Résultat :** un **calque vectoriel multi-objets** (lot V1), un objet par zone de couleur. Chaque objet se modifie ensuite séparément, ce qui équivaut au « Décomposer » d'Illustrator.
- **Grandes images :** le calcul se fait dans un fil séparé, avec une barre de progression et un bouton d'annulation.

## Lot V6 — Ajouts validés par l'utilisateur (le 2026-11-19)

1. **Repères commentés et magnétisme** (en V2) :
   - pendant un déplacement ou une transformation, l'objet s'aimante aux bords, aux centres et aux nœuds des autres objets et au document, avec les distances et les alignements affichés en surimpression ;
   - option « Aligner sur la grille de pixels ».
   - **Réutilise** les guides intelligents de la 3.21.0 (outil Déplacement), étendus aux objets.
2. **Couleurs globales et « Redéfinir les couleurs »** (en V3) :
   - **couleurs globales** : une nuance du nuancier marquée « globale » est référencée par les objets, et la modifier met à jour tous ces objets ;
   - **Redéfinir les couleurs** : fenêtre qui liste les couleurs du dessin ou de la sélection ; on les remplace, on applique une harmonie (roue de la 3.22.0) ou on réduit le nombre de couleurs.
3. **Aspect** (en V3) : plusieurs fonds et contours par objet, empilés, chacun avec son opacité et son mode. Le panneau Aspect affiche la pile, avec réorganisation et masquage.
4. **Vectorisation modifiable** (en V5) :
   - le résultat est un « objet vectorisé » qui garde l'image source et les réglages, et se réajuste plus tard en rouvrant le panneau ;
   - « Décomposer » le fige en objets normaux ;
   - on peut vectoriser la **sélection** seulement.
5. **Outil Largeur** (Maj+W) : sur un contour, on tire des poignées pour faire varier l'épaisseur. Profils de largeur réutilisables. Repose sur `powerstroke` de `chopgimp-geom.cc`.
6. **Peinture dynamique** : on convertit des objets en groupe de peinture dynamique, puis on colorie au pot de peinture les zones formées par les traits qui se croisent, sans opération booléenne. Les zones restent dynamiques quand on déplace un trait. Repose sur `chopgimp_geom_divide`. « Décomposer » donne des objets normaux.
7. **Symboles** : panneau Symboles. Un objet ou un groupe devient un symbole ; ses occurrences sont placées et transformées une à une. Modifier le symbole met à jour toutes les occurrences ; « Rompre le lien » rend une occurrence indépendante.
8. **Distorsion d'objets** : Enveloppe (maillage ou forme), Distorsion libre (4 coins), Déformation (préréglages arc, drapeau, onde…) sur l'objet sélectionné, modifiables tant qu'on n'a pas décomposé. Reprend les effets vivants `envelope` et `bend`.

**Ordre mis à jour :**
- **3.27.0** : V1, V2 et le repère / magnétisme ;
- **3.27.1** : V3, V4, les couleurs globales, Redéfinir et l'Aspect ;
- **3.27.2** : V5 et la vectorisation modifiable ;
- **3.27.3** : outil Largeur, Peinture dynamique, Symboles, Distorsion.

**Estimation totale :** environ 7 à 10 jours de travail, livrés version par version.

## Fichiers principaux

- **Modèle :** `app/path/gimpvectorlayer.c`, `gimpvectorlayeroptions.c`, nouveau `app/path/chopgimp-vobject.c`, `app/path/chopgimp-geom.cc`.
- **Enregistrement :** `app/xcf/xcf-save.c` / `xcf-load.c` (parasite).
- **Outils :** `app/tools/chopgimp-shapetool.c`, `chopgimp-shapebuildertool.c`, `gimppathtool.c`, `gimpmovetool.c`, plus un nouvel outil de sélection d'objets.
- **Actions et menus :** `app/actions/` (objets), `tools/build_menus.py`.
- **Interface :** `app/widgets/gimplayertreeview.c` (objets), `app/display/gimpoptionsbar.c`.
- **Greffons :** `plug-ins/chopgimp_vector/`, `plug-ins/chopgimp_pdf/chopgimp_pdf.py`, `build/gimp-src/plug-ins/common/file-svg.c`.
- **Vectoriser :** moteur dans GIMP, `app/path/chopgimp-trace.cc` (potrace, et autotrace / depixelize embarqués dans `app/path/trace/`), calque de vectorisation `app/core/chopgimp-trace-layer.c`, et le module potrace dans `tools/make_manifest.py`.

## Vérification

- **Banc graphique** (`tools/gui-test/guitest.sh`), captures relues :
  - créer 3 formes dans un calque, puis sélectionner, déplacer, recolorer et changer le contour de **chacune** ;
  - grouper, dissocier, changer l'ordre ;
  - annuler et rétablir ;
  - enregistrer en XCF puis rouvrir ;
  - ouvrir le XCF dans un GIMP standard : on y voit les pixels.
- **Anciens XCF avec calques vectoriels :** rendu identique, au pixel près.
- **Import :** un SVG et un PDF de test donnent un objet par élément, avec les groupes conservés.
- **Vectoriser :** chaque préréglage sur une photo, un logo et un croquis. Les objets doivent être modifiables, et l'annulation possible pendant le calcul.
- **Tests :** les 103 tests, plus de nouveaux tests dans `tools/dev/smoke.sh` (objets, XCF, vectorisation), et `bench-all.sh` pour vérifier que la fluidité n'a pas régressé.
- **Livraison par version :** VERSION incrémentée, commit avec l'identité ChopGimp, tag, push, SUIVI à jour, liste explicite de ce qui est fait et pas fait.

## Ordre et estimation

- La 3.26.1, déjà écrite, est à compiler et tester **avant** ce chantier.
- **V1 + V2** (3.27.0) : environ 2 à 3 jours. C'est le cœur : les objets indépendants.
- **V3 + V4** (3.27.1) : environ 1 à 2 jours.
- **V5** (3.27.2) : environ 1 à 2 jours.
- Chaque version a ses interrupteurs pour revenir en arrière.

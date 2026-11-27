# ChopGimp — plan final jusqu'à la 4.0.0 (validé le 2026-11-26)

Exécution d'une traite, lot après lot, sans arrêt entre les lots.

## Règles
- Un lot **ferme tout son domaine**, y compris les « Limites » connues du SUIVI. Une limite gardée n'est permise que si elle est techniquement impossible ; elle est alors notée « acceptée » dans le SUIVI, et on n'y revient plus.
- La recette se fait sur des cas réels : vraie vectorisation lourde, gros fichiers, calques 16/32 bits.
- Pas de nouveauté hors plan. Une idée nouvelle va dans le lot suivant.
- Chaque version : VERSION bumpée, SUIVI et README mis à jour, tests verts, commit, tag, push, installation. Chaque nouveauté a son interrupteur `CHOPGIMP_*`.

## Lot 0 — Installateur Windows (CI)
`.github/workflows/windows.yml` : corriger l'échec à l'étape d'installation de `2_build-gimp-msys2.ps1`. Le `.exe` doit sortir dans les Releases, à côté du Flatpak qui fonctionne depuis la v3.29.3.

## Lot 1 — 3.29.5 : finitions vectorielles
- **Angles dynamiques** : visibles en Sélection directe (A) ; leur rayon dans la barre d'options.
- **Plume** : une seule annulation par nouvel objet ; un sous-tracé dessiné pendant une sélection de plusieurs objets est gardé.
- **Objets** :
  - redimensionner sans changer l'épaisseur du contour (option) ;
  - la sélection d'objets est enregistrée dans le XCF ;
  - « Aligner sur l'objet clé » se comporte de façon cohérente quand il n'y a pas d'objet clé.
- **Transition** :
  - un groupe peut servir d'objet clé ;
  - « orienter le long du tracé » fait tourner les étapes ;
  - le tracé de base déplace les objets clés.
- **Dégradés** :
  - dégradé libre modifiable à l'outil Dégradé, avec un mode Lignes ;
  - dégradé en travers d'un contour à profil : il suit l'épaisseur locale.
- **Symboles** : glisser-déposer d'un symbole vers le canevas ; deux occurrences placées au même endroit ne se superposent plus.
- **Peinture dynamique** :
  - le double-clic sélectionne les zones voisines de même couleur ;
  - recalcul incrémental quand il y a beaucoup de tracés ;
  - Ajouter au groupe accepte des objets d'autres niveaux.
- **Couleurs** :
  - glisser une couleur globale sur le canevas ;
  - réordonner les couleurs ;
  - mise en page du panneau Aspect et de la fenêtre Redéfinir.
- **Vectorisation dynamique** : elle suit la mise à l'échelle de l'image.
- **Lasso magnétique** : quand la souris saute de plus de 100 px, il ne pose plus de points hors du bord.

## Lot 2 — 3.29.6 : performance complète (voir docs/PLAN-PERF-VECTEUR.md, « Reste »)
- **Calques 16/32 bits** : une conversion rapide en flottant.
- **Rastérisation parallèle étendue** aux filets, dégradés libres, motifs, flèches et contours variables.
- **Annulation partielle** : seuls les objets modifiés sont enregistrés. `get_xml` coûte environ 150 ms ; ce coût disparaît.
- **Contrôles** : test de charge de la rastérisation parallèle, et mesures au banc graphique.

## Lot 3 — 3.30.0 : blocs vectoriels 4 et 5
- **Pinceau goutte** : chaque coup devient une forme remplie, fusionnée avec les formes de même couleur.
- **Formes de pinceaux** : calligraphique, Art, Motif, Dispersion.
- **Répétitions** radiales, en grille et en miroir, qui restent modifiables.

## Lot 4 — 3.31.0 : bloc vectoriel 6
- **Plans de travail** : plusieurs pages ou formats par fichier, avec un export par plan.
- **Export PDF et EPS vectoriels.**
- **Grille de perspective** à laquelle les formes s'accrochent.
- **Export PSD façon Photoshop**, ajouté le 2026-11-26 à la demande de l'utilisateur :
  - calques, groupes, masques, modes de fusion et opacités ;
  - **effets de calque convertis en styles Photoshop** (descripteurs lfx2) : ombre portée, ombre interne, lueurs, biseau, contour, incrustations couleur, dégradé et motif, satin. Un effet sans équivalent est pixellisé dans un calque séparé et signalé dans un rapport ;
  - calques vectoriels → **calques de forme** (masque vectoriel et fond), à défaut des pixels plus un masque vectoriel ;
  - calques texte → **texte modifiable** (TySh) ;
  - ré-import dans ChopGimp sans perte ; à vérifier dans un lecteur PSD de référence.
- **Export PDF en calques** : calques PDF (OCG) visibles dans Acrobat et Illustrator, avec le vectoriel conservé ; les effets sans équivalent PDF sont pixellisés par calque.

## Lot 5 — 3.32.0 : interface
- **Lots D, E et F** : icônes de la boîte à outils, barre d'état, onglets, styles d'interface.
- **Restes à corriger** :
  - sous-menu Calque > Texte en double ;
  - onglet Accueil encore en anglais ;
  - raccourci L, qui doit activer l'outil affiché du groupe ;
  - profil de largeur relégué dans « ⋯ ».
- **Menus façon Photoshop** : Fichier, Édition, Sélection, Affichage, Fenêtres, Aide.

## Lot 6 — 4.0.0 : version finale (fait : 3.99.0 puis 4.0.0, voir SUIVI)
- **Compilation** : LTO + PGO (`make build LTO=all PGO=1`).
- **Recette complète au banc graphique** : chaque outil et chaque menu, sur des scénarios réels.
- **Nettoyage** : code mort ; interrupteurs `CHOPGIMP_*` documentés.
- **Documentation** : README, guide utilisateur, notes de version 4.0.

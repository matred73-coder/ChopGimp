# ChopGimp

**ChopGimp est GIMP 3.2.8 recompilé pour se manier comme Photoshop et Illustrator** :
gestes, raccourcis, barre d'options, styles de calque, objets vectoriels,
vectorisation, import/export PSD, PDF, AI et SVG. L'interface est en français.

Il ne s'agit pas d'un simple thème ni d'un pack de raccourcis. Le code de GIMP est
modifié par une série de patchs (voir [Ce qui a changé](#ce-qui-a-changé-par-rapport-à-gimp-328)),
complétée par des greffons, des thèmes et des données propres à ChopGimp. Le
logiciel reste libre (GPL-3.0-ou-ultérieure) et lit et écrit toujours le XCF : un
fichier ChopGimp s'ouvre dans un GIMP standard, qui y voit les pixels rendus.

- **Linux** : Flatpak `org.cen_na.ChopGimp`, installé à côté d'un GIMP existant,
  avec une configuration séparée (`~/.var/app/org.cen_na.ChopGimp/`).
- **Windows** : installateur Inno Setup ou version portable (zip).
- **Version actuelle** : 4.2.10 (Barbouillage : Flux progressif, Peinture au doigt ; Filet : sélection de points, la couleur de premier plan colore les points sélectionnés), sur la 4.2.9 (Sélection directe : un clic sur une autre forme la sélectionne, glisser une forme la déplace, flèches), sur la 4.2.8 (logo loup et lune aussi dans la fenêtre vide), sur la 4.2.7 (plus de traits gris avec l'aperçu rapide sur un calque à effets, icône loup et lune), sur la 4.2.6 (plus de traits gris en peignant sur un calque à effets, nettoyage et optimisations), sur la 4.2.5 (« Sélecteur de couleur… » de la barre d'options réparé), sur la 4.2.4 (nouvelle icône tête de loup, écran de démarrage avec numéro de version), sur la 4.2.3 (bouton Enregistrer en quittant, boutons Enregistrer / Ne pas enregistrer / Annuler), sur la 4.2.2 (menus sans décalage au survol, groupes d'outils plus réactifs) et la 4.2.1 (coller un SVG d'Inkscape ou d'Illustrator en objets, rapport de plantage enregistré, patchs regroupés en 23 thèmes), sur la 4.2.0 : CMJN façon Photoshop (Image > Mode > CMJN, profils ECI, conversion de profil, Exporter pour l'imprimeur en PDF/X ou TIFF CMJN) et finitions vectorielles (« mixte » dans Aspect / Contour, copier-coller d'objets, Lasso direct) (voir [`VERSION`](VERSION)).
  Le journal détaillé est dans [`docs/SUIVI.md`](docs/SUIVI.md).
- **Prise en main** : le [guide de l'utilisateur](docs/GUIDE.md), rangé par tâche
  (vectoriser, objets, exports, raccourcis).

---

## Installer

Les paquets de chaque version sont dans les
[**Releases GitHub**](https://github.com/matred73-coder/ChopGimp/releases) :

| Fichier | Système | Installation |
|---|---|---|
| `ChopGimp-<version>.flatpak` | Linux | `flatpak install --user ChopGimp-<version>.flatpak` (l'environnement GNOME 51 vient de Flathub) |
| `chopgimp-<version>-setup.exe` | Windows 10/11 | Double-clic |
| `ChopGimp-<version>-portable.zip` | Windows | À décompresser, sans installation |

Ils sont produits automatiquement par GitHub Actions à chaque tag `v*`
([`docs/CI-WINDOWS.md`](docs/CI-WINDOWS.md)). Pour un parc de postes avec mises
à jour automatiques (dépôt Flatpak privé signé), voir
[`docs/DEPLOIEMENT.md`](docs/DEPLOIEMENT.md).

---

## Ce qui a changé par rapport à GIMP 3.2.8

**En chiffres** :

- 23 patchs thématiques sur GIMP 3.2.8 (`patches/gimp-3.2.8/`, organisation dans
  [`docs/dev/PATCHS.md`](docs/dev/PATCHS.md)), soit environ 147 000 lignes ajoutées dans
  491 fichiers, dont 142 fichiers `chopgimp-*` nouveaux ;
- 7 patchs sur GEGL 0.4.72 et 2 sur babl 0.1.128 (performances, styles de calque,
  traductions) ;
- 12 greffons Python ChopGimp ;
- 2 thèmes, des préréglages d'outils et des palettes ;
- 273 tests automatiques (`tools/dev/smoke.sh`), un banc de performance du
  vectoriel (`tools/dev/bench_vector.sh`) et un banc de test graphique sans écran
  (`tools/gui-test/`).

### Prise en main façon Photoshop
- **Raccourcis et gestes Photoshop** : Ctrl+T, V, Espace pour la main (retour à
  l'outil au relâchement), Alt+clic droit pour la taille et la dureté du
  pinceau, Ctrl+clic sur une vignette, Ctrl+Y pour l'épreuve écran, Ctrl+F pour la
  recherche universelle, etc.
- **Clic sur l'outil actif** : affiche la liste des outils de son groupe.
- **Outils ajoutés** : Main (H), Rotation de la vue (R), Forme (U).
- **Contrôles de transformation** de l'outil Déplacement : cadre à poignées, qui suit
  les déplacements.
- **Barre d'options pour une quarantaine d'outils** : réglages chiffrés en champs
  compacts (« 51 px ▾ », avec calculs « 2*5 »). Ce qui ne tient pas passe dans
  « ⋯ ». Elle n'a pas de barre de défilement.
- **Curseurs façon Photoshop** partout : libellé, piste fine, valeur avec son unité,
  Maj pour un réglage fin. Croix de visée sur les petites brosses.
- **Menus** dans l'ordre de Photoshop, une seule place par commande : le menu
  Couleurs est fondu dans **Image > Réglages**, les créations de calques sont en
  tête du menu Calque, et un menu **Vecteur** réunit tout le vectoriel. Les cases à
  cocher laissent le menu ouvert. Environ 650 libellés de menus et de filtres sont
  traduits.
- **Les outils de peinture ne sont jamais aimantés**, comme dans Photoshop : plus de
  « paliers » dans les traits.

- **Lasso magnétique** et **Sélection rapide** comme dans Photoshop : le tracé suit
  les bords pendant qu'on bouge la souris, ou on peint et la sélection s'étend
  jusqu'aux bords. **Boîte à outils par familles** (gomme sous le pinceau) et
  **croix au centre de la brosse** réglable.

### Apparence et espaces de travail
- **Thème « ChopGimp »** en 7 variantes, avec couleur d'accent, densité, polices
  Inter et Source Sans 3, et taille de l'interface en rem. Le tout est réglable à
  chaud dans Affichage > Apparence.
- **Espaces de travail** : Essentiel, Photographie, Peinture, Typographie,
  Illustration, et « Mon espace de travail ».
- **Panneaux modernisés** : onglets avec icône et nom, panneau Calques compact,
  groupes de panneaux souples.
- **Fenêtre d'accueil** : la page « Créer » reprend l'accueil de Photoshop
  (documents en un clic, fichiers récents avec taille et date).

### Calques et styles de calque
- **Styles de calque non destructifs**, comme dans Photoshop : ombre portée et ombre
  interne, lueurs, biseau, contour, incrustations de couleur, de dégradé et de
  motif.
  - Une fenêtre « Style de calque » unifiée, l'icône fx et le copier / coller
    de style.
  - Les modes de fusion de l'ombre portée et de la lueur externe s'appliquent
    aux calques du dessous.
  - Commande « Pixelliser le style de calque ».
- **Calques de réglage** (15 réglages), **calques de remplissage**, **options de
  fusion « Si »**, **compositions de calques**, **instantanés**.
- **Objets dynamiques** : Placer (lié ou incorporé), calques liés surveillés.
- **Rendu rapide des effets** :
  - un cache par calque, enregistré aussi dans le XCF ;
  - des effets consécutifs calculés en une seule passe ;
  - le flou limité à la zone touchée ;
  - les effets recalculés seulement à la fin du trait.
  Résultat : peindre reste fluide sur un calque qui porte des effets.

### Vectoriel façon Illustrator
- **Calque vectoriel multi-objets** : chaque objet a son tracé, sa pile de fonds et
  de contours (couleur, dégradé, motif, opacité, mode), sa transformation, ses
  verrous et ses groupes. L'enregistrement est dans le XCF, et un GIMP standard voit
  les pixels.
- **Sélection (V) et Sélection directe (A) en mode objets** (un rectangle de la
  Sélection directe prend les points de plusieurs objets), avec **repères
  commentés** (aimantation aux bords, centres et nœuds, distances, espacements
  égaux).
- **Panneaux** Objets, Aspect et Contour (tirets, flèches, profils d'épaisseur).
  **Couleurs globales**. **Redéfinir les couleurs** (harmonies, réduction à N
  couleurs).
- **Pathfinder, Bâtisseur de formes, décalages, simplification, effets de tracé**,
  sur le moteur géométrique d'Inkscape (lib2geom).
- **Vectoriser** (l'équivalent de la Vectorisation dynamique d'Illustrator) :
  - moteurs potrace, autotrace (ligne centrale) et depixelize (pixel art) ;
  - 13 préréglages Illustrator et toutes les options avancées ;
  - aperçu en direct, calcul annulable, sélection seule ;
  - le résultat reste réglable, et « Décomposer » le fige en objets ordinaires.
- **Outil Largeur** (Maj+W) : on tire sur le contour d'un objet pour faire varier
  son épaisseur, d'un seul côté avec Alt ; les profils de largeur s'enregistrent
  et se réutilisent (barre d'options, panneau Contour).
- **Vecteur > Distorsion** : Déformation (15 modèles : arc, drapeau, onde, poisson…),
  Enveloppe à maille ou d'après l'objet du dessus, Distorsion libre en perspective,
  avec l'outil Enveloppe ; modifiable jusqu'à « Décomposer ».
- **Peinture dynamique** (Vecteur > Peinture dynamique, Ctrl+Maj+Alt+X) : les zones et
  les segments formés par des tracés qui se croisent se colorient séparément, sans
  opération booléenne, avec le Pot de peinture dynamique (K) et la Sélection de
  peinture dynamique (Maj+K) ; les couleurs suivent quand on déplace un tracé.
- **Symboles** (panneau Symboles, Vecteur > Symboles) : des objets réutilisables dont
  toutes les occurrences suivent les modifications ; `<symbol>` / `<use>` repris à
  l'import SVG.
- **Gomme vectorielle**, texte déformé, texte sur tracé et texte dans une forme.
- **Outils de dessin** (3.29.0) : Courbure, Crayon vectoriel et Lissage, Ciseaux, Cutter
  et Jonction ; angles dynamiques (arrondi, inversé, chanfrein) ; formes spirale, arc,
  grilles rectangulaire et polaire.
- **Transformations précises** (3.29.0) : panneau Transformation (point de référence à
  9 cases), Répéter la transformation (Ctrl+D), Transformer chaque, objet clé et
  « Aligner sur ».
- **Couleur et matière** (3.29.1) : outil **Transition** (étapes de forme, de couleur et de
  dégradé, dynamiques, qui peuvent suivre un tracé de base), **filet de dégradé** (outil
  Filet), **dégradé libre**, dégradé dans, le long ou en travers du contour.
- **Vectoriel rapide** (3.29.2) : ouverture des fichiers vectorisés ~20× plus rapide, glisser par rendus en cache, annulation instantanée par copie des objets (mesures : `docs/PLAN-PERF-VECTEUR.md`).
- **Sélection et nettoyage façon Illustrator** (3.29.3) : Sélection directe qui ne crée
  jamais de point, clic direct sur la forme (double-clic : le groupe), fond / contour suivant
  les couleurs de premier plan / d'arrière-plan, pipette d'objets, info-bulle au survol, mode
  isolation, clic droit = menu Vecteur ; Vecteur > Sélectionner / Nettoyer (Simplifier avec
  aperçu, petits objets, petits trous, fusion par couleur) / Couleurs (panneau « Couleurs du
  dessin ») ; tangentes du filet et export SVG en `<meshgradient>`.
- **Rendu vectoriel accéléré** (3.29.4) : conversion rapide des rendus cairo vers les calques
  8 bits (les calques 16 / 32 bits gardent babl) et rastérisation des objets en parallèle :
  glisser ×27 sur une grosse vectorisation (374 → 14 ms par image), recolorer ×3, rendu
  complet ×1,8.
- **Plans de travail et grille de perspective** (3.31.0, compilé en 3.99.0) : plusieurs pages
  ou formats dans un même fichier (outil Plan de travail Maj+O, panneau, export d'un
  fichier par plan) ; grille de perspective à 1, 2 ou 3 points de fuite avec ses widgets,
  outil Sélection de perspective, formes dessinées sur le plan actif.
- **Pinceau goutte, formes de pinceau, répétitions** (3.30.0, compilé en 3.99.0) : outil Pinceau
  goutte (les coups de même couleur fusionnent en une forme) ; formes de pinceau
  Calligraphique (variations aléatoire et pression), Art, Motif (tuiles d'angle, de début
  et de fin) et Dispersion qui suivent le tracé, panneau Formes (bibliothèque gardée) ;
  répétitions radiale, en grille et en miroir modifiables, avec poignées sur le canevas.
- **Masques d'opacité** et **motifs vectoriels** (grille, briques, hexagonal, mode de
  modification, exportés en `<pattern>` SVG).

### Texte
- **Outil Texte refait** : surlignage par ligne, poignées (texte de point ou de
  paragraphe), sélecteur de polices avec aperçu.
- **Panneaux Caractère et Paragraphe**, styles de texte, glyphes, vérification
  d'orthographe en français (Hunspell avec le dictionnaire de Grammalecte).

### Fichiers
- **PSD** : import avancé et export.
  - À l'import, les textes et les formes restent modifiables, les masques
    vectoriels, les effets, les calques de réglage et les objets dynamiques
    sont repris, avec un rapport d'import.
  - L'export, façon Photoshop (3.31.0, compilé en 3.99.0) : les effets de calque deviennent
    des styles Photoshop (ombres, lueurs, biseau, contour, incrustations couleur et
    dégradé), les calques vectoriels des calques de forme, les textes des calques de
    texte modifiables ; ce qui n'a pas d'équivalent est pixellisé à part et signalé
    dans un rapport ; ChopGimp relit le fichier sans perte (vérifié aussi avec
    psd-tools).
- **PDF, Illustrator, EPS et SVG** importés en calques modifiables : un objet par
  forme, avec les groupes, les dégradés et les masques d'écrêtage.
- **Export SVG** : un `<path>` par objet, compatible avec les calques Inkscape,
  aller-retour testé.
- **Export PDF et EPS vectoriels** (3.31.0, compilé en 3.99.0) : objets, dégradés, filets,
  motifs et textes en vecteurs, modes de fusion et masques gardés ; une page ou un
  fichier par plan de travail ; **calques PDF** (visibles dans Acrobat et Illustrator).
- **Export pour le web** (aperçu avec le poids du fichier), **traitement par lots**,
  **génération de ressources**.
- **Enregistrement automatique et récupération** après plantage.

### Retouche photo et IA locale
- **Camera Raw** (réglages non destructifs), **mise à l'échelle selon le contenu**
  (Liquid Rescale), **recadrage en perspective**, **Redresser**.
- **Remplir d'après le contenu** et **correcteur localisé** (Resynthesizer),
  séparation de fréquences, netteté optimisée, Sélectionner et masquer.
- **IA hors ligne** (onnxruntime) : Sélectionner le sujet, Supprimer l'arrière-plan,
  Agrandir ×2, ×3 ou ×4. Les modèles sont téléchargés une seule fois, après accord,
  et les images ne quittent pas l'ordinateur.

### Dessin et peinture
- **Stabilisateur** (corde), **courbe de pression rapide**, **palette contextuelle**
  (Maj+clic droit), boutons du stylet façon Photoshop.
- **Texture de papier**, **QuickShape**, préréglages Huile, Gouache, Aquarelle,
  Fusain et Pastel, pinceau mélangeur.
- **Atelier BD** : calque de croquis bleu, aplats sous l'encrage, cases de BD,
  guides de perspective, harmonies de couleurs, fenêtre de références,
  enregistrement en accéléré (WebM).

### Performances et fiabilité
- **Affichage** : rendu par tranches pendant l'action, « Aperçu rapide »,
  brouillons en résolution réduite, rendu en arrière-plan en option.
- **Système** :
  - mimalloc ;
  - babl et GEGL compilés en -O3 avec LTO ; GIMP aussi avec LTO et PGO
    (profil d'exécution, vectoriel compris) par `make build LTO=all PGO=1` ;
  - caches des objets vectoriels d'une seule couleur réduits à leur
    couverture (4.0) : mémoire divisée par plus de deux sur une grosse
    vectorisation, rendu plus rapide ;
  - 48 conversions directes ajoutées à babl (×30 à ×300).
- **Traceur de plantage** : journal de session, rapport avec la pile d'appels et
  symbolisation (`tools/crash_symbolize.sh`).
- **Interrupteurs de secours** pour revenir au comportement de GIMP : voir
  [Interrupteurs `CHOPGIMP_*`](#interrupteurs-chopgimp_).

---

## Interrupteurs `CHOPGIMP_*`

Chaque nouveauté peut être coupée par une variable d'environnement, pour revenir au
comportement précédent ou isoler un défaut. Il suffit de lui donner la valeur `1` :

```bash
flatpak run --env=CHOPGIMP_NO_VOBJECTS=1 org.cen_na.ChopGimp
```

Sous Windows, définissez la variable avant de lancer `chopgimp.exe`.

Depuis la 4.1.0, les fonctions éprouvées (livrées jusqu'à la 3.29.4) n'ont plus d'interrupteur :
chargement rapide des XCF, glisser et sprite, annulation rapide, conversion rapide et rendu
parallèle des objets, recoloration et info-bulle des objets, styles fusionnés, modes et calques
des effets « dessous », cache des effets dans le XCF, brouillons (`CHOPGIMP_NO_FAST_LOAD`,
`NO_FAST_DRAG`, `NO_DRAG_SPRITE`, `NO_FAST_UNDO`, `NO_FAST_BABL`, `NO_PAR_RENDER`,
`NO_FG_RECOLOR`, `NO_HOVER_TIP`, `NO_FUSED_STYLES`, `NO_BEHIND_MODES`, `NO_BEHIND_LAYERS`,
`NO_XCF_FX_CACHE`, `NO_DRAFT`, `LP_NO_THROTTLE` sont sans effet). Le cache des effets reste
réglable dans `chopgimprc` (`[xcf] fx-cache=false`).

**Interface**

| Variable | Effet |
|---|---|
| `CHOPGIMP_CLASSIC_PANELS` | Panneaux de GIMP (onglets, panneau Calques d'origine) |
| `CHOPGIMP_CLASSIC_SPIN_SCALE` | Curseurs de GIMP au lieu des curseurs façon Photoshop |
| `CHOPGIMP_CLASSIC_STATUSBAR` | Barre d'état de GIMP au lieu de la barre « Doc » |
| `CHOPGIMP_CLASSIC_TABS` | Onglets de documents de GIMP |
| `CHOPGIMP_NO_GROUP_KEY` | La touche d'un groupe d'outils active le premier outil du groupe, et non l'outil affiché |
| `CHOPGIMP_NO_INNER_STYLES` | Masque les styles Satin et Incrustation de motif |
| `CHOPGIMP_FULL_REDRAW` | Plans de travail et grille de perspective : toute la vue est redessinée à chaque changement |

**Calques et effets**

| Variable | Effet |
|---|---|
| `CHOPGIMP_NO_THREADED_RENDER` | Pas de rendu en arrière-plan |
| `CHOPGIMP_RENDER_THREAD_MIN_US`, `CHOPGIMP_THREADABLE_RECHECK_MS` | Réglages fins du rendu en arrière-plan (durées en µs et en ms) |
| `CHOPGIMP_NO_LASSO_STEPS` | Lasso magnétique : un grand saut de souris ne suit plus le bord par étapes |

**Vectoriel**

| Variable | Effet |
|---|---|
| `CHOPGIMP_NO_VOBJECTS` | Calques vectoriels de GIMP, sans objets (aussi à l'import PDF / AI) |
| `CHOPGIMP_NO_LAZY_LEGACY` | Ancien tracé réécrit tout de suite après chaque annulation |
| `CHOPGIMP_NO_PARTIAL_UNDO` | Annulation : tous les objets sont copiés, pas seulement ceux qui changent |
| `CHOPGIMP_NO_FAST_FLOAT` | Calques 16 / 32 bits : conversion du rendu par babl au lieu du passage en flottants |
| `CHOPGIMP_NO_PAR_RENDER_EXT` | Filets, motifs, flèches et profils rastérisés un à un (les autres objets restent en parallèle) |
| `CHOPGIMP_NO_A8_CACHE` | Cache d'un objet d'une seule couleur en RVBA au lieu de sa seule couverture (4.0.0 : 4× moins de mémoire) |
| `CHOPGIMP_NO_MULTI_NEW_PATH` | Plume : un sous-tracé dessiné pendant une sélection de plusieurs objets est perdu |
| `CHOPGIMP_NO_AUTO_KEY` | « Aligner sur l'objet clé » sans objet clé : pas d'objet clé automatique |
| `CHOPGIMP_NO_BLEND_GROUPS`, `CHOPGIMP_NO_BLEND_ORIENT`, `CHOPGIMP_NO_SPINE_KEYS` | Transition : pas de groupes comme objets clés, étapes non orientées le long du tracé, objets clés laissés en place |
| `CHOPGIMP_NO_GRADIENT_FREEFORM` | L'outil Dégradé ne modifie plus le dégradé libre d'un objet |
| `CHOPGIMP_NO_LOCAL_ACROSS` | Dégradé en travers d'un contour à profil : largeur moyenne au lieu de l'épaisseur locale |
| `CHOPGIMP_LP_NO_INCREMENTAL` | Peinture dynamique : recalcul complet |
| `CHOPGIMP_NO_BLOB_MERGE` | Pinceau goutte : les coups ne fusionnent jamais |
| `CHOPGIMP_NO_VBRUSHES` | Pas de formes de pinceau |
| `CHOPGIMP_NO_REPEAT` | Pas de répétitions |
| `CHOPGIMP_NO_PART_HIT` | Clic sur une forme de pinceau ou une répétition : la partie touchée, non l'ensemble |
| `CHOPGIMP_NO_PERSP_SOURCE` | Sélection de perspective : un calque pixel est rééchantillonné à chaque déplacement |

**Fichiers**

| Variable | Effet |
|---|---|
| `CHOPGIMP_NO_PDF_VECTOR` | Export PDF de GIMP (images, sans calques PDF) |
| `CHOPGIMP_PDF_PAGES` | Import PDF non interactif : pages à importer (ex. `1-3`) |
| `CHOPGIMP_PSD_PLAIN` | Import PSD de GIMP, sans reprise des styles, formes et textes |
| `CHOPGIMP_IA_ALLOW_DOWNLOAD` | Autorise un script à télécharger un modèle d'IA absent |

**Système et diagnostic**

| Variable | Effet |
|---|---|
| `CHOPGIMP_NO_MIMALLOC` | Allocateur de la glibc au lieu de mimalloc (Flatpak) |
| `CHOPGIMP_NO_SESSION_LOG` | Pas de journal de session (traceur de plantage) |
| `CHOPGIMP_CRASH_TEST` | Provoque un plantage de test (`N`, ou `tN` dans un fil de calcul) |
| `CHOPGIMP_DEBUG_RENDER`, `CHOPGIMP_DEBUG_GRAPH`, `CHOPGIMP_FUSED_STYLES_DEBUG`, `CHOPGIMP_FX_CACHE_DEBUG` | Messages de diagnostic du rendu, du graphe GEGL, des effets fusionnés et du cache des effets |

Les options de compilation (`make build LTO=… PGO=… GIMP_O=…`) passent par
`CHOPGIMP_LTO`, `CHOPGIMP_PGO` et `CHOPGIMP_GIMP_O` : voir le Makefile.

---

## Historique en bref

| Versions | Étape |
|---|---|
| 1.0 – 2.1 | « PhotoGIMP Pro » : thème, raccourcis et disposition façon Photoshop sur un GIMP non modifié |
| 3.0 – 3.11 | Recompilation de GIMP en Flatpak : gestes Photoshop, barre d'options, outil Forme, styles de calque, premiers greffons, installateur Windows |
| 3.12 – 3.16 | Panneaux, outils vectoriels avancés (lib2geom), curseurs, texte façon Photoshop / Illustrator |
| 3.17 – 3.24 | Apparence, outil Texte refait, PSD, PDF / AI / EPS / SVG, bases Photoshop, IA locale, dessin, revue finale |
| 3.25 – 3.26 | Passe de performance, barre d'options compacte, curseurs et panneaux modernisés |
| 3.27 | Objets vectoriels, panneaux Objets / Aspect / Contour, Vectoriser, fenêtre d'accueil |
| 3.28 | Menus réorganisés comme Photoshop (menu Vecteur…), Peinture dynamique et Symboles (3.28.1), petits défauts : contours à l'échelle, convertir en maille, pipette avec effets, ombres pixellisées dans leur mode (3.28.2), Lasso magnétique, Sélection rapide, boîte à outils par familles (3.28.3) |
| 3.29 | Vectoriel « complet » : outils Courbure, Crayon vectoriel, Lissage, Ciseaux, Cutter et Jonction, angles dynamiques, spirale / arc / grilles, panneau Transformation, Ctrl+D, Transformer chaque, objet clé (3.29.0) ; Transition, filet de dégradé, dégradé libre, masques d'opacité, motifs vectoriels (3.29.1) ; vectoriel rapide (3.29.2) ; sélection directe, nettoyage et couleurs du dessin façon Illustrator (3.29.3) ; rendu vectoriel accéléré (3.29.4) ; finitions vectorielles — transitions de groupes et le long d'un tracé, dégradé libre en lignes à l'outil Dégradé, peinture dynamique incrémentale (3.29.5, compilé en 3.99.0) ; performance vectorielle complète (3.29.6, compilé en 3.99.0) |
| 3.30 | Pinceau goutte, formes de pinceau (calligraphique, Art, Motif, Dispersion), répétitions radiale / grille / miroir modifiables (3.30.0, compilé en 3.99.0) |
| 3.31 | Plans de travail (outil, panneau, export par plan), grille de perspective à 1, 2 ou 3 points de fuite et Sélection de perspective (3.31.0 partie 1, compilé en 3.99.0) |
| 3.31 | Export PDF / EPS vectoriel par plan de travail, calques PDF, export PSD façon Photoshop (styles, formes, textes) (3.31.0 partie 2, compilé en 3.99.0) |
| 3.32 | Interface : icônes de la boîte à outils, barre d'état « Doc », onglets de documents façon Photoshop, menus Fichier / Édition / Sélection / Fenêtres sans doublon, styles Satin et Incrustation de motif (aussi en PSD) (3.32.0, compilé en 3.99.0) |
| 3.99 | Lots 1 à 5 compilés, corrigés et vérifiés (272 tests, banc de performance, banc graphique) ; version intermédiaire avant la 4.0 (3.99.0) |
| 4.0 | Version finale : caches d'objets 4× plus légers, compilation LTO + PGO, recette complète au banc graphique, avertissements éliminés, thèmes lisibles, traductions des exports, interrupteurs documentés, guide de l'utilisateur (4.0.0) ; CI Windows corrigée (4.0.1) ; liste des calques jamais cachée sous son en-tête (4.0.2) |
| 4.1 | Allègement : 14 interrupteurs retirés avec l'ancien code, code mort et doublons supprimés (`chopgimp-vutil.c`), smoke_test factorisé ; regroupement des patchs proposé (`docs/dev/archive/PLAN-PATCHS-4.1.md`) (4.1.0); une seule sélection d'objets (V, A, Plume, Forme, panneaux, couleurs PP/AP, Ctrl+A / Ctrl+Maj+A, « mixte »), PSD CMJN à profil d'entrée sans plantage (4.1.1) |
| 4.2 | CMJN façon Photoshop : profils ECI (ISO Coated v2 fourni, PSO v3 téléchargés en un clic), Image > Mode > CMJN, Convertir en profil CMJN, fenêtre « profil incorporé différent » (Garder / Convertir / Ignorer, toujours), Exporter pour l'imprimeur (PDF/X-4 vectoriel, PDF/X-1a, TIFF CMJN, fond perdu, traits de coupe, plans de travail), profils invalides refusés sans plantage ; « mixte » dans Aspect / Contour, copier-coller d'objets vectoriels, calque vectorisé sélectionné, outil Lasso direct (4.2.0) ; SVG d'Inkscape / Illustrator collé en objets, barre d'état du Lasso direct, rapport de plantage dans `crash-reports/`, patchs regroupés en 23 thèmes (4.2.1) ; menus sans décalage au survol, groupes d'outils ouverts en 120 ms, au clic sur le triangle ou en glissant (4.2.2) ; bouton Enregistrer dans Quitter / Fermer tout, libellés Enregistrer / Ne pas enregistrer / Annuler, Entrée = Enregistrer (4.2.3) ; icône tête de loup, écran de démarrage sombre avec version (4.2.4) ; « Sélecteur de couleur… » réparé (4.2.5) ; affichage des effets pendant le trait, coche des menus visible, nettoyage et optimisations (4.2.6) ; aperçu rapide sans traits gris sur les calques à effets, icône loup et lune (4.2.7) ; logo loup et lune dans la fenêtre d'image vide (4.2.8) ; Sélection directe (A) : clic sur une autre forme, glisser pour déplacer (Maj 45°, Alt copie, repères commentés), flèches (4.2.9) ; Barbouillage au Flux progressif, Peinture au doigt, « Force » ; Filet et dégradé libre : sélection de points (clic, Maj+clic, rectangle), couleur de premier plan appliquée aux points sélectionnés, Ctrl+clic pipette (4.2.10) |

Le détail de chaque version (ce qui est fait, vérifié, et ce qui reste) se trouve
dans [`docs/SUIVI.md`](docs/SUIVI.md). Le plan du chantier vectoriel est dans
[`docs/PLAN-VECTEURS.md`](docs/PLAN-VECTEURS.md).

---

## Organisation du dépôt

| Dossier | Contenu |
|---|---|
| `patches/gimp-3.2.8/` | Les modifications de GIMP : 22 thèmes et l'icône Windows, appliqués dans l'ordre (`docs/dev/PATCHS.md`) |
| `patches/gegl-0.4.72/`, `patches/babl-0.1.128/` | Patchs de GEGL et de babl |
| `plug-ins/` | Greffons ChopGimp (PSD, PDF, vectoriel, effets, IA, web, atelier…) |
| `themes/`, `icons/`, `cursors/`, `branding/` | Thèmes (générés depuis `themes/src/`), icônes, curseurs, marque |
| `config/`, `presets/`, `data/` | Raccourcis, dispositions, préréglages, palettes, dictionnaire |
| `flatpak/` | Manifeste Flatpak (généré par `tools/make_manifest.py`) et lanceur |
| `tools/` | Générateurs (menus, thèmes, raccourcis…), tests (`tools/dev/smoke.sh`), banc graphique (`tools/gui-test/`), scripts Windows |
| `docs/` | Guide de l'utilisateur, journal des versions, déploiement, compilation Windows, CI, crédits ; `docs/dev/archive/` : notes de développement terminées |
| `.github/workflows/` | Paquets Flatpak et Windows automatiques |

## Compiler

Sous Linux, il faut `flatpak` et `flatpak-builder`, ainsi que Flathub.

```bash
git clone https://gitlab.gnome.org/GNOME/gimp.git build/gimp-src   # puis : git checkout GIMP_3_2_8
# appliquer patches/gimp-3.2.8/*.patch sur une branche « photogimp-v2 » (git am)
make manifest      # génère flatpak/org.cen_na.ChopGimp.json
make build         # flatpak-builder (LTO=0 pour une compilation plus courte,
                   # LTO=all PGO=1 pour le paquet optimisé de la 4.0)
make bundle        # dist/ChopGimp-<VERSION>.flatpak
make install       # installe le bundle pour l'utilisateur
tools/dev/smoke.sh # tests automatiques
```

Pour modifier GIMP, on corrige le thème concerné dans `build/gimp-src` (branche
`photogimp-v2`, un commit par thème : `git commit --fixup`, puis `rebase --autosquash`),
puis `make patches` réexporte la série. Le patch de l'icône Windows est gardé tel quel.
L'ancienne série, un patch par commit, reste dans la branche `photogimp-legacy` et dans
les étiquettes `v4.2.0` et antérieures. Détails : [`docs/dev/PATCHS.md`](docs/dev/PATCHS.md).

Pour Windows, voir [`docs/COMPILATION-WINDOWS.md`](docs/COMPILATION-WINDOWS.md)
(MSYS2 CLANG64) ou laisser GitHub Actions s'en charger.

## Licence et crédits

ChopGimp est un logiciel libre sous **GPL-3.0-ou-ultérieure**, comme GIMP. Il
s'appuie sur GIMP, GEGL et babl, Resynthesizer, lib2geom et Inkscape, potrace,
autotrace, libdepixelize, liblqr, onnxruntime, Hunspell et le dictionnaire de
Grammalecte : voir [`docs/CREDITS.md`](docs/CREDITS.md).

ChopGimp n'est ni affilié ni approuvé par l'équipe GIMP ni par Adobe. Photoshop et
Illustrator sont des marques d'Adobe, citées seulement pour décrire le comportement
imité.

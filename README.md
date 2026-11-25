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
- **Version actuelle** : voir le fichier [`VERSION`](VERSION). Le journal détaillé
  est dans [`docs/SUIVI.md`](docs/SUIVI.md).

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

- 137 patchs sur GIMP 3.2.8 (`patches/gimp-3.2.8/`), soit environ 92 000 lignes
  ajoutées dans 370 fichiers, dont 83 fichiers `chopgimp-*` nouveaux ;
- 7 patchs sur GEGL 0.4.72 et 2 sur babl 0.1.128 (performances, styles de calque,
  traductions) ;
- 12 greffons Python ChopGimp ;
- 2 thèmes, des préréglages d'outils et des palettes ;
- 115 tests automatiques.

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
- **Sélection (V) et Sélection directe (A) en mode objets**, avec **repères
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
- **Gomme vectorielle**, texte déformé, texte sur tracé et texte dans une forme.

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
  - L'export conserve les formes et les textes.
- **PDF, Illustrator, EPS et SVG** importés en calques modifiables : un objet par
  forme, avec les groupes, les dégradés et les masques d'écrêtage.
- **Export SVG** : un `<path>` par objet, compatible avec les calques Inkscape,
  aller-retour testé.
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
  - babl et GEGL compilés en -O3 avec LTO ;
  - 48 conversions directes ajoutées à babl (×30 à ×300).
- **Traceur de plantage** : journal de session, rapport avec la pile d'appels et
  symbolisation (`tools/crash_symbolize.sh`).
- **Interrupteurs de secours** pour revenir au comportement de GIMP :
  `CHOPGIMP_NO_VOBJECTS`, `CHOPGIMP_CLASSIC_PANELS`, `CHOPGIMP_NO_MIMALLOC`, etc.
  Ils sont décrits dans `docs/SUIVI.md`.

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
| 3.28 | Menus réorganisés comme Photoshop : menu Vecteur, Couleurs fondu dans Image > Réglages, créations de calques en tête de Calque |

Le détail de chaque version (ce qui est fait, vérifié, et ce qui reste) se trouve
dans [`docs/SUIVI.md`](docs/SUIVI.md). Le plan du chantier vectoriel est dans
[`docs/PLAN-VECTEURS.md`](docs/PLAN-VECTEURS.md).

---

## Organisation du dépôt

| Dossier | Contenu |
|---|---|
| `patches/gimp-3.2.8/` | Les modifications de GIMP, un patch par commit, appliquées dans l'ordre |
| `patches/gegl-0.4.72/`, `patches/babl-0.1.128/` | Patchs de GEGL et de babl |
| `plug-ins/` | Greffons ChopGimp (PSD, PDF, vectoriel, effets, IA, web, atelier…) |
| `themes/`, `icons/`, `cursors/`, `branding/` | Thèmes (générés depuis `themes/src/`), icônes, curseurs, marque |
| `config/`, `presets/`, `data/` | Raccourcis, dispositions, préréglages, palettes, dictionnaire |
| `flatpak/` | Manifeste Flatpak (généré par `tools/make_manifest.py`) et lanceur |
| `tools/` | Générateurs (menus, thèmes, raccourcis…), tests (`tools/dev/smoke.sh`), banc graphique (`tools/gui-test/`), scripts Windows |
| `docs/` | Journal des versions, déploiement, compilation Windows, CI, crédits |
| `.github/workflows/` | Paquets Flatpak et Windows automatiques |

## Compiler

Sous Linux, il faut `flatpak` et `flatpak-builder`, ainsi que Flathub.

```bash
git clone https://gitlab.gnome.org/GNOME/gimp.git build/gimp-src   # puis : git checkout GIMP_3_2_8
# appliquer patches/gimp-3.2.8/*.patch sur une branche « photogimp » (git am)
make manifest      # génère flatpak/org.cen_na.ChopGimp.json
make build         # flatpak-builder (LTO=0 pour une compilation plus courte)
make bundle        # dist/ChopGimp-<VERSION>.flatpak
make install       # installe le bundle pour l'utilisateur
tools/dev/smoke.sh # tests automatiques
```

Pour modifier GIMP, on commite dans `build/gimp-src` (branche `photogimp`), puis
`make patches` exporte les nouveaux commits en patchs numérotés. Un patch existant
n'est jamais réécrit.

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

# ChopGimp — suivi du plan d'attaque (depuis la 3.16.1)

Plan complet : lots 0 à 6, idées en plus, calendrier de 17 étapes (voir l'historique des commits « ChopGimp 3.x »).

| Étape | Version | Contenu | État |
|---|---|---|---|
| 1 | 3.16.2 | Fin de la revue de code | ✅ livrée |
| 2 | 3.17.0 | Apparence I (variantes, rem, accent, densité, polices, menu) | ✅ livrée |
| 3 | 3.17.1 | Apparence II (préférences, espaces de travail, barre d'outils, écran d'accueil) | ✅ livrée |
| 4 | 3.18.0 | Refonte de l'outil Texte | ✅ livrée |
| 5 | 3.19.0 | PSD I | ✅ livrée |
| 5 bis | 3.19.1 | Traceur de plantage + correctif (hors plan) | ✅ livrée |
| 5 ter | 3.19.2 | Retours d'utilisation (remplissage, filtres, styles, sélection auto) | ✅ livrée |
| 6 | 3.19.3 | PSD II | ✅ livrée |
| 7 | 3.20.0 | Vectoriel I (PDF/AI) | à faire |
| 8 | 3.20.1 | Vectoriel II (EPS, SVG, aperçus, Placer) | à faire |
| 9 | 3.20.2 | Vectoriel III (SVG natif, export SVG) | à faire |
| 10 | 3.21.0 | Base I | à faire |
| 11 | 3.21.1 | Base II | à faire |
| 12 | 3.21.2 | Base III | à faire |
| 13 | 3.22.0 | IA locale | à faire |
| 14 | 3.23.0 | Dessin I « Confort » | à faire |
| 15 | 3.23.1 | Dessin II « Peintre » | à faire |
| 16 | 3.23.2 | Dessin III « Atelier / BD » | à faire |
| 17 | 3.24.0 | Revue finale | à faire |

## 3.16.2 — fin de la revue de code

- **Panneaux** :
  - un panneau a maintenant sa propre fenêtre : la partie coupée d'un groupe réduit ne capte plus les clics du groupe d'en dessous ;
  - réduire la fenêtre n'écrase plus les groupes du bas sous leur barre d'onglets ;
  - la zone de dépôt ne recouvre plus un dernier groupe réduit ;
  - le bouton « vignettes recadrées » est synchronisé entre panneaux Calques.
- **Vignettes** : le recadrage se fait sur la transparence. Avant, il se faisait sur la couleur des coins, d'où une vignette vide pour une forme pleine. Le même correctif protège le recadrage automatique fait avant une transformation, qui pouvait rogner un calque opaque à bords unis.
- **Styles de calque** : l'aperçu ne laisse plus de trace dans l'historique, Annuler rend les filtres d'origine à l'identique, et une seule étape est créée à la validation. Appliquer un style de texte pendant l'édition crée aussi une seule étape.
- **Texte** :
  - texte sur tracé : on vérifie le nom du tracé (copie dans une autre image) ;
  - tirets et extrémités du contour respectés sur un texte déformé ;
  - guillemets typographiques corrects en mode refrappe.
- **Raccourci Maj+C** renommé « Perspective (transformation) » ; le vrai recadrage en perspective arrive à l'étape 10.
- **Banc de test graphique** : la vue d'ensemble GNOME est fermée par D-Bus (commande `nooverview`), et `CHOPGIMP_GUITEST_FLATPAK_ARGS` permet de passer des variables à l'application.

**Bugs connus restants** : Ctrl+poignée dérive légèrement sur un texte transformé (sera revu avec la refonte du Texte, étape 4).

## 3.17.0 — Apparence I

- **Thème « ChopGimp »**, généré par `tools/build_themes.py` à partir de `themes/src/` :
  - 7 variantes de couleurs : Sombre (Photoshop), Gris moyen, Gris clair, Clair, Contraste élevé, Anthracite (Affinity), Gris bleuté (Krita) ;
  - plus aucune couleur codée en dur dans la surcouche, vérification automatique (`--check`) ;
  - l'ancien nom « PS-Dark » renvoie vers ChopGimp.
- **Tailles en rem** : la taille de police des Préférences et la « Taille de l'interface » s'appliquent partout.
- **Menu Affichage > Apparence**, appliqué à chaud :
  - variante ;
  - couleur d'accent (8 couleurs ou celle de la variante) ;
  - densité (compacte, normale, aérée) ;
  - police (Inter, Source Sans 3, système) ;
  - taille de l'interface (90 / 100 / 115 / 130 %).
- **Polices Inter et Source Sans 3 fournies** (OFL) ; sous Windows, enregistrées au démarrage (`AddFontResourceEx`) pour que l'interface ne retombe plus sur une police de secours.
- **La zone autour de l'image suit le thème** (fond clair dans les variantes claires).
- Réglages enregistrés dans `chopgimprc [appearance]`.

## 3.17.1 — Apparence II

- **Préférences > Interface > Apparence** : variante, accent, densité, police, taille de l'interface (mêmes réglages que le menu).
- **Fenêtres > Espace de travail** : Essentiel, Photographie, Peinture, Typographie, Illustration, et « Mon espace de travail » (Enregistrer l'espace de travail). Les dispositions sont générées par `tools/build_layout.py` (`config/workspaces/`) et appliquées à chaud.
- **Fenêtres > Modifier la barre d'outils…** : ouvre directement Préférences > Boîte à outils (outils visibles, groupes).
- **Écran d'accueil** :
  - affiché au démarrage ;
  - onglet Créer : 7 documents en un clic (Par défaut, A4, Instagram, Story, Bannière, 4K, Toile), vignettes plus grandes pour les images récentes.

## 3.18.0 — Refonte de l'outil Texte

- **Sélection** : un seul surlignage bleu par ligne, au lieu d'un carré par caractère.
- **Plus de barre de style flottante sur le canevas** (désactivée par défaut). Ses réglages sont dans la barre d'options :
  - police et taille ;
  - couleur ;
  - gras, italique, souligné, barré (G / I / S / B) ;
  - alignement ;
  - approche et interlignage ;
  - cadre ;
  - déformation ;
  - panneaux.
- **Poignées** : sur un texte de point (cadre dynamique), elles mettent le texte à l'échelle. Sur un texte de paragraphe, elles redimensionnent le cadre, et Ctrl met à l'échelle.
- **Sélecteur de polices avec aperçu complet** (bouton ▾ du panneau Caractère) :
  - chaque police est dessinée dans sa propre face, avec le texte du calque comme échantillon ;
  - recherche et filtre par catégorie ;
  - aperçu en direct sur le calque au survol et aux flèches.
- **Nouveaux panneaux** :
  - « Polices » : toutes les polices en rendu réel ;
  - « Textes du document » : la liste des calques de texte ; un clic sélectionne le calque et passe en édition.
- **Effets en un clic** dans le panneau Caractère : style de calque, contour, dégradé.
- L'espace de travail Typographie affiche ces panneaux.

**Reporté** :
- curseurs des axes des polices variables. Les instances nommées sont déjà listées. Reporté à l'étape 17 ;
- dérive de Ctrl+poignée sur un texte avec effets.

## 3.19.0 — Import PSD I

- **Nouveau plug-in `chopgimp_psd`**, prioritaire pour les .psd et .psb :
  - l'import de GIMP charge d'abord les pixels, les groupes, les masques et les modes ;
  - `psdparse.py`, en Python pur, relit ensuite la section des calques (370 Mo lus en 0,2 s, sans toucher aux pixels) ;
  - chaque calque est retrouvé par son identifiant Photoshop.
- **Textes → calques de texte modifiables** :
  - police (nom PostScript retrouvé via fontconfig), taille, couleur, approche, interlignage, alignement ;
  - plusieurs styles dans un calque, en balises ;
  - texte de point ou cadre de paragraphe ;
  - rotation, inclinaison et étirement en transformation modifiable ;
  - déformation de Photoshop vers les 15 styles ChopGimp.
- **Formes → calques vectoriels** (fond uni, contour avec épaisseur, extrémités, angles et tirets).
- **Masques vectoriels** → masque de calque, plus un chemin du même nom.
- **Effets (lfx2) → styles ChopGimp** : ombre portée, ombre interne, lueurs, biseau, incrustation couleur, contour, incrustation de dégradé. Les anciens effets posés par l'import de GIMP sont retirés pour éviter le doublon.
- **Originaux** : les calques pixellisés remplacés sont gardés dans le groupe masqué « ⟲ Originaux ».
- **Polices absentes** : fenêtre de remplacement ; la correspondance est mémorisée dans `chopgimp-psd.json`.
- **Rapport** de ce qui est repris, approximé ou ignoré. Il est aussi enregistré dans le parasite d'image `chopgimp-psd-report`.
- **Couleurs des styles de calque** : elles étaient traitées en RVB linéaire, donc rendues trop claires. Elles sont maintenant en sRGB (`chopgimp_fx`).
- **PSD de test** généré par `tools/fixtures/make_psd.py` ; 8 tests ajoutés.

**Limites**, traitées en 3.19.1 :
- calques de réglage et de remplissage ;
- objets dynamiques ;
- contour intérieur ou extérieur d'une forme, rendu centré.

## 3.19.1 — Traceur de plantage (hors plan)

- **Journal de session** : la sortie de ChopGimp et de ses plug-ins est copiée, horodatée, dans `<dossier GIMP>/logs/session-AAAAMMJJ-HHMMSS.log`. Les 10 dernières sessions sont gardées. Les actions, les plug-ins lancés et les images ouvertes y sont notés.
- **Rapport de plantage fiable** (`app/chopgimp-crash.c`) :
  - il est écrit pour SIGSEGV, SIGBUS, SIGFPE, SIGILL et SIGABRT, quel que soit le fil, avant le traitement de GIMP ;
  - il n'utilise que des appels sûrs dans un signal, et une pile de secours ;
  - il contient le signal, le fil, la pile des plug-ins en cours, les 16 dernières actions, les images ouvertes, la mémoire, la pile d'appels et la fin du journal ;
  - il est enregistré dans `CrashLog/chopgimp-crash-*.txt`.
- **Au démarrage suivant**, une fenêtre « ChopGimp s'est arrêté brutalement » propose de copier le rapport ou d'ouvrir le dossier.
- **`tools/crash_symbolize.sh <rapport> [commit Debug]`** traduit la pile en fonction, fichier et ligne, avec les symboles de l'extension `org.cen_na.ChopGimp.Debug` (via eu-addr2line).
- **Test** : `CHOPGIMP_CRASH_TEST=N` (ou `tN` pour un fil de calcul) fait planter volontairement, pour le banc de test uniquement.
- **Plantage corrigé** : Ctrl ou Maj pendant une transformation, après le passage Déplacement → Transformation. Une ancienne grille restait liée aux réglages de l'outil et appelait son outil détruit (`gimp_transform_grid_tool_widget_changed`). Les grilles sont maintenant toujours libérées et débranchées.
- **Import PSD** :
  - procédure de vignette propre au plug-in (l'erreur au démarrage disparaît) ;
  - une police de remplacement mémorisée qui est un alias (Sans-serif) est reconnue.
- **Barre d'options de la transformation** : libellés lisibles pour les contraintes.

## 3.19.2 — Retours d'utilisation (livrée)

Signalés le 2026-11-13 en utilisant ChopGimp sur une affiche (scan 2480×3510) :

1. **Calques sans bords pour le remplissage et la peinture** : Édition > Remplir, le pot de peinture et les pinceaux agrandissent automatiquement le calque pour couvrir la sélection ou le trait. Aujourd'hui, une sélection hors des limites du calque ne se remplit pas : c'est le cas dans afficheDANY.xcf, où des calques sont décalés de (-1046, -1301).
2. **Réglages du menu Couleurs fusionnés par défaut** (Désaturer, Luminosité-Contraste, Teinte-Saturation, Niveaux, Courbes…), comme dans Photoshop, avec une case « Garder modifiable ». Aujourd'hui, ils restent en filtres actifs, et peindre ou remplir s'affiche alors filtré et rame.
3. **Avertissement dans la barre d'état** quand on peint ou remplit un calque très transparent (opacité < 50 %), masqué, ou qui porte des filtres actifs.
4. **Erreurs internes du journal** : `gimp_tool_set_active_modifier_state: assertion 'display == tool->focus_display'` (touche modificatrice pendant un collage ou un remplissage).
5. **Styles et contours avec fenêtre de réglage** :
   - Style de calque > Contour, Lueur externe et Ombre interne ouvrent la fenêtre « Style de calque… » avec l'effet coché ;
   - Tracé > Contour à l'intérieur / à l'extérieur ouvrent une petite fenêtre (épaisseur, couleur, aperçu) ;
   - le bouton Contour du panneau Caractère ouvre la même fenêtre ;
   - les libellés prennent des points de suspension « … ».
6. **Sélection automatique du calque (outil Déplacement)** :
   - le calque cliqué devient le calque actif et est mis en surbrillance dans le panneau Calques, comme dans Photoshop ;
   - un clic dans le vide garde le calque actuel ;
   - Maj+clic ajoute le calque à la sélection.

**Fait en 3.19.2** :
1. **Remplissage et peinture** :
   - Édition > Remplir et le pot de peinture agrandissent le calque jusqu'à la sélection, ou jusqu'à l'image entière (`core/chopgimp-layer-grow.c`) ;
   - les pinceaux ont « Agrandir les calques » activé par défaut.
2. **Réglages Couleurs et Filtres** : « Appliquer directement au calque » est coché par défaut ; décoché, le réglage reste un filtre modifiable.
3. **Avertissements dans la barre d'état**, une fois par calque : calque masqué, opacité < 50 %, filtres actifs.
4. **Assertion `focus_display`** : une touche modificatrice destinée à une autre image est ignorée.
5. **Fenêtres de réglage** :
   - Contour…, Lueur externe… et Ombre interne… ouvrent Style de calque avec l'effet coché, en gras et en aperçu ; le contour et l'incrustation couleur sont à 100 % par défaut ;
   - Contour à l'intérieur… / à l'extérieur… demandent l'épaisseur et la couleur ;
   - le bouton Contour… du panneau Caractère passe aussi par Style de calque.
6. **Sélection automatique** : le calque cliqué devient le calque actif (`move-tool-changes-active` activé par défaut). Maj+clic n'est pas modifié : il sert déjà à basculer le mode de l'outil.

**Également corrigé** :
- **Plantage pendant « Déformer le texte »** : double libération dans `chopgimp_text_fx_moves_glyphs`, à chaque redessin d'un texte déformé en cours d'édition.
- **Fenêtres de plug-ins passant derrière ChopGimp** (par exemple « Polices absentes » à l'ouverture d'un PSD), qui donnaient l'impression d'un logiciel figé. Toutes sont maintenant rattachées à la fenêtre de l'image (`libgimp/gimpui.c`).
- **Rapport de plantage** : les plug-ins terminés ne restent plus « en cours ».
- **Barre d'options de la sélection rectangulaire** : libellés lisibles.

## 3.19.3 — Import PSD II et export PSD

- **Calques de réglage → filtres modifiables** :
  - Niveaux (par couche, avec gamma) et Courbes (vraie courbe par couche) ;
  - Luminosité/Contraste, Teinte/Saturation, Coloriser, Balance des couleurs (tons foncés, moyens, clairs) ;
  - Négatif, Isohélie, Seuil, Exposition, Mélangeur de couches ;
  - Noir et blanc (3 couleurs sur 6) et Vibrance, rendus de façon approchée.
- **Placement des réglages** :
  - comme dans Photoshop, un réglage agit sur ce qui est en dessous : il devient un groupe « ◐ nom » contenant les calques du dessous, avec le filtre ;
  - un réglage écrêté devient un filtre sur son calque de base ;
  - l'opacité et la visibilité du réglage sont reprises.
- **Calques de remplissage** : la couleur unie devient un calque vectoriel couvrant l'image ; un dégradé ou un motif garde ses pixels, avec une mention dans le rapport.
- **Objets dynamiques incorporés** (`lnk2`/`lnkD`) : le fichier est extrait dans `<dossier GIMP>/psd-objets/<fichier>/` et devient un **calque lié**, placé d'après les 4 coins de la transformation.
- **Identifiants Photoshop** : quand l'import de GIMP donne le même identifiant à son groupe d'écrêtage qu'au calque, c'est le vrai calque qui est retenu.
- **Export PSD** (`plug-ins/file-psd/psd-chopgimp.c`) :
  - les calques vectoriels sont écrits comme **calques de forme** Photoshop (tracé, fond uni, contour) ;
  - option « **Textes modifiables (expérimental)** », désactivée par défaut : les calques de texte sont écrits comme calques de texte Photoshop, avec une mise en forme simple ;
  - nombres écrits avec un point, quelle que soit la langue (l'export en français écrivait « 36,0 »).
- **6 nouveaux tests**, dont l'aller-retour PSD (forme et texte relus modifiables) : 72 tests.

**À vérifier dans Photoshop** : l'export des textes, que je ne peux pas tester ici.

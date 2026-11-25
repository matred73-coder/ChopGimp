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
| 7 | 3.20.0 | Vectoriel I (PDF/AI, + EPS et SVG en avance) | ✅ livrée |
| 8 | 3.20.1 | Vectoriel II (Placer, objets dynamiques, aperçus) | ✅ livrée |
| 9 | 3.20.2 | Vectoriel III (SVG natif, export SVG) | ✅ livrée |
| 10 | 3.21.0 | Base I | ✅ livrée |
| 11 | 3.21.1 | Base II | ✅ livrée |
| 12 | 3.21.2 | Base III | ✅ livrée |
| 13 | 3.22.0 | IA locale | ✅ livrée |
| 14 | 3.23.0 | Dessin I « Confort » | ✅ livrée |
| 15 | 3.23.1 | Dessin II « Peintre » | ✅ livrée |
| 16 | 3.23.2 | Dessin III « Atelier / BD » | ✅ livrée |
| 17 | 3.24.0 | Revue finale | ✅ livrée |
| 18 | 3.24.1 | Optimisation « légèreté » et nettoyage en profondeur | ✅ livrée |

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

## 3.20.0 — Vectoriel I : PDF, Illustrator, EPS, SVG

- **Approche** (plus simple et portable que l'OutputDev C++ prévu) :
  - poppler (accessible depuis Python grâce à l'introspection activée dans le manifeste) et librsvg dessinent sur une surface **CairoScript** ;
  - `plug-ins/chopgimp_pdf/cairoscript.py` relit cet enregistrement : tracés de Bézier, couleurs, contours (épaisseur, extrémités, angles, tirets), dégradés, images incorporées.
- **PDF / AI moderne** (`file-chopgimp-pdf-load`, prioritaire) :
  - chaque **calque PDF (OCG, calques d'Illustrator)** devient un groupe : la page est rendue une fois par calque, et les objets propres à chaque calque sont séparés de ceux de la base ; la visibilité est reprise ;
  - tracés → **calques vectoriels** (fond, contour) ; les objets consécutifs de même style sont réunis, avec un plafond réglable (1 500 objets) au-delà duquel la page est importée en image ;
  - **images** → calques d'image placés sur leurs 4 coins ;
  - **textes** → calques de texte modifiables, ligne par ligne, avec police (polices standard Helvetica/Times/Courier ramenées à leur famille), taille et couleur ; ou contours vectoriels ;
  - **dégradés** → pixels exacts du rendu, masqués par la forme ;
  - **rendu de référence** de la page, masqué, pour comparer ;
  - fenêtre d'options (calques modifiables ou image comme avant, pages, texte, résolution, plafond, calques masqués) et rapport.
- **EPS / PS / ancien AI** (`file-chopgimp-eps-load`) : la bibliothèque Ghostscript du paquet (`libgs`, sans commande `gs`) convertit en PDF, puis même import.
- **SVG** (`file-chopgimp-svg-load`) : librsvg dessine chaque calque Inkscape séparément (groupes, visibilité) ; les textes sont relus dans le XML (position, taille, police, gras/italique, couleur) et deviennent modifiables ; dégradés en pixels.
- **Corrigé** :
  - signature de fichier de même longueur que celle de GIMP, sinon la priorité ne compte pas ;
  - procédure de vignette déclarée avant l'import (PSD aussi).
- **5 nouveaux tests** (`tools/fixtures/make_pdf.py`, `make_vector.py`) : 77 tests.

**Limites** :
- les découpes (masques d'écrêtage) ne sont pas appliquées aux vecteurs : voir le rendu de référence ;
- les calques PDF imbriqués sont mis à plat ;
- un texte situé dans un calque PDF va dans le groupe « Textes ».

## 3.20.1 — Vectoriel II : Placer et objets dynamiques

- **Fichier > Placer (lié)…** (Ctrl+Alt+Maj+O) et **Placer (incorporé)…** (Ctrl+Alt+O) : les actions « Ouvrir comme calque lié / comme calques » de GIMP, renommées comme dans Photoshop. Un calque lié est surveillé : il se met à jour quand son fichier change.
- **Calque > Objet dynamique** (`plug-ins/chopgimp_smart`) :
  - **Convertir en objet dynamique** : les calques sélectionnés sont enregistrés dans un XCF (`<dossier GIMP>/objets-dynamiques/<image>/`) et remplacés par un calque lié, à la même place ;
  - **Modifier le contenu** : ouvre le fichier lié ; il suffit de l'enregistrer pour mettre à jour l'objet ;
  - **Remplacer le contenu…** : lie le calque à un autre fichier.
- **Vignettes** dans la fenêtre d'ouverture : SVG (rendu par librsvg ; l'import SVG de GIMP n'en avait pas), EPS/PS/AI et PDF (vignettes d'origine).
- **2 nouveaux tests** : 79 tests.

## 3.20.2 — Vectoriel III : export SVG et aller-retour

- **Export SVG** (`plug-ins/common/file-svg.c`, celui de GIMP, enrichi) :
  - **nombres avec un point quelle que soit la langue** : en français, l'export d'origine écrivait `opacity="1,000000"`, un SVG invalide ;
  - les **calques masqués** sont exportés masqués (`display:none`), au lieu d'être perdus ;
  - les groupes deviennent des **calques Inkscape** (`inkscape:groupmode="layer"`) ;
  - chaque élément garde le **nom de son calque** (`inkscape:label`).
- **Import SVG** : les formes sont rendues depuis une copie sans `<text>`, car librsvg dessine le texte en tracés, qui faisaient doublon avec les calques de texte modifiables.
- **Aller-retour SVG** testé : import, export, réimport (groupes, visibilité, texte).
- **3 nouveaux tests** : 82 tests.

## 3.21.0 — Base I

- **Enregistrement automatique et récupération** (`app/gui/chopgimp-autosave.c`) :
  - toutes les 5 minutes (`chopgimprc [autosave] minutes`, 0 pour désactiver), copie XCF de chaque image modifiée dans `<dossier GIMP>/autosave/` ;
  - la copie est écrite par `xcf_save_stream`, donc sans changer l'état de l'image ni les documents récents, et jamais pendant un coup de pinceau ;
  - la copie est effacée quand l'image est enregistrée ou fermée, et toutes à la fermeture normale ;
  - après un plantage, une fenêtre « Récupération » propose de rouvrir les copies (sous leur nom d'origine, marquées modifiées), de les supprimer, ou de décider plus tard.
- **Aligner / répartir** dans la barre d'options de l'outil Déplacement : 6 alignements et 2 répartitions.
  - Un seul calque s'aligne sur la sélection ou la zone de travail ; plusieurs calques, sur leur ensemble.
  - Le calcul porte sur le contenu visible (transparence), pas sur le cadre du calque.
  - Une seule étape d'annulation.
- **Recherche universelle** : Ctrl+F ou `/` ouvre la recherche de commandes, filtres et menus de GIMP.
- **Repères intelligents** : l'aimantation de GIMP aux bords et centres des calques et aux espacements égaux (déjà active par défaut dans ChopGimp) est renommée ainsi dans le menu Affichage.
- **Image > Recadrage en perspective…** : un chemin de 4 points sur les coins est redressé en rectangle par une homographie, sur tous les calques, puis l'image est recadrée.
- **Image > Redresser…** : avec un chemin de 2 points, l'image tourne vers l'horizontale ou la verticale la plus proche, puis est recadrée sur le plus grand rectangle sans bord vide. Le bouton « Redresser » de l'outil Mesure existe aussi.
- **Image > Mise à l'échelle selon le contenu…** : Liquid Rescale (liblqr ajoutée au paquet, compilée en C17), avec option pour protéger la sélection.
- **3 nouveaux tests** : 85 tests. Récupération testée au banc, en tuant ChopGimp.

## 3.21.1 — Base II

- **Calque > Nouveau calque de réglage** (15 réglages : Niveaux, Courbes, Luminosité/Contraste, Exposition, Vibrance, Teinte/Saturation, Balance des couleurs, Noir et blanc, Filtre photo, Mélangeur de couches, Coloriser, Négatif, Isohélie, Seuil, Tons foncés/Tons clairs) :
  - un groupe « ◐ nom » reçoit le calque sélectionné et tous ceux du dessous, puis **la vraie fenêtre de réglage de GIMP s'ouvre sur ce groupe**, avec aperçu en direct ;
  - un filtre sur un groupe reste toujours modifiable (icône fx) ;
  - l'opacité, la visibilité et le masque du groupe font office de ceux du réglage.
  - Un vrai type « calque de réglage » demanderait un nouveau format XCF, illisible par GIMP.
- **Calque > Nouveau calque de remplissage** :
  - couleur unie : calque vectoriel couvrant l'image, couleur modifiable ;
  - dégradé : incrustation de dégradé modifiable ;
  - motif.
- **Calque > Style de calque > Options de fusion « Si »…** : plages « Ce calque » et « Calque du dessous », avec rampes comme les curseurs scindés de Photoshop. Le résultat est un masque de calque, recalculé en relançant la commande (réglages mémorisés).
- **Image > Instantané** : créer un instantané (copie de l'image, dans le panneau Images) et revenir à un instantané.
- **Filtres > Camera Raw…** : exposition, contraste, hautes lumières, ombres, clarté, vibrance, saturation, température, vignettage, grain. Chaque réglage devient un filtre modifiable « Camera Raw : … », avec aperçu en direct, une seule étape d'annulation, et Réinitialiser.
- **Épreuve écran en un clic** : Ctrl+Y (couleurs d'impression), Ctrl+Maj+Y (couleurs non imprimables).
- **2 nouveaux tests** : 87 tests.

## 3.21.2 — Base III

- **Édition > Actions** : « Enregistrer une action » (démarrer / arrêter) et « Rejouer l'action ».
  - Les commandes qui modifient l'image (menus, filtres, calques, plug-ins…) sont enregistrées dans `chopgimprc [macro]`, puis relancées dans l'ordre.
  - Une commande avec fenêtre la rouvre.
  - Ne sont pas enregistrés : affichage, fenêtres, outils, fichiers.
- **Fichier > Exporter > Traitement par lots…** : sur un dossier, côté maximal, accentuation, conversion sRGB, filigrane texte, format (JPEG, WebP, PNG, AVIF) et qualité.
- **Fichier > Exporter > Exporter pour le web…** : JPEG, WebP, AVIF ou PNG, qualité, taille, et aperçu avant/après avec le poids du fichier, recalculé à chaque réglage.
- **Fichier > Exporter > Générer les ressources** :
  - les calques nommés comme des fichiers (« logo.png », « vignette.jpg 50% », « icône.png 200% », plusieurs séparés par des virgules) sont exportés dans `<image>-ressources/` ;
  - « Générer les ressources à chaque enregistrement » le fait à chaque Ctrl+S (`app/file/file-save.c`).
- **Fenêtres > Compositions de calques…** : nouvelle, mettre à jour, appliquer (double-clic), supprimer, exporter tout. Une composition mémorise la visibilité, la position et l'opacité ; elle est enregistrée dans le XCF.
- **1 nouveau test** : 88 tests. La génération à l'enregistrement et les actions ont été vérifiées au banc graphique.

## 3.22.0 — IA locale

- **Moteur** : numpy 2.5.4 et onnxruntime 1.32.0 (paquets précompilés pour Python 3.14) ajoutés au paquet, qui passe de 58 à 92 Mo. Exécution hors ligne, sur le processeur.
- **Modèles téléchargés à la première utilisation**, après accord : une fenêtre indique la taille et la source. Ils sont rangés dans `<dossier GIMP>/ia-modeles/` et vérifiés par empreinte SHA-256. Les images ne quittent jamais l'ordinateur.
- **Sélection > Sujet (IA)** : détourage automatique, qui devient une sélection.
- **Image > Supprimer l'arrière-plan (IA)** : le détourage devient un masque de calque, donc réversible.
- **Image > Agrandir (IA)…** ×2, ×3 ou ×4 :
  - réseau de super-résolution (sub-pixel CNN, 240 Ko) appliqué à la luminance, par tuiles de 224 px avec recouvrement ;
  - chrominance et transparence agrandies en cubique ;
  - le résultat s'ouvre dans une nouvelle image.
- **Filtres > Améliorer > Réduire le bruit…** : filtre DCT de GEGL, non destructif. Ce n'est pas un réseau de neurones : aucun modèle de débruitage léger et fiable n'était disponible.
- **Fichier > Modèles d'IA…** : choix du modèle de détourage, modèles installés, suppression.
  - Rapide : U²-Net p, 4,5 Mo.
  - Équilibré : Silueta, 44 Mo (par défaut).
  - Précis : IS-Net, 178 Mo.
- **3 nouveaux tests** : 91 tests. Essai sur `face.psd` : le bâtiment est bien isolé.

## 3.23.0 — Dessin I « Confort »

- **Stabilisateur « corde »** (pinceau paresseux de Krita / StreamLine de Procreate), dans la barre d'options du pinceau et du crayon :
  - la pointe ne suit le curseur qu'au-delà de la longueur de corde (30 px par défaut, réglable), ce qui supprime les tremblements ;
  - « Rattrapage » : en fin de trait, la pointe rejoint le curseur ;
  - code dans `gimp_paint_core_smooth_coords`.
- **Courbe de pression rapide** dans la barre d'options : linéaire, douce, ferme ou légère, appliquée au stylet actif. Le réglage fin reste dans Édition > Périphériques d'entrée.
- **Réglage du pinceau à la volée** (Alt + clic droit glissé), comme dans Photoshop : à l'horizontale la taille, à la verticale la dureté, avec les valeurs dans la barre d'état.
- **Palette contextuelle** (Maj + clic droit, modificateur personnalisable) : une bulle sous le curseur avec les 10 derniers pinceaux, la taille, les couleurs récentes et un sélecteur de couleur.
- **Gestes** : pincer pour zoomer et faire pivoter à deux doigts existent déjà dans GIMP 3.2. Les tapes à deux ou trois doigts (annuler, rétablir) ne sont pas faites : sans écran tactile pour les tester, je n'ai pas voulu toucher à la gestion des événements du stylet.
- Vérifié au banc graphique : traits avec et sans stabilisateur, rattrapage, palette contextuelle. 91 tests automatiques.

## 3.23.1 — Dessin II « Peintre »

- **Texture de papier** (Corel Painter), dans le moteur de pinceau (`gimpbrushcore.c`) :
  - le masque du pinceau est multiplié par la luminance du motif actif (papier, papier froissé, toile…), lue dans les coordonnées de l'image : le grain reste fixe sur la feuille ;
  - réglages « Texture de papier », motif, « Grain » (intensité) et échelle, dans la barre d'options du pinceau.
- **QuickShape** (Procreate), pour le pinceau, le crayon, l'aérographe et la plume :
  - garder le stylet immobile 0,8 s en fin de trait le remplace par une ligne (trait presque droit), une ellipse ou un cercle (trait presque fermé) ;
  - même pinceau, une étape d'annulation ;
  - option « QuickShape » dans la barre d'options.
- **Préréglages d'outils** (panneau Préréglages d'outils, dossier PhotoGIMP) :
  - Huile (toile de jute), Gouache, Aquarelle sèche (papier froissé), Fusain, Pastel sec, avec texture de papier et dynamiques de pression ;
  - Pinceau mélangeur humide et sec (outil Barbouiller avec débit de couleur, sans effacement).
- **Pinceau mélangeur** : c'est l'outil Barbouiller de GIMP avec ses options « débit » (mélange de la couleur de premier plan) et « sans effacement ». Pas de nouveau moteur.
- **Aperçu de trait des préréglages** : non fait. Le panneau montre l'icône de l'outil.
- Vérifié au banc graphique : un cercle tremblé devient une ellipse nette. 93 tests.
- **Correctif après le tag** : `tools/build_documents.py` vidait tout le dossier des préréglages en régénérant les « PS-… », ce qui effaçait les nouveaux préréglages de peinture. Il ne supprime plus que ses propres fichiers. Le paquet 3.23.1 a été reconstruit avec la correction.

## 3.23.2 — Dessin III « Atelier / BD »

Nouveau greffon `plug-ins/chopgimp_atelier/` et deux ajouts dans le cœur.
- **Calque de croquis bleu** (Calque > Nouveau calque de croquis) :
  - calque teinté en bleu par un filtre non destructif, marqué « croquis » ;
  - **ignoré à l'export** (masqué pendant l'export, réaffiché ensuite) ;
  - Affichage > Croquis : afficher / masquer.
- **Aplats sous l'encrage** (Calque > Aplats…) : une couleur par zone fermée du calque d'encrage, avec fermeture des petites ouvertures. Le calque « Aplats » est créé sous l'encrage.
- **Outils BD** (Filtres > BD) :
  - **Cases** : planche découpée en N × M cases vectorielles avec gouttières et marge ;
  - **Bulle** : ellipse et queue unies en une seule forme vectorielle (opération booléenne ChopGimp), avec un calque de texte centré ;
  - **Trame** : demi-teintes non destructives (`gegl:newsprint`) ;
  - **Lignes de vitesse** et **lignes concentriques**, en calque vectoriel.
- **Gomme vectorielle** (Calque > Effets de tracé) : retire la sélection de la forme vectorielle. Le résultat reste vectoriel et garde son style.
- **Guides de perspective** (Affichage) : 1, 2 ou 3 points de fuite, sur un calque de croquis verrouillé à 50 %. Il n'y a pas d'aimantation des traits.
- **Harmonies de couleurs** (Couleurs) : complémentaire, triade, analogues, tétrade, complémentaires adjacentes, à partir de la couleur de premier plan. Elles peuvent être enregistrées en palette.
- **Références** (Fenêtres) : une fenêtre toujours au premier plan, avec des onglets d'images ajustées à la taille.
- **Enregistrement en accéléré** :
  - Affichage > Enregistrer en accéléré capture l'image toutes les 2 s si elle a changé (`gimpdir/timelapse/image-N/`) ;
  - Fichier > Exporter > Exporter le timelapse… encode les captures en WebM (VP8, 12 images/s).
- **Tests** : 7 nouveaux tests, 100 au total. Au banc graphique, 3 traits peints pendant l'enregistrement ont donné 2 captures (une toutes les 2 s). L'encodage WebM a été vérifié dans le Flatpak.
- **Correctif pendant les tests** : la forme gommée perdait son nom (GIMP renomme le calque d'après le chemin à l'insertion).
- **Limites** :
  - la capture se fait toutes les 2 s plutôt qu'à chaque trait ;
  - les guides de perspective sont visuels seulement ;
  - les références ne proposent pas de pipette.

## 3.24.0 — Revue finale

Relecture complète du code ajouté, en 4 lots parallèles : cœur C (peinture, affichage, interface), texte et formes (C), import PSD/PDF/SVG (Python), autres greffons et scripts. Environ 110 points relevés et corrigés.

- **Corrections importantes** :
  - l'**enregistrement automatique** ne copiait une image qu'une fois par période de modification (GIMP ne note que la première modification). Un compteur de changements par image le remplace, et le **timelapse** en profite : une capture par changement ;
  - un seul enregistrement automatique par passage (le plus ancien d'abord), pour ne plus figer l'interface avec plusieurs grosses images ;
  - QuickShape : minuteur arrêté quand l'outil change (risque de plantage) ;
  - palette contextuelle : pinceaux et couleurs retenus par référence (plantage si un pinceau était supprimé) ; suivi des pinceaux dès le démarrage ;
  - texture de papier ancrée sur le canevas (elle sautait quand le calque s'agrandissait) et calculée plus vite ;
  - pot de peinture : l'agrandissement du calque et le remplissage forment une seule étape d'annulation ; transformation annulée : le recadrage automatique est annulé aussi ;
  - macros : plus d'actions enregistrées en double, et une macro rejouée s'annule en une fois ;
  - **texte** : la dérive avec Ctrl+poignée sur un texte à effets est corrigée ; l'échelle H/V et le faux italique respectent la rotation ; une mise à l'échelle de l'image change la taille de police au lieu de déformer le texte ; contour en motif conservé avec les effets ; aperçu de police en direct restauré sur le bon calque ;
  - formes : plus de chemins orphelins dans le panneau Chemins après le constructeur de formes, la division, les effets de tracé ou la gomme vectorielle ;
  - export PSD : taille de police en pt/mm convertie, longueurs du texte en UTF-16 (emoji) ;
  - **import PSD** : un fichier tronqué ou malformé ne peut plus bloquer ni planter l'import (essai sur 400 fichiers corrompus). Le fichier est lu par projection mémoire : un PSD de 400 Mo n'occupe plus 400 Mo pour lire ses calques ;
  - import PDF : les pages trop chargées ou en erreur sont vraiment importées en image ; taille de rendu limitée à 16 384 px de côté ;
  - SVG : images liées conservées (la copie sans texte gardait un mauvais dossier de base), rotation autour d'un centre et inclinaisons, plafond d'objets ;
  - « Supprimer l'arrière-plan » et « Options de fusion Si » ne détruisent plus un masque peint par l'utilisateur ;
  - styles de calque : historique jamais laissé gelé après une erreur ; l'opacité s'applique à l'incrustation de couleur et au biseau (le biseau passe à 75 % par défaut) ;
  - Couleurs des styles PS (photogimp_ps) corrigées (sRGB) ;
  - export web, lots, compositions : plus d'images temporaires ni de dossiers laissés derrière ; « Exporter tout » ne modifie plus l'image ouverte ;
  - agrandissement IA : mémoire fortement réduite (traitement par bandes) ; mise à l'échelle selon le contenu et aplats nettement plus rapides ;
  - BD : la bulle et les lignes concentriques prenaient toute l'image quand il n'y avait pas de sélection (test de sélection inversé) ;
  - export timelapse : chemin du fichier passé proprement à GStreamer.
- **Nettoyage** : code mort, imports inutiles, doublons (actions de réglage, redessin des outils), traces du journal de session qui sortaient aussi dans le terminal, injecteur de plantage sans fuite.
- **Compilation** : plus aucun avertissement dans le code ChopGimp (dont un format `printf` décalé dans le panneau Caractère, et une lecture d'un octet de trop dans l'export SVG).
- **Construction** : le dépôt OSTree (`flatpak/repo`, plusieurs Go) n'est plus recopié à chaque compilation.
- 100 tests verts ; vérifié au banc : 3 traits pendant l'enregistrement en accéléré donnent maintenant 4 captures.
- **Restent ouverts** (notés pour la suite) :
  - axes des polices variables (curseurs graisse/chasse…) : non faits, c'est un chantier à part ;
  - un calque SVG masqué est importé vide ;
  - le panneau texte se rafraîchit encore par minuteur (mais plus quand il est caché) ;
  - nettoyage en profondeur (scripts v1 en doublon, anciens scripts, module commun aux greffons) : à valider à l'étape 18.

## 3.24.1 — Légèreté et nettoyage en profondeur

Sauvegarde préalable : tag `backup-avant-nettoyage-3.24.1` (dépôt et sources GIMP, poussé) et archive `.backups/avant-nettoyage-3.24.1.tar.gz`.

**Mesures avant / après**

| Mesure | 3.24.0 | 3.24.1 |
|---|---|---|
| Paquet à télécharger | 96 Mo | 83 Mo |
| Taille installée | 402 Mo | 328 Mo |
| Réveils au repos (fil principal) | ≈ 5,6 /s | ≈ 1 /s |
| Processeur au repos (30 s) | < 0,1 % | < 0,1 % |
| Mémoire au repos (interface, une image) | 186 Mo | 184 Mo |
| Démarrage console (à chaud / premier lancement) | 2,3 s / 17 s | inchangé |

- **Paquet allégé** :
  - traductions limitées au français et à l'anglais (84 autres langues retirées, ≈ 55 Mo) ;
  - numpy sans ses tests ni f2py, onnxruntime sans ses outils de développement (≈ 28 Mo) ;
  - en-têtes et fichiers pkg-config retirés.
- **Plus d'interrogation périodique** :
  - les panneaux Caractère, Paragraphe, Glyphes et Textes du document se mettent à jour sur signaux (changement d'image, de calque, de texte, annulation) au lieu de minuteurs à 0,4–0,7 s. Un panneau caché ne suit plus rien ; il se met à jour quand il réapparaît ;
  - le suivi des images ouvertes du traceur de plantage ne tourne plus qu'après un changement.
  - Il ne reste au repos que l'enregistrement automatique (toutes les 5 min).
- **Nettoyage** :
  - module commun `plug-ins/_common/chopgimp_common.py` (couleurs sRGB, parasites, copie du style vectoriel, suppression d'un calque et de ses chemins, appels PDB, parcours des calques), copié dans chaque greffon à l'installation et utilisé par les 12 greffons. Les copies divergentes (source de plusieurs bugs) disparaissent ;
  - scripts v1 en doublon retirés, chacun remplacé par l'équivalent ChopGimp : compositions de calques, mise à l'échelle selon le contenu, texte déformé et effets de texte, lorem ipsum, développement RAW (Camera Raw), export des calques, export par lots, processeur d'images. Les effets « néon », « chrome » et « 3D » en un clic n'existent plus ; on les obtient par les styles de calque ;
  - 27 scripts v1 désactivés depuis longtemps retirés du dépôt, avec leur liste ;
  - ancien installeur Snap, lanceur et outils d'audit v1 retirés ; branches « v2 » des générateurs supprimées ;
  - recherche de commandes : entrées pointant vers les commandes ChopGimp, et seules les commandes réellement présentes sont proposées ;
  - code mort et imports inutiles.
- **Non fait, volontairement** :
  - fusion des 90 patchs : sans gain à l'exécution, et risque de casser l'historique des corrections ;
  - plafonds mémoire de GIMP (cache de tuiles, historique) laissés tels quels : ce sont des maxima, utilisés seulement si besoin ; les réduire ralentirait les grosses images ;
  - un pic de mémoire très bref (≈ 0,1 s, ≈ 350 Mo) au démarrage du cœur, dont l'origine n'est pas identifiée. Il n'a pas d'effet ensuite (55 Mo en console).
- 100 tests verts ; vérifié au banc : panneau Caractère à jour après création d'un texte, réveils au repos mesurés.

## 3.24.2 — Retours d'utilisation

- **Ctrl + clic sur la vignette d'un calque** (contour des pixels, comme Photoshop) : le calque cliqué n'est plus retiré de la sélection des calques. Avant, il fallait le resélectionner, et le pinceau n'affichait plus son cercle, faute de calque où peindre.
- **Tampon de duplication** : pendant le choix d'une nouvelle source, plus de croix à l'ancienne source.
- **Style de calque (Contour…)** : la fenêtre se fermait aussitôt ouverte chez l'utilisateur, sans erreur (non reproduit au banc). Une fermeture reçue moins d'une seconde après l'ouverture est maintenant ignorée, et chaque réponse est notée dans le journal de session (« [style de calque] réponse … »).
- **Banc graphique** : l'arrêt tue aussi les services de sa session privée. Ils s'accumulaient à chaque essai (environ 800 processus) et ont saturé les connexions D-Bus de l'utilisateur, ce qui empêchait d'installer le paquet.
- Restent à traiter : lenteur du Ctrl + clic sur un calque très détaillé.

## 3.24.3 — Fenêtres des greffons refermées aussitôt

- **Cause** : sous Ubuntu, GNOME accroche les fenêtres modales à leur parent (`attach-modal-dialogs`, activé par défaut). Une fenêtre de greffon modale, rattachée à la fenêtre de ChopGimp (un autre processus), était refermée dès son ouverture, plus de 2 000 fois par seconde. Étaient touchés : Style de calque (Contour, Lueur externe, Ombre interne), Camera Raw, Exporter pour le web, Harmonies, outils BD, IA, import PDF… Les fenêtres de réglage standard de GIMP (Ombre portée) n'étaient pas touchées.
- **Correction** (libgimp) : les fenêtres de greffons rattachées à ChopGimp ne sont plus modales. Le marquage n'avait aucun effet entre deux processus.
- Le traceur provisoire de la fenêtre Style de calque est retiré.
- **Banc graphique** : il active désormais `attach-modal-dialogs` comme Ubuntu. Son arrêt ne laisse plus de processus.
- Vérifié au banc avec le réglage d'Ubuntu : Camera Raw et Style de calque > Contour restent ouverts.

## 3.24.4 — Styles de calque cohérents : une fenêtre de filtre par effet

Demande de l'utilisateur : chaque style s'ouvre « dans le même style que l'ombre portée », en réutilisant et en améliorant ce qui existe au lieu de le réinventer.
- **Calque > Style de calque** (et le même sous-menu dans le panneau Calques) : Ombre portée, **Contour…**, **Lueur externe…**, **Ombre interne…**, **Lueur interne…**, Biseau, Incrustation couleur, Ombre longue, Estampage. Tous ouvrent la fenêtre de filtre de GIMP : aperçu en direct, préréglages, « Appliquer directement au calque », modifiable ensuite par l'icône fx.
- Contour, Lueur externe, Ombre interne et Lueur interne sont de nouvelles actions `filters-chopgimp-*`, qui ouvrent la fenêtre du filtre GEGL avec des réglages de départ :
  - Contour : ombre portée sans décalage ni flou, épaisseur 3, noir, opacité 1 ;
  - Lueur externe : flou 18, jaune clair ;
  - Ombre interne : lueur interne noire décalée de 4 px ;
  - Lueur interne : jaune clair, flou 10.

  Pour cela, une action de filtre interactive accepte maintenant « opération\n(réglages) », un format que GIMP savait déjà lire pour ses filtres préréglés.
- **Amélioration de l'existant** : le filtre GEGL « lueur interne » ne rend que la lueur. Appliqué en mode Remplacer (le défaut de GIMP), il rendait l'intérieur du calque transparent. Ombre interne et Lueur interne l'appliquent en mode Normal.
- Panneau Caractère : les boutons Ombre… et Contour… ouvrent ces mêmes fenêtres.
- La fenêtre ChopGimp qui regroupe tous les effets reste dans le sous-menu, sous le nom « Style de calque (fenêtre)… ». Elle sert aussi aux scripts et à l'import PSD. Les entrées par effet n'y mènent plus.
- Vérifié au banc : les quatre fenêtres s'ouvrent avec leurs réglages et leur aperçu. 100 tests.

## 3.24.5 — Vrai filtre Contour et fenêtres au style de GIMP

- **Calque > Style de calque > Contour…** est un vrai filtre GEGL, `chopgimp:stroke`. Il reste réglable par l'icône fx, est enregistré dans le XCF et suit l'objet quand on le retouche. Il reprend les options d'Édition > Tracer la sélection :
  - position extérieur / centre / intérieur, épaisseur, couleur, opacité, anticrénelage ;
  - pointillés (les préréglages de GIMP), extrémités, jointures (arrondies par défaut), limite d'onglet ;
  - seuil d'opacité du bord.

  Le contour est calculé à partir du bord des pixels avec le code de GIMP (`gimp_boundary_find`, motifs de tirets), puis tracé avec cairo et composé en virgule flottante.
  - La fenêtre est celle, native, des filtres GIMP (même présentation que l'Ombre portée).
  - **Non repris** : le motif (la fenêtre automatique des filtres n'a pas de sélecteur de motif) et le tracé avec un outil de peinture (impossible dans un filtre). Pour ces cas, Édition > Tracer la sélection reste disponible.
  - Les deux listes du filtre (Position, Pointillés) sont dans libgimpbase, comme GimpCapStyle et GimpJoinStyle : greffons et scripts peuvent lire et régler ce filtre (`Gimp.ContourPosition`, `Gimp.ContourDash`).
- **Fenêtres des greffons ChopGimp au style de GIMP** : curseurs GimpSpinScale (libellé dans la barre), boutons de couleur GIMP, cadres titrés, marges de GIMP.
  - Fenêtres concernées : Style de calque (fenêtre), largeur et position du contour, Camera Raw, instantanés, Options de fusion « Si », calque de couleur, outils BD, harmonies, export web, lots, compositions, effets vivants, mise à l'échelle selon le contenu, effets de texte, IA, import PDF, polices absentes et rapport PSD.
  - Éléments communs dans `chopgimp_common.py` : `spin_scale`, `color_button`, `frame`, `check_frame`…
- 3 nouveaux tests (contour extérieur, intérieur, pointillés) : 103 tests.
- Vérifié au banc : fenêtre Contour avec aperçu, Style de calque, Camera Raw, Cases de BD. Non vérifié : enregistrement XCF puis réouverture d'un calque avec Contour.

## 3.24.6 — Peinture fluide sur les calques avec effets

- **Symptôme** : gommer ou peindre sur un calque portant un effet (ombre portée, contour…) rendait tout lent, avec un curseur saccadé.
- **Mesure** (journal de performance de GIMP, affiche de 2480 × 3508 avec ombre portée, même coup de gomme) : le fil principal passait 41 de ses 59 échantillons actifs dans `gimp_projection_flush_now`. GIMP y recalcule l'image sur place, effet compris, toutes les quelques millisecondes pendant le trait, et le curseur attend la fin de chaque calcul.
- **Correction** (`gimppainttool-paint.c`) : quand un calque visible de l'image porte des effets, le rendu pendant le trait passe par le rendu en morceaux de GIMP (`gimp_projection_flush`), qui rend la main entre deux morceaux et répartit le travail sur les fils de calcul. Sans effet, rien ne change. Après correction : 0 échantillon dans le recalcul immédiat.
- **Vignettes recadrées** : le cadrage était calculé sur tout le calque en pleine résolution après chaque trait (≈ 0,6 s mesurée sur l'affiche). Il est maintenant estimé sur une copie réduite (512 px de côté au plus, en virgule flottante pour ne rater aucun pixel pâle), avec une marge d'un échantillon. Les outils (recadrage au contenu…) gardent le calcul exact.
- 103 tests verts ; vérifié au banc : trait de gomme, ombre portée et vignette à jour.

## 3.24.7 — Effets de calque : peinture fluide

Constat de l'utilisateur : peindre ou gommer sur un calque avec effets est lent, même sur l'écran du portable (DisplayLink écarté). Confirmé après correction : « c'est mieux, le problème vient du calcul de l'effet ».
- **Flou des ombres et lueurs limité à la zone touchée** (patch GEGL `0002-layer-styles-fir-blur`) :
  - en mode AUTO, le flou gaussien de GEGL passe en IIR dès σ ≥ 1, et l'IIR exige des lignes et colonnes entières (`gblur-1d.c`, `get_required_for_output`), donc tout le calque à chaque touche ;
  - `gegl:dropshadow` (Ombre portée, Lueur externe, ancien Contour) passe en FIR jusqu'à σ 40 ; `gegl:inner-glow` et `gegl:bevel` toujours en FIR (rayons ≤ 40 et ≤ 8) ;
  - environ 12 fois plus rapide sur une zone de 64 px, pour une différence invisible (≤ 8/255 sur les bords).
- **Rendu des effets mis en mémoire par calque** : un nœud `gegl:cache` est placé après les filtres et avant opacité, mode et masque, et actif seulement s'il y a des effets. Peindre sur un calque ne recalcule plus les effets des autres calques.
- **« Effets à la fin du trait »** (option des outils de peinture, activée par défaut, aussi dans la barre d'options) : pendant un trait, les effets du calque peint sont court-circuités dans le graphe de rendu (pas de modification du filtre, de l'historique ni du fichier). Ils sont recalculés une fois au relâchement. Ils sont aussi rétablis à l'annulation, au changement d'outil, à la fermeture et en cas d'échec.
- Mesure sur la session de l'utilisateur pendant qu'il peint : le fil du curseur reste léger la plupart du temps. Il reste un à-coup de 0,5 à 1 s à chaque relâchement (recalcul des effets), à traiter.

## 3.24.8 — Traits sans paliers : la peinture n'est plus aimantée

- **Symptôme** : des paliers horizontaux dans les traits, toujours à la même hauteur (le milieu du document), même dans une image neuve.
- **Cause** : dans GIMP, les outils de peinture suivent l'aimantation (guides, bords et milieu du canevas, bords des calques, espacements), et ChopGimp l'active par défaut pour les guides intelligents. Sur un trait en biais, la hauteur restait collée à la ligne d'accroche pendant que la main avançait : un palier. Confirmé par l'utilisateur en décochant une aimantation.
- **Correction** : comme dans Photoshop, les outils de peinture (pinceau, crayon, aérographe, gomme, tampon, correcteur, doigt, plume, MyPaint…) ne sont plus jamais aimantés. Déplacement, sélections, formes, transformations et guides le restent.
- 103 tests verts ; vérifié au banc : traits en biais à travers le milieu, sans palier.

## 3.24.9 — Menus : les cases à cocher laissent le menu ouvert

- Un clic sur une case à cocher ou un choix d'option (Affichage > Afficher…, Aligner sur…, etc.) bascule l'option **sans refermer le menu**. On peut en régler plusieurs d'affilée. Les commandes ordinaires et le clavier ferment toujours le menu (`gimpmenu.c`, interception du relâchement du clic gauche).
- Vérifié au banc : « Afficher la grille » puis « Aligner sur la grille » dans le même menu ouvert.
- L'utilisateur confirme que QuickShape et l'à-coup de fin de trait ne se manifestent plus : c'étaient des effets de l'aimantation, corrigée en 3.24.8.

## 3.24.10 — Barre d'espace comme Photoshop, croix sur les petites brosses

- **Espace** (réglage « déplacer la vue », par défaut) :
  - l'appui affiche aussitôt la **main** ; bouger la souris ne déplace plus rien ;
  - **Espace + clic maintenu + glisser** déplace la vue, sans trace de pinceau ; on peut relâcher le bouton et recommencer tant qu'Espace est enfoncé ;
  - au relâchement d'Espace, l'outil et son curseur reviennent ;
  - Espace + Maj / Ctrl (rotation, zoom) fonctionnent au glisser ; le bouton du milieu marche comme avant ; Espace se tape toujours dans un texte.
- **Petites brosses** : sous 10 px à l'écran, une croix de visée (11 px, contrastée) s'affiche au centre du cercle de la brosse.
- Vérifié au banc : main dès l'appui sur Espace, vue déplacée par Espace + glisser sans trace, cercle rétabli au relâchement, croix sur une brosse de 4 px. 103 tests.

## 3.24.11 — Copier / coller le style de calque

- **Calque > Style de calque** (et menu clic droit du panneau Calques) :
  - **Copier le style de calque** : mémorise tous les effets du calque actif, avec leurs réglages, opacité, mode, région et visibilité. C'est un instantané : modifier ou supprimer le calque source ensuite ne change rien. Il marche d'une image à l'autre.
  - **Coller le style de calque** : remplace les effets de tous les calques sélectionnés par ceux copiés, en une seule étape d'annulation (comme Photoshop).
  - **Coller le style de calque (en ajoutant)** : garde les effets existants et ajoute les copiés par-dessus.
- **Liste des effets (icône fx)** : un bouton **Copier** ne met que l'effet choisi dans le presse-papiers.
- Repose sur le mécanisme de GIMP qui recopie les effets lors de la duplication d'un calque. La création des effets collés suit la duplication et le chargement XCF.
- Vérifié au banc : style copié de « Haut », collé sur « Milieu » (ombre portée visible), annulé en une fois ; entrées du menu présentes. 103 tests.

## 3.25.0 — Passe de performance, styles de calque complets, traduction

**Mesures sur la copie de l'affiche de l'utilisateur** (`tools/dev/bench-all.sh`, médiane de 3, avec effets) :

| Geste | CPU total 3.24.11 → 3.25.0 | Blocage max de l'interface |
|---|---|---|
| Ouverture | 3,58 s → 2,15 s | 229 → 113 ms |
| Trait | 0,87 → 0,80 s | 41 → 25 ms |
| Déplacer un calque | 4,18 → 3,46 s | ~300 → ~285 ms |
| Masquer un calque | 0,66 → 0,58 s | ~310 → ~285 ms |
| Ctrl+clic vignette | 1,34 → 1,27 s | ~970 → ~960 ms |

Restent à traiter (identiques avec ou sans effets) : blocages au déplacement, au masquage et au Ctrl+clic.

- **Affichage** : rendu de la projection par tranches de 8 ms pendant l'action ; « Aperçu rapide » (barre d'options) : seule la zone visible est rendue pendant l'action, le reste 200 ms après ; mise à jour du trait calée sur l'horloge d'affichage.
- **Effets** : flou de l'ombre et des lueurs sur l'alpha seul (patch GEGL 0004, ×2,5 à ×3,5) ; Contour calculé sur la zone demandée ; cache des effets préservé (translate/crop non réécrits à l'identique) ; seule la zone peinte recalculée au relâchement ; groupes à effets mis à jour localement ; texte non rendu s'il n'a pas changé ; réglages des fenêtres de filtre regroupés ; doublon de cache supprimé ; correctif amont buffer-source-validate.
- **Panneaux** : copie réduite (512 px) du rendu des effets pour les vignettes, mise à jour par zones ; vignettes et Navigation limitées à 2 rafraîchissements/s ; histogramme non bloquant (échantillon pendant le travail) ; panneau Calques mis à jour au plus toutes les 250 ms ; contour de sélection (gimpboundary) et fourmis rapides ; Tableau de bord : groupe « Réactivité ».
- **Système** : mimalloc (lanceur `/app/bin/chopgimp`, `CHOPGIMP_NO_MIMALLOC=1` pour couper) ; babl et GEGL en -O3 + LTO (`make build LTO=0` pour revenir) ; PGO en option (`make build PGO=1`, non essayé) ; sauvegarde automatique repoussée pendant le travail ; mesures `tools/dev/bench-all.sh`.
- **Styles de calque façon Photoshop** : Contour avec remplissage Couleur / Dégradé (6 styles dont éclat de forme) / Motif, mode de fusion, surimpression ; glisser sur l'image pour déplacer ombre, ombre interne, lueurs, dégradé ou motif ; lueurs : bruit, source dégradé, courbes de contour, plage (patch GEGL 0005, `gegl:glow-map`) ; « Ajouter un autre contour » et numérotation dans la liste fx ; « Définir par défaut » / « Rétablir ». Non fait : mode de fusion de l'ombre portée et de la lueur externe (demande le fond sous le calque), « Aligner sur le calque », technique précise.
- **Traduction** : ~650 libellés de menus et de filtres (gimp, plug-ins, GEGL : patch 0003) ; liste dans `docs/dev/traductions-3.25.0.tsv`. **Pixelliser le style de calque** (Calque > Style de calque).
- Vérifié : 103 tests ; fenêtre Contour au banc (dégradé linéaire et éclat de forme).

## 3.25.1 — Fin de la passe de performance (blocages, cache XCF, rendu en arrière-plan, styles fusionnés, babl)

**Mesures** (`tools/dev/bench-all.sh`, copie de l'affiche avec effets, médiane de 3 ; machine parfois chargée, comparaisons faites en alternance) :

| Geste | Blocage 3.24.11 | 3.25.0 | 3.25.1 |
|---|---|---|---|
| Déplacer un calque | ~300 ms | ~285 ms | 11–22 ms |
| Masquer un calque | ~310 ms | ~285 ms | 7–13 ms |
| Ctrl+clic vignette | ~970 ms | ~960 ms | 18–60 ms |
| Trait | 41 ms | 25 ms | 6–12 ms |
| Ouverture (CPU total) | 3,58 s | 2,15 s | 2,1–2,4 s ; **0,78 s** si le fichier a été enregistré par la 3.25.1 (cache des effets) |

- **Blocages** (cause : l'outil Déplacement recalculait les bords du calque à chaque étape d'annulation, via une conversion babl lente ; et le Ctrl+clic attendait un verrou global de babl) : bords du calque en cache, lecture directe de l'alpha (`chopgimp-alpha-bounds.c`), extraction directe dans `gimp_channel_new_from_alpha`.
- **babl** (patchs `patches/babl-0.1.128/`, nouveau mécanisme dans `make_manifest.py`) : 48 conversions directes vers « A <type> » (×30 à ×300, identiques au bit près), verrou de la conversion de référence restreint (`BABL_REFERENCE_FULL_LOCK=1` pour revenir).
- **Cache des effets dans le XCF** (`chopgimp-fx-cache.c`, propriété privée « CHOP », ignorée par GIMP standard) : les effets déjà calculés sont enregistrés et réutilisés à l'ouverture si rien n'a changé (clé SHA-256). Coupure : `[xcf] fx-cache=false` dans chopgimprc ou `CHOPGIMP_NO_XCF_FX_CACHE=1`. Fichier +2 Mo sur l'affiche.
- **Styles de calque fusionnés** (`chopgimp:layer-style-fused`) : ombre, contour, lueurs et ombre interne consécutifs calculés en une passe (−30 à −40 % sur 4 effets). Coupure : `CHOPGIMP_NO_FUSED_STYLES=1`.
- **Rendu en arrière-plan** (fil de rendu + verrou du graphe, patch GEGL 0006) : case « Rendu en arrière-plan », **désactivée par défaut** (ouverture plus légère pour l'interface, mais trait 2× plus coûteux pour le fil principal) ; aucun gel sur 24 essais par geste. Coupure : `CHOPGIMP_NO_THREADED_RENDER=1`.
- **Brouillons** : pendant une action à la souris/stylet, zones modifiées rendues en résolution réduite puis affinées (cache GEGL rendu compatible avec les niveaux). Les brouillons au repos quand on dézoome ont été retirés : ils doublaient le travail à l'ouverture (+80 % mesuré). Coupure : `CHOPGIMP_NO_DRAFT=1`.
- **Banc** : `BENCH_GIMPRC` pour régler une préférence du banc.
- **Reporté en 3.25.2** : GIMP compilé avec LTO + PGO (version compilée et 103 tests réussis, pas encore mesurée).
- Vérifié : 103 tests.

## 3.26.0 — Barre d'options compacte

- Maquette validée par l'utilisateur : `docs/maquettes/barre-options.html`.
- **Champ compact** (`app/widgets/chopgimp-value-field.c`) pour tous les réglages chiffrés de la barre : « 51 px ▾ », « Dureté 50 % ▾ ». ▾ ouvre un petit curseur (même courbe que l'ancien curseur, gamma 1,7 pour la taille) ; glisser sur le libellé change la valeur (Maj = fin) ; saisie (virgule acceptée, Entrée / Échap) ; molette ; ↑/↓ (Maj ×10).
- **Plus de défilement** : la barre n'est plus dans une fenêtre défilante. Ce qui ne tient pas passe dans « ⋯ N » (priorité par réglage : taille, police, mode, opacité gardés en dernier), et revient quand la fenêtre s'élargit. Dernière ligne de ⋯ : « Toutes les options de l'outil… ».
- **⚡** : Aperçu rapide et Rendu en arrière-plan dans un menu (en bleu si l'un est actif).
- Séparateurs entre groupes (« | » dans `bar_specs[]`), sélecteur de police élargi, liste Mode réduite (12 caractères), libellés lisibles.
- Correctif : le Flux de l'aérographe (déjà 0–100) était affiché ×100.
- Banc : `CHOPGIMP_GUITEST_SIZE=1280x800` pour tester une largeur de portable.
- Vérifié au banc : Pinceau et Texte à 1600 et 1280 px (aucun défilement, ⋯ 5 / ⋯ 7), curseur de Dureté, menu ⋯ ; 103 tests.
- Restes connus : pas de calcul dans la saisie (« 2*5 ») ; unités de l'approche et de l'interlignage non affichées ; le reste de la modernisation (curseurs des fenêtres, styles de calque unifiés, panneaux, icônes, styles d'interface) est gardé pour plus tard (plan).

## 3.26.1 — Curseurs façon Photoshop, Style de calque unifié, panneaux modernisés

- **Curseurs façon Photoshop partout** (`GimpSpinScale` amélioré) : libellé, curseur fin à poignée ronde, valeur + unité ; plus de − / + ; glisser sur la piste ou le libellé, Maj = fin. `CHOPGIMP_CLASSIC_SPIN_SCALE=1` pour l'ancien curseur.
- **Fenêtres de filtres** : boutons en bas (Réinitialiser à gauche, Annuler / Valider à droite), « ? » pour l'aide, options techniques dans « Avancé » (replié, mémorisé).
- **Fenêtre « Style de calque » unifiée** (Calque > Style de calque > Options de fusion…, bouton fx, double-clic dans la liste fx) : effets à gauche avec cases à cocher, réglages à droite, « + » pour un second Contour / Ombre portée, une seule étape d'annulation.
- **Mode de fusion de l'ombre portée et de la lueur externe** sur les calques du dessous (Produit / Écran par défaut ; patch GEGL 0007 ; `CHOPGIMP_NO_BEHIND_MODES=1`). Anciens fichiers identiques. Limites : groupe « Traverser », pixelliser / fusionner (ombre figée en Normal), pas de cache XCF pour ces ombres.
- **Panneaux** (`CHOPGIMP_CLASSIC_PANELS=1` pour revenir) : onglets icône + nom (soulignement accent, ⋮), barres de boutons regroupées, panneau Calques (Mode + Opacité sur une ligne, vignettes arrondies, œil / cadenas discrets, bande « Effets » du calque actif), panneau Couleur compact.
- **Cache des effets XCF** : clé stable (`CHOPGIMP_FX_RENDER_VERSION` dans `app/core/chopgimp-fx-render-version.h`) — **à incrémenter à chaque changement du rendu d'un effet** — au lieu de l'identifiant de compilation ; il survit donc aux mises à jour.
- **Rendu en arrière-plan** : contrôle du graphe au plus toutes les 250 ms (cause du surcoût pendant un trait), petites zones sur le fil principal. Toujours désactivé par défaut, **à mesurer**.
- **Finitions** : calculs dans les champs de la barre (« 2*5 »), unités (approche px, interligne, Déformation %), « Aide », unités dans les fenêtres des greffons, ombres « Produit » visibles dans les vignettes, Contour « Aligner sur le calque » / « Lier au calque », opacités des styles en %.
- Vérifié : 103 tests ; banc : fenêtre Style de calque, panneaux, onglets (après correction des noms réduits à « … »).
- Non fait / à surveiller : pipette sur le calque sans les effets (comportement GIMP) ; pendant la fenêtre Style de calque, une action sur l'image va dans la même étape d'annulation ; mesure du rendu en arrière-plan.

## 3.27.0 — Objets vectoriels (lots V1, V2 et repères du plan docs/PLAN-VECTEURS.md)

- **Calque vectoriel multi-objets** (`app/path/chopgimp-vobject.c`) : chaque objet a son tracé, fond (couleur, dégradé linéaire/radial, motif), contour (couleur, épaisseur, alignement intérieur/centre/extérieur, tirets…), opacité, mode, transformation, visibilité, verrou ; groupes, masque d'écrêtage. Rendu cairo par objet (cache, zone modifiée seule). XCF : parasite `chopgimp-vobjects` ; GIMP standard voit le rendu et toute la géométrie (tracé du calque = tous les sous-tracés). Anciens fichiers identiques au pixel (rendu GIMP tant que le calque n'est pas modifié en objets). Annulation : une étape par action. `CHOPGIMP_NO_VOBJECTS=1` pour revenir à 3.26.
- **Commandes** : Fusionner en un calque vectoriel, Dissocier en calques, Décomposer les sous-tracés en objets (les trous restent avec leur contour).
- **Outil Déplacement (V) en mode objets** sur un calque multi-objets : clic, Maj+clic, rectangle de sélection, cadre à 8 poignées (Maj proportions, Alt depuis le centre), rotation (Maj 15°), Alt+glisser duplique, flèches (Maj ×10), double-clic entre dans un groupe, Échap, Suppr.
- **Repères commentés** (`app/tools/chopgimp-vsnap.c`) : aimantation aux bords, centres, nœuds des objets, autres calques, canevas, repères, grille ; lignes magenta, distances, espacements égaux ; Ctrl désactive. Nouveau : Affichage > « Aligner sur les pixels ».
- **Sélection directe (A)** : nœuds de l'objet cliqué seulement. **Forme (U) et Plume** : option « Ajouter au calque vectoriel actif » (par défaut).
- **Bâtisseur de formes et Pathfinder** sur les objets sélectionnés (PDB `chopgimp-vobjects-pathfinder`, `chopgimp-vobjects-command`).
- **Menu Objet** (après Calque) : Grouper / Dissocier, Disposition, Aligner et répartir, Verrouiller / Masquer, Masque d'écrêtage (Ctrl+7), Pathfinder, Pipette de style, Sélectionner tous les objets, Supprimer, et les 3 commandes ci-dessus. Raccourcis : Ctrl+G et Ctrl+] [ agissent sur les objets quand des objets sont sélectionnés ; Maj+Ctrl+G, Ctrl+2/3/7 (+Alt).
- **Barre d'options en mode objet** : Fond, Contour, Épaisseur, Opacité, X / Y / L / H, Rotation.
- Vérifié : 103 tests ; tests gimp-console (booléens, masque d'écrêtage + XCF, alignements, groupes, verrous) ; banc : 3 formes dans un calque, sélection et déplacement d'une seule.
- Limites connues : Plume = 2 étapes d'annulation pour un nouvel objet ; redimensionner met aussi à l'échelle l'épaisseur du contour ; la sélection d'objets n'est pas enregistrée ; pour déplacer tout un calque multi-objets, passer par le panneau Calques ; modes de fusion rares approchés.
- Suite du plan : 3.27.1 (panneaux Objets / Aspect / Contour, import-export par objet, couleurs globales, Redéfinir les couleurs), 3.27.2 (Vectoriser), 3.27.3 (Largeur, Peinture dynamique, Symboles, Distorsion).

## 3.27.1 — Correctif : mode objets sur tout calque vectoriel

- Signalé par l'utilisateur : formes dessinées, « Créer un calque vectoriel » (barre de la Plume), puis V ne manipulait pas les formes séparément.
- Causes : le mode objets de V exigeait ≥ 2 objets ; « Créer un calque vectoriel » mettait tous les sous-tracés dans un seul objet ; l'option « Ajouter au calque vectoriel actif » de la Plume ne se déclenchait jamais (clic dans le vide vu comme « ajout de point »).
- Corrections : V passe en mode objets sur **tout** calque vectoriel (une forme seule a son cadre) ; « Créer un calque vectoriel » crée **un objet par forme séparée** (trous conservés) ; la Plume crée bien un nouvel objet sur un clic dans le vide. Sélectionner ne change pas le rendu (tant qu'on ne modifie pas). PDB `gimp-vector-layer-new` inchangé pour les scripts.
- Vérifié : 103 tests ; tests console (2 rectangles → 2 objets, carré troué + rectangle → 2 objets, rendu inchangé après sélection) ; banc : une forme seule sélectionnée avec poignées.

## 3.27.2 — Panneaux Objets / Aspect / Contour, couleurs globales, import-export par objet

- **Liste « Objets »** sous les calques : sélection synchronisée avec le canevas, œil, verrou, renommer (double-clic), glisser-déposer (ordre, groupes), « (vide) » / « (masque d'écrêtage) ».
- **Aspect** : plusieurs fonds et contours par objet (couleur, dégradé, motif, opacité, mode, visibilité, ordre). Format XML des objets **version 2** (la version 1 reste lue).
- **Contour** : épaisseur, alignement, extrémités, angles, limite, tirets, flèches (triangle, flèche, cercle, carré, barre), profils d'épaisseur.
- **Couleurs globales** (`app/path/chopgimp-vcolors.c`, parasite d'image `chopgimp-global-colors`) : panneau « Couleurs globales » (nouvelle, modifier en direct, renommer, supprimer, appliquer au fond / contour, délier), section dans les listes de couleurs de la barre d'options et d'Aspect (◆ = couleur liée).
- **Objet > Redéfinir les couleurs…** : couleurs groupées par teinte, actuelle → nouvelle, harmonies, Réduire à N (k-means Lab), Assigner les couleurs globales, curseurs TSL, aperçu, une seule annulation.
- **Import SVG** (lecture XML directe) : un calque vectoriel par calque Inkscape, un objet par forme, groupes, noms, transformations, dégradés vectoriels, masques d'écrêtage, opacités, flèches reconnues. **PDF / AI / EPS** : un objet par élément, masques et dégradés vectoriels. Plus de plafond à 1 500 objets (sécurité 50 000). Option « Fusionner les objets de même style ».
- **Export SVG** : un `<path>` par objet, groupes, `<clipPath>`, dégradés, piles Aspect, marqueurs (flèches), profils en contour plein, couleurs globales en nuances Inkscape.
- **Correctifs** : dupliquer un calque ou une image ne remplace plus le dégradé du premier objet par sa couleur ; décalage d'un demi-pixel à l'aller-retour SVG.
- Vérifié : 106 tests (dont aller-retour SVG dans GIMP) ; tests console t4–t7 ; banc : liste Objets, panneau Aspect, Redéfinir les couleurs.
- Limites : panneau Aspect tassé dans son emplacement par défaut ; boutons de la fenêtre Redéfinir en haut ; glisser une couleur globale sur le canevas et réordonner les couleurs : non faits ; masques SVG, filtres et motifs SVG non importés ; les profils d'épaisseur ignorent l'alignement et les tirets.

## 3.27.3 — Vectoriser (lot V5) et vectorisation dynamique (lot V6 point 4)

- **Correctifs de la 3.27.2** : la fenêtre « Redéfinir les couleurs » a ses boutons en bas (plus de barre d'en-tête, même si GNOME la demande) ; la liste du panneau Aspect fait au moins 150 px de haut, l'emplacement du dock s'agrandit au lieu de la tasser.
- **Calque > Vectoriser…** et **Objet > Vectorisation** (`app/dialogs/chopgimp-trace-dialog.c`), comme la Vectorisation dynamique d'Illustrator :
  - paramètres prédéfinis (Par défaut, Photo haute / basse fidélité, 3 / 6 / 16 couleurs, Niveaux de gris, Logo noir et blanc, Croquis, Silhouettes, Dessin au trait, Dessin technique, Pixel art) ;
  - Vue (Résultat, Contours, Contours + source), Mode (Couleur, Niveaux de gris, Noir et blanc), Palette (Automatique, Limitée, Couleurs globales du document, Nuancier actif), Couleurs / Fidélité / Seuil ;
  - Avancé : Chemins, Angles, Bruit, Lissage, Méthode (Adjacent / Superposé), Fonds / Contours (épaisseur max., longueur min.), Arrondir les courbes en lignes, Ignorer le blanc, Ignorer la transparence, Inverser, Grouper par couleur, Moteur (potrace, tracé central, pixel art) ;
  - **aperçu vectoriel sur le canevas** (net à tout zoom), calculé dans un fil séparé 250 ms après le dernier réglage (le calcul précédent est annulé), barre de progression et « Arrêter » pour les longs calculs, statistiques chemins · couleurs · points d'ancrage ;
  - « Sélection seulement », « Masquer l'original », fenêtre non modale (on peut zoomer pendant l'aperçu).
- **Résultat** : un nouveau calque vectoriel au-dessus de la source, un objet par forme, un groupe par couleur ; une seule annulation.
- **Vectorisation dynamique** (`app/core/chopgimp-trace-layer.c`) : le calque garde l'image source (PNG, sélection dans l'alpha) et les réglages (parasite `chopgimp-trace`, gardé par le XCF et la copie du calque). « Options de vectorisation… » (menu Objet, bouton « Vectorisation… » de la barre d'options en mode objet) revectorise sur place ; si les objets ont été retouchés depuis, la fenêtre prévient que « Appliquer » les remplace (« Décomposer » les garde). « Décomposer » oublie la source : objets ordinaires. Choix : retoucher les objets ne décompose pas automatiquement (comme Illustrator, la vectorisation reste réglable jusqu'à « Décomposer »).
- **PDB** : `chopgimp-image-trace` (calque, préréglage + réglages, sélection seulement, dynamique) et `chopgimp-image-trace-command` (options, edited, expand, retrace).
- `CHOPGIMP_NO_VOBJECTS=1` masque Vectoriser.
- Vérifié : 115 tests (dont 9 nouveaux : logo noir et blanc, couleurs groupées, sélection seulement, options relues, objets non modifiés, revectoriser, aller-retour XCF, copie du calque, Décomposer) ; banc : fenêtre (boutons en bas), aperçu sur le canevas (Résultat, Contours + source), préréglage 6 couleurs, calque créé et original masqué, Options de vectorisation rouvertes avec les réglages, Décomposer.
- Corrigé avant livraison : « Angles » → alphamax quadratique (50 % = défaut de potrace, 75 % garde les cercles ronds) ; singulier / pluriel dans les statistiques.
- Limites : une vectorisation dynamique ne suit pas une mise à l'échelle de l'image (la source garde sa taille) ; Pixel art refusé au-delà de 1 Mpx ; une photo en haute fidélité peut dépasser 700 000 points (⚠ dans la fenêtre).

## 3.27.4 — Fenêtre d'accueil

- Page « Créer » façon accueil Photoshop (`app/dialogs/welcome-dialog.c`) : colonne d'actions à gauche (« Nouveau… », « Ouvrir… », « Afficher au démarrage » en bas), à droite les 7 documents en un clic sur une ligne puis les fichiers récents en grille (2 lignes de 5, vignette, nom, taille, date, dossier au survol, un clic ouvre). Retirés : le bouton « Créer » en double et « Ouvrir les images sélectionnées ».
- La fenêtre prend la hauteur de l'onglet affiché (pile non homogène en hauteur) au lieu de celle de l'onglet le plus grand.
- Titre « Bienvenue dans ChopGimp », onglets Accueil / Personnaliser / Contribuer / Créer.
- Vérifié : 115 tests ; banc graphique (onglet Créer : tout tient, la fenêtre s'arrête sous la grille).
- Reste en anglais : les textes de l'onglet Accueil (« GIMP is Free Software… », « Community Tutorials »).

## 3.27.5 — Vectoriser : correctifs, accueil en français

- **Plus de liseré entre formes adjacentes** (`app/path/chopgimp-trace.cc`, option « Masquer les jointures », activée par défaut) : en mode Adjacent, chaque forme passe 1 pixel sous ses voisines dessinées au-dessus (masque dilaté vers les couleurs supérieures seulement, rien ne déborde sur le transparent ni sur le blanc ignoré) ; en pixel art, un filet de 0,6 px de la couleur de la forme. Mesuré : alpha minimal sur le bord d'un disque 253/255 avec, 0 sans.
- **La vectorisation dynamique suit le calque et l'image** (`app/core/chopgimp-trace-layer.c`, `app/path/gimppath.c`) : nouvelle matrice « tracé → image » (parasite `chopgimp-trace-matrix`, avec annulation) mise à jour par les transformations du chemin du calque vectoriel (déplacer, mettre à l'échelle, recadrer, taille du canevas, retourner, faire pivoter, transformer — les opérations sur l'image passent par le chemin, pas par le calque) ; « Revectoriser » et l'aperçu passent par elle. « Objets modifiés » ne se trompe plus après une transformation : l'empreinte (« sig ») ramène les points dans le repère du tracé (sommes pondérées, tolérance des flottants 32 bits du XCF) et ignore le style propre du calque (`options-style`).
- **Fenêtre Vectoriser à côté du canevas** (`app/dialogs/chopgimp-trace-dialog.c`) : les options s'ouvrent en panneau dans la fenêtre d'image, à droite du canevas (qui se rétrécit : rien de l'image n'est caché ; sous Wayland une fenêtre ne peut pas être placée) ; si la zone tracée n'est pas entièrement visible, la vue la cadre, et revient comme avant à la fermeture. Bouton « Détacher » : les mêmes options dans une fenêtre (retenu pour la session). Une boîte « sur le canevas » (GimpOverlayDialog) a été essayée puis écartée : ses listes déroulantes s'ouvrent au mauvais endroit.
- **Pixel art agrandi** : la taille des blocs (pgcd des changements de couleur en lignes et en colonnes, avec leur décalage) est détectée, l'image tracée à sa taille d'origine puis remise à l'échelle (cellules du bord coupées au cadre). Refus seulement si l'image dépasse encore 1 Mpx, avec un message qui propose « Contours remplis (potrace) ». Mesuré : 1280 × 960 (blocs de 8) tracé en 0,3 s.
- **Alléger les résultats lourds** (option activée par défaut) : au-delà de 150 000 points d'ancrage, jusqu'à 4 passes de lissage des bords (filtre majoritaire 3 × 3 sur les couleurs), fusion des petites zones (bruit × 4) et chemins simplifiés (−12 %). Mesuré sur une photo 1280 × 981 en « Photo haute fidélité » : 839 923 → 109 941 points, tracé 3,2 → 2,0 s, déplacement du calque 2,28 → 0,31 s ; 2560 × 1962 : 2 612 106 → 385 953 points, déplacement 14,3 → 0,9 s. La bulle des statistiques dit quand le résultat a été allégé.
- **Arrêter** : l'aperçu garde le résultat précédent, marqué « Arrêtée — aperçu précédent », rien ne repart tout seul ; « Vectoriser » relance le tracé des réglages actuels puis applique (avant : il appliquait l'ancien résultat).
- **Palette « Nuancier actif » / « Couleurs globales »** : une ligne dit d'où viennent les couleurs et combien (le nuancier actif d'un profil neuf est l'historique des couleurs, souvent 1 couleur).
- **Fenêtre d'accueil** : textes des onglets Accueil, Personnaliser, Contribuer et Nouveautés en français (absents du fr.po de GIMP 3.2.8), « Bienvenue dans ChopGimp, basé sur GIMP 3.2.8 ! ».
- Vérifié : 126 tests (11 nouveaux : jointures, pixel art agrandi, refus clair, allègement, suivi de l'échelle / du déplacement / du retournement / du recadrage, modification détectée après transformations, aller-retour XCF transformé, en couleurs) ; banc graphique : panneau à droite du canevas, listes déroulantes au bon endroit, Arrêter pendant un tracé de 20 Mpx puis Vectoriser, avertissement « objets modifiés », nuancier actif, Détacher, aperçu aligné sur un tracé mis à l'échelle et déplacé, onglets de l'accueil en français.
- Limites : déplacer le chemin lui-même avec l'outil Chemin (et non le calque) puis annuler peut laisser la vectorisation dynamique décalée ; une très grande photo en haute fidélité peut rester au-dessus de 150 000 points après 4 passes (⚠ et bulle d'aide) ; le filet anti-jointures du pixel art garde l'ancienne couleur si on ne change que le fond d'un objet dans Aspect (Redéfinir les couleurs change les deux).

## 3.27.6 — Outil Largeur, Distorsion d'objets (lot V6 points 5 et 8)

- **Outil Largeur** (Maj+W, groupe Forme de la boîte à outils, `app/tools/chopgimp-widthtool.c`) : sur le contour d'un objet d'un calque vectoriel, un clic pose un point de largeur et le glisser élargit ou affine le trait (les deux côtés ; Alt : le côté du pointeur seulement) ; les poignées d'un point changent sa largeur, son losange le déplace le long du tracé (les extrémités restent aux bouts), Suppr le supprime, double-clic : fenêtre « Point de largeur » (côté 1 / côté 2 en px) ; une seule annulation par geste, Échap / clic droit annule. Le résultat est le profil de largeur du contour (format « t:w » des préréglages, étendu à « t:gauche/droite » pour les largeurs asymétriques, > 1 possible), dessiné par le powerstroke de `chopgimp-geom.cc` (côtés séparés) ; l'export SVG le dessine en contour plein, asymétrie comprise.
- **Profils réutilisables** (`app/widgets/chopgimp-width-profile-box.c`) : dans les options de l'outil et la barre d'options (« Profil de largeur ») : liste des profils (préréglages + profils de l'utilisateur), « Enregistrer… » (nom → `<dossier GIMP>/chopgimp-width-profiles`), « Uniforme ». Le panneau Contour liste aussi les profils enregistrés et affiche « Personnalisé (outil Largeur) » pour un profil fait à la main. Les limites du calque tiennent compte des largeurs > 1.
- **Objet > Distorsion** (`app/path/chopgimp-vdistort.c`, effet « distort » de `chopgimp-geom.cc`) :
  - **Déformation…** : 15 modèles (Arc, Arc inférieur, Arc supérieur, Arche, Renflement, Coquillage inférieur / supérieur, Drapeau, Onde, Poisson, Montée, Œil de poisson, Gonflement, Compression, Torsion), Horizontal / Vertical, Courbure, Distorsion horizontale et verticale, aperçu en direct sur le canevas, Réinitialiser ; rouvrir la fenêtre sur un objet déformé reprend ses réglages ;
  - **Créer d'après une maille…** (lignes × colonnes, lissage Catmull-Rom entre les points), **Créer d'après l'objet du dessus** (l'objet sélectionné le plus haut devient l'enveloppe des autres, puis disparaît, comme dans Illustrator), **Distorsion libre** (4 coins, perspective) ;
  - **outil Enveloppe** (groupe Forme, `app/tools/chopgimp-envelopetool.c`) : on tire les points de la maille, les objets suivent en direct ; barre d'options « Distorsion » (créer, modifier le contenu, décomposer) ;
  - **Modifier l'enveloppe** (outil Enveloppe) / **Modifier le contenu** (Sélection directe sur le tracé d'origine), **Décomposer la distorsion** (la forme déformée devient le tracé), **Annuler la distorsion**.
  - Une distorsion est un effet vivant par objet (dernier groupe de son « lpe » : enregistrée dans le XML des objets et le XCF, une étape d'annulation par commande) ; plusieurs objets sélectionnés partagent la même boîte ; le XML des fichiers et des greffons porte le tracé aplati (`d-effective`), que l'export SVG écrit.
- **PDB** `chopgimp-vobjects-command` : `distort-warp:style:courbure:h:v:vertical`, `distort-mesh:lignes:colonnes`, `distort-mesh-point:k:dx:dy`, `distort-top`, `distort-free`, `distort-expand`, `distort-release`, `width-profile:<profil>`, `save-profile:<nom>`.
- **Restes de la 3.27.5 corrigés** :
  - **vectorisation dynamique déplacée par l'outil Chemin** (et annulation) : la signature des objets garde aussi la somme des poids ; une translation d'ensemble des objets sans la matrice est reconnue et la matrice remise d'aplomb (`chopgimp_trace_layer_sync_matrix()`), à l'ouverture des options et avant de revectoriser ;
  - **filet anti-jointures du pixel art** : il suit le fond de son objet (`follow-fill` dans le XML) : changer seulement le fond dans Aspect change aussi le filet.
- **Corrigé en passant** : les effets vivants sur un tracé ouvert (onde, zigzag, profils de largeur…) ajoutaient un segment de retour vers le début (lib2geom compte le segment de fermeture même sur un tracé ouvert).
- **Raccourci** : Maj+W passe à l'outil Largeur (comme Illustrator) ; la Sélection de premier plan n'a plus de raccourci (groupe W de la boîte à outils, menu Outils).
- Vérifié : 137 tests (11 nouveaux : profil asymétrique, profil enregistré, 15 déformations, distorsion gardée et aplatie, maille, distorsion libre, XCF, Décomposer, d'après l'objet du dessus, filet qui suit le fond, vectorisation suivie après déplacement des objets) ; banc graphique : outil Largeur (point posé et tiré), fenêtre Déformation (aperçu puis Valider), Distorsion libre et outil Enveloppe (coin tiré, perspective).

## 3.28.0 — Réorganisation des menus I : Vecteur, Calque, Image / Couleurs

Objectif : rester proche de Photoshop, une seule place par commande, plus de doublons. Étapes suivantes : Texte, Filtres, puis Fichier / Édition / Sélection / Affichage / Fenêtres / Aide.
- **Menu « Vecteur »** (ex-« Objet ») : tout le vectoriel au même endroit. Grouper, Disposition, Aligner, Verrouiller / Masquer, Masque d'écrêtage, **un seul Pathfinder** (celui du plug-in : objets sélectionnés, sinon calques vectoriels), **Contours**, **Nœuds**, **Effets de tracé** (avec la Gomme vectorielle), **Distorsion** (3.27.6), Aspect / Contour / Couleurs globales / Pipette de style / Redéfinir les couleurs, Vectorisation, **Convertir** (Fusionner en un calque vectoriel, Dissocier en calques, Décomposer les sous-tracés, Séparer les formes), Sélectionner tous les objets, Supprimer les objets.
- **Calque** : toutes les créations en tête (Nouveau calque, groupe, depuis le visible, calque de réglage, **calque de remplissage**, **calque de croquis**) ; Dupliquer / Ancrer / Supprimer ; fusions (dont **Fusionner les calques visibles** et **Aplatir l'image**, venus d'Image, et Aligner les calques visibles) ; Style de calque, masque d'écrêtage, Objet dynamique ; texte et pixellisation ; Pile / Masque / Transparence / Transformer ; tailles ; Vectoriser…, Aplats. Plus de commandes vectorielles en double.
- **Le menu Couleurs disparaît, fondu dans Image > Réglages** (sans doublons) : réglages essentiels, Virage partiel, inversions, Postériser / Seuil / Tramage / Clip RVB, puis Auto, Composants, Désaturation, Carte, Tonalités chromatiques, Informations (histogramme, palettes, Harmonies de couleurs).
- **Image** dans l'ordre Photoshop : Mode / Codage / Gestion des couleurs ; Réglages ; **Tons auto, Contraste auto, Couleur auto** (libellé « Contrastee auto » corrigé) ; tailles et Transformer ; recadrages (+ perspective, Redresser) ; Mise à l'échelle selon le contenu, IA ; Dupliquer, Instantané ; Propriétés, Métadonnées.
- **Affichage** : Guides et Configurer la grille (venus d'Image), après les « Afficher… ».
- **Patch 0139** (`app/plug-in/plug-in-menu-path.c`, `plug-in-rc.c`) : `<Image>/Colors…` → `<Image>/Image/Réglages…`, `<Image>/Image/Guides` → `<Image>/View/Guides`, `<Image>/Image/[Arrange]` → `<Image>/Layer/[Arrange]`, aussi pour les chemins relus d'un pluginrc existant (sinon GIMP recréerait les anciens menus).
- **Méthode** : `tools/build_menus.py` place les commandes des plug-ins ChopGimp par leur nom (`app.<procédure>`) ; ces plug-ins ne déclarent plus de chemin dans la barre de menus (clic droit du panneau Calques inchangé). **Garde-fou** : la génération s'arrête si une action d'origine de GIMP disparaît des menus.
- **Doublon retiré des menus** : « Harmonie des couleurs… » (PhotoGIMP), remplacée par « Harmonies de couleurs… » de ChopGimp ; la procédure reste appelable par script.
- Vérifié (Windows, build C:\cg327) : génération des menus sans action perdue ; les 670 actions des menus existent (GIMP ou plug-in) ; après enregistrement, plus aucun chemin `<Image>/Colors` ni `<Image>/Image/Guides`, avec un profil vierge et avec un ancien pluginrc (17 chemins redirigés) ; scripts Script-Fu (Guides, palette) redirigés ; démarrage et sortie de l'interface (instance séparée). Vérifications faites sur une base 3.27.3 avant de rattraper la 3.27.6 (sous-menu Distorsion ajouté au menu Vecteur pendant la fusion, non recompilé). Pas encore vu à l'écran par l'utilisateur.
- Reste : sous-menu Calque > Texte en double avec le menu Texte (étape Texte).

## 3.28.1 — Peinture dynamique et Symboles (lot V6 points 6 et 7)

- **Vecteur > Peinture dynamique** (`app/path/chopgimp-vlivepaint.c`, géométrie `chopgimp_geom_planar` dans `chopgimp-geom.cc`) : **Créer** (Ctrl+Maj+Alt+X) fait des objets sélectionnés un groupe de peinture dynamique. Leurs tracés (ouverts ou fermés) découpent le plan en **zones** et en **segments** (morceaux de tracé entre deux croisements), coloriés séparément sans opération booléenne. Les tracés restent dans un sous-groupe masqué « Tracés » ; zones et segments sont des objets ordinaires (dessinés, enregistrés, exportés à plat ; un ChopGimp plus ancien voit un groupe).
  - Dynamique : quand un tracé bouge (Sélection directe, qui vise les tracés et non les zones, mode objets, scripts, annulation), zones et segments sont recalculés au prochain changement du calque ; chaque zone garde le style de l'ancienne zone qui la recouvre le plus, chaque segment celui de l'ancien segment du même tracé au même endroit. Signature des tracés dans le XML : rien n'est recalculé si rien n'a bougé.
  - **Ajouter au groupe**, **Options d'écarts…** (les bouts des tracés ouverts sont prolongés de N px pour fermer les petites ouvertures), **Décomposer** (les zones et segments peints deviennent un groupe ordinaire), **Libérer** (les tracés reviennent avec leur style d'origine).
  - **Outil Pot de peinture dynamique (K)** : la zone survolée est soulignée, clic = couleur de premier plan, Maj+clic = segment, Alt+clic = prendre la couleur. **Outil Sélection de peinture dynamique (Maj+K)** : clic / Maj+clic sur zones et segments ; barre d'options (mode objets), panneau Aspect, ou boutons « Fond / Contour ← premier plan », « Aucun fond » dans les options de l'outil.
- **Symboles** (`app/path/chopgimp-vsymbols.c`, panneau `app/widgets/chopgimp-symbols-editor.c`) : définitions gardées par l'image (parasite `chopgimp-symbols`, XCF, annulable) ; une occurrence est un groupe `symbol="<id>"` avec sa propre transformation.
  - **Nouveau symbole** (les objets sélectionnés deviennent le symbole et sa première occurrence), **Placer une occurrence** (bouton ou double-clic, au centre de l'image, dans le calque vectoriel actif ou un nouveau), **Modifier le symbole** (ouvre l'occurrence : ce qu'on y change s'applique au symbole et à toutes les occurrences, dans tous les calques), **Rompre le lien**, **Renommer**, **Supprimer** (les occurrences restent en groupes). Vignettes sur damier, nombre d'occurrences en info-bulle. Menu Vecteur > Symboles, Fenêtres > Symboles, espace de travail Illustration.
  - Seules les modifications faites **dans** l'occurrence ouverte (Modifier le symbole) changent le symbole ; les autres occurrences suivent sans étape d'annulation propre (annuler la modification les ramène toutes). Une occurrence modifiée de l'extérieur (distorsion, style appliqué au groupe…) **quitte le symbole** (comme Rompre le lien ; annuler rétablit le lien) — constaté au banc : sans cette règle, une Distorsion libre sur une occurrence déformait toutes les autres.
  - **Import SVG** : `<use>` d'un `<symbol>` → occurrences et symbole « svg-<id> » (si toutes les occurrences ont le même contenu ; sinon groupes ordinaires). **Export SVG** : aplati (groupes), pas de `<symbol>` / `<use>`.
- **Raccourcis** (catégorie Vecteur) : K, Maj+K ; Ctrl+Maj+Alt+X (Créer), Distorsion : Ctrl+Maj+Alt+A (Déformation), Ctrl+Maj+Alt+M (maille), Ctrl+Maj+Alt+C (objet du dessus). Les raccourcis d'Illustrator sans Maj sont déjà pris par Photoshop (Ctrl+Alt+X Recadrer, Ctrl+Alt+M Masque, Ctrl+Alt+C Taille de la zone de travail, Ctrl+Maj+Alt+W Exporter sous) ; Maj+L reste au lasso magnétique ; **K n'est plus le raccourci de l'outil Plume (ink) de GIMP**.
- **PDB** `chopgimp-vobjects-command` : `livepaint-make|add|expand|release`, `livepaint-gap:<px>`, `livepaint-fill:<x>:<y>:#rrggbb|none`, `livepaint-stroke:…`, `livepaint-select:<x>:<y>`, `symbol-new[:<nom>]`, `symbol-place:<id>`, `symbol-edit`, `symbol-break`, `symbol-rename:<id>:<nom>`, `symbol-delete:<id>`.
- **Corrigé en passant** : un chemin ouvert produit par le moteur géométrique (contours, segments…) recevait un segment de retour vers son début.
- Vérifié : tests automatiques (15 nouveaux : 4 zones d'un rectangle coupé par une croix, pot sur une seule zone, segment, zones qui suivent un tracé déplacé, écarts, aller-retour XCF, décomposer ; symbole, occurrence, occurrence modifiée de l'extérieur qui quitte le symbole, modification dans « Modifier le symbole » propagée, XCF, rompre, supprimer, import SVG) ; banc graphique : outil K (zone soulignée, Alt+clic prend le rouge, clic remplit la zone), panneau Symboles (vignette, Placer), outil Enveloppe après Distorsion libre (cadre serré sur l'objet, coin tiré en perspective).
- Limites : la zone survolée est soulignée avec la couleur de surbrillance de GIMP, pas en rouge ; pas de glisser-déposer du panneau Symboles vers le canevas (bouton ou double-clic) ; une occurrence placée deux fois au centre se superpose à la précédente ; la Sélection de peinture dynamique ne sélectionne pas d'un double-clic les zones voisines de même couleur ; Ajouter au groupe ne prend que des objets du même niveau que le groupe ; un très grand nombre de tracés croisés rend le recalcul lent (chaque déplacement recalcule l'arrangement) ; double-clic / Suppr de l'outil Largeur et enregistrement d'un profil depuis l'interface : couverts par les tests automatiques (PDB) de la 3.27.6, pas revus au banc.

## 3.28.2 — Petits défauts restants

Correctifs des « Limites » notées de 3.26.1 à 3.28.1 (patch 0141).
- **Vectoriel** :
  - **Plume** : un nouvel objet et son premier point = une seule étape d'annulation (« Ajouter un objet »).
  - **« Mettre à l'échelle les contours et effets »** (comme Illustrator) : case « Contours à l'échelle » dans la barre d'options du mode objet et Préférences > Options des outils > Objets vectoriels (`chopgimprc [vector] scale-strokes`, cochée par défaut = comportement d'avant). Décochée, un objet redimensionné garde l'épaisseur de son contour (et le décalage des tirets). Les effets de calque ne sont pas concernés.
  - **Sélection d'objets gardée par le XCF** (attribut `selection` du parasite `chopgimp-vobjects`, ids vérifiés au chargement).
  - **Déplacer tout un calque multi-objets** : **Ctrl+Maj+glisser** avec l'outil Déplacement (l'outil Déplacement de GIMP prend le relais).
- **Aspect et couleurs** :
  - **Couleurs globales** : glisser une nuance du panneau sur un objet du canevas = son fond la suit (Maj au dépôt : son contour) ; glisser une nuance sur une autre = la réordonner.
  - **Profils d'épaisseur** : ils suivent maintenant l'**alignement** (intérieur / extérieur) et les **tirets** du contour (rendu et zone de clic). Export SVG : toujours un contour plein centré.
  - **Import SVG** : un **masque simple** (formes blanches opaques) devient un masque d'écrêtage ; un **motif** devient sa couleur moyenne (pondérée par l'aire), signalé « approché » dans le rapport. Les filtres SVG et les masques en dégradé restent signalés « non repris ».
- **Distorsion** :
  - **Décomposer** ne fige plus que la distorsion : les autres effets vivants de l'objet restent modifiables (ils s'appliquent désormais après elle).
  - **Convertir en maille** (Vecteur > Distorsion, barre d'options de l'outil Enveloppe) : une Déformation devient une enveloppe 4 × 4 passant par les mêmes points, modifiable avec l'outil Enveloppe (approchée entre les points).
  - **Plusieurs objets tournés distordus ensemble** : leur transformation passe d'abord dans leur tracé (même étape d'annulation), la boîte commune est donc juste. Pas pour l'aperçu de la fenêtre Déformation (approché pour des objets tournés).
- **Peinture dynamique et Symboles** :
  - Survol du **Pot de peinture dynamique en rouge** (couleur propre d'un élément du canevas, `chopgimp-rgb`).
  - **Glisser un symbole du panneau sur le canevas** = une occurrence à l'endroit du dépôt ; une occurrence placée au centre là où il y en a déjà une est **décalée de 10 px**.
  - **Double-clic de la Sélection de peinture dynamique** : les zones (ou segments) voisines de même couleur.
  - **Ajouter au groupe** accepte des objets de niveaux différents.
  - **Recalcul** : boîtes des tracés triées (balayage) et grille pour les sommets au lieu de comparaisons de toutes les paires ; pendant qu'on déplace un tracé d'un gros groupe (calcul > 60 ms), recalcul au plus toutes les 2 × sa durée, puis une dernière fois (`CHOPGIMP_LP_NO_THROTTLE=1` pour couper). Mesure (avant) : 60 + 60 tracés croisés, 3 481 zones en 0,44 s.
  - **Outil Largeur**, testé au banc : le **double-clic** sur un point n'ouvrait pas ses largeurs (doubles-clics non demandés à GIMP) → corrigé ; **Suppr** supprimait tout l'objet au lieu du point → il retire d'abord le point sélectionné ; **Enregistrer…** un profil : vérifié (fichier `chopgimp-width-profiles`).
- **Styles de calque** :
  - **Pipette** : case « Calque avec effets » (cochée par défaut, comme Photoshop), active quand « Échantillonner sur tous les calques » est décochée : la couleur du calque tel qu'il est affiché (ombre, contour, lueur…).
  - **Fenêtre Style de calque ouverte** : une action faite ailleurs sur l'image (menu, panneau…) ferme d'abord l'étape « Style de calque » et reste séparée. Dans ce cas, Annuler dans la fenêtre ne retire plus les réglages faits avant cette action (Ctrl+Z les retire).
  - **Pixelliser le style de calque** : une ombre portée ou une lueur externe dans son propre mode (Produit, Écran…) devient **un calque à part, dans ce mode**, sous le calque (comme « Créer des calques » de Photoshop) au lieu d'être figée en Normal (`CHOPGIMP_NO_BEHIND_LAYERS=1` pour l'ancien comportement). Fusionner des calques : non modifié.
- **Corrigé en passant** : la source d'une vectorisation dynamique était enregistrée en PNG par gdk-pixbuf, qui passe dans le runtime GNOME 51 par les chargeurs glycin (processus à part, qui échouent parfois) : la vectorisation n'était alors pas dynamique (15 tests en échec par intermittence). PNG par cairo désormais.
- **PDB** `chopgimp-vobjects-command` : `distort-to-mesh`, `scale-strokes:0|1`, `scale-objects:<facteur>`.
- Vérifié : 158 tests (5 nouveaux : épaisseur conservée, sélection dans le XCF, convertir en maille, décomposer seulement la distorsion, ombre en Produit pixellisée en calque Produit) ; banc graphique : outil Largeur (point posé et élargi, double-clic, Suppr, enregistrer un profil), case « Contours à l'échelle ».
- Non vérifié au banc : glisser-déposer des couleurs globales et des symboles, surbrillance rouge, double-clic de la Sélection de peinture dynamique, Ctrl+Maj+glisser, pipette avec effets, garde d'annulation de la fenêtre Style de calque.
- Limites : avec l'outil Largeur et un objet sélectionné, le profil de largeur passe dans « ⋯ » de la barre d'options (place) ; « Fusionner les calques » avec une ombre en Produit : non vérifié.

## 3.28.3 — Boîte à outils par familles, Lasso magnétique, Sélection rapide, croix de la brosse, Sélection directe sur plusieurs objets

- **Boîte à outils réorganisée par familles** (`tools/build_layout.py`) :
  - Sélection / composition : Déplacement, Rectangle, **Lasso (magnétique par défaut)**, Baguette / **Sélection rapide**, Recadrage, Transformation, Pipette ;
  - Peinture : Pinceau, **Gomme juste dessous**, Dégradé, Goutte d'eau, Densité ;
  - Retouche : Correcteurs, Tampons ;
  - Vectoriel / texte : Plume, Texte, Forme, Largeur, Peinture dynamique, en 3 groupes ;
  - Navigation : Main, Zoom.
  
  Les raccourcis ne changent pas. Pas de trait entre les familles : la palette de GIMP range ses outils dans un seul groupe, par position.
- **Lasso magnétique** (L, outil `gimp-magnetic-lasso-tool`, les Ciseaux intelligents de GIMP en mode magnétique) :
  - un clic pose le départ, puis le tracé suit le bord pendant qu'on déplace la souris, sans bouton ;
  - des points sont posés tout seuls selon la **Fréquence** ; options **Largeur** et **Contraste** (10, 10, 57 par défaut, comme Photoshop), dans la barre d'options ;
  - un clic force un point, Retour arrière retire le dernier, double-clic, Entrée ou clic sur le départ ferment **et sélectionnent**, Échap annule, Alt trace un segment droit ;
  - les Ciseaux intelligents restent dans le groupe ; leur recherche du bord est maintenant centrée sur le pointeur aussi au bord de l'image (identique ailleurs).
- **Sélection rapide** (W) : l'outil Paint Select de GIMP n'est plus expérimental.
  - On peint et la sélection s'étend jusqu'aux bords ; Alt retire ; `[` et `]` changent la taille ; croix au centre de la brosse.
  - Options : **Échantillonner tous les calques**, **Améliorer le contour** (flou de 1,2 px puis seuil), **Calcul autour du trait** (graphe limité à la zone du trait), bouton **Sélectionner et masquer…**.
  - GEGL est compilé avec ses opérations « workshop » pour `gegl:paint-select` (avec maxflow) ; les autres opérations expérimentales sont retirées du paquet.
- **Croix au centre de la brosse** : Préférences > Périphériques d'entrée > Outils de peinture, **Toujours** (par défaut), Petites brosses seulement (3.24.10) ou Jamais (`brush-crosshair` dans le gimprc, appliqué à chaud).
- **Sélection directe (A) sur plusieurs objets** : un rectangle tracé depuis le vide, même sans objet en cours, sélectionne les points de **tous** les objets visibles et non verrouillés du calque vectoriel actif ; ils se déplacent ensemble en **une** étape d'annulation. Maj ajoute, Alt retire, un clic dans le vide désélectionne.
- **Corrigé en passant (reste de la 3.28.0)** : les opérations GEGL suivent maintenant les mêmes redirections de menus que les greffons. `gegl:local-threshold` recréait un menu anglais « Colors » ; « Seuil local… » est désormais dans Image > Réglages.
- Vérifié : 162 tests (4 nouveaux : croix réglée sur Toujours, `gegl:paint-select` présent, ordre de la boîte à outils, Lasso magnétique affiché dans le groupe L). Banc graphique :
  - boîte à outils dans le nouvel ordre, groupe W (Baguette, Sélection rapide, Premier plan, Par couleur) ;
  - croix au centre d'une brosse de 51 px ;
  - Lasso magnétique : le tracé suit le bord d'un cercle, Retour arrière, double-clic qui ferme et sélectionne (corrigé : le double-clic n'arrivait pas à l'outil), barre d'options (ajoutée : elle était vide) ;
  - Sélection rapide : un petit trait sélectionne tout un rectangle, Alt+trait le retire ;
  - Sélection directe : rectangle sur 2 objets, déplacement des deux, une seule annulation ;
  - restes de la 3.28.2 : Ctrl+Maj+glisser déplace tout le calque vectoriel (le calque pris est celui sous le pointeur, comme Ctrl = sélection automatique), survol rouge du Pot de peinture dynamique ;
  - menu Image > Réglages avec « Seuil local… », plus de menu « Colors ».
- Non vérifié au banc : glisser-déposer des couleurs globales et des symboles, pipette avec effets (vérifiés par les tests automatiques de la 3.28.2).
- Limites :
  - Lasso magnétique : des mouvements de souris très rapides (sauts de plus de 100 px) peuvent poser des points hors du bord, que Retour arrière retire ;
  - dans la Sélection directe sur plusieurs objets, un nouveau sous-tracé dessiné à la Plume n'appartient à aucun objet et n'est pas gardé ;
  - le raccourci L active le Lasso libre (action de l'outil), pas l'outil affiché du groupe.

## 3.29.0 — Vectoriel « complet » I : outils de dessin et transformations précises

Blocs 1 et 2 validés par l'utilisateur le 2026-11-25 (dessin et édition,
transformations précises), comme Illustrator.

- **Outil Courbure** (Maj+P, groupe Plume, `app/tools/chopgimp-vpentools.c`) :
  chaque clic pose un point, la courbe passe par tous en douceur (poignées de
  Catmull-Rom) ; Alt+clic : point d'angle ; double-clic sur un point : lisse ↔
  angle ; glisser un point le déplace ; clic sur le premier : fermer ; Entrée /
  Échap : terminer ; Retour arrière : retirer le dernier point ; changer d'outil
  garde la courbe. Le résultat est un objet du calque vectoriel actif (option
  « Ajouter au calque vectoriel actif ») ou un nouveau calque vectoriel.
- **Crayon vectoriel** (N, groupe avec Lissage) : tracé à main levée ajusté en
  courbes de Bézier (algorithme de Schneider de lib2geom, option « Fidélité »)
  ; partir de l'extrémité du tracé sélectionné le prolonge (« Garder la
  sélection »), finir sur le point de départ le ferme. Le crayon de GIMP garde
  Maj+B.
- **Lissage** : frotter les objets sélectionnés lisse leur tracé autour du
  pointeur (options Rayon et Force), une étape d'annulation par geste.
- **Ciseaux** (groupe Ciseaux / Cutter / Jonction, sans raccourci : C est au
  Recadrage) : un clic coupe un tracé (fermé : ouvert à cet endroit ; ouvert
  et seul : deux objets).
- **Cutter** : glisser à main levée tranche les formes traversées en morceaux
  fermés (arrangement planaire de la Peinture dynamique), même style.
- **Jonction** : frotter par-dessus deux extrémités ouvertes les relie (bouts
  confondus à moins de 0,5 px, sinon un segment) ; deux objets deviennent un.
- **Angles dynamiques** : avec l'outil Déplacement en mode objets, un seul
  objet sélectionné montre un petit cercle dans chaque angle ; le tirer vers
  l'intérieur arrondit tous les angles (Alt : seulement celui-ci). Effet vivant
  « corners » par objet (arrondi, arrondi inversé, chanfrein ; rayon commun et
  rayons par angle), gardé par le XCF, aplati à l'export SVG. Vecteur >
  Transformer > Retirer les angles dynamiques.
- **Nouvelles formes** (outil Forme) : Spirale (tours, décroissance), Arc
  (ouvert ou fermé, convexe ou concave), Grille rectangulaire (lignes,
  colonnes, cadre), Grille polaire (cercles, séparateurs) ; tracées sans fond.
- **Panneau Transformation** (Fenêtres, Maj+F8) : point de référence à 9 cases,
  X / Y (coordonnées de ce point), L / H avec proportions liées, angle et
  inclinaison (d'un objet seul ; saisir une valeur tourne ou incline de la
  différence), « Contours à l'échelle », retournements H / V ; une étape
  d'annulation par saisie.
- **Répéter la transformation** (Vecteur > Transformer, et Ctrl+D quand aucune
  sélection de pixels n'est active) : refait le dernier déplacement, la
  dernière mise à l'échelle ou rotation d'objets ; après Alt+glisser, une
  série de copies.
- **Transformer chaque…** (Ctrl+Alt+D ; Alt+Maj+Ctrl+D est déjà « Dupliquer
  l'image ») : échelle H / V, déplacement H / V, rotation, symétries X / Y,
  point de référence, aléatoire, copier, aperçu.
- **Objet clé** : en mode objets, un clic sur un objet déjà sélectionné en fait
  l'objet clé (contour et cadre en surbrillance) ; Aligner s'aligne sur lui
  sans le bouger ; nouveau clic ou Vecteur > Aligner > Annuler l'objet clé
  pour le retirer. **Aligner sur** : la sélection, l'objet clé, le plan de
  travail (l'image).
- **PDB** (`chopgimp-vobjects-command`) : transform-again, transform-record,
  transform-each, key, key-none, align-to, box, flip-h / flip-v, corners,
  cut-at, knife, join-at.
- Vérifié : 170 tests (8 nouveaux : angles dynamiques, Ciseaux + Jonction, Cutter, objet clé et Aligner sur, Répéter, Transformer chaque, panneau, outils présents) ; banc graphique : Courbure (4 clics → courbe lisse, objet « Courbure »), Crayon vectoriel (tracé à main levée ajusté en courbes), Ciseaux puis Jonction (2 objets → 1), Cutter (rectangle tranché en 2 objets), angles dynamiques (poignée tirée → angle arrondi), Spirale, Arc, grilles rectangulaire et polaire, panneau Transformation (point de référence en haut à gauche, L = 70 → mise à l'échelle proportionnelle ancrée en haut à gauche), glisser puis Ctrl+D ×2 (3 pas identiques), Alt+glisser puis Ctrl+D ×2 (série de 3 copies), Ctrl+D avec une sélection de pixels (désélectionne, objets immobiles), Transformer chaque (rotation 30° de chaque objet en aperçu, Annuler rend l'état d'origine), objet clé (contour doré) et Aligner à gauche sur lui.
- Corrigé à l'intégration : compilation (`End` déjà défini → `VJoinEnd`, appel ambigu de `is_corner`, `Geom::Rect::expandedBy` absent de lib2geom 1.4) ; **Lissage** sans effet visible (moyenne des voisins immédiats d'échantillons serrés) : rééchantillonnage régulier du tracé (1,5 px), puis moyenne glissante sur 0,4 × le rayon le long du tracé (pas de cassure au bord de la brosse), 1 à 9 passes selon la Force ; vérifié au banc : une crête frottée s'aplatit.
- Limites connues : les angles dynamiques ne s'affichent pas en
  Sélection directe (A), seulement en mode objets (V) ; leur rayon n'est pas
  dans la barre d'options (poignées et Retirer seulement) ; un objet sans
  effets propres qui suivait les effets du calque (parasite « chopgimp-lpe »)
  ne les suit plus une fois ses angles arrondis ; « Aligner sur l'objet clé »
  sans objet clé aligne sur la sélection ; le Cutter ignore les tracés
  ouverts ; Répéter refait la transformation autour du même point de l'image
  (rotation de copies autour d'un centre : la série tourne bien autour de lui) ;
  la poignée d'un angle dynamique reste au sommet de l'angle (elle ne suit pas le
  rayon pendant qu'on la tire).

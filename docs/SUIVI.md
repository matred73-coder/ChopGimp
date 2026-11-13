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
| 6 | 3.19.2 | PSD II | à faire |
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

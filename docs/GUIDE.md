# ChopGimp 4.2 — guide de l'utilisateur

Un guide court, rangé par tâche. Il suppose que vous connaissez Photoshop ou
Illustrator : ChopGimp en reprend les gestes et les raccourcis. Le détail de chaque
fonction se trouve dans le [README](../README.md) et dans le journal
[`SUIVI.md`](SUIVI.md).

---

## 1. Démarrer

- **Fichier > Nouveau** (Ctrl+N) ou la page **Créer** de la fenêtre d'accueil :
  formats prêts à l'emploi et fichiers récents.
- **Fenêtres > Espace de travail** : Essentiel, Photographie, Peinture, Typographie,
  Illustration. Choisissez **Illustration** pour le vectoriel : panneaux Objets,
  Aspect, Contour, Formes, Plans de travail.
- **Affichage > Apparence** : 7 variantes de thème, couleur d'accent, densité et
  police, appliquées à chaud.
- **Recherche universelle** (Ctrl+F) : tapez le nom d'une commande, d'un filtre
  ou d'un outil.

## 2. Vectoriser une image

1. Sélectionnez le calque de l'image.
2. Choisissez **Vecteur > Vectoriser…**, puis un préréglage :
   - « Photo haute fidélité » pour une photo ;
   - « Logo noir et blanc » pour un logo ;
   - « Pixel art » pour une image en gros pixels.
3. L'aperçu se met à jour en direct. Pour une grosse image, gardez « Alléger les
   résultats lourds » coché.
4. **Valider** crée un calque vectoriel. Ce calque reste **dynamique** : rouvrez
   Vectoriser pour changer les réglages. Le résultat suit aussi la mise à l'échelle
   et le recadrage de l'image.
5. **Décomposer** fige le résultat en objets ordinaires, qu'on modifie un à un.

Pour une très grande image (plus d'un million de pixels), utilisez le moteur
« Contours remplis (potrace) ».

## 3. Travailler les objets

- **V (Sélection)** : un clic choisit un objet, un double-clic son groupe. Maj+clic
  ajoute un objet, un glisser trace un rectangle de sélection. Un clic droit ouvre
  le menu Vecteur.
- **A (Sélection directe)** : déplace les points. Les angles dynamiques s'arrondissent
  depuis leur poignée ; leur rayon se règle dans la barre d'options.
- **Recolorer** :
  - Vecteur > Sélectionner > Même couleur de fond, puis une couleur de premier plan ;
  - Vecteur > Couleurs > **Redéfinir les couleurs** pour une harmonie ou une
    réduction à N couleurs.
- **Isoler** : un double-clic entre dans un groupe ; Échap en sort.
- **Combiner** : Pathfinder (Ctrl+Alt+U pour réunir, Ctrl+Alt+Y pour soustraire) et
  Bâtisseur de formes.
- **Nettoyer** : Vecteur > Nettoyer (Simplifier, petits objets, petits trous, fusion
  par couleur).
- **Panneaux** : Objets (ordre, verrous, visibilité), Aspect (pile de fonds et de
  contours), Contour (tirets, flèches, profils de largeur).

### Dessiner

- **P (Plume)**, Courbure, Crayon vectoriel, Lissage.
- **U (Forme)** : rectangle, ellipse, polygone, étoile, spirale, grilles.
- **Maj+W (Largeur)** : faites varier l'épaisseur d'un contour.
- **Pinceau goutte** (groupe du Crayon vectoriel) : chaque coup devient une forme
  remplie de la couleur du contour, fusionnée avec les formes de même couleur qu'il
  touche.

### Répétitions et formes de pinceau

- **Vecteur > Répétition** : radiale, en grille ou en miroir. La source reste
  modifiable. Avec l'outil Déplacement (V), les poignées règlent le centre, le
  nombre d'instances, les espacements et l'axe.
- **Vecteur > Formes de pinceau** : Calligraphique, Art, Motif, Dispersion. Le
  panneau **Formes** applique une forme d'un double-clic et en définit de nouvelles
  depuis la sélection.

### Plans de travail et perspective

- **Maj+O (Plan de travail)** : tracez des pages de tailles différentes dans le même
  fichier. Le panneau Plans de travail permet de les renommer et de les réordonner.
- **Ctrl+Maj+Alt+I** affiche la grille de perspective (1, 2 ou 3 points de fuite).
  Les formes (U) dessinées s'y posent sur le plan actif ; les touches 1 à 4 changent
  de plan.

## 4. Exporter

| Format | Commande | À savoir |
|---|---|---|
| **PDF en calques** | Fichier > Exporter > Exporter sous… (Ctrl+Maj+Alt+W), `.pdf` | Le vectoriel reste vectoriel. Les calques deviennent des calques PDF, visibles dans Acrobat et Illustrator. Un plan de travail peut donner une page. |
| **PSD** | Exporter sous…, `.psd` (la boîte de dialogue propose styles, formes et textes modifiables) | Les styles de calque deviennent des styles Photoshop, les calques vectoriels des calques de forme, les textes restent modifiables. Un effet sans équivalent est pixellisé dans un calque à part et signalé. |
| **SVG** | Exporter sous…, `.svg` | Objets, dégradés, filets, motifs, symboles et répétitions. |
| **EPS** | Exporter sous…, `.eps` | Vectoriel, une page par plan de travail. |
| **Un fichier par plan** | Fichier > Exporter > Exporter les plans de travail… | PNG, JPEG, WebP ou TIFF. Pour un PDF ou un EPS, choisissez « Une page par plan de travail » à l’export. |
| **PDF/X, TIFF CMJN** | Fichier > Exporter > Exporter pour l'imprimeur… | Voir [Imprimer en CMJN](#5-imprimer-en-cmjn). |
| **XCF** | Fichier > Enregistrer (Ctrl+S) | Le format natif garde tout : objets, effets, plans, grille. Un GIMP standard l'ouvre et y voit les pixels. |

## 5. Imprimer en CMJN

ChopGimp travaille en RVB comme GIMP, mais il gère le CMJN comme Photoshop : un
profil CMJN par image, l'aperçu à l'écran de l'impression et des fichiers CMJN pour
l'imprimeur.

### Les profils CMJN

- **ISO Coated v2 (FOGRA39)** de l'ECI est fourni (sa licence permet de le
  redistribuer ; elle est installée à côté du profil).
- **PSO Coated v3 (FOGRA51)** et **PSO Uncoated v3 (FOGRA52)**, les profils offset
  actuels de l'ECI, ne peuvent pas être fournis : leur licence l'interdit. Un clic
  les télécharge depuis eci.org : **Image > Gestion des couleurs > Télécharger les
  profils CMJN PSO v3 (ECI)…** (proposé aussi au premier passage en CMJN). PSO Coated
  v3 devient alors le profil CMJN de travail.
- Le profil CMJN de travail se change dans Préférences > Gestion des couleurs
  (« Profil CMJN préféré »).

### Passer une image en CMJN

**Image > Mode > CMJN (impression)** : l'image prend le profil CMJN de travail
(ou garde le sien), l'écran simule l'impression (épreuvage) et les exports TIFF, JPEG
et PSD proposent le CMJN par défaut. L'onglet du document affiche « CMJN/8 ». Pour
revenir : décochez CMJN ou choisissez Image > Mode > RVB (une étape d'annulation).

### Convertir vers un autre profil CMJN

**Image > Gestion des couleurs > Convertir en profil CMJN…** : par exemple de FOGRA39
vers PSO Coated v3, avec le mode de rendu et la compensation du point noir. Les
calques de pixels sont convertis ; les calques de texte et les calques vectoriels
gardent leurs couleurs (elles sont converties à l'export).

### Ouvrir un fichier CMJN

Un fichier CMJN (PSD, TIFF, JPEG) s'ouvre en mode CMJN. Si son profil n'est pas
votre profil de travail, ChopGimp demande, comme Photoshop :

- **Garder** : le document garde son profil ;
- **Convertir** : ses couleurs passent au profil de travail ;
- **Ignorer** : le profil de travail lui est attribué, sans conversion.

« Toujours faire ce choix » évite la question (le choix est gardé dans `chopgimprc`,
section `[color]`). La même fenêtre existe pour un profil RVB, avec un bouton Ignorer.
Un profil illisible ou inutilisable n'est jamais employé : un message le signale et le
profil de travail le remplace.

### Exporter pour l'imprimeur

**Fichier > Exporter > Exporter pour l'imprimeur…**

| Réglage | Choix |
|---|---|
| Format | **PDF/X-4** (vectoriel : tracés et textes en couleurs CMJN, transparence gardée, images en RVB balisé que l'imprimeur convertit), **PDF/X-1a** (chaque page en image CMJN), **TIFF CMJN** |
| Profil CMJN cible | celui de l'image, PSO Coated v3, PSO Uncoated v3 ou ISO Coated v2 : les couleurs sont converties s'il diffère, et il est intégré au fichier (intention de sortie) |
| Mode de rendu, compensation du point noir | comme pour la conversion |
| Fond perdu | 3 mm par défaut ; ce qui dépasse du plan de travail est gardé, sinon du blanc |
| Traits de coupe | en couleur de repérage, hors du fond perdu (PDF) |
| Plans de travail | image entière, une page ou un fichier par plan de travail |
| Noir pur en 100 % K | les tracés et textes noirs n'utilisent que l'encre noire (PDF/X-4) |

La résolution est celle de l'image (Image > Taille d'impression) : 300 ppp pour
l'impression offset.

## 6. Raccourcis clés

| Raccourci | Action |
|---|---|
| V / A | Sélection (Déplacement) / Sélection directe (le Lasso direct est dans son groupe, sans raccourci : Q reste le masque) |
| P / U / T | Plume / Forme / Texte |
| B / E / G | Pinceau / Gomme / Dégradé |
| L / M / W | Lasso (l'outil affiché du groupe) / Rectangle de sélection / Baguette magique |
| H / R / Espace | Main / Rotation de la vue / Main tant que la touche est enfoncée |
| Maj+W / Maj+O | Largeur / Plan de travail |
| K / Maj+K | Pot de peinture dynamique / Sélection de peinture dynamique |
| Ctrl+T | Transformation manuelle |
| Ctrl+D | Répéter la dernière transformation (objets) |
| Ctrl+G / Ctrl+Maj+G | Grouper / Dissocier |
| Ctrl+Z / Ctrl+Maj+Z | Annuler / Rétablir |
| Alt+clic droit glissé | Taille et dureté du pinceau |
| Ctrl+F | Recherche universelle |
| Ctrl+Maj+Alt+I | Grille de perspective |
| Ctrl+Maj+Alt+X | Peinture dynamique |
| Ctrl+Maj+Alt+W | Exporter sous |

L'outil actif se change aussi d'un clic sur son icône : la liste des outils de son
groupe s'ouvre.

## 7. En cas de problème

- **Plantage** : au redémarrage, ChopGimp propose le rapport (journal de session et
  pile d'appels). Joignez-le à votre signalement.
- **Revenir au comportement de GIMP** : chaque nouveauté a son interrupteur
  `CHOPGIMP_*`. La liste se trouve dans le README, section
  [Interrupteurs](../README.md#interrupteurs-chopgimp_).
  Exemple : `flatpak run --env=CHOPGIMP_NO_VOBJECTS=1 org.cen_na.ChopGimp`.

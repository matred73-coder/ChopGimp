## 3.29.3 — Sélection directe façon Illustrator, outils rangés, objets souples (NON COMPILÉ)

- **Sélection directe (A)** (`gimptoolpath.c`) : ne crée plus jamais de point. Dans le vide (avec ou sans objet en cours), un appui trace un rectangle de sélection ; relier / supprimer / insérer reviennent à la Plume ; un clic sur une ligne sélectionne le segment (ses deux nœuds, Maj ajoute). Poignées d'angles dynamiques redessinées dès qu'un objet est pris (`gimppathtool.c`).
- **Boîte à outils** : bloc vectoriel rangé par intention — A seule ; Plume · Courbure ; Crayon · Lissage ; Formes ; Bâtisseur · Peinture dynamique · Sélection de peinture dynamique ; Largeur · Enveloppe ; Ciseaux · Cutter · Jonction ; Filet · Transition ; Texte. Raccourcis inchangés. La Gomme vectorielle est une commande (menu Vecteur), pas un outil.
- **Clic direct** (outil V, mode objets) : un clic prend la forme sous le pointeur même dans un groupe, un double-clic son groupe ; Vecteur > Sélectionner > « Un clic sélectionne le groupe » pour la manière d'Illustrator.
- **Fond / Contour** : avec V sur des objets sélectionnés, la couleur de premier plan est leur fond et celle d'arrière-plan leur contour — nuancier, palettes, sélecteur, pipette et X les recolorent (une annulation par rafale). `CHOPGIMP_NO_FG_RECOLOR=1` pour couper.
- **Vecteur > Sélectionner** : Même couleur de fond / de contour / Même couleur, Inverser, Objets plus petits que… ; **Vecteur > Nettoyer** : Supprimer les petits objets…, Fusionner les formes de même couleur (une annulation) ; **Vecteur > Couleurs** : Permuter fond et contour, Fond : aucun, Contour : aucun ; Verrouiller / Masquer les autres objets (Ctrl+Maj+Alt+2 / 3).
- PDB `chopgimp-vobjects-command` : select-same-*, select-inverse, select-smaller:, delete-smaller:, merge-same-color, swap-fill-stroke, fill-none, lock-others, hide-others.
- Tests : 4 nouveaux (petits objets, même fond, fusion par couleur, ordre de la boîte à outils).
- **Pipette (I)** : avec des objets sélectionnés, un clic sur un autre objet leur copie son fond et son contour (Illustrator) ; ailleurs ou avec une touche, prélèvement de couleur habituel.
- **Survol** (V) : la barre d'état dit ce qu'un clic prendra (nom, couleur de fond, groupe) ; **Tab** passe à l'objet suivant sous le pointeur.
- **Barre d'un résultat de Vectoriser** : phrase d'aide et boutons Décomposer / Dissocier / Supprimer.
- **Vecteur > Nettoyer** : Simplifier… (écart en px), Remplir les petits trous… (trous plus petits que côté²), sur la sélection ou tout le calque, une annulation. PDB simplify:, fill-holes:.
- Sélection directe : un simple clic sur un segment ne crée plus d'étape d'annulation vide.
- Tests : 6 nouveaux.
- **Non fait** : mode isolation grisé (entrer dans un groupe par double-clic existe, sans grisé), menu clic droit propre aux objets (le clic droit ouvre le menu de l'image, qui contient Vecteur), info-bulle flottante (remplacée par la barre d'état), panneau « Couleurs du dessin » (Vecteur > Redéfinir les couleurs liste déjà les couleurs et leurs nombres), aperçu en direct de Simplifier, export SVG `<meshgradient>` et tangentes du filet.

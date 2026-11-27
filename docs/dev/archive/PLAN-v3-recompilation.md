# PhotoGIMP Pro v3 — GIMP recompilé « façon Photoshop » + paquet Flatpak

*Plan rédigé le 2026-11-11 — cible : Linux uniquement — périmètre : complet, barre d'options comprise.*

## Objectif

Passer d'une **surcouche de configuration** (v2, sur le GIMP Snap) à un **logiciel recompilé** :
GIMP 3.2.8 + une série de modifications du code (patchs) + réglages Photoshop intégrés d'origine,
livré en **paquet Flatpak** installable sur n'importe quel poste Linux, avec mises à jour.

La v2 reste maintenue comme solution de repli pour le GIMP Snap.

## Architecture

```
photogimp-pro/
├── patches/gimp-3.2.8/       série de patchs (git format-patch) appliqués sur le tag GIMP_3_2_8
├── flatpak/
│   ├── org.cen_na.PhotoGimpPro.yml   manifeste (dérivé du manifeste officiel Flathub org.gimp.GIMP)
│   └── modules/                      dépendances (babl, GEGL… versions alignées sur GIMP 3.2.8)
├── data/                     thème PS-Dark, icônes PS-Line, menus, gimprc système, modèles…
├── plug-ins/                 photogimp_ps + plug-ins v1 validés
├── tools/                    générateurs existants (menus, raccourcis, outils, documents) + scripts de build
└── Makefile                  make source | make build | make bundle | make repo | make test
```

- **Identifiant de l'application** : `org.cen_na.PhotoGimpPro`. Il est distinct de `org.gimp.GIMP`, donc les deux peuvent être installés côte à côte. La configuration est séparée, dans `~/.var/app/org.cen_na.PhotoGimpPro/`.
- **Réglages intégrés d'origine** :
  - menus, thème et icônes installés dans le dossier de données de l'application ;
  - `etc/gimp/3.0/gimprc`, `sessionrc`, `toolrc`, `templaterc` et `controllerrc` comme valeurs système ;
  - raccourcis et options d'outils modifiés directement dans le code C.
- **Contournements supprimés** : plus de variable `GIMP_TESTING_MENUS_PATH`, de lanceur spécial ni de copie des icônes.

## Phases

### Phase 0 — Chaîne de compilation (2 à 3 jours)
- Installer `flatpak-builder` et les runtimes GNOME/Freedesktop requis par le manifeste officiel.
- Reprendre le manifeste Flathub de GIMP 3.2.8, renommer l'application, compiler GIMP **sans modification**.
- Produire `PhotoGimpPro-3.2.8-v3.0.0-alpha.flatpak`, l'installer à côté du Snap, vérifier qu'il démarre.
- Écrire `make` : compilation reproductible, appliquée sur le tag officiel puis sur nos patchs.

### Phase 1 — Réglages v2 intégrés → **v3.0.0 déployable** (2 à 3 jours)
- Intégrer le thème, les icônes, les menus Photoshop générés à la compilation, la disposition, les modèles, les préréglages, la molette et le plug-in photogimp_ps, ainsi que les 24 plug-ins v1 validés.
- Raccourcis Photoshop et options d'outils (déplacement du calque actif, recadrage destructif, Ctrl+T proportionnel, tolérance 32…) modifiés dans le code C : ils deviennent les valeurs d'usine.
- Vérification : banc de test des plug-ins, plus une liste de contrôle visuelle avec toi.

### Phase 2 — Comportements Photoshop dans le code (1,5 à 2 semaines)
| # | Modification | Fichiers GIMP concernés |
|---|---|---|
| 1 | Sélections : Maj = ajouter, **Alt = soustraire**, Maj+Alt = intersection | `app/tools/gimpselectiontool.c` |
| 2 | Tampon / correcteur : **Alt+clic** = définir la source | `app/tools/gimpsourcetool.c` |
| 3 | Zoom : Alt = zoom arrière | `app/tools/gimpmagnifytool.c` |
| 4 | Déplacement : **Ctrl+clic** = sélection automatique du calque sous le curseur | `app/tools/gimpmovetool.c` |
| 5 | Panneau Calques : Ctrl+clic sur la vignette = charger la sélection, Alt+clic sur l'œil = isoler | `app/widgets/gimplayertreeview.c`, `gimpitemtreeview.c` |
| 6 | Panneau Calques : **bouton fx** dans la barre du bas (menu Style de calque), double-clic = styles | `app/widgets/gimplayertreeview.c` |
| 7 | Masque d'écrêtage natif (Ctrl+Alt+G) avec indentation du calque écrêté | `app/core/gimplayer.c`, `app/widgets/gimplayertreeview.c` |
| 8 | Touches **1 à 0** = opacité de l'outil de peinture actif, sinon du calque | `app/actions/tools-actions.c`, `context-actions.c` |
| 9 | **Alt+clic droit glissé** = taille (horizontal) / dureté (vertical) du pinceau | `app/tools/gimppainttool.c` |

### Phase 3 — Barre d'options horizontale (3 à 4 semaines)
- Nouveau composant `GimpToolOptionsBar` placé **sous la barre de menus, au-dessus des documents**, en mode fenêtre unique.
- **Contenu commun** : sélecteur de préréglages d'outil (à gauche, comme dans Photoshop), puis les options principales de l'outil actif, sous forme de contrôles compacts générés à partir des propriétés de l'outil.
- **Options retenues par outil**, par exemple :
  - pinceau : forme, taille, dureté, mode, opacité, flux ;
  - sélections : boutons nouvelle / ajouter / soustraire / intersection, contour progressif, lissage ;
  - déplacement : sélection automatique, transformation ;
  - recadrage : ratio, supprimer les pixels ;
  - texte : police, taille, couleur, alignement ;
  - transformation : proportions, interpolation ;
  - etc. pour chaque outil de la boîte.
- Un bouton « … » ouvre toutes les options dans une bulle. Le panneau Options de l'outil reste disponible mais n'est plus affiché par défaut.
- C'est le chantier le plus lourd : une interface à concevoir et valider par familles d'outils.

### Phase 4 — Distribution et mises à jour (1 à 2 jours)
- **Dépôt Flatpak privé** (OSTree, signé GPG) hébergé sur un serveur du CEN. Sur un poste, on l'installe avec `flatpak remote-add` puis `flatpak install`, et les mises à jour arrivent automatiquement par `flatpak update`.
- Le fichier `.flatpak` autonome reste disponible pour une installation hors ligne.
- Documentation de déploiement, et mise à disposition du code source pour respecter la GPLv3.

## Maintenance
- Mises à jour mineures de GIMP (3.2.x) : réappliquer les patchs, généralement en quelques heures.
- Version majeure (3.4) : demande un vrai travail de portage, surtout pour la barre d'options. Il faut le prévoir.
- Chaque version de PhotoGIMP Pro reçoit un numéro, et les anciens paquets `.flatpak` sont conservés.

## Points d'attention
- **Licence** : GPLv3. Le code source des modifications doit accompagner le logiciel, ce que le dépôt git assure.
- **Nom** : « PhotoGIMP » est déjà le nom d'un projet communautaire connu (Diolinux). Un nom propre évitera la confusion. À décider avant la phase 4.
- **Marques** : aucun nom, logo ou icône d'Adobe, ce qui est déjà respecté.
- **Coût machine** : première compilation d'environ 1 h et 10 à 15 Go de disque. Ton poste convient (14 cœurs, 30 Go de RAM, 221 Go libres).

## Estimation totale
Environ **6 à 8 semaines** de travail, phases 0 à 4 comprises. La phase 1 livre déjà une version déployable, au bout de 1 à 1,5 semaine.

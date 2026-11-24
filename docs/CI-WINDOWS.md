# Installateur Windows automatique (GitHub Actions)

Le workflow `.github/workflows/windows.yml` refait sur un serveur Windows de GitHub
ce que décrit [COMPILATION-WINDOWS.md](COMPILATION-WINDOWS.md), sans intervention.

## Quand il se lance

- **À chaque tag `v*`** poussé (par exemple `git push origin v3.27.5`).
  - L'installateur `chopgimp-<version>-setup.exe`, la version portable `.zip` et `SHA256SUMS.txt`
    sont joints à la **Release GitHub** du tag. Elle est créée si elle n'existe pas.
  - Le tag doit correspondre au fichier `VERSION` (`v3.27.5` ↔ `3.27.5`), sinon la compilation s'arrête.
- **À la main** : onglet **Actions > Windows > Run workflow**, en choisissant la branche.
  - Pas de Release : les fichiers sont téléchargeables 14 jours dans l'artefact de l'exécution.

Durée : environ **2 à 3 h** la première fois, moins ensuite grâce au cache ccache. La limite
est de 6 h.

## Ce qu'il fait, dans l'ordre

1. Il installe MSYS2 CLANG64 et les paquets du guide :
   - pour lib2geom : boost, gsl, double-conversion ;
   - pour Vectoriser : potrace ;
   - pour les compléments : hunspell, liblqr et GStreamer ;
   - pour la marque : Pillow.
2. Il récupère les mêmes versions que le Flatpak :
   - babl 0.1.128 et GEGL 0.4.72, avec leurs patchs ;
   - GIMP 3.2.8, avec `git am` de `patches/gimp-3.2.8/*.patch`.
3. Il compile babl, GEGL et exiv2 avec `1_build-deps-msys2.ps1`, puis lib2geom 1.4 (même commit que le Flatpak).
4. Il compile ChopGimp **directement en mode installateur**, en un seul passage au lieu des étapes 5 et 7 du guide, avec les options :
   - `-Dgimpdir=ChopGimp` ;
   - `-Dwindows-installer=true` ;
   - `-Drelocatable-bundle=yes`.

   La compilation **échoue si libpotrace n'est pas trouvé**. Elle est relancée une fois si win_bison perd un fichier.
5. Il compile Resynthesizer 3.0.1, puis refait le dossier autonome `gimp-clang64`.
6. Il applique `install_data.sh` sur ce dossier, puis `windows_bundle_extras.py` (DLL chargées à l'exécution).
7. Il applique `windows_branding.py installer` et lance `3_dist-gimp-inno.ps1` (installateur), puis `make_windows_portable.ps1` (version portable).

## Relancer

- **Une exécution qui a échoué :** sur sa page, **Re-run jobs**.
- **Refaire l'installateur d'un tag existant :** **Run workflow** en choisissant le tag dans la liste des branches. Les fichiers vont alors dans l'artefact, pas dans la Release.
- **Remplacer les fichiers d'une Release :** les supprimer de la Release, puis repousser le tag ou relancer l'exécution du tag.

## Coût

- **Dépôt public** : c'est le cas de `matred73-coder/ChopGimp`, vérifié le 2026-11-24. Les minutes des runners standards sont **gratuites et illimitées**.
- **Si le dépôt devient privé :**
  - la formule gratuite inclut 2 000 minutes par mois, et les minutes **Windows comptent double** ;
  - une compilation de 2 à 3 h consomme donc 240 à 360 minutes, soit environ 5 à 8 versions par mois ;
  - au-delà, c'est facturé ou bloqué selon la limite de dépenses.

## Cache

- **Ce qui est gardé :** ccache (compilation) et les paquets MSYS2.
- **Ce qui n'en profite pas :** un tag ne réutilise que les caches de la branche par défaut et ceux du tag lui-même. Le premier passage d'un nouveau tag repart donc de zéro, sauf si un « Run workflow » sur `master` a déjà rempli le cache.

## Limites

- **Installateur non signé :** Windows affiche « éditeur inconnu ».
- **IA locale absente sous Windows**, comme en compilation manuelle.

## Flatpak (Linux)

`.github/workflows/flatpak.yml` se lance sur les mêmes tags `v*` : runner
Ubuntu 24.04, `flatpak-builder` sur le manifeste commité
`flatpak/org.cen_na.ChopGimp.json` (le même que `make build`), puis
`ChopGimp-<VERSION>.flatpak` et `SHA256SUMS-flatpak.txt` sont joints à la
Release du tag, à côté du `.exe`. Penser à `make manifest` avant de taguer
(le manifeste commité doit lister tous les patchs). Lancement manuel :
Actions > Flatpak > Run workflow (artefact seulement, 14 jours).

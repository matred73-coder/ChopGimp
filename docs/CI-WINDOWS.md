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

## Pièges connus (corrigés pour v3.29.3)

- **Flatpak — « Dependency "exiv2" not found » au module gexiv2** : le
  `flatpak-builder` d'Ubuntu 24.04 (1.4.2) ne passe pas `CMAKE_INSTALL_LIBDIR=lib`,
  donc les modules cmake s'installent dans `/app/lib64`. Le workflow installe
  `flatpak-builder` 1.4.8 depuis le PPA `flatpak/stable` (même version qu'en local).
- **Windows — « Configurer ChopGimp » échoue en 1 s** : PowerShell coupe un
  argument natif non cité comme `-Dpkgconfig.relocatable=true` au point. Toutes les
  options `-D…` de `meson setup` sont donc entre guillemets ; la sortie de meson est
  recopiée dans `meson-setup.log`, publié en annotation en cas d'échec.

## Pièges connus (corrigés pour la version qui suit v3.29.4)

- **Windows — `meson install` échoue juste après les scripts `copy2`** : le
  script suivant est `2_bundle-gimp-uni_base.py`, qui fabrique `gimp-clang64`. Il
  retrouve MSYS2 en cherchant `\bin\python.exe` dans la ligne « Main binary: » de
  `meson-log.txt`. Or `setup-msys2` exporte `MSYSTEM=CLANG64` pour tout le job, et le
  Python de MSYS2 écrit alors ses chemins avec des `/`. La recherche échoue et le
  script s'arrête, avec un Traceback que `2_build-gimp-msys2.ps1` ne garde pas
  (il ne recopie que la sortie standard de `ninja install`). Les étapes PowerShell
  de GIMP retirent donc `MSYSTEM`, comme sur la CI de GIMP. La ligne « Main binary: »
  est affichée à la configuration et publiée en annotation `notice`.
- **Annotations** : si la compilation échoue, `ninja install` est relancé avec sa
  sortie d'erreur dans `install.log`. L'étape « Journal de l'échec » publie d'abord
  les lignes `error` / `FAILED` / `Traceback`, avec leur contexte, puis la fin de
  `install.log`, `steps.log`, `meson-setup.log` et `meson-log.txt`. Elle publie au
  plus 10 annotations d'environ 3,5 Ko, et les journaux complets sont repliés dans
  la sortie de l'étape.

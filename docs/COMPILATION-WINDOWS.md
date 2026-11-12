# Compiler ChopGimp 3.11.1 sous Windows 11 depuis VS Code

ChopGimp, c'est GIMP 3.2.8 recompilé pour ressembler à Photoshop et fonctionner comme lui.
Ce guide produit `C:\gimpshop\_install\bin\gimp-3.2.exe`, puis un installateur `setup.exe` si tu le veux.

> **Temps :** environ 30 min d'installation des outils, puis 1 à 2 h pour la première compilation.
> **Il faut :** environ 15 Go libres sur `C:` et une connexion Internet.

---

## 0. Ce que contient le dossier `gimpshop` du SSD

| Chemin | Contenu |
|---|---|
| `flatpak\ChopGimp-3.11.1.flatpak` | Paquet Linux déjà compilé (inutile sous Windows) |
| `sources\chopgimp-sources-3.11.1.zip` | Toutes les sources pour Windows (voir ci-dessous) |

Dans le zip :

| Dossier | Rôle |
|---|---|
| `gimp-3.2.8-chopgimp\` | GIMP 3.2.8 avec les **patchs ChopGimp déjà appliqués**, `gimp-data` inclus |
| `babl\` | babl **0.1.128**, version figée identique au Flatpak |
| `gegl\` | GEGL **0.4.72**, version figée identique au Flatpak |
| `resynthesizer-3.0.1\` | Moteur du Correcteur localisé (J) et de « Remplir d'après le contenu » (Maj+F5) |
| `ChopGimp-3.11.1\` | Thème, icônes, raccourcis, menus, plug-ins, scripts, patchs |

---

## 1. Installer les outils (une seule fois)

Dans VS Code, ouvre un terminal avec **Terminal > Nouveau terminal** (PowerShell par défaut) et lance :

```powershell
winget install --id MSYS2.MSYS2 -e
winget install --id Git.Git -e
winget install --id Microsoft.PowerShell -e
winget install --id JRSoftware.InnoSetup -e   # seulement pour fabriquer un setup.exe
```

Ensuite, **ferme puis rouvre VS Code** pour qu'il voie les nouveaux programmes.

Autorise ensuite les scripts PowerShell pour ton utilisateur :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Ajouter les terminaux « PowerShell 7 » et « MSYS2 CLANG64 » dans VS Code

1. Fais `Ctrl+Maj+P`, choisis **Préférences : Ouvrir les paramètres utilisateur (JSON)**.
2. Ajoute ce bloc dans les accolades principales :

```jsonc
"terminal.integrated.profiles.windows": {
  "PowerShell 7": {
    "path": "C:\\Program Files\\PowerShell\\7\\pwsh.exe"
  },
  "MSYS2 CLANG64": {
    "path": "C:\\msys64\\usr\\bin\\bash.exe",
    "args": ["--login", "-i"],
    "env": { "MSYSTEM": "CLANG64", "CHERE_INVOKING": "1" }
  }
},
"terminal.integrated.defaultProfile.windows": "PowerShell 7"
```

Pour ouvrir l'un ou l'autre, clique sur la flèche **˅** à côté du **+** du panneau Terminal.

---

## 2. Extraire les sources

Branche le SSD et repère sa lettre de lecteur (ici `E:`, à adapter). Dans **PowerShell 7** :

```powershell
New-Item -ItemType Directory -Force C:\gimpshop | Out-Null
tar -xf E:\gimpshop\sources\chopgimp-sources-3.11.1.zip -C C:\gimpshop
Get-ChildItem C:\gimpshop
```

Tu dois voir `babl`, `gegl`, `gimp-3.2.8-chopgimp`, `resynthesizer-3.0.1` et `ChopGimp-3.11.1`.

> ⚠️ **Utilise un chemin court, sans espace ni accent.**
> ⚠️ `babl` et `gegl` doivent rester **à côté** de `gimp-3.2.8-chopgimp`. Le script de GIMP les compile à la place de leur version de développement.

Ouvre ensuite le dossier dans VS Code avec **Fichier > Ouvrir le dossier… > `C:\gimpshop`**.

---

## 3. Compiler babl, GEGL et ChopGimp

Dans **PowerShell 7** :

```powershell
cd C:\gimpshop\gimp-3.2.8-chopgimp
.\build\windows\1_build-deps-msys2.ps1
```

Ce premier script installe les paquets MSYS2 (GTK, Python…) puis compile babl, GEGL et exiv2. C'est long.
Le message *« fatal: not a git repository »* au sujet de babl ou gegl est **normal**.

```powershell
.\build\windows\2_build-gimp-msys2.ps1
```

Ce second script compile ChopGimp et l'installe dans `C:\gimpshop\_install`.

Pour un premier test de lancement :

```powershell
C:\gimpshop\_install\bin\gimp-3.2.exe
```

---

## 4. Compiler Resynthesizer

Ouvre un terminal **MSYS2 CLANG64** :

```bash
cd /c/gimpshop/resynthesizer-3.0.1
export PKG_CONFIG_PATH=/c/gimpshop/_install/lib/pkgconfig
meson setup _build --prefix=/c/gimpshop/_install
ninja -C _build install
```

Sans Resynthesizer, l'interface fonctionne, mais **J** et **Maj+F5** affichent « module Resynthesizer absent ».

---

## 5. Installer les réglages et plug-ins ChopGimp

Toujours dans **MSYS2 CLANG64** :

```bash
cd /c/gimpshop/ChopGimp-3.11.1
sh tools/install_data.sh /c/gimpshop/_install
```

Ce script installe le thème PS-Dark, les icônes PS-Line, les menus et raccourcis Photoshop, la disposition des panneaux, les options d'outils d'usine, les nuanciers et les plug-ins (`chopgimp_fx`, `photogimp_ps` et les plug-ins v1 validés).

Si `python3` est introuvable :

```bash
pacman -S --needed mingw-w64-clang-x86_64-python
```

Relance ensuite `C:\gimpshop\_install\bin\gimp-3.2.exe` : tu dois retrouver ChopGimp comme sous Linux.

---

## 6. Fabriquer l'installateur `setup.exe` (facultatif)

Dans **PowerShell 7** :

```powershell
cd C:\gimpshop\gimp-3.2.8-chopgimp
.\build\windows\installer\3_dist-gimp-inno.ps1
```

L'installateur n'est pas signé, donc Windows affichera « éditeur inconnu » (choisis *Informations complémentaires > Exécuter quand même*).

> Pour l'instant, le script d'installateur de GIMP ne prend pas en compte l'étape 5. À vérifier au premier essai.

---

## 7. En cas d'erreur, que m'envoyer

| Étape | À copier |
|---|---|
| 3 (deps) | Les dernières lignes du terminal |
| 3 (GIMP) | Les lignes `error:` et `C:\gimpshop\gimp-3.2.8-chopgimp\_build-clang64\meson-logs\meson-log.txt` (la fin) |
| 4 | La sortie de `meson setup` ou de `ninja` |
| 5 | La sortie complète de `install_data.sh` |

---

## Points connus

1. **Les patchs ChopGimp n'ont jamais été compilés sous Windows.** Des erreurs de compilation sont possibles dans les fichiers `app/tools/chopgimp-*.c`, `app/display/gimpoptionsbar.c` et `app/widgets/gimpviewrendererdrawable.c`.
2. **Le dossier de réglages est partagé avec un GIMP officiel.** Sous Windows, ChopGimp range ses réglages dans `%APPDATA%\GIMP\3.2`, comme un GIMP officiel. La séparation n'est faite que pour le Flatpak. **N'installe pas un GIMP officiel sur le même PC pour l'instant.**
3. **`install_data.sh` a été écrit pour Linux.** Il marche dans MSYS2, mais quelques chemins peuvent coincer.
4. Si le premier lancement est bizarre (panneaux vides, anglais), supprime `%APPDATA%\GIMP\3.2` et relance.

---

## Annexe : contexte pour un assistant de code (Claude dans VS Code)

Si tu fais faire la compilation par un assistant dans VS Code, donne-lui cette section.

- **Projet :** ChopGimp, GIMP 3.2.8 modifié pour ressembler à Photoshop. Sources : https://github.com/matred73-coder/ChopGimp (tag `v3.11.1`). Les modifications C sont dans `ChopGimp-3.11.1/patches/gimp-3.2.8/*.patch` et sont **déjà appliquées** dans `gimp-3.2.8-chopgimp/`.
- **Chaîne de compilation :** MSYS2 **CLANG64**, scripts officiels `build/windows/1_build-deps-msys2.ps1` puis `2_build-gimp-msys2.ps1`, préfixe `C:\gimpshop\_install`. babl et GEGL sont figés : les dossiers `C:\gimpshop\babl` et `C:\gimpshop\gegl` remplacent le `git clone` du script.
- **Modules ajoutés :** Resynthesizer 3.0.1 (meson), puis `sh tools/install_data.sh <préfixe>` pour les données ChopGimp.
- **Contraintes :**
  - Ne pas renommer les menus de premier niveau : les plug-ins s'y accrochent par leur libellé anglais.
  - Les couleurs des propriétés GIMP 3.2 sont des `GimpParamSpecColor`.
  - Un outil doit avoir un `help_id` non NULL, sinon il n'est pas enregistré.
- **Corrections attendues propres à Windows :** les modifier de façon portable avec `#ifdef G_OS_WIN32`, sans toucher au comportement Linux et Flatpak.
- **Identité git du projet :** `ChopGimp <mathieu.redon@proton.me>`.

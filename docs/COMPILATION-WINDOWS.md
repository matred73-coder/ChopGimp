# Compiler ChopGimp 3.11.1 sous Windows 11 et fabriquer son installateur

ChopGimp, c'est GIMP 3.2.8 recompilé pour ressembler à Photoshop et fonctionner comme lui.
Ce guide produit **`chopgimp-3.11.1-setup.exe`**, un installateur Windows au nom de ChopGimp.

> **Temps :** environ 30 min pour installer les outils, puis environ 1 h de compilation.
> **Il faut :** environ 15 Go libres sur `C:` et une connexion Internet.
> Procédure vérifiée le 12/11/2026 sur Windows 11 (build 26300), MSYS2 CLANG64 et PowerShell 7.7.

---

## 0. Ce que contient le dossier `gimpshop` du SSD

| Chemin | Contenu |
|---|---|
| `flatpak\ChopGimp-3.11.1.flatpak` | Paquet Linux déjà compilé (inutile sous Windows) |
| `sources\chopgimp-sources-3.11.1.zip` | Toutes les sources pour Windows (voir ci-dessous) |
| `setup-windows\chopgimp-3.11.1-setup.exe` | Installateur Windows déjà fabriqué avec ce guide |

Dans le zip :

| Dossier | Rôle |
|---|---|
| `gimp-3.2.8-chopgimp\` | GIMP 3.2.8 avec les **patchs ChopGimp déjà appliqués**, `gimp-data` inclus |
| `babl\` | babl **0.1.128**, version figée identique au Flatpak |
| `gegl\` | GEGL **0.4.72**, version figée identique au Flatpak |
| `resynthesizer-3.0.1\` | Moteur du Correcteur localisé (J) et de « Remplir d'après le contenu » (Maj+F5) |
| `ChopGimp-3.11.1\` | Thème, icônes, raccourcis, menus, plug-ins, scripts, patchs |

---

## 1. Préparer Windows (une seule fois)

### 1.1 Désactiver le Contrôle intelligent des applications

**Obligatoire.** Ce contrôle bloque tout programme non signé et inconnu de Microsoft : les outils
MSYS2 (`cp.exe`…), les centaines de programmes produits par la compilation, puis ChopGimp lui-même.
Il n'existe aucune liste d'exceptions.

*Sécurité Windows > Contrôle des applications et du navigateur > Paramètres du contrôle intelligent
des applications > **Désactivé***.

Pour vérifier (PowerShell) : `(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy').VerifiedAndReputablePolicyState`
doit afficher `0`.

### 1.2 Installer les outils

Dans VS Code, ouvre un terminal (**Terminal > Nouveau terminal**) et lance :

```powershell
winget install --id MSYS2.MSYS2 -e
winget install --id Git.Git -e
winget install --id Microsoft.PowerShell -e
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Inno Setup est inutile ici : le script de l'installateur le télécharge et l'installe lui-même.
Ferme puis rouvre VS Code.

> winget installe PowerShell 7 en version **Store** : il ne se trouve **pas** dans
> `C:\Program Files\PowerShell\7\`, on le lance par `%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe`.

### 1.3 Ajouter les terminaux « PowerShell 7 » et « MSYS2 CLANG64 » dans VS Code

`Ctrl+Maj+P` > **Préférences : Ouvrir les paramètres utilisateur (JSON)**, puis ajoute (remplace `TONNOM`) :

```jsonc
"terminal.integrated.profiles.windows": {
  "PowerShell 7": {
    "path": "C:\\Users\\TONNOM\\AppData\\Local\\Microsoft\\WindowsApps\\pwsh.exe"
  },
  "MSYS2 CLANG64": {
    "path": "C:\\msys64\\usr\\bin\\bash.exe",
    "args": ["--login", "-i"],
    "env": { "MSYSTEM": "CLANG64", "CHERE_INVOKING": "1" }
  }
},
"terminal.integrated.defaultProfile.windows": "PowerShell 7"
```

---

## 2. Extraire les sources

Dans **PowerShell 7** (adapte `E:` à la lettre du SSD) :

```powershell
New-Item -ItemType Directory -Force C:\gimpshop | Out-Null
tar -xf E:\gimpshop\sources\chopgimp-sources-3.11.1.zip -C C:\gimpshop
Get-ChildItem C:\gimpshop
```

> ⚠️ Chemin court, sans espace ni accent. `babl` et `gegl` restent **à côté** de `gimp-3.2.8-chopgimp`.

**Si le zip ne contient pas encore les patchs Windows 0043 à 0046** (zip 3.11.1 d'origine),
applique-les depuis le dépôt :

```powershell
git clone https://github.com/matred73-coder/ChopGimp.git C:\gimpshop\ChopGimp-repo
cd C:\gimpshop\gimp-3.2.8-chopgimp
foreach ($p in Get-ChildItem C:\gimpshop\ChopGimp-repo\patches\gimp-3.2.8\004[3-6]*.patch) { git apply --binary $p.FullName }
Copy-Item C:\gimpshop\ChopGimp-repo\tools\windows_branding.py C:\gimpshop\ChopGimp-3.11.1\tools\
```

---

## 3. Préparer chaque terminal PowerShell 7

**À taper dans chaque nouveau terminal PowerShell 7** avant les scripts de GIMP :

```powershell
$PSNativeCommandArgumentPassing = 'Legacy'   # les scripts de GIMP en dépendent (sinon : « cc cannot compile programs »)
$env:MSYS_ROOT  = 'C:/msys64'
$env:PYTHONUTF8 = '1'                         # scripts Python ChopGimp en UTF-8
```

Et une fois pour toutes, Pillow (images de l'installateur) :

```powershell
C:\msys64\usr\bin\pacman.exe --noconfirm -S --needed mingw-w64-clang-x86_64-python-pillow
```

---

## 4. Compiler babl, GEGL et exiv2

```powershell
cd C:\gimpshop\gimp-3.2.8-chopgimp
.\build\windows\1_build-deps-msys2.ps1
```

- Le message *« fatal: not a git repository »* au sujet de babl ou gegl est **normal**.
- **MSYS2 se met d'abord à jour lui-même et ferme le script** : c'est normal, relance la même commande.
- Erreur **429** au téléchargement : les miroirs limitent le débit, relance (le reste est en cache).

Rends ensuite les fichiers `.pc` relatifs (exigé pour l'installateur), puis relance le script.
Dans un terminal **MSYS2 CLANG64** :

```bash
cd /c/gimpshop
meson configure babl/_build-clang64 -Dpkgconfig.relocatable=true
meson configure gegl/_build-clang64 -Dpkgconfig.relocatable=true
```

Puis dans **PowerShell 7** (terminal préparé) : `.\build\windows\1_build-deps-msys2.ps1` (GEGL se recompile, ~3 min).

---

## 5. Compiler ChopGimp (premier passage)

Dans **PowerShell 7** :

```powershell
cd C:\gimpshop\gimp-3.2.8-chopgimp
C:\msys64\clang64\bin\python3.exe -I C:\gimpshop\ChopGimp-3.11.1\tools\windows_branding.py ico C:\gimpshop\gimp-3.2.8-chopgimp
.\build\windows\2_build-gimp-msys2.ps1
```

La première commande met l'icône ChopGimp dans `gimp.ico` (déjà fait si le patch 0045 est appliqué ;
la relancer ne fait pas de mal). Le script compile ChopGimp et l'installe dans `C:\gimpshop\_install`.

---

## 6. Compiler Resynthesizer

Dans **MSYS2 CLANG64** (avant l'étape 7, pour qu'il entre dans l'installateur) :

```bash
cd /c/gimpshop/resynthesizer-3.0.1
export PKG_CONFIG_PATH=/c/gimpshop/_install/lib/pkgconfig
meson setup _build --prefix=/c/gimpshop/_install
ninja -C _build install
```

---

## 7. Recompiler ChopGimp en mode « installateur »

Dans **MSYS2 CLANG64** :

```bash
cd /c/gimpshop/gimp-3.2.8-chopgimp
meson configure _build-clang64 -Dgimpdir=ChopGimp -Dpkgconfig.relocatable=true \
                               -Dwindows-installer=true -Drelocatable-bundle=yes
```

- `-Dgimpdir=ChopGimp` : réglages dans `%APPDATA%\ChopGimp\3.2`, jamais dans ceux d'un GIMP officiel.
- `-Dwindows-installer=true -Drelocatable-bundle=yes` : fabrique le dossier autonome
  `gimp-3.2.8-chopgimp\gimp-clang64` que l'installateur empaquette.

Puis dans **PowerShell 7** (terminal préparé) :

```powershell
$env:PATH = 'C:\gimpshop\winflexbison;' + $env:PATH
.\build\windows\2_build-gimp-msys2.ps1
```

> Si la compilation s'arrête sur *« no such file … imap_cern_parse.c »*, relance la même commande
> (`win_bison` lancé en parallèle perd parfois un fichier ; ninja le régénère au passage suivant).

---

## 8. Installer les données ChopGimp

`ninja install` réinstalle les fichiers d'origine de GIMP : les données ChopGimp s'appliquent **après**,
sur le dossier autonome (pour l'installateur) et sur `_install` (pour lancer ChopGimp sans l'installer).
Dans **MSYS2 CLANG64** :

```bash
export PYTHONUTF8=1
cd /c/gimpshop/ChopGimp-3.11.1
sh tools/install_data.sh /c/gimpshop/gimp-3.2.8-chopgimp/gimp-clang64
sh tools/install_data.sh /c/gimpshop/_install
```

> ⚠️ `install_data.sh` ajoute ses réglages à la fin de `gimprc` : ne le lance qu'**une fois** après
> chaque `ninja install`.

---

## 9. Fabriquer `chopgimp-3.11.1-setup.exe`

Dans **PowerShell 7** (terminal préparé) :

```powershell
cd C:\gimpshop\gimp-3.2.8-chopgimp
C:\msys64\clang64\bin\python3.exe -I C:\gimpshop\ChopGimp-3.11.1\tools\windows_branding.py installer C:\gimpshop\gimp-3.2.8-chopgimp\_build-clang64
.\build\windows\installer\3_dist-gimp-inno.ps1
```

- La première commande remplace les images de l'installateur (icône, accueil, page de fin) par
  celles de ChopGimp et passe ses textes (47 langues) au nom de ChopGimp.
- Le script installe Inno Setup pour ton utilisateur et produit
  `C:\gimpshop\gimp-3.2.8-chopgimp\chopgimp-3.11.1-setup.exe` (~110 Mo).

L'installateur n'est pas signé : Windows affiche « éditeur inconnu » (*Informations complémentaires
> Exécuter quand même*). Sur un PC où le Contrôle intelligent des applications est actif, il est bloqué.

Pour une autre version : `$env:CHOPGIMP_VERSION = '3.11.2'` avant la commande, et mettre à jour
la valeur par défaut `CHOPGIMP_VERSION` de `build/windows/installer/gimp-setup.iss` (patch 0046).

---

## 10. En cas d'erreur, que m'envoyer

| Étape | À copier |
|---|---|
| 4 | Les dernières lignes du terminal |
| 5, 7 | Les lignes `error:` / `FAILED:` et la fin de `C:\gimpshop\gimp-3.2.8-chopgimp\_build-clang64\meson-logs\meson-log.txt` |
| 6 | La sortie de `meson setup` ou de `ninja` |
| 8 | La sortie complète de `install_data.sh` |
| 9 | Les lignes `(ERROR)` et les dernières lignes du terminal |

---

## Points connus

1. **Ce que l'installateur sépare d'un GIMP officiel** (patchs 0044 à 0046) : dossier
   `Program Files\ChopGimp`, réglages `%APPDATA%\ChopGimp\3.2`, entrée de désinstallation, raccourcis,
   associations de fichiers, mutex et fenêtre d'instance unique.
2. **Ce qui reste partagé** : les exécutables s'appellent toujours `gimp-3.2.exe`, donc la clé
   « Ouvrir avec » `Software\Classes\Applications\gimp-3.2.exe` est commune avec un GIMP officiel.
3. **`gimp.ico`** du patch 0045 est généré par `tools/windows_branding.py ico` : le régénérer si le logo change.
4. Si le premier lancement est bizarre (panneaux vides, anglais), supprime `%APPDATA%\ChopGimp\3.2` et relance.

---

## Annexe : contexte pour un assistant de code (Claude dans VS Code)

- **Projet :** ChopGimp, GIMP 3.2.8 modifié pour ressembler à Photoshop. Sources :
  https://github.com/matred73-coder/ChopGimp. Les modifications C sont dans
  `patches/gimp-3.2.8/*.patch` (0043 à 0046 = Windows) et sont **déjà appliquées** dans `gimp-3.2.8-chopgimp/`.
- **Chaîne de compilation :** MSYS2 **CLANG64**, scripts officiels `build/windows/1_build-deps-msys2.ps1`,
  `2_build-gimp-msys2.ps1`, `installer/3_dist-gimp-inno.ps1`, préfixe `C:\gimpshop\_install`.
  babl et GEGL sont figés : les dossiers `C:\gimpshop\babl` et `C:\gimpshop\gegl` remplacent le `git clone` du script.
- **Pièges vérifiés :**
  - lancer les scripts avec `$PSNativeCommandArgumentPassing = 'Legacy'` (PowerShell ≥ 7.3) ;
  - `PYTHONUTF8=1` pour les scripts Python ChopGimp (sinon `cp1252` et `UnicodeEncodeError`) ;
    `python -I` ignore cette variable ;
  - Git pour Windows n'est pas dans le `PATH` d'un shell MSYS2 : un `meson configure` de babl lancé
    de là échoue ; préférer relancer les scripts officiels depuis PowerShell ;
  - `-Dpkgconfig.relocatable=true` (babl, GEGL, GIMP) est exigé par le script de bundle ; la CI de
    GIMP le passe via `PKGCONF_RELOCATABLE_OPTION`, les scripts locaux non.
- **Modules ajoutés :** Resynthesizer 3.0.1 (meson), puis `sh tools/install_data.sh <préfixe>`,
  puis `tools/windows_branding.py installer <build>` avant `3_dist-gimp-inno.ps1`.
- **Contraintes :**
  - Ne pas renommer les menus de premier niveau : les plug-ins s'y accrochent par leur libellé anglais.
  - Les couleurs des propriétés GIMP 3.2 sont des `GimpParamSpecColor`.
  - Un outil doit avoir un `help_id` non NULL, sinon il n'est pas enregistré.
- **Corrections propres à Windows :** de façon portable (`#ifdef G_OS_WIN32` ou fichiers propres à
  Windows), sans toucher au comportement Linux et Flatpak.
- **Identité git du projet :** `ChopGimp <mathieu.redon@proton.me>`.

# ═══════════════════════════════════════════════════════════════
# ChopGimp — version portable Windows (sans installation)
#
#   pwsh tools/make_windows_portable.ps1 [-Bundle <gimp-clang64>] [-OutDir <dossier>] [-Version <x.y.z>]
#
# À lancer après l'étape 8 de docs/COMPILATION-WINDOWS.md (données ChopGimp
# appliquées au dossier autonome gimp-clang64). Produit :
#   <OutDir>\ChopGimp-<version>-portable\        (dossier prêt à l'emploi)
#   <OutDir>\ChopGimp-<version>-portable.zip
#
# Ce que fait l'installateur et que la version portable doit faire elle-même :
#   - PATH des plug-ins dans lib\gimp\3.0\environ\default.env ;
#   - fichiers d'interpréteurs (Python, Script-Fu) avec des chemins absolus :
#     le lanceur ChopGimp.cmd les réécrit à chaque lancement (dossier déplaçable).
# Les réglages vont dans .\profil (GIMP3_DIRECTORY), jamais dans %APPDATA%.
# ═══════════════════════════════════════════════════════════════
param(
    [string]$Bundle  = 'C:\gimpshop\gimp-3.2.8-chopgimp\gimp-clang64',
    [string]$OutDir  = 'C:\gimpshop\portable',
    [string]$Version = (Get-Content (Join-Path $PSScriptRoot '..\VERSION') -TotalCount 1).Trim()
)
$ErrorActionPreference = 'Stop'

$name = "ChopGimp-$Version-portable"
$dst  = Join-Path $OutDir $name
$zip  = Join-Path $OutDir "$name.zip"
if (-not (Test-Path "$Bundle\bin\gimp-3.2.exe")) { throw "Dossier autonome introuvable : $Bundle" }
if (-not (Select-String -Quiet -Path "$Bundle\etc\gimp\3.0\gimprc" -Pattern 'PS-Dark')) {
    throw "Données ChopGimp absentes de $Bundle : lancer d'abord tools/install_data.sh sur ce dossier"
}

foreach ($p in $dst, $zip) { if (Test-Path $p) { Remove-Item -Recurse -Force $p } }
New-Item -ItemType Directory -Force $dst | Out-Null

# 1. Copie sans débogage (*.pdb) ni kit de développement (include, *.a, *.pc),
#    comme l'installation par défaut
robocopy $Bundle $dst /E /NFL /NDL /NJH /NJS /NP /XF *.pdb *.a *.pc gimp.cmd /XD "$Bundle\include" "$Bundle\lib\pkgconfig" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy a échoué ($LASTEXITCODE)" }

# 2. PATH des plug-ins, relatif au dossier (même ligne que l'installateur)
Add-Content -Encoding utf8 "$dst\lib\gimp\3.0\environ\default.env" "`nPATH=`${gimp_installation_dir}\bin`n"

# 3. Lanceur
$cmd = @'
@echo off
rem ChopGimp portable : les reglages restent dans le dossier "profil" a cote de ce fichier.
rem A chaque lancement, les fichiers d'interpreteurs (Python, Script-Fu) sont reecrits avec
rem le chemin reel du dossier, comme le fait l'installateur : le dossier peut etre deplace.
setlocal
chcp 65001 >nul
set "D=%~dp0"
set "D=%D:~0,-1%"
set "I=%D%\lib\gimp\3.0\interpreters"
set "SF=%D%\bin\gimp-script-fu-interpreter-3.0.exe"

> "%I%\pygimp.interp"     echo python=%D%\bin\python.exe
>>"%I%\pygimp.interp"     echo python3=%D%\bin\python.exe
>>"%I%\pygimp.interp"     echo /usr/bin/python=%D%\bin\python.exe
>>"%I%\pygimp.interp"     echo /usr/bin/python3=%D%\bin\python.exe
rem Separateur virgule (et non deux-points) : le chemin Windows contient "C:"
>>"%I%\pygimp.interp"     echo ,Python,E,,py,,%D%\bin\python.exe,

> "%I%\pygimp_win.interp" echo python=%D%\bin\pythonw.exe
>>"%I%\pygimp_win.interp" echo python3=%D%\bin\pythonw.exe
>>"%I%\pygimp_win.interp" echo /usr/bin/python=%D%\bin\pythonw.exe
>>"%I%\pygimp_win.interp" echo /usr/bin/python3=%D%\bin\pythonw.exe
>>"%I%\pygimp_win.interp" echo ,Python,E,,py,,%D%\bin\pythonw.exe,

for %%F in (gimp-script-fu-interpreter.interp gimp-script-fu-interpreter_win.interp) do (
  > "%I%\%%F" echo gimp-script-fu-interpreter=%SF%
  >>"%I%\%%F" echo gimp-script-fu-interpreter-3.0=%SF%
  >>"%I%\%%F" echo /usr/bin/gimp-script-fu-interpreter=%SF%
  >>"%I%\%%F" echo ,ScriptFu,E,,scm,,%SF%,
)

set "GIMP3_DIRECTORY=%D%\profil"
if /i "%~1"=="--preparer" exit /b 0
start "" "%D%\bin\gimp-3.2.exe" %*
'@
[IO.File]::WriteAllText("$dst\ChopGimp.cmd", ($cmd -replace "`r?`n", "`r`n"), [Text.Encoding]::ASCII)

$readme = @"
ChopGimp $Version - version portable (sans installation)
=====================================================

Lancer ChopGimp : double-cliquer sur ChopGimp.cmd

- Rien n'est installe sur le PC : on peut copier ce dossier sur une cle USB ou un disque externe.
- Les reglages (raccourcis, panneaux, preferences) sont ranges dans le sous-dossier "profil",
  cree au premier lancement. Supprimer "profil" = revenir aux reglages d'usine.
- Pour desinstaller : supprimer le dossier.

Si Windows bloque le lancement
- "Windows a protege votre ordinateur" : Informations complementaires > Executer quand meme.
- Si le Controle intelligent des applications de Windows 11 est actif, ChopGimp ne peut pas
  demarrer (programme non signe).

ChopGimp est derive de GIMP (gimp.org), sous licence GPLv3.
Sources : https://github.com/matred73-coder/ChopGimp
"@
[IO.File]::WriteAllText("$dst\LISEZMOI.txt", ($readme -replace "`r?`n", "`r`n"), [Text.Encoding]::UTF8)

# 4. Zip
Push-Location $OutDir
try { tar.exe -a -cf "$name.zip" $name; if ($LASTEXITCODE) { throw "tar a échoué" } } finally { Pop-Location }

$size = (Get-ChildItem $dst -Recurse -File | Measure-Object Length -Sum).Sum
"== $dst ($([math]::Round($size/1MB)) Mo)"
"== $zip ($([math]::Round((Get-Item $zip).Length/1MB)) Mo, sha256 $((Get-FileHash $zip).Hash.ToLower()))"

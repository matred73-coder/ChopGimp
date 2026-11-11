# Déployer ChopGimp sur des postes Linux

ChopGimp (ex-PhotoGIMP Pro v3) est GIMP 3.2.8 recompilé avec une interface et des gestes façon Photoshop.
Il est livré en **Flatpak** sous l'identifiant `org.cen_na.ChopGimp`. Il s'installe à côté
d'un GIMP existant sans le modifier, et sa configuration est séparée
(`~/.var/app/org.cen_na.ChopGimp/`).

## Prérequis sur le poste
- Flatpak installé (`sudo apt install flatpak` sur Ubuntu/Debian).
- Le dépôt Flathub, qui fournit l'environnement GNOME 51 nécessaire :
  `flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo`

## Option A — fichier autonome (hors ligne ou poste isolé)
```bash
flatpak install --user -y ChopGimp-<version>.flatpak
```
Si l'environnement GNOME 51 n'est pas encore présent, il est téléchargé depuis Flathub.
Mettre à jour : réinstaller le fichier de la version suivante (`--reinstall`).

## Option B — dépôt privé avec mises à jour automatiques (recommandé pour un parc)
Côté serveur, sur la machine de compilation :
```bash
make build GPG_KEY=<clé>                 # compile et signe
make repo  GPG_KEY=<clé> REPO_DEST=serveur:/var/www/photogimp/repo \
           REPO_URL=https://<serveur>/photogimp/repo
```
Cela publie le dépôt et produit `dist/chopgimp.flatpakrepo` et `dist/ChopGimp.flatpakref`.
Le dépôt est un simple dossier statique servi en HTTPS (nginx, Apache…).

Côté poste (une seule fois, à l'échelle du système) :
```bash
sudo flatpak remote-add --if-not-exists photogimp https://<serveur>/photogimp/chopgimp.flatpakrepo
sudo flatpak install -y photogimp org.cen_na.ChopGimp
```
Les mises à jour arrivent ensuite avec `flatpak update`, ou automatiquement par GNOME Logiciels.

## Désinstaller
```bash
flatpak uninstall org.cen_na.ChopGimp        # ajouter --delete-data pour effacer la configuration
```

## Licence
ChopGimp est dérivé de GIMP, sous licence GPLv3. Le code source complet (patchs, recette
de compilation, données) est dans le dépôt git du projet et doit être fourni avec le logiciel.
Les icônes PS-Line et le thème PS-Dark sont des créations originales ; aucun élément d'Adobe
n'est utilisé.

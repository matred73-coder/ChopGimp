# ═══════════════════════════════════════════════════════════════
# ChopGimp (ex-PhotoGIMP Pro v3) — GIMP recompilé façon Photoshop (Flatpak)
#
#   make patches   exporte la série thématique depuis build/gimp-src (branche photogimp-v2)
#   make build     compile le Flatpak (GIMP 3.2.8 + patchs + données)
#   make bundle    produit dist/ChopGimp-<version>.flatpak (installable hors ligne)
#   make install   installe le paquet pour l'utilisateur courant
#   make run       lance ChopGimp
#   make repo      publie le dépôt de mises à jour dans $(REPO_DEST)
#   make vanilla   compile GIMP 3.2.8 sans modification (référence)
#
# Variables : LTO=1|all|0   optimisation à l'édition de liens (1 = babl et GEGL, défaut ;
#                           all = GIMP aussi ; 0 = aucune)
#             PGO=1          GIMP optimisé d'après un profil d'exécution (compilation ×2,
#                           voir tools/dev/pgo_train.py)
#             GIMP_O=2|3     niveau d'optimisation de GIMP (défaut 2)
#             GPG_KEY=<id>   signe le dépôt et le paquet
#             REPO_DEST=<chemin ou serveur rsync>   destination de « make repo »
#             REPO_URL=<https://…/photogimp/repo>   URL publique du dépôt
# ═══════════════════════════════════════════════════════════════

APP       := org.cen_na.ChopGimp
VERSION   := $(shell cat VERSION)
FLATHUB   := https://dl.flathub.org/repo/flathub.flatpakrepo
REPO_DEST ?= dist/repo-public
REPO_URL  ?= https://example.cen-na.org/photogimp/repo
GPG       := $(if $(GPG_KEY),--gpg-sign=$(GPG_KEY),)
LTO       ?= 1
PGO       ?= 0
GIMP_O    ?= 2
FB        := flatpak-builder --user --ccache --disable-rofiles-fuse --force-clean \
             --install-deps-from=flathub --state-dir=.flatpak-builder

.PHONY: patches manifest build bundle install run repo vanilla clean

# 4.2.1 : série regroupée par thèmes (docs/dev/PATCHS.md), un commit par thème
# sur la branche $(GIMP_BRANCH) de build/gimp-src ; la série entière est
# réexportée (un correctif = un « fixup » du thème, puis rebase --autosquash).
# Le patch de l'icône Windows (ancien 0045) ne se régénère pas depuis gimp-src
# (il touche le sous-module gimp-data) : il est gardé tel quel. L'ancienne
# série (un patch par commit) reste dans la branche photogimp-legacy et dans
# les étiquettes v4.2.0 et antérieures du projet.
GIMP_BRANCH  ?= photogimp-v2
ICON_SUBJECT := Windows identity of the executables
EXPORT_DIR   := build/patches-export

patches:
	@set -e; d=patches/gimp-3.2.8; mkdir -p $(EXPORT_DIR); \
	 rm -f $(EXPORT_DIR)/*.patch $(EXPORT_DIR)/icon.keep; \
	 icon=$$(grep -l "^Subject: .*$(ICON_SUBJECT)" $$d/*.patch | head -1); \
	 if [ -z "$$icon" ]; then echo "ERREUR : patch de l'icône Windows introuvable"; exit 1; fi; \
	 cp "$$icon" $(EXPORT_DIR)/icon.keep; \
	 git -C build/gimp-src format-patch -q --zero-commit --no-signature \
	   -o $(CURDIR)/$(EXPORT_DIR) GIMP_3_2_8..$(GIMP_BRANCH); \
	 new=$$(grep -l "^Subject: .*$(ICON_SUBJECT)" $(EXPORT_DIR)/0*.patch | head -1); \
	 if [ -z "$$new" ]; then echo "ERREUR : commit de l'icône Windows absent de $(GIMP_BRANCH)"; exit 1; fi; \
	 cp $(EXPORT_DIR)/icon.keep "$$new"; \
	 rm -f $$d/*.patch; mv $(EXPORT_DIR)/0*.patch $$d/; rm -f $(EXPORT_DIR)/icon.keep; \
	 echo "$$(ls $$d/*.patch | wc -l) patchs exportés depuis $(GIMP_BRANCH)"

manifest:
	CHOPGIMP_LTO=$(LTO) CHOPGIMP_PGO=$(PGO) CHOPGIMP_GIMP_O=$(GIMP_O) python3 tools/make_manifest.py

build: manifest
	cd flatpak && $(FB) --repo=repo $(GPG) --default-branch=stable \
	  --subject="ChopGimp $(VERSION)" build-dir $(APP).json

bundle:
	mkdir -p dist
	flatpak build-bundle $(GPG) --runtime-repo=$(FLATHUB) flatpak/repo \
	  dist/ChopGimp-$(VERSION).flatpak $(APP) stable
	@ls -lh dist/ChopGimp-$(VERSION).flatpak

install:
	flatpak install --user -y --reinstall dist/ChopGimp-$(VERSION).flatpak

run:
	flatpak run $(APP)

repo:
	mkdir -p $(REPO_DEST)
	flatpak build-update-repo $(GPG) --generate-static-deltas --prune flatpak/repo
	rsync -a --delete flatpak/repo/ $(REPO_DEST)/
	python3 tools/make_repofiles.py "$(REPO_URL)" "$(GPG_KEY)" dist
	@echo "Dépôt publié dans $(REPO_DEST) ; fichiers d'installation dans dist/"

vanilla:
	python3 tools/make_manifest.py --vanilla
	cd flatpak && $(FB) --repo=repo-vanilla build-dir-vanilla $(APP).vanilla.json

clean:
	rm -rf flatpak/build-dir flatpak/build-dir-vanilla

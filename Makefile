# ═══════════════════════════════════════════════════════════════
# PhotoGIMP Pro v3 — GIMP recompilé façon Photoshop (Flatpak)
#
#   make patches   exporte les patchs depuis build/gimp-src (branche photogimp)
#   make build     compile le Flatpak (GIMP 3.2.8 + patchs + données)
#   make bundle    produit dist/PhotoGimpPro-<version>.flatpak (installable hors ligne)
#   make install   installe le paquet pour l'utilisateur courant
#   make run       lance PhotoGIMP Pro
#   make repo      publie le dépôt de mises à jour dans $(REPO_DEST)
#   make vanilla   compile GIMP 3.2.8 sans modification (référence)
#
# Variables : GPG_KEY=<id>   signe le dépôt et le paquet
#             REPO_DEST=<chemin ou serveur rsync>   destination de « make repo »
#             REPO_URL=<https://…/photogimp/repo>   URL publique du dépôt
# ═══════════════════════════════════════════════════════════════

APP       := org.cen_na.PhotoGimpPro
VERSION   := $(shell cat VERSION)
FLATHUB   := https://dl.flathub.org/repo/flathub.flatpakrepo
REPO_DEST ?= dist/repo-public
REPO_URL  ?= https://example.cen-na.org/photogimp/repo
GPG       := $(if $(GPG_KEY),--gpg-sign=$(GPG_KEY),)
FB        := flatpak-builder --user --ccache --disable-rofiles-fuse --force-clean \
             --install-deps-from=flathub --state-dir=.flatpak-builder

.PHONY: patches manifest build bundle install run repo vanilla clean

patches:
	cd build/gimp-src && rm -f ../../patches/gimp-3.2.8/*.patch && \
	  git format-patch -q -o ../../patches/gimp-3.2.8 GIMP_3_2_8..photogimp 2>/dev/null || \
	  git format-patch -q -o ../../patches/gimp-3.2.8 7addd2b..photogimp
	@ls patches/gimp-3.2.8

manifest:
	python3 tools/make_manifest.py

build: manifest
	cd flatpak && $(FB) --repo=repo $(GPG) --default-branch=stable \
	  --subject="PhotoGIMP Pro $(VERSION)" build-dir $(APP).json

bundle:
	mkdir -p dist
	flatpak build-bundle $(GPG) --runtime-repo=$(FLATHUB) flatpak/repo \
	  dist/PhotoGimpPro-$(VERSION).flatpak $(APP) stable
	@ls -lh dist/PhotoGimpPro-$(VERSION).flatpak

install:
	flatpak install --user -y --reinstall dist/PhotoGimpPro-$(VERSION).flatpak

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

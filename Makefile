# easy MQTT handler 2 Makefile - Copyright (C) 2023 A. Zeil
#
# This is a thin convenience wrapper. All real logic lives in tasks.py, which
# runs identically on Windows, Linux and macOS. You can always call it directly:
#
#     python tasks.py <task>
#     python tasks.py --help
#
PYTHON ?= python3

.PHONY: help venv activate-venv clean translation-templates compile-translations \
        regenerate-icons test dev package package-portable build-all-linux \
        build-linux-appimage build-linux-flatpak build-macos-app

help:
	@$(PYTHON) tasks.py --help

venv:
	@$(PYTHON) tasks.py venv

# kept under its historical name so existing docs and muscle memory still work
activate-venv: venv

clean:
	@$(PYTHON) tasks.py clean

translation-templates:
	@$(PYTHON) tasks.py translation-templates

compile-translations:
	@$(PYTHON) tasks.py compile-translations

regenerate-icons:
	@$(PYTHON) tasks.py icons

test:
	@$(PYTHON) tasks.py test

dev:
	@$(PYTHON) tasks.py dev

package: venv
	@$(PYTHON) tasks.py package

# Windows-only: self-contained portable .zip with a data/ folder inside
package-portable: venv
	@$(PYTHON) tasks.py package-portable

build-all-linux: venv
	@$(PYTHON) tasks.py build-all-linux

build-linux-appimage: venv
	@$(PYTHON) tasks.py build --platform linux --format appimage

build-linux-flatpak: venv
	@$(PYTHON) tasks.py package --platform linux --format flatpak

build-macos-app: venv
	@$(PYTHON) tasks.py build --platform macOS --format app

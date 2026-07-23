"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  util/AppInfo.py
*
*  Resolves the program's own name, version and URL at runtime, so that they
*  never have to be repeated in the source and can never drift from
*  pyproject.toml, which is the single place they are defined.
*
*  Copyright (C) 2026 AtmanActive
"""
import os
from functools import lru_cache
from pathlib import Path

# the distribution briefcase installs alongside the packaged app
DISTRIBUTION_NAME = "easy-mqtt-handler"

# used when neither source of information is available, which should only ever
# happen if the app is run from an incomplete copy of the source tree
FALLBACK_NAME = "Easy MQTT Handler 2"
FALLBACK_URL = "https://github.com/AtmanActive/easy-mqtt-handler-2"
UNKNOWN_VERSION = "unknown"


def _from_installed_metadata():
    """Read the metadata briefcase writes next to the packaged app."""
    try:
        from importlib import metadata

        info = metadata.metadata(DISTRIBUTION_NAME)
    except Exception:
        return None

    # briefcase records the display name separately from the package name
    name = info.get("Formal-Name") or info.get("Name")
    return {
        "name": name or FALLBACK_NAME,
        "version": info.get("Version") or UNKNOWN_VERSION,
        "url": info.get("Home-page") or FALLBACK_URL,
    }


def _find_pyproject():
    """Look for pyproject.toml above this file, for runs from a source tree."""
    for parent in Path(os.path.abspath(__file__)).parents:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def _from_pyproject():
    """Fall back to pyproject.toml, which is how a dev checkout finds itself."""
    pyproject = _find_pyproject()
    if pyproject is None:
        return None

    try:
        import tomllib

        with open(pyproject, "rb") as handle:
            config = tomllib.load(handle)["tool"]["briefcase"]

        # there is exactly one app defined; read its key rather than hardcoding
        app = next(iter(config["app"].values()))
    except Exception:
        return None

    return {
        "name": app.get("formal_name", FALLBACK_NAME),
        "version": config.get("version", UNKNOWN_VERSION),
        "url": config.get("url", FALLBACK_URL),
    }


@lru_cache(maxsize=1)
def get_app_info():
    """Return the program's name, version and URL.

    The packaged app answers from its installed metadata; a source checkout
    answers from pyproject.toml.
    """
    return (_from_installed_metadata()
            or _from_pyproject()
            or {"name": FALLBACK_NAME, "version": UNKNOWN_VERSION, "url": FALLBACK_URL})


def get_name():
    return get_app_info()["name"]


def get_version():
    return get_app_info()["version"]


def get_url():
    return get_app_info()["url"]

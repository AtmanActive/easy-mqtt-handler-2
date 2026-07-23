"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_app_info.py
*
*  Tests that the program can report its own name, version and URL
*
*  Copyright (C) 2026 AtmanActive
"""
import re
import tomllib
from pathlib import Path

import pytest

from easy_mqtt_handler.util import AppInfo

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


@pytest.fixture(autouse=True)
def clear_cache():
    # the lookup is cached for the life of the process
    AppInfo.get_app_info.cache_clear()
    yield
    AppInfo.get_app_info.cache_clear()


def read_pyproject():
    with open(PYPROJECT, "rb") as handle:
        return tomllib.load(handle)["tool"]["briefcase"]


def test_version_matches_pyproject():
    # the About dialog would otherwise quietly show a stale version
    assert AppInfo.get_version() == read_pyproject()["version"]


def test_version_looks_like_a_version():
    assert re.match(r"^\d+\.\d+\.\d+$", AppInfo.get_version())


def test_name_matches_pyproject():
    expected = next(iter(read_pyproject()["app"].values()))["formal_name"]

    assert AppInfo.get_name() == expected


def test_url_matches_pyproject():
    assert AppInfo.get_url() == read_pyproject()["url"]


def test_url_is_a_real_looking_url():
    assert AppInfo.get_url().startswith("https://")


def test_info_has_every_field_populated():
    info = AppInfo.get_app_info()

    assert set(info) == {"name", "version", "url"}
    assert all(value for value in info.values())


def test_falls_back_when_no_source_of_information_is_available(monkeypatch):
    # neither installed metadata nor a reachable pyproject.toml
    monkeypatch.setattr(AppInfo, "_from_installed_metadata", lambda: None)
    monkeypatch.setattr(AppInfo, "_from_pyproject", lambda: None)
    AppInfo.get_app_info.cache_clear()

    info = AppInfo.get_app_info()

    # it must still answer rather than raise, so the dialog always opens
    assert info["name"] == AppInfo.FALLBACK_NAME
    assert info["version"] == AppInfo.UNKNOWN_VERSION
    assert info["url"] == AppInfo.FALLBACK_URL


def test_broken_installed_metadata_falls_through_to_pyproject(monkeypatch):
    monkeypatch.setattr(AppInfo, "_from_installed_metadata", lambda: None)
    AppInfo.get_app_info.cache_clear()

    assert AppInfo.get_version() == read_pyproject()["version"]

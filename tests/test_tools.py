"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_tools.py
*
*  Tests for the Utils helper collection
*
*  Copyright (C) 2023 A. Zeil
"""
import datetime
import os

from easy_mqtt_handler.util.Tools import Utils


def test_get_config_path_is_platform_specific():
    path = Utils.get_config_path()

    assert "easy-mqtt-handler" in path
    if os.name == "nt":
        # %appdata% must have been expanded, not passed through verbatim
        assert "%appdata%" not in path
    else:
        assert path.startswith(os.path.expanduser("~"))


def test_create_path_if_not_exists_reports_creation_only_once(tmp_path):
    target = str(tmp_path / "config")

    assert Utils.create_path_if_not_exists(target) is True
    assert os.path.isdir(target)
    # second call finds the directory already there
    assert Utils.create_path_if_not_exists(target) is False


def test_get_timestamp_matches_expected_format():
    # the app renders log lines with this exact layout
    datetime.datetime.strptime(Utils.get_timestamp(), "%d.%m.%Y, %H:%M:%S")


def test_load_license_file_returns_contents(tmp_path):
    license_file = tmp_path / "COPYING"
    license_file.write_text("GNU GENERAL PUBLIC LICENSE", encoding="utf-8")

    assert Utils.load_license_file(str(license_file)) == "GNU GENERAL PUBLIC LICENSE"


def test_load_license_file_falls_back_when_missing(tmp_path):
    result = Utils.load_license_file(str(tmp_path / "does-not-exist"))

    assert "couldn't be loaded" in result


def test_resource_path_resolves_against_package_root():
    # assets live next to the util package, so this is how the app finds them
    resolved = Utils.resource_path("assets/app-icon/app-icon.ico")

    assert os.path.exists(resolved)

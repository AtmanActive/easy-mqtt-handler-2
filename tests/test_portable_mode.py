"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_portable_mode.py
*
*  Tests for automatic portable mode: a "data" directory next to the executable
*  redirects all runtime configuration into it
*
*  Copyright (C) 2026 AtmanActive
"""
import os
import sys

import pytest

from easy_mqtt_handler.util.Tools import Utils


@pytest.fixture(autouse=True)
def clear_portable_env(monkeypatch):
    # tests must not inherit these from the surrounding environment
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.delenv(Utils.PORTABLE_DATA_ENV_VAR, raising=False)


@pytest.fixture
def fake_exe_dir(tmp_path, monkeypatch):
    """Pretend the executable lives in a throwaway directory."""
    exe_dir = tmp_path / "app"
    exe_dir.mkdir()
    monkeypatch.setattr(Utils, "get_executable_directory", staticmethod(lambda: str(exe_dir)))
    return exe_dir


def test_portable_mode_is_off_without_a_data_directory(fake_exe_dir):
    assert Utils.get_portable_data_path() is None
    assert Utils.is_portable() is False


def test_portable_mode_is_on_when_data_directory_exists(fake_exe_dir):
    (fake_exe_dir / "data").mkdir()

    assert Utils.is_portable() is True
    assert Utils.get_portable_data_path() == str(fake_exe_dir / "data") + os.sep


def test_config_path_uses_the_data_directory(fake_exe_dir):
    (fake_exe_dir / "data").mkdir()

    assert Utils.get_config_path() == str(fake_exe_dir / "data") + os.sep


def test_config_path_falls_back_to_the_os_location(fake_exe_dir):
    # no "data" directory, so the well known per-user location is used
    config_path = Utils.get_config_path()

    assert "easy-mqtt-handler" in config_path
    assert str(fake_exe_dir) not in config_path


def test_a_file_named_data_does_not_enable_portable_mode(fake_exe_dir):
    # only a directory counts; a stray file of the same name must be ignored
    (fake_exe_dir / "data").write_text("not a directory", encoding="utf-8")

    assert Utils.is_portable() is False


def test_config_files_land_in_the_data_directory(fake_exe_dir):
    data_dir = fake_exe_dir / "data"
    data_dir.mkdir()

    assert Utils.get_settings_file() == str(data_dir / Utils.DEFAULT_SETTINGS_FILENAME)
    assert Utils.get_payload_file() == str(data_dir / Utils.DEFAULT_PAYLOADS_FILENAME)


def test_config_files_follow_the_os_location_when_not_portable(fake_exe_dir):
    settings = Utils.get_settings_file()
    payloads = Utils.get_payload_file()

    assert settings.endswith(Utils.DEFAULT_SETTINGS_FILENAME)
    assert payloads.endswith(Utils.DEFAULT_PAYLOADS_FILENAME)
    assert os.path.dirname(settings) == os.path.dirname(payloads)
    assert str(fake_exe_dir) not in settings


def test_portable_mode_is_decided_at_call_time(fake_exe_dir):
    # the data directory may appear after import, so nothing may be cached
    assert Utils.is_portable() is False

    (fake_exe_dir / "data").mkdir()

    assert Utils.is_portable() is True


def test_certificate_chain_temp_file_follows_portable_mode(fake_exe_dir):
    data_dir = fake_exe_dir / "data"
    data_dir.mkdir()

    # get_certificate_chain writes its scratch .pem next to the config
    assert Utils.get_config_path() + "tmp.pem" == str(data_dir / "tmp.pem")


def test_executable_directory_is_absolute():
    assert os.path.isabs(Utils.get_executable_directory())


def test_the_env_var_names_the_data_directory(tmp_path, monkeypatch):
    """The Linux portable launcher sets this.

    Its bundled interpreter lives in usr/bin, well below the folder the user
    unpacked, so the data directory beside the launcher has to be named rather
    than discovered.
    """
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv(Utils.PORTABLE_DATA_ENV_VAR, str(data))

    assert Utils.is_portable() is True
    assert Utils.get_config_path() == str(data) + os.sep


def test_the_env_var_wins_over_a_neighbouring_folder(fake_exe_dir, monkeypatch, tmp_path):
    (fake_exe_dir / "data").mkdir()
    named = tmp_path / "elsewhere"
    named.mkdir()
    monkeypatch.setenv(Utils.PORTABLE_DATA_ENV_VAR, str(named))

    assert Utils.get_config_path() == str(named) + os.sep


def test_a_missing_named_directory_turns_portable_mode_off(fake_exe_dir, monkeypatch, tmp_path):
    # deleting the data folder must revert to the per-user location, even
    # though the launcher still sets the variable
    monkeypatch.setenv(Utils.PORTABLE_DATA_ENV_VAR, str(tmp_path / "gone"))

    assert Utils.is_portable() is False
    assert "easy-mqtt-handler" in Utils.get_config_path()


def test_an_empty_env_var_is_ignored(fake_exe_dir, monkeypatch):
    (fake_exe_dir / "data").mkdir()
    monkeypatch.setenv(Utils.PORTABLE_DATA_ENV_VAR, "")

    # falls back to looking beside the executable
    assert Utils.get_config_path() == str(fake_exe_dir / "data") + os.sep


def test_appimage_variable_is_not_consulted(tmp_path, monkeypatch):
    """AppImages have their own portable convention.

    Ours must not compete with it, so an .AppImage with a data folder beside it
    is deliberately not treated as portable.
    """
    appimage = tmp_path / "Easy_MQTT_Handler_2.AppImage"
    appimage.write_text("", encoding="utf-8")
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("APPIMAGE", str(appimage))

    assert Utils.get_executable_directory() == os.path.dirname(os.path.abspath(sys.executable))

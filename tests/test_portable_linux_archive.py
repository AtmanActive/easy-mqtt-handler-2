"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_portable_linux_archive.py
*
*  Tests for the Linux portable .tar.gz, the counterpart of the Windows
*  portable .zip: the app folder plus a data folder, and no AppImage
*
*  Copyright (C) 2026 AtmanActive
"""
import sys
import tarfile

import pytest

import tasks

VERSION = "2.0.5"
APP_NAME = "easy-mqtt-handler"
FORMAL_NAME = "Easy MQTT Handler 2"
LABEL = f"{FORMAL_NAME}-{VERSION}-Portable"


@pytest.fixture
def built_archive(tmp_path, monkeypatch):
    """Run the packaging task against a stand-in AppDir."""
    appdir = tmp_path / "build" / APP_NAME / "linux" / "appimage" / f"{FORMAL_NAME}.AppDir"
    (appdir / "usr" / "bin").mkdir(parents=True)
    (appdir / "usr" / "app" / "easy_mqtt_handler").mkdir(parents=True)
    (appdir / "usr" / "lib").mkdir(parents=True)

    (appdir / "AppRun").write_text("#!/bin/sh\n", encoding="utf-8")
    (appdir / "usr" / "bin" / "python3").write_text("", encoding="utf-8")
    (appdir / "usr" / "app" / "easy_mqtt_handler" / "__main__.py").write_text("", encoding="utf-8")
    (appdir / "usr" / "lib" / "libQt5Core.so.5").write_text("", encoding="utf-8")
    # a leftover from local testing, which must not reach the release
    (appdir / "data").mkdir()
    (appdir / "data" / "default-settings.json").write_text('{"hostname": "secret"}', encoding="utf-8")

    dist = tmp_path / "dist"
    monkeypatch.setattr(tasks, "ROOT", tmp_path)
    monkeypatch.setattr(tasks, "DIST_DIR", dist)
    monkeypatch.setattr(tasks, "read_briefcase_metadata",
                        lambda: (APP_NAME, FORMAL_NAME, VERSION))
    monkeypatch.setattr(tasks, "task_build", lambda args: None)
    monkeypatch.setattr(sys, "platform", "linux")

    args = type("Args", (), {"platform": None, "format": None})()
    tasks.task_package_portable_linux(args)

    return dist / f"{LABEL}.tar.gz"


def names_in(archive):
    with tarfile.open(archive) as tar:
        return tar.getnames()


def test_the_archive_is_created(built_archive):
    assert built_archive.is_file()


def test_everything_sits_under_one_folder(built_archive):
    tops = {name.split("/")[0] for name in names_in(built_archive)}

    # unpacking must not scatter files into the current directory
    assert tops == {LABEL}


def test_no_appimage_is_shipped(built_archive):
    # an AppImage has its own portable convention and is not wrapped in ours
    assert not any(name.lower().endswith(".appimage") for name in names_in(built_archive))


def test_the_app_folder_is_shipped(built_archive):
    names = names_in(built_archive)

    for expected in (f"{LABEL}/AppRun",
                     f"{LABEL}/usr/bin/python3",
                     f"{LABEL}/usr/app/easy_mqtt_handler/__main__.py",
                     f"{LABEL}/usr/lib/libQt5Core.so.5"):
        assert expected in names


def test_the_launcher_sits_at_the_top_like_the_windows_exe(built_archive):
    assert f"{LABEL}/{FORMAL_NAME}" in names_in(built_archive)


def test_the_launcher_is_executable(built_archive):
    with tarfile.open(built_archive) as tar:
        entry = tar.getmember(f"{LABEL}/{FORMAL_NAME}")

    # a launcher without the executable bit cannot be started at all
    assert entry.mode & 0o111, f"mode was {entry.mode:o}"


def test_the_launcher_points_at_the_data_folder(built_archive):
    with tarfile.open(built_archive) as tar:
        script = tar.extractfile(f"{LABEL}/{FORMAL_NAME}").read().decode("utf-8")

    assert "EASY_MQTT_HANDLER_DATA" in script
    assert '"$here/data"' in script
    # it must launch the bundled app rather than whatever is on the PATH
    assert 'exec "$here/AppRun"' in script


def test_apprun_stays_executable(built_archive):
    with tarfile.open(built_archive) as tar:
        entry = tar.getmember(f"{LABEL}/AppRun")

    # the launcher execs it, so without this the archive cannot start at all
    assert entry.mode & 0o111, f"mode was {entry.mode:o}"


def test_the_data_folder_is_present_and_not_empty(built_archive):
    # a truly empty directory is dropped by some tools, so it carries a readme
    assert f"{LABEL}/data/README.txt" in names_in(built_archive)


def test_a_leftover_data_folder_is_not_shipped(built_archive):
    # a test configuration in the build tree must never reach a release
    with tarfile.open(built_archive) as tar:
        readme = tar.extractfile(f"{LABEL}/data/README.txt").read().decode("utf-8")

    assert f"{LABEL}/data/default-settings.json" not in names_in(built_archive)
    assert "secret" not in readme


def test_the_readme_describes_the_linux_locations(built_archive):
    with tarfile.open(built_archive) as tar:
        readme = tar.extractfile(f"{LABEL}/data/README.txt").read().decode("utf-8")

    assert "~/.config/easy-mqtt-handler/" in readme
    # the Windows wording must not leak into the Linux archive
    assert "%appdata%" not in readme
    assert ".exe" not in readme


def test_symlinks_are_preserved(tmp_path, monkeypatch):
    """Bundled libraries are usually symlinks, and following them would bloat
    the archive and break the sonames they exist to provide."""
    appdir = tmp_path / "build" / APP_NAME / "linux" / "appimage" / f"{FORMAL_NAME}.AppDir"
    (appdir / "usr" / "lib").mkdir(parents=True)
    (appdir / "AppRun").write_text("#!/bin/sh\n", encoding="utf-8")
    real = appdir / "usr" / "lib" / "libfoo.so.1.2.3"
    real.write_text("x", encoding="utf-8")
    try:
        (appdir / "usr" / "lib" / "libfoo.so.1").symlink_to("libfoo.so.1.2.3")
    except (OSError, NotImplementedError):
        pytest.skip("this platform does not allow creating symlinks here")

    monkeypatch.setattr(tasks, "ROOT", tmp_path)
    monkeypatch.setattr(tasks, "DIST_DIR", tmp_path / "dist")
    monkeypatch.setattr(tasks, "read_briefcase_metadata",
                        lambda: (APP_NAME, FORMAL_NAME, VERSION))
    monkeypatch.setattr(tasks, "task_build", lambda args: None)
    monkeypatch.setattr(sys, "platform", "linux")

    args = type("Args", (), {"platform": None, "format": None})()
    tasks.task_package_portable_linux(args)

    with tarfile.open(tmp_path / "dist" / f"{LABEL}.tar.gz") as tar:
        entry = tar.getmember(f"{LABEL}/usr/lib/libfoo.so.1")

    assert entry.issym()


def test_it_refuses_to_build_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "platform", "win32")

    args = type("Args", (), {"platform": None, "format": None})()
    with pytest.raises(SystemExit):
        tasks.task_package_portable_linux(args)


def test_it_fails_when_the_app_was_not_built(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks, "ROOT", tmp_path)
    monkeypatch.setattr(tasks, "DIST_DIR", tmp_path / "dist")
    monkeypatch.setattr(tasks, "read_briefcase_metadata",
                        lambda: (APP_NAME, FORMAL_NAME, VERSION))
    monkeypatch.setattr(tasks, "task_build", lambda args: None)
    monkeypatch.setattr(sys, "platform", "linux")

    args = type("Args", (), {"platform": None, "format": None})()
    with pytest.raises(SystemExit):
        tasks.task_package_portable_linux(args)

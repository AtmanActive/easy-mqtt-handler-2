"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_release_naming.py
*
*  Tests that published artifacts are named after the platform they are for
*
*  Copyright (C) 2026 AtmanActive
"""
import pytest

import tasks

VERSION = "2.0.5"

# the names briefcase and the portable task actually produced for 2.0.5
REAL_ARTIFACTS = [
    ("windows", "Easy MQTT Handler 2-2.0.5.msi",
     "Easy MQTT Handler 2-2.0.5-windows.msi"),
    ("windows", "Easy MQTT Handler 2-2.0.5-Portable.zip",
     "Easy MQTT Handler 2-2.0.5-windows-Portable.zip"),
    ("linux", "Easy_MQTT_Handler_2-2.0.5-x86_64.AppImage",
     "Easy_MQTT_Handler_2-2.0.5-linux-x86_64.AppImage"),
    ("linux", "Easy MQTT Handler 2-2.0.5-Portable.tar.gz",
     "Easy MQTT Handler 2-2.0.5-linux-Portable.tar.gz"),
    ("linux", "Easy MQTT Handler 2-2.0.5.flatpak",
     "Easy MQTT Handler 2-2.0.5-linux.flatpak"),
    ("macos", "Easy MQTT Handler 2-2.0.5.dmg",
     "Easy MQTT Handler 2-2.0.5-macos.dmg"),
]


def test_a_double_extension_is_kept_intact():
    # .tar.gz must not become .tar-linux.gz or lose the .tar
    renamed = tasks.add_platform_to_name(
        "Easy MQTT Handler 2-2.0.5-Portable.tar.gz", "linux", VERSION)

    assert renamed.endswith(".tar.gz")


@pytest.mark.parametrize("platform,original,expected", REAL_ARTIFACTS)
def test_real_artifact_names_get_their_platform(platform, original, expected):
    assert tasks.add_platform_to_name(original, platform, VERSION) == expected


@pytest.mark.parametrize("platform,original,expected", REAL_ARTIFACTS)
def test_the_extension_is_preserved(platform, original, expected):
    renamed = tasks.add_platform_to_name(original, platform, VERSION)

    assert renamed.rpartition(".")[2] == original.rpartition(".")[2]


@pytest.mark.parametrize("platform,original,_expected", REAL_ARTIFACTS)
def test_every_artifact_names_its_platform(platform, original, _expected):
    renamed = tasks.add_platform_to_name(original, platform, VERSION)

    assert platform in renamed.lower()


def test_renaming_is_idempotent():
    # collecting twice, or a name that already says windows, must not repeat it
    once = tasks.add_platform_to_name("app-2.0.5.msi", "windows", VERSION)
    twice = tasks.add_platform_to_name(once, "windows", VERSION)

    assert once == twice
    assert once.lower().count("windows") == 1


def test_the_version_is_still_present():
    renamed = tasks.add_platform_to_name("app-2.0.5.msi", "linux", VERSION)

    assert VERSION in renamed


def test_a_name_without_the_version_still_gets_labelled():
    assert tasks.add_platform_to_name("installer.msi", "windows", VERSION) == \
        "installer-windows.msi"


def test_a_name_without_an_extension_still_gets_labelled():
    assert tasks.add_platform_to_name("installer", "linux", VERSION) == "installer-linux"


def test_only_the_first_version_occurrence_is_used():
    # a version appearing twice must not produce two platform labels
    renamed = tasks.add_platform_to_name("app-2.0.5-build-2.0.5.zip", "macos", VERSION)

    assert renamed.lower().count("macos") == 1
    assert renamed == "app-2.0.5-macos-build-2.0.5.zip"


@pytest.mark.parametrize("directory,expected", [
    ("windows", "windows"),
    ("macos", "macos"),
    # both Linux uploads must still say just "linux" in the released filename
    ("linux-appimage", "linux"),
    ("linux-flatpak", "linux"),
    ("Linux-AppImage", "linux"),
])
def test_platform_label_drops_the_format_suffix(directory, expected):
    assert tasks.platform_label(directory) == expected


def test_both_linux_formats_are_labelled_linux(tmp_path, monkeypatch):
    source = tmp_path / "artifacts"
    (source / "linux-appimage").mkdir(parents=True)
    (source / "linux-flatpak").mkdir(parents=True)
    (source / "linux-appimage" / "Easy_MQTT_Handler_2-2.0.5-x86_64.AppImage").write_text("x")
    (source / "linux-flatpak" / "Easy MQTT Handler 2-2.0.5.flatpak").write_text("x")

    monkeypatch.setattr(tasks, "ROOT", tmp_path)
    monkeypatch.setattr(tasks, "read_briefcase_metadata",
                        lambda: ("easy-mqtt-handler", "Easy MQTT Handler 2", VERSION))

    args = type("Args", (), {"source": "artifacts", "dest": "release"})()
    tasks.task_collect_release(args)

    produced = sorted(p.name for p in (tmp_path / "release").iterdir())
    assert produced == [
        "Easy MQTT Handler 2-2.0.5-linux.flatpak",
        "Easy_MQTT_Handler_2-2.0.5-linux-x86_64.AppImage",
    ]
    # neither name should carry the disambiguating upload suffix
    assert not any("appimage-" in name.lower() for name in produced)


def test_collect_release_renames_and_gathers(tmp_path, monkeypatch):
    source = tmp_path / "artifacts"
    for platform, original, _expected in REAL_ARTIFACTS:
        platform_dir = source / platform
        platform_dir.mkdir(parents=True, exist_ok=True)
        (platform_dir / original).write_text("x", encoding="utf-8")

    monkeypatch.setattr(tasks, "ROOT", tmp_path)
    monkeypatch.setattr(tasks, "read_briefcase_metadata",
                        lambda: ("easy-mqtt-handler", "Easy MQTT Handler 2", VERSION))

    args = type("Args", (), {"source": "artifacts", "dest": "release"})()
    tasks.task_collect_release(args)

    produced = sorted(p.name for p in (tmp_path / "release").iterdir())
    assert produced == sorted(expected for _p, _o, expected in REAL_ARTIFACTS)


def test_collect_release_fails_when_there_is_nothing_to_collect(tmp_path, monkeypatch):
    (tmp_path / "artifacts").mkdir()
    monkeypatch.setattr(tasks, "ROOT", tmp_path)
    monkeypatch.setattr(tasks, "read_briefcase_metadata",
                        lambda: ("easy-mqtt-handler", "Easy MQTT Handler 2", VERSION))

    args = type("Args", (), {"source": "artifacts", "dest": "release"})()
    # an empty upload means the build produced nothing, which must not pass silently
    with pytest.raises(SystemExit):
        tasks.task_collect_release(args)

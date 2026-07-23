"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_theme.py
*
*  Tests for OS light/dark detection and palette selection
*
*  Copyright (C) 2026 AtmanActive
"""
import sys

import pytest

from PyQt5.QtGui import QColor, QPalette

from easy_mqtt_handler.util import Theme


@pytest.fixture(autouse=True)
def clear_theme_override(monkeypatch):
    # the override is read from the environment, so keep tests isolated from it
    monkeypatch.delenv("EASY_MQTT_HANDLER_THEME", raising=False)


def make_palette(window_color):
    palette = QPalette()
    palette.setColor(QPalette.Active, QPalette.Window, window_color)
    return palette


def test_palette_is_dark_for_dark_window():
    assert Theme.palette_is_dark(make_palette(QColor(35, 35, 35))) is True


def test_palette_is_dark_is_false_for_light_window():
    assert Theme.palette_is_dark(make_palette(QColor(240, 240, 240))) is False


def test_dark_palette_is_actually_dark():
    palette = Theme.build_dark_palette()

    assert Theme.palette_is_dark(palette)
    # text has to stay readable against that background
    window = palette.color(QPalette.Active, QPalette.Window)
    text = palette.color(QPalette.Active, QPalette.WindowText)
    assert text.lightness() > window.lightness()


def test_dark_palette_restyles_disabled_text():
    palette = Theme.build_dark_palette()

    disabled = palette.color(QPalette.Disabled, QPalette.WindowText)
    enabled = palette.color(QPalette.Active, QPalette.WindowText)
    # disabled text must be dimmer than normal text but not invisible
    assert disabled.lightness() < enabled.lightness()
    assert disabled.lightness() > palette.color(QPalette.Active, QPalette.Window).lightness()


def test_environment_override_wins(monkeypatch):
    monkeypatch.setenv("EASY_MQTT_HANDLER_THEME", "dark")
    assert Theme.detect_system_theme() == Theme.DARK

    monkeypatch.setenv("EASY_MQTT_HANDLER_THEME", "LIGHT")
    assert Theme.detect_system_theme() == Theme.LIGHT


def test_unknown_override_is_ignored(monkeypatch):
    monkeypatch.setenv("EASY_MQTT_HANDLER_THEME", "chartreuse")
    # falls through to real detection, which must still return a valid answer
    assert Theme.detect_system_theme() in (Theme.DARK, Theme.LIGHT, None)


def test_detect_system_theme_returns_a_known_value():
    assert Theme.detect_system_theme() in (Theme.DARK, Theme.LIGHT, None)


def test_set_titlebar_dark_rejects_a_bogus_handle():
    # must degrade quietly rather than raise; it is decoration, not function
    assert Theme.set_titlebar_dark(0, True) in (True, False)
    assert Theme.set_titlebar_dark("not-a-handle", True) is False


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Windows-only DWM call")
def test_set_titlebar_dark_is_a_noop_off_windows():
    assert Theme.set_titlebar_dark(12345, True) is False

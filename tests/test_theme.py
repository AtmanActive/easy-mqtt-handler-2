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


# --- Linux desktop detection ------------------------------------------------
#
# These mock the individual gsettings reads, so the desktop-specific logic can
# be checked from any platform. The values are what each desktop really returns.

def fake_gsettings(mapping):
    """Return a _gsettings_get stand-in backed by a {(schema, key): value} map."""
    return lambda schema, key: mapping.get((schema, key))


CINNAMON = "org.cinnamon.desktop.interface"
MATE = "org.mate.interface"
GNOME = "org.gnome.desktop.interface"


def test_cinnamon_dark_is_detected(monkeypatch):
    # the exact case reported: Mint Cinnamon in dark mode. The GNOME schema is
    # unhelpful; the Cinnamon theme name is what tells the truth.
    monkeypatch.setattr(Theme, "_gsettings_get", fake_gsettings({
        (CINNAMON, "gtk-theme"): "Mint-Y-Dark-Aqua",
        (GNOME, "color-scheme"): "default",
        (GNOME, "gtk-theme"): "Adwaita",
    }))

    assert Theme._detect_linux() == Theme.DARK


def test_cinnamon_light_is_detected(monkeypatch):
    monkeypatch.setattr(Theme, "_gsettings_get", fake_gsettings({
        (CINNAMON, "gtk-theme"): "Mint-Y-Aqua",
        (GNOME, "color-scheme"): "default",
    }))

    assert Theme._detect_linux() == Theme.LIGHT


def test_mate_dark_is_detected(monkeypatch):
    monkeypatch.setattr(Theme, "_gsettings_get", fake_gsettings({
        (MATE, "gtk-theme"): "Yaru-dark",
    }))

    assert Theme._detect_linux() == Theme.DARK


def test_gnome_prefer_dark_is_detected(monkeypatch):
    monkeypatch.setattr(Theme, "_gsettings_get", fake_gsettings({
        (GNOME, "color-scheme"): "prefer-dark",
    }))

    assert Theme._detect_linux() == Theme.DARK


def test_gnome_prefer_light_is_detected(monkeypatch):
    monkeypatch.setattr(Theme, "_gsettings_get", fake_gsettings({
        (GNOME, "color-scheme"): "prefer-light",
    }))

    assert Theme._detect_linux() == Theme.LIGHT


def test_gnome_default_with_a_dark_theme_is_dark(monkeypatch):
    # color-scheme says nothing, but the chosen GTK theme is clearly dark
    monkeypatch.setattr(Theme, "_gsettings_get", fake_gsettings({
        (GNOME, "color-scheme"): "default",
        (GNOME, "gtk-theme"): "Adwaita-dark",
    }))

    assert Theme._detect_linux() == Theme.DARK


def test_gnome_default_with_a_plain_theme_is_inconclusive(monkeypatch):
    # a bare GNOME theme name is not trusted to mean "light" on its own, so the
    # native palette is left to stand
    monkeypatch.setattr(Theme, "_gsettings_get", fake_gsettings({
        (GNOME, "color-scheme"): "default",
        (GNOME, "gtk-theme"): "Adwaita",
    }))

    assert Theme._detect_linux() is None


def test_kde_falls_through_to_none(monkeypatch):
    # KDE does not populate these gsettings schemas, so detection is
    # inconclusive and the already-correct native Qt palette is kept
    monkeypatch.setattr(Theme, "_gsettings_get", fake_gsettings({}))

    assert Theme._detect_linux() is None


def test_the_cinnamon_schema_wins_over_a_stale_gnome_scheme(monkeypatch):
    # a leftover prefer-light in the GNOME schema must not override Cinnamon's
    # own, current, dark theme
    monkeypatch.setattr(Theme, "_gsettings_get", fake_gsettings({
        (CINNAMON, "gtk-theme"): "Mint-Y-Dark",
        (GNOME, "color-scheme"): "prefer-light",
    }))

    assert Theme._detect_linux() == Theme.DARK


@pytest.mark.parametrize("kind,value,expected", [
    ("scheme", "prefer-dark", Theme.DARK),
    ("scheme", "prefer-light", Theme.LIGHT),
    ("scheme", "default", None),
    ("theme", "Mint-Y-Dark-Aqua", Theme.DARK),
    ("theme", "Mint-Y-Aqua", Theme.LIGHT),
    ("theme-weak", "Adwaita-dark", Theme.DARK),
    ("theme-weak", "Adwaita", None),
])
def test_interpret_linux_theme(kind, value, expected):
    assert Theme._interpret_linux_theme(kind, value) == expected


# --- the manager actually switching the palette -----------------------------

@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_applying_dark_over_a_light_native_palette_darkens_it(app):
    # this is the Cinnamon fix seen end to end: Qt gave us a light palette, but
    # the desktop is dark, so the manager must actually darken the app
    app.setPalette(make_palette(QColor(240, 240, 240)))
    manager = Theme.ThemeManager(app)
    assert not manager._native_is_dark

    manager.apply(Theme.DARK)

    assert Theme.palette_is_dark(app.palette())


def test_applying_light_afterwards_restores_the_native_palette(app):
    app.setPalette(make_palette(QColor(240, 240, 240)))
    manager = Theme.ThemeManager(app)

    manager.apply(Theme.DARK)
    manager.apply(Theme.LIGHT)

    assert not Theme.palette_is_dark(app.palette())


def test_an_already_dark_desktop_is_left_alone(app):
    # KDE: Qt already produced a dark palette, so the manager must not replace it
    app.setPalette(make_palette(QColor(45, 45, 45)))
    manager = Theme.ThemeManager(app)
    assert manager._native_is_dark

    manager.apply(Theme.DARK)

    # still dark, and it kept the native palette rather than the Fusion one
    assert Theme.palette_is_dark(app.palette())


# --- the configured Theme choice --------------------------------------------

def test_resolve_theme_honours_an_explicit_choice():
    assert Theme.resolve_theme("dark") == Theme.DARK
    assert Theme.resolve_theme("light") == Theme.LIGHT


def test_resolve_theme_system_follows_the_os(monkeypatch):
    monkeypatch.setattr(Theme, "detect_system_theme", lambda: Theme.DARK)

    assert Theme.resolve_theme("system") == Theme.DARK


def test_resolve_theme_treats_unknown_and_empty_as_system(monkeypatch):
    monkeypatch.setattr(Theme, "detect_system_theme", lambda: Theme.LIGHT)

    assert Theme.resolve_theme("") == Theme.LIGHT
    assert Theme.resolve_theme("nonsense") == Theme.LIGHT
    assert Theme.resolve_theme(None) == Theme.LIGHT


def test_a_dark_choice_darkens_a_light_native_app(app):
    # the point of the feature: force dark even when the OS is light
    app.setPalette(make_palette(QColor(240, 240, 240)))
    manager = Theme.ThemeManager(app, theme_getter=lambda: "dark")

    manager.sync_with_system()

    assert Theme.palette_is_dark(app.palette())


def test_a_light_choice_keeps_a_light_app_light_even_if_os_is_dark(app, monkeypatch):
    monkeypatch.setattr(Theme, "detect_system_theme", lambda: Theme.DARK)
    app.setPalette(make_palette(QColor(240, 240, 240)))
    manager = Theme.ThemeManager(app, theme_getter=lambda: "light")

    manager.sync_with_system()

    # the explicit light choice wins over the dark OS
    assert not Theme.palette_is_dark(app.palette())


def test_system_choice_follows_detection(app, monkeypatch):
    monkeypatch.setattr(Theme, "detect_system_theme", lambda: Theme.DARK)
    app.setPalette(make_palette(QColor(240, 240, 240)))
    manager = Theme.ThemeManager(app, theme_getter=lambda: "system")

    manager.sync_with_system()

    assert Theme.palette_is_dark(app.palette())


def test_a_broken_theme_getter_falls_back_to_system(app, monkeypatch):
    monkeypatch.setattr(Theme, "detect_system_theme", lambda: Theme.LIGHT)

    def _broken():
        raise RuntimeError("settings not ready")

    manager = Theme.ThemeManager(app, theme_getter=_broken)

    # must not raise; treats a broken getter as "system"
    assert manager._configured_choice() == Theme.SYSTEM


def test_no_getter_means_follow_the_system(app):
    manager = Theme.ThemeManager(app)

    assert manager._configured_choice() == Theme.SYSTEM


def test_set_titlebar_dark_rejects_a_bogus_handle():
    # must degrade quietly rather than raise; it is decoration, not function
    assert Theme.set_titlebar_dark(0, True) in (True, False)
    assert Theme.set_titlebar_dark("not-a-handle", True) is False


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Windows-only DWM call")
def test_set_titlebar_dark_is_a_noop_off_windows():
    assert Theme.set_titlebar_dark(12345, True) is False

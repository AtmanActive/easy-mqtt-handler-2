"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  util/Theme.py
*
*  Detects the operating system's light/dark preference and applies a matching
*  palette to the application.
*
*  Qt5 does not follow the Windows or macOS colour scheme on its own. On Linux
*  the platform theme plugin usually does, which is why the app already looked
*  dark there. So the rule here is: only override when the platform has not
*  already produced a palette matching the system preference.
*
*  Copyright (C) 2023 A. Zeil
*  Copyright (C) 2026 AtmanActive
"""
import os
import subprocess
import sys

from PyQt5.QtCore import QObject, QTimer
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QStyleFactory

DARK = "dark"
LIGHT = "light"

# the extra choice the user can make in the Connection tab: follow the OS
SYSTEM = "system"
# the values offered in the Theme drop down, and stored in the settings file
THEME_CHOICES = (SYSTEM, LIGHT, DARK)
DEFAULT_THEME_CHOICE = SYSTEM

# how often we re-check the system preference so the app can follow a live switch
WATCH_INTERVAL_MS = 2000

# Fusion is the only built-in style that honours a custom palette across every
# widget; the native Windows style paints most controls from the OS theme.
FUSION = "Fusion"

# a palette this dark or darker is treated as an already-dark theme
DARK_LIGHTNESS_THRESHOLD = 128


def _detect_windows():
    """Read the Windows personalisation setting. 0 means dark, 1 means light."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        with key:
            apps_use_light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return LIGHT if apps_use_light else DARK
    except (ImportError, OSError, FileNotFoundError):
        return None


def _detect_macos():
    """AppleInterfaceStyle only exists while dark mode is on."""
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        # the key is absent in light mode, which `defaults` reports as an error
        return LIGHT
    return DARK if "dark" in result.stdout.strip().lower() else LIGHT


# Where each desktop keeps its light/dark preference. The desktop-specific
# schemas come first: on Cinnamon and MATE the GTK theme name is the real
# signal, and the GNOME schema is either absent or stuck at a default that does
# not reflect the actual theme, which is why the app used to stay light there.
#
# The "kind" says how to read the value:
#   scheme      - a color-scheme setting: "prefer-dark"/"prefer-light"/"default"
#   theme       - a GTK theme name from a schema that only exists on that
#                 desktop, so it is authoritative: dark if the name says so,
#                 otherwise light
#   theme-weak  - a GTK theme name from the shared GNOME schema, which is
#                 ambiguous: only a "dark" in the name is trusted
LINUX_THEME_SOURCES = (
    ("org.cinnamon.desktop.interface", "gtk-theme", "theme"),
    ("org.mate.interface", "gtk-theme", "theme"),
    ("org.gnome.desktop.interface", "color-scheme", "scheme"),
    ("org.gnome.desktop.interface", "gtk-theme", "theme-weak"),
)


def _gsettings_get(schema, key):
    """Read one gsettings value, or None if it cannot be read."""
    try:
        result = subprocess.run(
            ["gsettings", "get", schema, key],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        # gsettings is not installed, or hung
        return None

    if result.returncode != 0:
        # the schema is not installed on this desktop
        return None

    value = result.stdout.strip().strip("'\"")
    return value or None


def _interpret_linux_theme(kind, value):
    """Turn one setting's value into DARK, LIGHT, or None (inconclusive)."""
    lowered = value.lower()
    if kind == "scheme":
        if "dark" in lowered:
            return DARK
        if "light" in lowered:
            return LIGHT
        return None  # "default" tells us nothing
    if kind == "theme":
        return DARK if "dark" in lowered else LIGHT
    if kind == "theme-weak":
        return DARK if "dark" in lowered else None
    return None


def _detect_linux():
    """Ask the desktop's own settings, most authoritative source first."""
    for schema, key, kind in LINUX_THEME_SOURCES:
        value = _gsettings_get(schema, key)
        if value is None:
            continue
        result = _interpret_linux_theme(kind, value)
        if result is not None:
            return result
    return None


def detect_system_theme():
    """Return DARK, LIGHT, or None when the preference cannot be determined."""
    # an explicit override always wins, and makes the behaviour testable by hand
    override = os.environ.get("EASY_MQTT_HANDLER_THEME", "").strip().lower()
    if override in (DARK, LIGHT):
        return override

    if sys.platform.startswith("win"):
        return _detect_windows()
    if sys.platform == "darwin":
        return _detect_macos()
    return _detect_linux()


def resolve_theme(theme_choice):
    """Turn the user's choice into the theme to apply.

    A "light" or "dark" choice is honoured directly; "system" (or an empty or
    unfamiliar value, which is what an older settings file has) follows the
    operating system.
    """
    if theme_choice == DARK:
        return DARK
    if theme_choice == LIGHT:
        return LIGHT
    return detect_system_theme()


# DWM attribute that switches a window's title bar to the dark variant. Windows 10
# builds before 18985 used 19 for this, so both are attempted.
_DWMWA_USE_IMMERSIVE_DARK_MODE = (20, 19)


def set_titlebar_dark(window_id, dark):
    """Ask DWM to draw a native title bar in the dark variant.

    Qt5 styles only the client area, so without this the title bar stays light
    while the rest of the window is dark. No-op anywhere but Windows.
    """
    if not sys.platform.startswith("win"):
        return False

    try:
        import ctypes

        value = ctypes.c_int(1 if dark else 0)
        for attribute in _DWMWA_USE_IMMERSIVE_DARK_MODE:
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(int(window_id)),
                ctypes.c_int(attribute),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
            if result == 0:
                return True
    except (ImportError, AttributeError, OSError, ValueError):
        pass
    return False


def palette_is_dark(palette):
    """True when a palette's window background is darker than its text."""
    window = palette.color(QPalette.Active, QPalette.Window)
    return window.lightness() < DARK_LIGHTNESS_THRESHOLD


def build_dark_palette():
    """A neutral dark palette in the spirit of the Fusion style."""
    window = QColor(53, 53, 53)
    base = QColor(35, 35, 35)
    text = QColor(220, 220, 220)
    disabled = QColor(127, 127, 127)
    highlight = QColor(42, 130, 218)

    palette = QPalette()
    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, window)
    palette.setColor(QPalette.ToolTipBase, window)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, window)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, QColor(255, 80, 80))
    palette.setColor(QPalette.Link, highlight)
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))

    # without these, disabled controls keep the light theme's near-black text
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText,
                 QPalette.HighlightedText):
        palette.setColor(QPalette.Disabled, role, disabled)
    palette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(80, 80, 80))

    return palette


class ThemeManager(QObject):
    """Keeps the application palette in step with the OS colour scheme."""

    def __init__(self, app, parent=None, theme_getter=None):
        super().__init__(parent)
        self._app = app
        # returns the user's saved choice ("system"/"light"/"dark"); when it is
        # None or missing we simply follow the operating system. Passed in
        # rather than reading the settings directly, so this stays decoupled
        # from the settings model and works before the settings even exist.
        self._theme_getter = theme_getter
        # remember how the platform styled us before we touched anything, so
        # switching back to light restores the real native look
        self._native_style = app.style().objectName()
        self._native_palette = QPalette(app.palette())
        self._native_is_dark = palette_is_dark(self._native_palette)
        self._applied = None
        self._timer = None
        # windows whose title bar we have already switched, keyed by window id
        self._styled_titlebars = {}

    def _configured_choice(self):
        if self._theme_getter is None:
            return SYSTEM
        try:
            return self._theme_getter() or SYSTEM
        except Exception:  # noqa: BLE001 - a bad getter must never break theming
            return SYSTEM

    @property
    def applied_theme(self):
        return self._applied

    def apply(self, theme):
        """Apply DARK or LIGHT, doing nothing if the platform already matches."""
        if theme not in (DARK, LIGHT) or theme == self._applied:
            return

        if theme == DARK:
            if self._native_is_dark:
                # the platform theme is already dark; leave it alone
                self._restore_native()
            else:
                self._app.setStyle(QStyleFactory.create(FUSION))
                self._app.setPalette(build_dark_palette())
        else:
            self._restore_native()

        self._applied = theme
        self._styled_titlebars.clear()
        self.refresh_titlebars()

    def refresh_titlebars(self):
        """Apply the current theme to every top-level window's title bar.

        Dialogs are created after startup, so this is re-run rather than done
        once; each window is only touched when its state needs to change.
        """
        if self._applied is None:
            return

        dark = self._applied == DARK
        for widget in self._app.topLevelWidgets():
            if not widget.isVisible():
                continue
            window_id = int(widget.winId())
            if self._styled_titlebars.get(window_id) == dark:
                continue
            if set_titlebar_dark(window_id, dark):
                self._styled_titlebars[window_id] = dark

    def _restore_native(self):
        style = QStyleFactory.create(self._native_style)
        if style is not None:
            self._app.setStyle(style)
        self._app.setPalette(self._native_palette)

    def sync_with_system(self):
        """Apply the theme the user asked for, or the OS one when set to system."""
        theme = resolve_theme(self._configured_choice())
        if theme is not None:
            self.apply(theme)
        # catches windows opened since the last check
        self.refresh_titlebars()
        return theme

    def start_watching(self, interval_ms=WATCH_INTERVAL_MS):
        """Poll for changes, so toggling the OS setting updates a running app.

        Qt5 emits no signal for this on Windows, and the checks are cheap, so
        polling is the pragmatic option.
        """
        if self._timer is not None:
            return
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.sync_with_system)
        self._timer.start()

    def stop_watching(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer = None


def install(app, watch=True, theme_getter=None):
    """Apply the chosen theme to app and optionally keep following it.

    theme_getter, when given, returns the saved choice; without it the app
    simply follows the operating system, as it always did.
    """
    manager = ThemeManager(app, theme_getter=theme_getter)
    manager.sync_with_system()
    if watch:
        manager.start_watching()
    return manager

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


def _detect_linux():
    """Ask the XDG desktop settings, falling back to the GTK theme name."""
    for schema, key in (
        ("org.gnome.desktop.interface", "color-scheme"),
        ("org.gnome.desktop.interface", "gtk-theme"),
    ):
        try:
            result = subprocess.run(
                ["gsettings", "get", schema, key],
                capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        if result.returncode != 0:
            continue

        value = result.stdout.strip().strip("'\"").lower()
        if not value:
            continue
        if "dark" in value:
            return DARK
        # an explicit 'prefer-light'/'default' answer from color-scheme is
        # conclusive; a theme name that merely lacks "dark" is not
        if key == "color-scheme" and value != "default":
            return LIGHT

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

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app
        # remember how the platform styled us before we touched anything, so
        # switching back to light restores the real native look
        self._native_style = app.style().objectName()
        self._native_palette = QPalette(app.palette())
        self._native_is_dark = palette_is_dark(self._native_palette)
        self._applied = None
        self._timer = None
        # windows whose title bar we have already switched, keyed by window id
        self._styled_titlebars = {}

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
        """Detect the current preference and apply it."""
        theme = detect_system_theme()
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


def install(app, watch=True):
    """Apply the system theme to app and optionally keep following it."""
    manager = ThemeManager(app)
    manager.sync_with_system()
    if watch:
        manager.start_watching()
    return manager

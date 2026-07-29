"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  util/Fonts.py
*
*  Scales the whole application's font to the size chosen in the Connection tab.
*
*  Copyright (C) 2026 AtmanActive
"""
from PyQt5.QtGui import QFont

# offered in the Font Size drop down, smallest to largest, and stored in the
# settings file
FONT_SIZE_CHOICES = ("xxsmall", "xsmall", "small", "default", "large", "xlarge", "xxlarge")
DEFAULT_FONT_SIZE = "default"

# how much each choice scales the platform's own default font size; "default"
# leaves it exactly as the platform set it
FONT_SIZE_SCALES = {
    "xxsmall": 0.70,
    "xsmall": 0.80,
    "small": 0.90,
    "default": 1.00,
    "large": 1.15,
    "xlarge": 1.30,
    "xxlarge": 1.50,
}


def scale_for(choice):
    return FONT_SIZE_SCALES.get(choice, 1.0)


class FontManager:
    """Applies a font size choice to the whole application."""

    def __init__(self, app, size_getter=None):
        self._app = app
        # returns the saved choice; passed in rather than read from the settings
        # directly, so this stays decoupled and works before the settings exist
        self._size_getter = size_getter
        # the platform's own default font, captured before anything is scaled, so
        # every size is worked out from the same starting point instead of
        # compounding one change onto the last
        self._base_font = QFont(app.font())
        self._applied = None

    @property
    def applied_size(self):
        return self._applied

    def _configured_size(self):
        if self._size_getter is None:
            return DEFAULT_FONT_SIZE
        try:
            return self._size_getter() or DEFAULT_FONT_SIZE
        except Exception:  # noqa: BLE001 - a bad getter must never break the UI
            return DEFAULT_FONT_SIZE

    def apply(self, choice):
        """Scale the application font to the chosen size and return that choice."""
        if choice not in FONT_SIZE_CHOICES:
            choice = DEFAULT_FONT_SIZE

        scale = scale_for(choice)
        font = QFont(self._base_font)
        # a font is sized in points on most platforms, but occasionally in
        # pixels; scale whichever one the platform actually used
        if self._base_font.pointSizeF() > 0:
            font.setPointSizeF(self._base_font.pointSizeF() * scale)
        elif self._base_font.pixelSize() > 0:
            font.setPixelSize(max(1, round(self._base_font.pixelSize() * scale)))

        self._app.setFont(font)
        self._applied = choice
        return choice

    def apply_configured(self):
        return self.apply(self._configured_size())


def install(app, size_getter=None):
    """Apply the saved font size to app, or the default when there is none."""
    manager = FontManager(app, size_getter=size_getter)
    manager.apply_configured()
    return manager

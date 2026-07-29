"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_fonts.py
*
*  Tests for scaling the application font to the chosen size
*
*  Copyright (C) 2026 AtmanActive
"""
import pytest

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

from easy_mqtt_handler.util import Fonts


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fixed_base(app):
    # a known base font so the scaled sizes are predictable
    base = QFont(app.font())
    base.setPointSizeF(10.0)
    app.setFont(base)
    yield
    app.setFont(base)


def test_the_choices_and_scales_line_up():
    # every offered choice has a scale, and nothing extra is scaled
    assert set(Fonts.FONT_SIZE_CHOICES) == set(Fonts.FONT_SIZE_SCALES)


def test_default_scale_is_one():
    assert Fonts.scale_for("default") == 1.0


def test_the_scales_increase_with_size():
    scales = [Fonts.scale_for(choice) for choice in Fonts.FONT_SIZE_CHOICES]

    # smallest to largest, strictly increasing
    assert scales == sorted(scales)
    assert scales[0] < 1.0 < scales[-1]


def test_default_leaves_the_font_unchanged(app, fixed_base):
    manager = Fonts.FontManager(app)

    manager.apply("default")

    assert app.font().pointSizeF() == pytest.approx(10.0)


def test_larger_and_smaller_scale_the_point_size(app, fixed_base):
    manager = Fonts.FontManager(app)

    manager.apply("xxlarge")
    assert app.font().pointSizeF() == pytest.approx(10.0 * 1.5)

    manager.apply("xxsmall")
    assert app.font().pointSizeF() == pytest.approx(10.0 * 0.7)


def test_changes_do_not_compound(app, fixed_base):
    # every size is worked out from the same base, not from the last applied one
    manager = Fonts.FontManager(app)

    manager.apply("xxlarge")
    manager.apply("xxlarge")
    manager.apply("default")

    assert app.font().pointSizeF() == pytest.approx(10.0)


def test_an_unknown_size_falls_back_to_default(app, fixed_base):
    manager = Fonts.FontManager(app)

    applied = manager.apply("gigantic")

    assert applied == "default"
    assert app.font().pointSizeF() == pytest.approx(10.0)


def test_apply_configured_uses_the_getter(app, fixed_base):
    manager = Fonts.FontManager(app, size_getter=lambda: "large")

    manager.apply_configured()

    assert manager.applied_size == "large"
    assert app.font().pointSizeF() == pytest.approx(10.0 * 1.15)


def test_a_broken_getter_falls_back_to_default(app, fixed_base):
    def _broken():
        raise RuntimeError("settings not ready")

    manager = Fonts.FontManager(app, size_getter=_broken)

    manager.apply_configured()

    assert manager.applied_size == "default"


def test_no_getter_means_default(app, fixed_base):
    manager = Fonts.FontManager(app)

    manager.apply_configured()

    assert manager.applied_size == "default"


def test_a_pixel_sized_base_font_is_scaled(app):
    base = QFont(app.font())
    base.setPixelSize(20)
    app.setFont(base)
    try:
        manager = Fonts.FontManager(app)
        manager.apply("xxlarge")

        assert app.font().pixelSize() == round(20 * 1.5)
    finally:
        app.setFont(QFont())

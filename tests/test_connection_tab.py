"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_connection_tab.py
*
*  Tests for the Connection tab's Theme override
*
*  Copyright (C) 2026 AtmanActive
"""
import json

import pytest

from PyQt5.QtWidgets import QApplication

from easy_mqtt_handler.util.MQTTSettings import MQTTSettings
from easy_mqtt_handler.qt.tabs.ConnectionTabWidget import ConnectionTabWidget


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(app, tmp_path):
    MQTTSettings(str(tmp_path / "settings.json"))
    widget = ConnectionTabWidget()
    widget.showEvent(None)  # loads settings and wires the change handlers
    return widget


def test_the_theme_dropdown_offers_the_three_choices(tab):
    items = [tab.theme_dropdown.itemText(i) for i in range(tab.theme_dropdown.count())]

    assert items == ["system", "light", "dark"]


def test_the_theme_defaults_to_system(tab):
    assert tab.theme_dropdown.currentText() == "system"


def test_choosing_a_theme_is_saved_into_the_settings(tab):
    tab.theme_dropdown.setCurrentText("dark")

    # the whole-dict rebuild must carry the theme through
    assert MQTTSettings.get_instance().theme == "dark"


def test_a_connection_edit_does_not_wipe_the_theme(tab):
    tab.theme_dropdown.setCurrentText("dark")
    # now change an unrelated field, which rebuilds the settings dict
    tab.hostname_textbox.setText("broker.example.org")

    settings = MQTTSettings.get_instance()
    assert settings.theme == "dark"
    assert settings.hostname == "broker.example.org"


def test_changing_the_theme_emits_the_live_apply_signal(tab):
    fired = []
    tab.theme_changed.connect(lambda: fired.append(True))

    tab.theme_dropdown.setCurrentText("light")

    assert fired


def test_changing_the_theme_marks_settings_unsaved(tab):
    changed = []
    tab.settings_changed.connect(changed.append)

    tab.theme_dropdown.setCurrentText("dark")

    assert changed


def test_the_saved_theme_is_shown_when_the_tab_is_reopened(app, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    MQTTSettings(str(settings_file))

    widget = ConnectionTabWidget()
    widget.showEvent(None)

    assert widget.theme_dropdown.currentText() == "dark"

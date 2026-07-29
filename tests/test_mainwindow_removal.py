"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_mainwindow_removal.py
*
*  Tests that a confirmed Home Assistant removal deletes the row from the
*  configuration and the table
*
*  Copyright (C) 2026 AtmanActive
"""
import json

import pytest

from PyQt5.QtWidgets import QApplication

from easy_mqtt_handler.util.MQTTPayloads import MQTTPayloads
from easy_mqtt_handler.util.MQTTSettings import MQTTSettings
from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages
from easy_mqtt_handler.qt.MainWindow import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    # empty connection settings, so the worker thread does not try to connect
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"hostname": "", "port": "", "topic": ""}), encoding="utf-8")

    startup_file = tmp_path / "startup.json"
    win = MainWindow(app, str(settings_file), str(tmp_path / "payloads.json"), str(startup_file))
    yield win
    win.worker_thread.quit()
    win.worker_thread.wait(2000)


def test_a_confirmed_removal_deletes_the_matching_row(window):
    store = MQTTStartupMessages.get_instance()
    store.startup_data = [
        {"topic": "keep/me", "type": "literal", "payload": "x"},
        {"topic": "", "type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "gone"},
    ]

    window.on_ha_entity_removal_confirmed("homeassistant/sensor/gone/config")

    remaining = MQTTStartupMessages.get_instance().startup_data
    assert len(remaining) == 1
    assert remaining[0]["topic"] == "keep/me"


def test_the_deletion_is_saved_to_disk(window, tmp_path):
    store = MQTTStartupMessages.get_instance()
    store.startup_data = [
        {"topic": "", "type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "gone"},
    ]

    window.on_ha_entity_removal_confirmed("homeassistant/sensor/gone/config")

    saved = json.loads((tmp_path / "startup.json").read_text(encoding="utf-8"))
    assert saved == []


def test_an_unrelated_confirmation_removes_nothing(window):
    store = MQTTStartupMessages.get_instance()
    store.startup_data = [
        {"topic": "", "type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "gone"},
    ]

    window.on_ha_entity_removal_confirmed("homeassistant/sensor/someone_else/config")

    assert len(MQTTStartupMessages.get_instance().startup_data) == 1


def test_only_the_confirmed_entity_is_removed_when_several_exist(window):
    store = MQTTStartupMessages.get_instance()
    store.startup_data = [
        {"topic": "", "type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "one"},
        {"topic": "", "type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "two"},
    ]

    window.on_ha_entity_removal_confirmed("homeassistant/sensor/one/config")

    remaining = MQTTStartupMessages.get_instance().startup_data
    assert [r["ha_id"] for r in remaining] == ["two"]

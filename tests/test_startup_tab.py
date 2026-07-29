"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_startup_tab.py
*
*  Tests for the "Send on Startup" tab, especially the Payload cell switching
*  between a text box and a drop down as the Type changes
*
*  Copyright (C) 2026 AtmanActive
"""
import pytest

from PyQt5.QtWidgets import QApplication, QComboBox, QTableWidgetItem

from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages
from easy_mqtt_handler.util.StartupPayload import builtin_keys
from easy_mqtt_handler.qt.tabs import StartupTabWidget as stw_module
from easy_mqtt_handler.qt.tabs.StartupTabWidget import (
    StartupTabWidget, COLUMN_TOPIC, COLUMN_PAYLOAD, COLUMN_TYPE, COLUMN_HA_ID,
    REMOVAL_TEXT_COLOR)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def tab(app, tmp_path):
    MQTTStartupMessages(str(tmp_path / "startup.json"))
    widget = StartupTabWidget()
    return widget


def payload_widget(tab, row):
    return tab.table.cellWidget(row, COLUMN_PAYLOAD)


# --- the remove_ha_entity row type ------------------------------------------

def test_a_removal_row_colours_its_text_cells_red(tab):
    tab.add_data("", "", 0, False, ha_entity="sensor", ha_id="old_one",
                 payload_type="remove_ha_entity")

    topic_item = tab.table.item(0, COLUMN_TOPIC)
    id_item = tab.table.item(0, COLUMN_HA_ID)
    assert topic_item.foreground().color() == REMOVAL_TEXT_COLOR
    assert id_item.foreground().color() == REMOVAL_TEXT_COLOR


def test_a_removal_row_colours_its_type_drop_down(tab):
    from PyQt5.QtGui import QPalette

    tab.add_data("", "", 0, False, ha_id="old_one", payload_type="remove_ha_entity")

    type_combo = tab.table.cellWidget(0, COLUMN_TYPE)
    # the colour is carried on the palette, not a style sheet, so it cannot
    # blank the combo's background on some Linux styles
    assert type_combo.palette().color(QPalette.Text) == REMOVAL_TEXT_COLOR
    # and no style sheet was set on the table or the combo
    assert type_combo.styleSheet() == ""
    assert tab.table.styleSheet() == ""


def test_an_ordinary_row_is_not_coloured(tab):
    from PyQt5.QtGui import QPalette

    tab.add_data("t", "ON", 0, False, payload_type="literal")

    assert tab.table.item(0, COLUMN_TOPIC).foreground().color() != REMOVAL_TEXT_COLOR
    assert tab.table.cellWidget(0, COLUMN_TYPE).palette().color(QPalette.Text) != REMOVAL_TEXT_COLOR


def test_switching_a_row_to_removal_turns_it_red_then_back(tab):
    tab.add_data("t", "ON", 0, False, ha_id="x", payload_type="literal")
    assert tab.table.item(0, COLUMN_TOPIC).foreground().color() != REMOVAL_TEXT_COLOR

    tab.table.cellWidget(0, COLUMN_TYPE).setCurrentText("remove_ha_entity")
    assert tab.table.item(0, COLUMN_TOPIC).foreground().color() == REMOVAL_TEXT_COLOR

    tab.table.cellWidget(0, COLUMN_TYPE).setCurrentText("literal")
    assert tab.table.item(0, COLUMN_TOPIC).foreground().color() != REMOVAL_TEXT_COLOR


def test_a_removal_type_is_saved(tab):
    tab.add_data("", "", 0, False, ha_entity="sensor", ha_id="gone",
                 payload_type="remove_ha_entity")
    tab.set_new_startup_data()

    saved = MQTTStartupMessages.get_instance().startup_data
    assert saved[0]["type"] == "remove_ha_entity"
    assert saved[0]["ha_id"] == "gone"


def test_reload_from_settings_rebuilds_the_table(tab):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "a", "type": "literal", "payload": "x"},
        {"topic": "", "type": "remove_ha_entity", "ha_id": "gone"},
    ]

    tab.reload_from_settings()

    assert tab.table.rowCount() == 2
    assert tab.type_value(1) == "remove_ha_entity"


def test_a_literal_row_has_a_text_payload_cell(tab):
    tab.add_data("t", "ON", 0, False, payload_type="literal")

    assert payload_widget(tab, 0) is None
    assert tab.table.item(0, COLUMN_PAYLOAD).text() == "ON"


def test_a_command_row_has_a_text_payload_cell(tab):
    tab.add_data("t", "run.sh", 0, False, payload_type="command")

    assert payload_widget(tab, 0) is None
    assert tab.table.item(0, COLUMN_PAYLOAD).text() == "run.sh"


def test_an_environment_row_has_a_text_payload_cell(tab):
    # the variable name is free text, so no drop down
    tab.add_data("t", "HOME", 0, False, payload_type="environment")

    assert payload_widget(tab, 0) is None
    assert tab.table.item(0, COLUMN_PAYLOAD).text() == "HOME"


def test_switching_from_built_in_to_environment_restores_a_text_cell(tab):
    tab.add_data("t", "networking: hostname", 0, False, payload_type="built-in")
    assert isinstance(payload_widget(tab, 0), QComboBox)

    tab.table.cellWidget(0, 1).setCurrentText("environment")

    assert payload_widget(tab, 0) is None
    assert tab.type_value(0) == "environment"


def test_a_built_in_row_has_a_drop_down_payload_cell(tab):
    tab.add_data("t", "networking: hostname", 0, False, payload_type="built-in")

    widget = payload_widget(tab, 0)
    assert isinstance(widget, QComboBox)
    assert widget.currentText() == "networking: hostname"
    # the drop down offers exactly the registered built-ins
    assert [widget.itemText(i) for i in range(widget.count())] == builtin_keys()


def test_switching_to_built_in_replaces_the_text_cell_with_a_drop_down(tab):
    tab.add_data("t", "whatever", 0, False, payload_type="literal")
    assert payload_widget(tab, 0) is None

    tab.table.cellWidget(0, 1).setCurrentText("built-in")

    assert isinstance(payload_widget(tab, 0), QComboBox)


def test_switching_away_from_built_in_restores_a_text_cell(tab):
    tab.add_data("t", "networking: hostname", 0, False, payload_type="built-in")
    assert isinstance(payload_widget(tab, 0), QComboBox)

    tab.table.cellWidget(0, 1).setCurrentText("literal")

    assert payload_widget(tab, 0) is None
    assert tab.table.item(0, COLUMN_PAYLOAD) is not None


def test_the_type_is_saved(tab):
    tab.add_data("home/x", "networking: hostname", 0, False, payload_type="built-in")

    tab.set_new_startup_data()
    saved = MQTTStartupMessages.get_instance().startup_data

    assert saved[0]["type"] == "built-in"
    assert saved[0]["payload"] == "networking: hostname"


def test_a_disk_built_in_is_offered_in_the_drop_down(tab):
    from easy_mqtt_handler.util import StartupPayload as sp

    if not sp.discover_disks():
        pytest.skip("no disks discovered on this machine")

    tab.add_data("t", "disks: disk 1 free size B", 0, False, payload_type="built-in")

    widget = payload_widget(tab, 0)
    assert isinstance(widget, QComboBox)
    assert widget.currentText() == "disks: disk 1 free size B"


def test_a_stale_disk_key_from_another_machine_is_preserved(tab, monkeypatch):
    from easy_mqtt_handler.util import StartupPayload as sp

    # this machine has one disk, but the config was made where there were five
    monkeypatch.setattr(sp, "discover_disks", lambda: [("only", "/only")])
    tab.add_data("t", "disks: disk 5 free size B", 0, False, payload_type="built-in")

    # the saved value must survive viewing the tab, not be rewritten to disk 1
    assert tab.payload_value(0) == "disks: disk 5 free size B"
    widget = payload_widget(tab, 0)
    assert "disks: disk 5 free size B" in [widget.itemText(i) for i in range(widget.count())]


def test_a_built_in_selection_is_saved(tab):
    tab.add_data("home/x", "", 0, False, payload_type="built-in")
    payload_widget(tab, 0).setCurrentText("time: now unixtime")

    tab.set_new_startup_data()
    saved = MQTTStartupMessages.get_instance().startup_data

    assert saved[0]["payload"] == "time: now unixtime"


def test_a_row_round_trips_through_save_and_reload(tab):
    tab.add_data("home/x", "run.sh", 2, True, "sensor", "an_id", "A Name",
                 payload_type="command")
    tab.set_new_startup_data()

    # re-showing rebuilds the table from what was saved
    tab.showEvent(None)

    assert tab.type_value(0) == "command"
    assert tab.payload_value(0) == "run.sh"
    assert tab.table.item(0, COLUMN_TOPIC).text() == "home/x"


def test_switching_type_carries_the_old_payload_across(tab):
    tab.add_data("t", "some-command", 0, False, payload_type="command")

    tab.table.cellWidget(0, 1).setCurrentText("literal")

    # the text the user had typed is not thrown away by the switch
    assert tab.payload_value(0) == "some-command"


def test_a_default_row_is_literal(tab):
    tab.add_message()

    assert tab.type_value(0) == "literal"
    assert payload_widget(tab, 0) is None


def test_building_the_table_does_not_report_changes(tab, monkeypatch):
    reported = []
    tab.settings_changed.connect(reported.append)

    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "a", "type": "built-in", "payload": "networking: hostname"},
        {"topic": "b", "type": "literal", "payload": "x"},
    ]
    tab.showEvent(None)

    # loading saved rows must not look like the user editing them
    assert reported == []

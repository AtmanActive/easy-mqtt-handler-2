"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_duplicate_button.py
*
*  Tests the Duplicate button on both tables: it copies the selected row and
*  inserts the copy right below it, and does nothing when no row is selected
*
*  Copyright (C) 2026 AtmanActive
"""
import pytest

from PyQt5.QtWidgets import QApplication

from easy_mqtt_handler.util.MQTTPayloads import MQTTPayloads
from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages
from easy_mqtt_handler.qt.tabs.PayloadTabWidget import PayloadTabWidget
from easy_mqtt_handler.qt.tabs.StartupTabWidget import StartupTabWidget, COLUMN_TOPIC


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# --- Send on Startup --------------------------------------------------------

@pytest.fixture
def startup_tab(app, tmp_path):
    MQTTStartupMessages(str(tmp_path / "startup.json"))
    tab = StartupTabWidget()
    return tab


def test_duplicating_with_nothing_selected_does_nothing(startup_tab):
    startup_tab.add_data("a", "1", 0, False, payload_type="literal")
    startup_tab.add_data("b", "2", 0, False, payload_type="literal")
    startup_tab.table.clearSelection()
    startup_tab.table.setCurrentCell(-1, -1)

    startup_tab.duplicate_message()

    assert startup_tab.table.rowCount() == 2


def test_duplicating_copies_the_selected_row(startup_tab):
    startup_tab.add_data("home/one", "ON", 1, True, "sensor", "id_one", "Name One",
                         payload_type="literal")
    startup_tab.add_data("home/two", "OFF", 0, False, payload_type="literal")
    startup_tab.table.selectRow(0)

    startup_tab.duplicate_message()

    assert startup_tab.table.rowCount() == 3
    # the copy carries the same values
    assert startup_tab.table.item(1, COLUMN_TOPIC).text() == "home/one"
    assert startup_tab.type_value(1) == "literal"


def test_the_copy_is_inserted_directly_below_the_original(startup_tab):
    startup_tab.add_data("first", "", 0, False, payload_type="literal")
    startup_tab.add_data("second", "", 0, False, payload_type="literal")
    startup_tab.add_data("third", "", 0, False, payload_type="literal")
    startup_tab.table.selectRow(1)  # "second"

    startup_tab.duplicate_message()

    topics = [startup_tab.table.item(r, COLUMN_TOPIC).text() for r in range(startup_tab.table.rowCount())]
    assert topics == ["first", "second", "second", "third"]


def test_the_new_row_is_selected_after_duplicating(startup_tab):
    startup_tab.add_data("a", "", 0, False, payload_type="literal")
    startup_tab.add_data("b", "", 0, False, payload_type="literal")
    startup_tab.table.selectRow(0)

    startup_tab.duplicate_message()

    assert startup_tab.table.currentRow() == 1


def test_duplicating_a_removal_row_keeps_it_a_removal(startup_tab):
    startup_tab.add_data("", "", 0, False, "sensor", "gone", "", payload_type="remove_ha_entity")
    startup_tab.table.selectRow(0)

    startup_tab.duplicate_message()

    assert startup_tab.table.rowCount() == 2
    assert startup_tab.type_value(1) == "remove_ha_entity"


# --- Payload Handlers -------------------------------------------------------

@pytest.fixture
def payload_tab(app, tmp_path):
    MQTTPayloads(str(tmp_path / "payloads.json"))
    tab = PayloadTabWidget()
    return tab


def test_payload_duplicating_with_nothing_selected_does_nothing(payload_tab):
    payload_tab.add_data("cmd", "arg", "/run", "args")
    payload_tab.table.clearSelection()
    payload_tab.table.setCurrentCell(-1, -1)

    payload_tab.duplicate_payload()

    assert payload_tab.table.rowCount() == 1


def test_payload_duplicating_copies_the_row_below(payload_tab):
    payload_tab.add_data("notify", "test", "/usr/bin/notify-send", "$1 $2")
    payload_tab.add_data("other", "x", "/bin/true", "")
    payload_tab.table.selectRow(0)

    payload_tab.duplicate_payload()

    assert payload_tab.table.rowCount() == 3
    assert payload_tab.table.item(1, 0).text() == "notify"
    assert payload_tab.table.item(1, 1).text() == "test"
    assert payload_tab.table.item(1, 4).text() == "$1 $2"
    # and the original third row moved down
    assert payload_tab.table.item(2, 0).text() == "other"


def test_payload_new_row_is_selected(payload_tab):
    payload_tab.add_data("a", "1", "/x", "")
    payload_tab.add_data("b", "2", "/y", "")
    payload_tab.table.selectRow(1)

    payload_tab.duplicate_payload()

    assert payload_tab.table.currentRow() == 2

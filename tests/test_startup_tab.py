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
from easy_mqtt_handler.qt.TableStyle import NoScrollComboBox
from easy_mqtt_handler.qt.tabs import StartupTabWidget as stw_module
from easy_mqtt_handler.qt.tabs.StartupTabWidget import (
    StartupTabWidget, COLUMN_TOPIC, COLUMN_PAYLOAD, COLUMN_TYPE, COLUMN_QOS,
    COLUMN_HA_ENTITY, COLUMN_HA_ID, REMOVAL_TEXT_COLOR)


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


# --- drop downs ignore the mouse wheel --------------------------------------

class _FakeWheelEvent:
    """Stands in for a QWheelEvent, recording whether it was ignored."""

    def __init__(self):
        self.ignored = False

    def ignore(self):
        self.ignored = True

    def accept(self):
        self.ignored = False


def test_a_no_scroll_combo_ignores_the_wheel_and_keeps_its_value(app):
    combo = NoScrollComboBox()
    combo.addItems(["a", "b", "c"])
    combo.setCurrentIndex(1)

    event = _FakeWheelEvent()
    combo.wheelEvent(event)

    # the event is passed up to the table (to scroll), and the value is unchanged
    assert event.ignored
    assert combo.currentIndex() == 1


def test_every_cell_drop_down_ignores_the_mouse_wheel(tab):
    # a built-in row gives every column that can hold a drop down one
    tab.add_data("t", "networking: hostname", 0, False, ha_entity="sensor",
                 payload_type="built-in")

    for column in (COLUMN_TYPE, COLUMN_PAYLOAD, COLUMN_QOS, COLUMN_HA_ENTITY):
        widget = tab.table.cellWidget(0, column)
        assert isinstance(widget, NoScrollComboBox), f"column {column} is not wheel-proof"


# --- the help button --------------------------------------------------------

def test_the_help_button_is_a_question_mark_at_the_far_right(tab):
    # the button is a bare "?"
    assert tab.help_button.text() == "?"

    # it is the last widget in the button bar, after the jump box, the buttons
    # and the reorder controls
    outer = tab.layout()
    button_bar = outer.itemAt(outer.count() - 1).layout()
    widgets = [button_bar.itemAt(i).widget() for i in range(button_bar.count())]
    buttons = [w for w in widgets if w is not None]
    assert buttons == [tab.jump_box, tab.save_button, tab.duplicate_button,
                       tab.cancel_button, tab.move_up_button, tab.move_down_button,
                       tab.move_top_button, tab.move_bottom_button, tab.position_box,
                       tab.help_button]


def test_the_explanation_text_is_held_for_the_help_pop_up(tab):
    # the instructional text moved off the tab and behind the help button
    assert "remove_ha_entity" in tab.help_text
    assert not hasattr(tab, "hint")


def test_the_action_buttons_show_the_verb_and_explain_in_the_tooltip(tab):
    assert tab.save_button.text() == "Add"
    assert tab.save_button.toolTip() == "Add Message row"
    assert tab.duplicate_button.text() == "Duplicate"
    assert tab.duplicate_button.toolTip() == "Duplicate Message row"
    assert tab.cancel_button.text() == "Remove"
    assert tab.cancel_button.toolTip() == "Remove Message row"


# --- jump to row ------------------------------------------------------------

def _selected_rows(tab):
    return [index.row() for index in tab.table.selectionModel().selectedRows()]


def test_the_jump_box_starts_empty_and_narrow_with_a_tooltip(tab):
    assert tab.jump_box.text() == ""
    assert tab.jump_box.toolTip() == "Jump to row number"
    # three digits, and the leftmost widget in the button bar
    assert tab.jump_box.maxLength() == 3
    outer = tab.layout()
    button_bar = outer.itemAt(outer.count() - 1).layout()
    assert button_bar.itemAt(0).widget() is tab.jump_box


def test_jumping_to_a_valid_row_selects_it_and_keeps_the_number(tab):
    for i in range(3):
        tab.add_data(f"t{i}", "", 0, False, payload_type="literal")

    tab.jump_box.setText("2")
    tab.jump_box.jump_to_row()

    # row 2 (counting from 1) is the row at index 1
    assert _selected_rows(tab) == [1]
    # a successful jump leaves the number in place
    assert tab.jump_box.text() == "2"


def test_jumping_past_the_last_row_is_ignored_and_clears_the_box(tab):
    tab.add_data("t0", "", 0, False, payload_type="literal")

    tab.jump_box.setText("9")
    tab.jump_box.jump_to_row()

    assert _selected_rows(tab) == []
    assert tab.jump_box.text() == ""


def test_jumping_to_row_zero_is_ignored(tab):
    tab.add_data("t0", "", 0, False, payload_type="literal")

    tab.jump_box.setText("0")
    tab.jump_box.jump_to_row()

    assert _selected_rows(tab) == []
    assert tab.jump_box.text() == ""


def test_stray_characters_are_ignored_and_clear_the_box(tab):
    tab.add_data("t0", "", 0, False, payload_type="literal")

    tab.jump_box.setText("ab")
    tab.jump_box.jump_to_row()

    assert tab.jump_box.text() == ""


def test_an_empty_box_does_nothing_on_return(tab):
    tab.add_data("t0", "", 0, False, payload_type="literal")

    tab.jump_box.setText("")
    tab.jump_box.jump_to_row()

    assert tab.jump_box.text() == ""


# --- reorder rows -----------------------------------------------------------

def _topics(tab):
    return [tab.table.item(row, COLUMN_TOPIC).text() for row in range(tab.table.rowCount())]


def _three_rows(tab):
    for i in range(3):
        tab.add_data(f"t{i}", "", 0, False, payload_type="literal")


def test_the_reorder_controls_carry_the_right_glyphs_and_tooltips(tab):
    assert tab.move_up_button.text() == "▲"
    assert tab.move_down_button.text() == "▼"
    assert tab.move_top_button.text() == "╤"
    assert tab.move_bottom_button.text() == "╧"
    assert tab.move_up_button.toolTip() == "Move the selected row up"
    assert tab.move_bottom_button.toolTip() == "Move the selected row to the bottom"
    assert tab.position_box.toolTip() == "Move the selected row to position number"
    assert tab.position_box.text() == "" and tab.position_box.maxLength() == 3


def test_moving_a_row_up_swaps_it_with_the_one_above(tab):
    _three_rows(tab)
    tab.table.selectRow(2)

    tab.move_row_up()

    assert _topics(tab) == ["t0", "t2", "t1"]
    assert _selected_rows(tab) == [1]


def test_moving_a_row_down_swaps_it_with_the_one_below(tab):
    _three_rows(tab)
    tab.table.selectRow(0)

    tab.move_row_down()

    assert _topics(tab) == ["t1", "t0", "t2"]
    assert _selected_rows(tab) == [1]


def test_moving_a_row_to_the_top(tab):
    _three_rows(tab)
    tab.table.selectRow(2)

    tab.move_row_to_top()

    assert _topics(tab) == ["t2", "t0", "t1"]
    assert _selected_rows(tab) == [0]


def test_moving_a_row_to_the_bottom(tab):
    _three_rows(tab)
    tab.table.selectRow(0)

    tab.move_row_to_bottom()

    assert _topics(tab) == ["t1", "t2", "t0"]
    assert _selected_rows(tab) == [2]


def test_moving_up_from_the_top_does_nothing(tab):
    _three_rows(tab)
    tab.table.selectRow(0)

    tab.move_row_up()

    assert _topics(tab) == ["t0", "t1", "t2"]
    assert _selected_rows(tab) == [0]


def test_moving_with_nothing_selected_does_nothing(tab):
    _three_rows(tab)  # add_data leaves no row selected

    tab.move_row_to_bottom()

    assert _topics(tab) == ["t0", "t1", "t2"]


def test_moving_a_row_to_a_position_shifts_the_rows_below_down(tab):
    _three_rows(tab)
    tab.table.selectRow(0)

    tab.position_box.setText("3")
    tab.position_box.returnPressed.emit()

    # t0 lands at position 3; t1 and t2 shift up to fill the gap
    assert _topics(tab) == ["t1", "t2", "t0"]
    assert _selected_rows(tab) == [2]
    # a satisfiable move keeps the number in the box
    assert tab.position_box.text() == "3"


def test_moving_a_row_to_its_own_position_keeps_the_number_and_does_nothing(tab):
    _three_rows(tab)
    tab.table.selectRow(1)

    tab.position_box.setText("2")
    tab.position_box.returnPressed.emit()

    assert _topics(tab) == ["t0", "t1", "t2"]
    assert tab.position_box.text() == "2"


def test_moving_to_a_position_past_the_last_row_clears_the_box(tab):
    _three_rows(tab)
    tab.table.selectRow(0)

    tab.position_box.setText("9")
    tab.position_box.returnPressed.emit()

    assert _topics(tab) == ["t0", "t1", "t2"]
    assert tab.position_box.text() == ""


def test_moving_to_a_position_with_nothing_selected_clears_the_box(tab):
    _three_rows(tab)  # nothing selected

    tab.position_box.setText("2")
    tab.position_box.returnPressed.emit()

    assert _topics(tab) == ["t0", "t1", "t2"]
    assert tab.position_box.text() == ""


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

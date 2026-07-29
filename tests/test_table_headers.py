"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_table_headers.py
*
*  Every table's header labels are left-aligned, so they line up with the
*  left-aligned data in the cells below them
*
*  Copyright (C) 2026 AtmanActive
"""
import pytest

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from easy_mqtt_handler.util.MQTTPayloads import MQTTPayloads
from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages
from easy_mqtt_handler.qt.tabs.PayloadTabWidget import PayloadTabWidget
from easy_mqtt_handler.qt.tabs.StartupTabWidget import StartupTabWidget


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def assert_left_aligned(table):
    alignment = table.horizontalHeader().defaultAlignment()
    assert alignment & Qt.AlignLeft, f"expected left-aligned headers, got {int(alignment)}"


def test_payload_handlers_headers_are_left_aligned(app, tmp_path):
    MQTTPayloads(str(tmp_path / "payloads.json"))
    tab = PayloadTabWidget()  # kept alive so its table is not garbage-collected

    assert_left_aligned(tab.table)


def test_send_on_startup_headers_are_left_aligned(app, tmp_path):
    MQTTStartupMessages(str(tmp_path / "startup.json"))
    tab = StartupTabWidget()

    assert_left_aligned(tab.table)


def test_tables_carry_no_style_sheet(app, tmp_path):
    # a style sheet on a QTableWidget blanks the cell backgrounds on some Linux
    # styles, so padding must come from geometry instead
    MQTTPayloads(str(tmp_path / "payloads.json"))
    MQTTStartupMessages(str(tmp_path / "startup.json"))

    # references are held: PyQt5 frees the C++ widget the moment its Python
    # wrapper is collected, so a bare PayloadTabWidget().table would dangle
    payload_tab = PayloadTabWidget()
    startup_tab = StartupTabWidget()
    assert payload_tab.table.styleSheet() == ""
    assert startup_tab.table.styleSheet() == ""


def test_tables_have_extra_row_height(app, tmp_path):
    # the readability padding is applied through geometry, not a style sheet
    from PyQt5.QtWidgets import QTableWidget
    from easy_mqtt_handler.qt.TableStyle import CELL_PADDING

    MQTTStartupMessages(str(tmp_path / "startup.json"))
    tab = StartupTabWidget()

    # held so it is not garbage-collected before defaultSectionSize() is read,
    # which otherwise segfaults on macOS
    reference_table = QTableWidget()
    default = reference_table.verticalHeader().defaultSectionSize()
    assert tab.table.verticalHeader().defaultSectionSize() == default + 2 * CELL_PADDING

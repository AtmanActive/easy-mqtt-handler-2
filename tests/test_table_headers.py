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

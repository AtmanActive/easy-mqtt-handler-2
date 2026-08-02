"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  qt/tabs/PayloadTabWidget.py
*
*  Defines the Payload Editor Tab
*
*  Copyright (C) 2023 A. Zeil
"""
import gettext
import os

from PyQt5 import QtGui
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QTableWidget, QAbstractItemView, QPushButton, QVBoxLayout, QHBoxLayout, \
    QHeaderView, QSizePolicy, QTableWidgetItem, QFileDialog, QMessageBox

from easy_mqtt_handler.qt.RowReorder import RowReorderMixin
from easy_mqtt_handler.qt.TableStyle import add_table_padding, RowJumpBox
from easy_mqtt_handler.util.MQTTPayloads import MQTTPayloads
from easy_mqtt_handler.util.Tools import Utils

# Set the local directory
localedir = Utils.resource_path("./locale")

# Set up your magic function
translate = gettext.translation("PayloadTabWidget", localedir, fallback=True)
_ = translate.gettext


class PayloadTabWidget(RowReorderMixin, QWidget):

    settings_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        # explain the matching and the $1/$2 substitution, which is otherwise
        # only documented in the README and easy to miss. It lives behind the
        # "?" button rather than above the table, to keep the tab uncluttered
        self.help_text = _("When a message arrives whose \"command\" and \"args\" match a row, the program runs "
                           "that row's Command to Run.\n\n"
                           "Command line arguments may contain $1, $2, ... which are replaced by the payload's "
                           "\"param1\", \"param2\", ... A $X with no matching param is removed.\n\n"
                           "Example payload: {\"command\": \"notify\", \"args\": \"test\", "
                           "\"param1\": \"hello\", \"param2\": \"world\"}")

        # create the table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([_('Payload Command'), _('Payload Argument'),
                                              _('Command to Run'), "", _('Command line arguments')])

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        # a narrow box for jumping the selection to a row by its number
        self.jump_box = RowJumpBox(self.table, _("Jump to row number"))

        # create the buttons: a short action word on the face, the fuller
        # description in the tool tip
        self.save_button = QPushButton(_('Add'))
        self.save_button.setToolTip(_('Add Payload row'))
        self.save_button.clicked.connect(self.add_payload)
        self.duplicate_button = QPushButton(_('Duplicate'))
        self.duplicate_button.setToolTip(_('Duplicate Payload row'))
        self.duplicate_button.clicked.connect(self.duplicate_payload)
        self.cancel_button = QPushButton(_('Remove'))
        self.cancel_button.setToolTip(_('Remove Payload row'))
        self.cancel_button.clicked.connect(self.remove_payload)
        # the move-the-selected-row buttons and the "move to position" box
        reorder_controls = self.build_reorder_controls(
            _("Move the selected row up"),
            _("Move the selected row down"),
            _("Move the selected row to the top"),
            _("Move the selected row to the bottom"),
            _("Move the selected row to position number"))
        # a compact "?" at the far right, opening the explanation that used to
        # sit above the table
        self.help_button = QPushButton("?")
        self.help_button.setFixedWidth(40)
        self.help_button.clicked.connect(self.show_help)

        # create the layout
        layout = QVBoxLayout()
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.jump_box)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.duplicate_button)
        button_layout.addWidget(self.cancel_button)
        for control in reorder_controls:
            button_layout.addWidget(control)
        button_layout.addStretch()
        button_layout.addWidget(self.help_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.horizontalHeader().setStretchLastSection(True)
        # left-align the header labels to line up with the left-aligned cell data
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        add_table_padding(self.table)

    def setting_changed_event(self, text):
        self.settings_changed.emit(True)
        self.set_new_payload_data()

    def show_help(self):
        # a modal information box, in the spirit of the About dialog, holding the
        # explanation of what this tab does
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(_("Payload Handlers — Help"))
        box.setText(self.help_text)
        box.exec_()

    def add_data(self, payload_command, payload_argument, command_to_run, command_line_arguments):
        row_count = self.table.rowCount()
        self.table.setRowCount(row_count + 1)

        self.table.setItem(row_count, 0, QTableWidgetItem(payload_command))
        self.table.setItem(row_count, 1, QTableWidgetItem(payload_argument))
        self.table.setItem(row_count, 2, QTableWidgetItem(command_to_run))

        button = QPushButton("...")
        button.setFixedWidth(40)
        button.setProperty("row", row_count)
        self.table.setCellWidget(row_count, 3, button)
        button.clicked.connect(lambda: self.browse_executable(button))

        self.table.setItem(row_count, 4, QTableWidgetItem(command_line_arguments))

    def browse_executable(self, cur_button):

        # set some options for the file open dialog if we are on windows
        if os.name == "nt":
            start_dir = "C:\\"
            file_filter = "*.*"
        # or on linux and macOS
        else:
            start_dir = "/"
            file_filter = "*"

        filedialog = QFileDialog()
        filedialog.setWindowTitle(_('Select an executable file'))
        filedialog.setDirectory(start_dir)
        filedialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        filedialog.setNameFilter(file_filter)
        filedialog.setViewMode(QFileDialog.ViewMode.List)

        if filedialog.exec_() and len(filedialog.selectedFiles()) == 1:
            selected_file = filedialog.selectedFiles()[0]
            self.table.item(cur_button.property("row"), 2).setText(selected_file)
            self.table.viewport().update()

    def add_payload(self):
        row_count = self.table.rowCount()
        self.table.setRowCount(row_count + 1)

        self.table.setItem(row_count, 0, QTableWidgetItem(""))
        self.table.setItem(row_count, 1, QTableWidgetItem(""))
        self.table.setItem(row_count, 2, QTableWidgetItem(""))

        button = QPushButton("...")
        button.setFixedWidth(40)
        button.setProperty("row", row_count)
        self.table.setCellWidget(row_count, 3, button)
        button.clicked.connect(lambda: self.browse_executable(button))

        self.setting_changed_event(True)

    def set_new_payload_data(self):
        # ensure payload data is empty
        new_payload_data = []
        # payload_data.clear()

        # for each line of the table append one item to the payload config
        for row in range(self.table.rowCount()):
            payload_command = "" if self.table.item(row, 0) is None else self.table.item(row, 0).text()
            payload_argument = "" if self.table.item(row, 1) is None else self.table.item(row, 1).text()
            command_to_run = "" if self.table.item(row, 2) is None else self.table.item(row, 2).text()
            command_line_arguments = "" if self.table.item(row, 4) is None else self.table.item(row, 4).text()
            new_payload_data.append({
                'payload_command': payload_command,
                'payload_argument': payload_argument,
                'command_to_run': command_to_run,
                'command_line_arguments': command_line_arguments
            })

        MQTTPayloads.get_instance().payload_data = new_payload_data

    def remove_payload(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return
        self.table.removeRow(selected_row)
        self.setting_changed_event(True)

    def duplicate_payload(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            # nothing selected: do nothing at all
            return

        # copy the selected row and put the copy right after it, then rebuild so
        # the browse buttons keep the right row bindings
        self.set_new_payload_data()
        store = MQTTPayloads.get_instance()
        data = list(store.payload_data) if isinstance(store.payload_data, list) else []
        if selected_row >= len(data):
            return
        data.insert(selected_row + 1, dict(data[selected_row]))
        store.payload_data = data

        self.reload_from_settings()
        self.table.selectRow(selected_row + 1)
        self.setting_changed_event(True)

    # --- hooks for RowReorderMixin ------------------------------------------

    def _capture_rows(self):
        self.set_new_payload_data()

    def _get_rows(self):
        data = MQTTPayloads.get_instance().payload_data
        return list(data) if isinstance(data, list) else []

    def _set_rows(self, rows):
        MQTTPayloads.get_instance().payload_data = rows

    def _changed(self):
        self.setting_changed_event(True)

    def reload_from_settings(self):
        """Rebuild the table from the saved payload data."""
        # unbind dataChanged event until we've loaded the new payload data
        try:
            self.table.model().dataChanged.disconnect()
        except TypeError:
            # nothing connected yet, which is the case on the very first show
            pass

        payload_settings = MQTTPayloads.get_instance().payload_data
        if not isinstance(payload_settings, list):
            payload_settings = []

        # clear the table to get a fresh copy of the payload config
        self.table.clearContents()
        self.table.setRowCount(0)

        # fill table with current payload config
        for item in payload_settings:
            if not isinstance(item, dict):
                continue
            self.add_data(str(item.get('payload_command', "")),
                          str(item.get('payload_argument', "")),
                          str(item.get('command_to_run', "")),
                          str(item.get('command_line_arguments', "")))

        # now that we've loaded data: enable listening to dataChanged event and send a signal on changes
        self.table.model().dataChanged.connect(self.setting_changed_event)

    def showEvent(self, a0: QtGui.QShowEvent) -> None:
        self.reload_from_settings()

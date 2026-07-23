"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  qt/tabs/StartupTabWidget.py
*
*  Defines the "Send on Startup" Tab, which holds the MQTT messages that are
*  published once a connection to the broker has been established
*
*  Copyright (C) 2026 AtmanActive
"""
import gettext

from PyQt5 import QtGui
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QTableWidget, QAbstractItemView, QPushButton, QVBoxLayout, QHBoxLayout, \
    QHeaderView, QSizePolicy, QTableWidgetItem, QComboBox, QLabel

from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages, VALID_QOS_LEVELS, \
    HA_COMMON_COMPONENTS, HA_DEFAULT_COMPONENT
from easy_mqtt_handler.util.Tools import Utils

# Set the local directory
localedir = Utils.resource_path("./locale")

# Set up your magic function
translate = gettext.translation("StartupTabWidget", localedir, fallback=True)
_ = translate.gettext

COLUMN_TOPIC = 0
COLUMN_PAYLOAD = 1
COLUMN_QOS = 2
COLUMN_RETAIN = 3
COLUMN_HA_ENTITY = 4
COLUMN_HA_ID = 5
COLUMN_HA_NAME = 6


class StartupTabWidget(QWidget):

    settings_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        # a short explanation, because this tab does something quite different
        # from the Payload Handlers tab it otherwise resembles
        self.hint = QLabel(_("These messages are published every time a connection to the broker has been "
                             "established, before listening starts. Topics are absolute, they are not "
                             "prefixed with the topic from the Connection tab. Leave this empty to disable.\n"
                             "Fill in HA ID to have Home Assistant create an entity for the message "
                             "automatically. Leave HA ID empty to just send the message."))
        self.hint.setWordWrap(True)

        # create the table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([_('Topic'), _('Payload'), _('QoS'), _('Retain'),
                                              _('HA Entity'), _('HA ID'), _('HA Name')])

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        # create the buttons
        self.save_button = QPushButton(_('Add Message'))
        self.save_button.clicked.connect(self.add_message)
        self.cancel_button = QPushButton(_('Remove Message'))
        self.cancel_button.clicked.connect(self.remove_message)

        # create the layout
        layout = QVBoxLayout()
        layout.addWidget(self.hint)
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.horizontalHeader().setStretchLastSection(True)

    def setting_changed_event(self, text):
        self.settings_changed.emit(True)
        self.set_new_startup_data()

    def make_qos_selector(self, row, qos):
        selector = QComboBox()
        selector.addItems([str(level) for level in VALID_QOS_LEVELS])
        selector.setCurrentText(str(qos if qos in VALID_QOS_LEVELS else 0))
        self.table.setCellWidget(row, COLUMN_QOS, selector)
        # a combo box is a cell widget, so it does not raise the table's
        # dataChanged signal; report changes ourselves
        selector.currentIndexChanged.connect(self.setting_changed_event)
        return selector

    def make_component_selector(self, row, component):
        # editable, because Home Assistant knows far more components than the
        # few we can sensibly offer in a drop down
        selector = QComboBox()
        selector.setEditable(True)
        selector.addItems(list(HA_COMMON_COMPONENTS))
        selector.setCurrentText(component if component else HA_DEFAULT_COMPONENT)
        self.table.setCellWidget(row, COLUMN_HA_ENTITY, selector)
        selector.currentTextChanged.connect(self.setting_changed_event)
        return selector

    def add_data(self, topic, payload, qos, retain, ha_entity="", ha_id="", ha_name=""):
        row_count = self.table.rowCount()
        self.table.setRowCount(row_count + 1)

        self.table.setItem(row_count, COLUMN_TOPIC, QTableWidgetItem(topic))
        self.table.setItem(row_count, COLUMN_PAYLOAD, QTableWidgetItem(payload))
        self.make_qos_selector(row_count, qos)

        # a checkable cell item keeps Retain editable without a second widget
        retain_item = QTableWidgetItem()
        retain_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        retain_item.setCheckState(Qt.Checked if retain else Qt.Unchecked)
        self.table.setItem(row_count, COLUMN_RETAIN, retain_item)

        self.make_component_selector(row_count, ha_entity)
        self.table.setItem(row_count, COLUMN_HA_ID, QTableWidgetItem(ha_id))
        self.table.setItem(row_count, COLUMN_HA_NAME, QTableWidgetItem(ha_name))

    def add_message(self):
        self.add_data("", "", 0, False)
        self.setting_changed_event(True)

    def remove_message(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return
        self.table.removeRow(selected_row)
        self.setting_changed_event(True)

    def set_new_startup_data(self):
        new_startup_data = []

        # for each line of the table append one item to the startup config
        for row in range(self.table.rowCount()):
            topic = "" if self.table.item(row, COLUMN_TOPIC) is None else self.table.item(row, COLUMN_TOPIC).text()
            payload = "" if self.table.item(row, COLUMN_PAYLOAD) is None else self.table.item(row, COLUMN_PAYLOAD).text()

            qos_selector = self.table.cellWidget(row, COLUMN_QOS)
            qos = 0 if qos_selector is None else int(qos_selector.currentText())

            retain_item = self.table.item(row, COLUMN_RETAIN)
            retain = retain_item is not None and retain_item.checkState() == Qt.Checked

            component_selector = self.table.cellWidget(row, COLUMN_HA_ENTITY)
            ha_entity = "" if component_selector is None else component_selector.currentText()
            ha_id = "" if self.table.item(row, COLUMN_HA_ID) is None else self.table.item(row, COLUMN_HA_ID).text()
            ha_name = "" if self.table.item(row, COLUMN_HA_NAME) is None else self.table.item(row, COLUMN_HA_NAME).text()

            new_startup_data.append({
                'topic': topic,
                'payload': payload,
                'qos': qos,
                'retain': retain,
                'ha_entity': ha_entity,
                'ha_id': ha_id,
                'ha_name': ha_name
            })

        MQTTStartupMessages.get_instance().startup_data = new_startup_data

    def showEvent(self, a0: QtGui.QShowEvent) -> None:
        # unbind dataChanged event until we've loaded the new startup data
        try:
            self.table.model().dataChanged.disconnect()
        except TypeError:
            # nothing connected yet, which is the case on the very first show
            pass

        startup_messages = MQTTStartupMessages.get_instance().startup_data

        # clear the table to get a fresh copy of the startup config
        self.table.clearContents()
        self.table.setRowCount(0)

        # fill table with current startup config
        for item in startup_messages:
            self.add_data(str(item.get('topic', "")),
                          str(item.get('payload', "")),
                          item.get('qos', 0),
                          bool(item.get('retain', False)),
                          str(item.get('ha_entity', "")),
                          str(item.get('ha_id', "")),
                          str(item.get('ha_name', "")))

        # now that we've loaded data: enable listening to dataChanged event and send a signal on changes
        self.table.model().dataChanged.connect(self.setting_changed_event)

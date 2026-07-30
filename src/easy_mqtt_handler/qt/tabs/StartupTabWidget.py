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
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QWidget, QTableWidget, QAbstractItemView, QPushButton, QVBoxLayout, QHBoxLayout, \
    QHeaderView, QSizePolicy, QTableWidgetItem, QComboBox, QLabel, QApplication

from easy_mqtt_handler.qt.TableStyle import add_table_padding
from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages, VALID_QOS_LEVELS, \
    HA_COMMON_COMPONENTS, HA_DEFAULT_COMPONENT
from easy_mqtt_handler.util.StartupPayload import PAYLOAD_TYPES, DEFAULT_TYPE, TYPE_BUILTIN, \
    TYPE_REMOVE_HA_ENTITY, builtin_keys
from easy_mqtt_handler.util.Tools import Utils

# Set the local directory
localedir = Utils.resource_path("./locale")

# Set up your magic function
translate = gettext.translation("StartupTabWidget", localedir, fallback=True)
_ = translate.gettext

COLUMN_TOPIC = 0
COLUMN_TYPE = 1
COLUMN_PAYLOAD = 2
COLUMN_QOS = 3
COLUMN_RETAIN = 4
COLUMN_HA_ENTITY = 5
COLUMN_HA_ID = 6
COLUMN_HA_NAME = 7

# a red-tinted white, so a removal row stands out as something that is meant to
# make a change happen
REMOVAL_TEXT_COLOR = QColor(255, 120, 120)


class StartupTabWidget(QWidget):

    settings_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        # set while the table is being (re)built from saved data, so that
        # populating cells does not look like the user editing them
        self._suspend_changes = False

        # a short explanation, because this tab does something quite different
        # from the Payload Handlers tab it otherwise resembles
        self.hint = QLabel(_("These messages are published every time a connection to the broker has been "
                             "established, before listening starts. Topics are absolute, they are not "
                             "prefixed with the topic from the Connection tab. Leave this empty to disable.\n"
                             "Type decides how Payload is read: \"literal\" sends it as-is, \"command\" runs it "
                             "as a program and sends its output, \"built-in\" sends a value this program works "
                             "out itself, \"environment\" sends the value of an environment variable.\n"
                             "Fill in HA ID to have Home Assistant create an entity for the message automatically. "
                             "The \"remove_ha_entity\" type instead removes the entity named by HA Entity and HA ID "
                             "(shown in red); the row deletes itself once the broker confirms the removal."))
        self.hint.setWordWrap(True)

        # create the table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([_('Topic'), _('Type'), _('Payload'), _('QoS'), _('Retain'),
                                              _('HA Entity'), _('HA ID'), _('HA Name')])

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        # create the buttons
        self.save_button = QPushButton(_('Add Message'))
        self.save_button.clicked.connect(self.add_message)
        self.duplicate_button = QPushButton(_('Duplicate Message'))
        self.duplicate_button.clicked.connect(self.duplicate_message)
        self.cancel_button = QPushButton(_('Remove Message'))
        self.cancel_button.clicked.connect(self.remove_message)

        # create the layout
        layout = QVBoxLayout()
        layout.addWidget(self.hint)
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.duplicate_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.horizontalHeader().setStretchLastSection(True)
        # left-align the header labels to line up with the left-aligned cell data
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        add_table_padding(self.table)

    def setting_changed_event(self, _ignored=None):
        # ignore the churn of rebuilding the table from saved data
        if self._suspend_changes:
            return
        self.settings_changed.emit(True)
        self.set_new_startup_data()

    # --- cell builders ------------------------------------------------------

    def make_type_selector(self, row, payload_type):
        selector = QComboBox()
        selector.addItems(list(PAYLOAD_TYPES))
        selector.setCurrentText(payload_type if payload_type in PAYLOAD_TYPES else DEFAULT_TYPE)
        self.table.setCellWidget(row, COLUMN_TYPE, selector)
        # rebuild the payload cell when the type changes, then report the change
        selector.currentTextChanged.connect(lambda _t, r=row: self.on_type_changed(r))
        return selector

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

    def set_payload_cell(self, row, payload_type, payload):
        """Give the Payload column the right editor for the row's type.

        A built-in row picks from a fixed list of values, so it gets a drop
        down; a literal or command row is free text, so it gets a plain cell.
        """
        # whichever editor was there before must go, or the two would overlap
        self.table.removeCellWidget(row, COLUMN_PAYLOAD)
        self.table.setItem(row, COLUMN_PAYLOAD, None)

        if payload_type == TYPE_BUILTIN:
            selector = QComboBox()
            keys = builtin_keys()
            # a saved value that is not currently offered, e.g. a disk that was
            # connected on another machine or an earlier run, is kept rather
            # than being silently rewritten to something else
            if payload and payload not in keys:
                keys = sorted(keys + [payload])
            selector.addItems(keys)
            selector.setCurrentText(payload if payload in keys else (keys[0] if keys else ""))
            self.table.setCellWidget(row, COLUMN_PAYLOAD, selector)
            selector.currentTextChanged.connect(self.setting_changed_event)
        else:
            # literal, command, environment and remove_ha_entity are all free
            # text (the last one ignores it, but keeps a cell for consistency)
            self.table.setItem(row, COLUMN_PAYLOAD, QTableWidgetItem(payload))

    def style_row(self, row, payload_type):
        """Colour a removal row so it stands out from ordinary rows."""
        is_removal = payload_type == TYPE_REMOVE_HA_ENTITY

        for column in (COLUMN_TOPIC, COLUMN_PAYLOAD, COLUMN_HA_ID, COLUMN_HA_NAME):
            item = self.table.item(row, column)
            if item is None:
                continue
            if is_removal:
                item.setForeground(REMOVAL_TEXT_COLOR)
            else:
                # clear any colour a previous type left behind, back to default
                item.setData(Qt.ForegroundRole, None)

        # the drop downs are cell widgets, so their text colour is set through
        # the palette. deliberately not a style sheet, which would blank the
        # widget's own background on some Linux styles.
        for column in (COLUMN_TYPE, COLUMN_QOS, COLUMN_HA_ENTITY, COLUMN_PAYLOAD):
            widget = self.table.cellWidget(row, column)
            if isinstance(widget, QComboBox):
                self._colour_combo(widget, REMOVAL_TEXT_COLOR if is_removal else None)

    @staticmethod
    def _colour_combo(combo, colour):
        already_red = combo.palette().color(QPalette.Text) == REMOVAL_TEXT_COLOR
        if colour is None:
            # only undo a previous reddening; an untouched combo is left with no
            # explicit palette so it keeps following the application palette,
            # e.g. when the theme is switched at runtime
            if already_red:
                combo.setPalette(QApplication.palette(combo))
            return
        palette = combo.palette()
        for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
            palette.setColor(role, colour)
        combo.setPalette(palette)

    def on_type_changed(self, row):
        # rebuild the payload cell for the new type, carrying the old value over
        self._suspend_changes = True
        try:
            payload_type = self.type_value(row)
            self.set_payload_cell(row, payload_type, self.payload_value(row))
            self.style_row(row, payload_type)
        finally:
            self._suspend_changes = False
        self.setting_changed_event()

    # --- cell readers -------------------------------------------------------

    def type_value(self, row):
        selector = self.table.cellWidget(row, COLUMN_TYPE)
        return selector.currentText() if selector is not None else DEFAULT_TYPE

    def payload_value(self, row):
        # the payload cell is either a drop down (built-in) or a text item
        widget = self.table.cellWidget(row, COLUMN_PAYLOAD)
        if isinstance(widget, QComboBox):
            return widget.currentText()
        item = self.table.item(row, COLUMN_PAYLOAD)
        return item.text() if item is not None else ""

    # --- rows ---------------------------------------------------------------

    def add_data(self, topic, payload, qos, retain, ha_entity="", ha_id="", ha_name="",
                 payload_type=DEFAULT_TYPE):
        row = self.table.rowCount()
        self.table.setRowCount(row + 1)

        self.table.setItem(row, COLUMN_TOPIC, QTableWidgetItem(topic))
        self.make_type_selector(row, payload_type)
        self.set_payload_cell(row, payload_type, payload)
        self.make_qos_selector(row, qos)

        # a checkable cell item keeps Retain editable without a second widget
        retain_item = QTableWidgetItem()
        retain_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        retain_item.setCheckState(Qt.Checked if retain else Qt.Unchecked)
        self.table.setItem(row, COLUMN_RETAIN, retain_item)

        self.make_component_selector(row, ha_entity)
        self.table.setItem(row, COLUMN_HA_ID, QTableWidgetItem(ha_id))
        self.table.setItem(row, COLUMN_HA_NAME, QTableWidgetItem(ha_name))

        self.style_row(row, payload_type)

    def add_message(self):
        self.add_data("", "", 0, False)
        self.setting_changed_event()

    def remove_message(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return
        self.table.removeRow(selected_row)
        self.setting_changed_event()

    def duplicate_message(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            # nothing selected: do nothing at all
            return

        # copy the selected row's data and put the copy right after it, then
        # rebuild so the drop downs and their row bindings are correct. going
        # through the data avoids the fiddliness of inserting a live row with
        # its cell widgets in the middle of the table.
        self.set_new_startup_data()
        store = MQTTStartupMessages.get_instance()
        data = list(store.startup_data)
        data.insert(selected_row + 1, dict(data[selected_row]))
        store.startup_data = data

        self.reload_from_settings()
        self.table.selectRow(selected_row + 1)
        self.setting_changed_event()

    def set_new_startup_data(self):
        new_startup_data = []

        # for each line of the table append one item to the startup config
        for row in range(self.table.rowCount()):
            topic = "" if self.table.item(row, COLUMN_TOPIC) is None else self.table.item(row, COLUMN_TOPIC).text()

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
                'type': self.type_value(row),
                'payload': self.payload_value(row),
                'qos': qos,
                'retain': retain,
                'ha_entity': ha_entity,
                'ha_id': ha_id,
                'ha_name': ha_name
            })

        MQTTStartupMessages.get_instance().startup_data = new_startup_data

    def reload_from_settings(self):
        """Rebuild the table from the saved startup data.

        Used both when the tab is shown and after the app deletes a confirmed
        removal row, so the table stays in step with the configuration.
        """
        # unbind dataChanged event until we've loaded the new startup data
        try:
            self.table.model().dataChanged.disconnect()
        except TypeError:
            # nothing connected yet, which is the case on the very first show
            pass

        startup_messages = MQTTStartupMessages.get_instance().startup_data

        # clear the table to get a fresh copy of the startup config
        self._suspend_changes = True
        try:
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
                              str(item.get('ha_name', "")),
                              str(item.get('type', DEFAULT_TYPE)))
        finally:
            self._suspend_changes = False

        # now that we've loaded data: enable listening to dataChanged event and send a signal on changes
        self.table.model().dataChanged.connect(self.setting_changed_event)

    def showEvent(self, a0: QtGui.QShowEvent) -> None:
        self.reload_from_settings()

"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  qt/tabs/ConnectionTabWidget.py
*
*  Defines the connection settings tab
*
*  Copyright (C) 2023 A. Zeil
"""
import gettext
import os

from PyQt5 import QtGui
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QCheckBox, QHBoxLayout, QFileDialog, QPushButton, \
    QComboBox
from easy_mqtt_handler.util.Fonts import FONT_SIZE_CHOICES, DEFAULT_FONT_SIZE
from easy_mqtt_handler.util.MQTTSettings import MQTTSettings
from easy_mqtt_handler.util.Theme import THEME_CHOICES, DEFAULT_THEME_CHOICE
from easy_mqtt_handler.util.Tools import Utils

# Set the local directory
localedir = Utils.resource_path("./locale")

# Set up your magic function
translate = gettext.translation("ConnectionTabWidget", localedir, fallback=True)
_ = translate.gettext


class ConnectionTabWidget(QWidget):
    settings_changed = pyqtSignal(bool)
    # emitted when the theme choice changes, so it can be applied straight away
    theme_changed = pyqtSignal()
    # emitted when the font size choice changes, applied the same way
    font_size_changed = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Create the textboxes and labels
        self.hostname_label = QLabel(_("Hostname:"))
        self.hostname_textbox = QLineEdit()
        self.port_label = QLabel(_("Port:"))
        self.port_textbox = QLineEdit()

        self.insecure_ssl_checkbox = QCheckBox()
        self.insecure_ssl_label = QLabel(_("Allow insecure SSL/TLS"))
        self.insecure_ssl_label.setStyleSheet("border: 1px solid red;")

        self.insecure_ssl_layout = QHBoxLayout()
        self.insecure_ssl_layout.setSpacing(10)
        self.insecure_ssl_layout.addWidget(self.insecure_ssl_checkbox)
        self.insecure_ssl_layout.addWidget(self.insecure_ssl_label)
        self.insecure_ssl_layout.addStretch()

        self.username_label = QLabel(_("Username:"))
        self.username_textbox = QLineEdit()
        self.password_label = QLabel(_("Password:"))
        self.password_textbox = QLineEdit()
        # Set the password textbox to hide input
        self.password_textbox.setEchoMode(QLineEdit.Password)
        self.topic_label = QLabel(_("MQTT Topic:"))
        self.topic_textbox = QLineEdit()

        self.enable_ssl_checkbox = QCheckBox()
        self.enable_ssl_label = QLabel(_("Use SSL/TLS"))
        self.enable_ssl_layout = QHBoxLayout()
        self.enable_ssl_layout.setSpacing(10)
        self.enable_ssl_layout.addWidget(self.enable_ssl_checkbox)
        self.enable_ssl_layout.addWidget(self.enable_ssl_label)
        self.enable_ssl_layout.addStretch()

        self.server_certificate_label = QLabel(_("Server Certificate / Certificate Chain:"))
        self.server_certificate_file = QLineEdit()
        self.server_certificate_browse_btn = QPushButton('...')
        self.server_certificate_browse_btn.clicked.connect(lambda: self.cryptofile_browse("server-cert"))
        self.server_certificate_browse_btn.setFixedWidth(40)

        self.server_certificate_layout = QHBoxLayout()
        self.server_certificate_layout.setSpacing(10)
        self.server_certificate_layout.addWidget(self.server_certificate_file)
        self.server_certificate_layout.addWidget(self.server_certificate_browse_btn)

        self.enable_client_ssl_auth_checkbox = QCheckBox()
        self.enable_client_ssl_auth_label = QLabel(_("Enable client certificate authentication"))
        self.enable_client_ssl_auth_layout = QHBoxLayout()
        self.enable_client_ssl_auth_layout.setSpacing(10)
        self.enable_client_ssl_auth_layout.addWidget(self.enable_client_ssl_auth_checkbox)
        self.enable_client_ssl_auth_layout.addWidget(self.enable_client_ssl_auth_label)
        self.enable_client_ssl_auth_layout.addStretch()

        self.client_certificate_label = QLabel(_("Client certificate file:"))
        self.client_certificate_file = QLineEdit()
        self.client_certificate_browse_btn = QPushButton('...')
        self.client_certificate_browse_btn.clicked.connect(lambda: self.cryptofile_browse("client-cert"))
        self.client_certificate_browse_btn.setFixedWidth(40)

        self.client_certificate_layout = QHBoxLayout()
        self.client_certificate_layout.setSpacing(10)
        self.client_certificate_layout.addWidget(self.client_certificate_file)
        self.client_certificate_layout.addWidget(self.client_certificate_browse_btn)

        self.client_key_label = QLabel(_("Client key file:"))
        self.client_key_file = QLineEdit()
        self.client_key_browse_btn = QPushButton('...')
        self.client_key_browse_btn.clicked.connect(lambda: self.cryptofile_browse("client-key"))
        self.client_key_browse_btn.setFixedWidth(40)

        self.client_key_layout = QHBoxLayout()
        self.client_key_layout.setSpacing(10)
        self.client_key_layout.addWidget(self.client_key_file)
        self.client_key_layout.addWidget(self.client_key_browse_btn)

        self.client_ssl_auth_widget = QWidget()
        self.layout_client_ssl_auth_settings = QVBoxLayout(self.client_ssl_auth_widget)
        self.layout_client_ssl_auth_settings.addWidget(self.client_certificate_label)
        self.layout_client_ssl_auth_settings.addLayout(self.client_certificate_layout)
        self.layout_client_ssl_auth_settings.addWidget(self.client_key_label)
        self.layout_client_ssl_auth_settings.addLayout(self.client_key_layout)

        self.ssl_settings_widget = QWidget()
        self.layout_ssl_settings = QVBoxLayout(self.ssl_settings_widget)
        self.layout_ssl_settings.addWidget(self.server_certificate_label)
        self.layout_ssl_settings.addLayout(self.server_certificate_layout)
        self.layout_ssl_settings.addLayout(self.insecure_ssl_layout)
        self.layout_ssl_settings.addLayout(self.enable_client_ssl_auth_layout)
        self.layout_ssl_settings.addWidget(self.client_ssl_auth_widget)

        # the light/dark override, sitting on its own at the very bottom
        self.theme_label = QLabel(_("Theme:"))
        self.theme_dropdown = QComboBox()
        self.theme_dropdown.addItems(list(THEME_CHOICES))

        # and the whole-application font size, right below the theme
        self.font_size_label = QLabel(_("Font Size:"))
        self.font_size_dropdown = QComboBox()
        self.font_size_dropdown.addItems(list(FONT_SIZE_CHOICES))

        # Create a layout for the textboxes and labels
        layout = QVBoxLayout()
        layout.addWidget(self.hostname_label)
        layout.addWidget(self.hostname_textbox)
        layout.addWidget(self.port_label)
        layout.addWidget(self.port_textbox)
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_textbox)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_textbox)
        layout.addWidget(self.topic_label)
        layout.addWidget(self.topic_textbox)
        layout.addLayout(self.enable_ssl_layout)
        layout.addWidget(self.ssl_settings_widget)

        layout.addStretch(1)

        # kept below the stretch so they stay pinned to the bottom of the tab
        layout.addWidget(self.theme_label)
        layout.addWidget(self.theme_dropdown)
        layout.addWidget(self.font_size_label)
        layout.addWidget(self.font_size_dropdown)

        # Set the layout for the QWidget
        self.setLayout(layout)

    def cryptofile_browse(self, cert_type):

        # set some options for the file open dialog if we are on windows
        if os.name == "nt":
            start_dir = "C:\\"
            file_filter = "*.*"
        # or on linux and macOS
        else:
            start_dir = "/"
            file_filter = "*"

        filedialog = QFileDialog()

        if cert_type == "client-cert":
            filedialog.setWindowTitle(_('Select a client certificate'))
        elif cert_type == "server-cert":
            filedialog.setWindowTitle(_('Select a server certificate'))
        elif cert_type == "client-key":
            filedialog.setWindowTitle(_('Select client key file'))

        filedialog.setDirectory(start_dir)
        filedialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        filedialog.setNameFilter(file_filter)
        filedialog.setViewMode(QFileDialog.ViewMode.List)

        if filedialog.exec_() and len(filedialog.selectedFiles()) == 1:
            selected_file = filedialog.selectedFiles()[0]
            if cert_type == "client-cert":
                self.client_certificate_file.setText(selected_file)
            elif cert_type == "server-cert":
                self.server_certificate_file.setText(selected_file)
            elif cert_type == "client-key":
                self.client_key_file.setText(selected_file)
            self.settings_changed.emit(True)

    def setting_changed_event(self):
        self.settings_changed.emit(True)
        self.set_new_connection_settings()

    def enable_ssl_changed_event(self):
        self.ssl_settings_widget.setHidden(not self.enable_ssl_checkbox.isChecked())
        self.setting_changed_event()

    def enable_client_ssl_auth_changed_event(self):
        self.client_ssl_auth_widget.setHidden(not self.enable_client_ssl_auth_checkbox.isChecked())
        self.setting_changed_event()

    def theme_changed_event(self):
        # record and mark unsaved like any other setting, then apply it live so
        # the user sees the result without waiting or restarting
        self.setting_changed_event()
        self.theme_changed.emit()

    def font_size_changed_event(self):
        self.setting_changed_event()
        self.font_size_changed.emit()

    def set_new_connection_settings(self):
        settings_data = []

        # Create a dictionary from the textbox data
        settings_data = {
            "hostname": self.hostname_textbox.text(),
            "port": self.port_textbox.text(),
            "username": self.username_textbox.text(),
            "password": self.password_textbox.text(),
            "topic": self.topic_textbox.text(),
            "enable_ssl": self.enable_ssl_checkbox.isChecked(),
            "server_certificate_file": self.server_certificate_file.text(),
            "enable_client_ssl_auth": self.enable_client_ssl_auth_checkbox.isChecked(),
            "client_certificate_file": self.client_certificate_file.text(),
            "client_key_file": self.client_key_file.text(),
            "allow_insecure_ssl": self.insecure_ssl_checkbox.isChecked(),
            # included here because refresh_settings replaces the whole dict; if
            # these were left out, saving a connection change would drop them
            "theme": self.theme_dropdown.currentText(),
            "font_size": self.font_size_dropdown.currentText()
        }

        MQTTSettings.get_instance().refresh_settings(settings_data)

    def showEvent(self, a0: QtGui.QShowEvent) -> None:
        settings = MQTTSettings.get_instance()

        self.hostname_textbox.setText(settings.hostname)
        self.port_textbox.setText(settings.port)
        self.username_textbox.setText(settings.username)
        self.password_textbox.setText(settings.password)
        self.topic_textbox.setText(settings.topic)
        self.enable_ssl_checkbox.setChecked(settings.enable_ssl)
        self.server_certificate_file.setText(settings.server_certificate_file)
        self.enable_client_ssl_auth_checkbox.setChecked(settings.enable_client_ssl_auth)
        self.client_certificate_file.setText(settings.client_certificate_file)
        self.client_key_file.setText(settings.client_key_file)
        self.insecure_ssl_checkbox.setChecked(settings.allow_insecure_ssl)
        self.theme_dropdown.setCurrentText(settings.theme if settings.theme in THEME_CHOICES
                                           else DEFAULT_THEME_CHOICE)
        self.font_size_dropdown.setCurrentText(settings.font_size if settings.font_size in FONT_SIZE_CHOICES
                                               else DEFAULT_FONT_SIZE)

        # now that we've loaded the settings, enable event handlers to catch changes
        self.hostname_textbox.textChanged.connect(self.setting_changed_event)
        self.port_textbox.textChanged.connect(self.setting_changed_event)
        self.username_textbox.textChanged.connect(self.setting_changed_event)
        self.password_textbox.textChanged.connect(self.setting_changed_event)
        self.topic_textbox.textChanged.connect(self.setting_changed_event)
        self.enable_ssl_checkbox.stateChanged.connect(self.enable_ssl_changed_event)
        self.server_certificate_file.textChanged.connect(self.setting_changed_event)
        self.enable_client_ssl_auth_checkbox.stateChanged.connect(self.enable_client_ssl_auth_changed_event)
        self.client_certificate_file.textChanged.connect(self.setting_changed_event)
        self.client_key_file.textChanged.connect(self.setting_changed_event)
        self.insecure_ssl_checkbox.stateChanged.connect(self.setting_changed_event)
        self.theme_dropdown.currentTextChanged.connect(self.theme_changed_event)
        self.font_size_dropdown.currentTextChanged.connect(self.font_size_changed_event)

        # check whether we need to show SSL/TLS settings
        self.ssl_settings_widget.setHidden(not self.enable_ssl_checkbox.isChecked())
        self.client_ssl_auth_widget.setHidden(not self.enable_client_ssl_auth_checkbox.isChecked())

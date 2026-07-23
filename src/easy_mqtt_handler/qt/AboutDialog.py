"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  qt/AboutDialog.py
*
*  Defines the About Dialog
*
*  Copyright (C) 2023 A. Zeil
"""
import gettext

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QTabWidget, QTextEdit, QVBoxLayout, QPushButton, QLabel, QHBoxLayout

from easy_mqtt_handler.util import AppInfo
from easy_mqtt_handler.util.Icons import *
from easy_mqtt_handler.util.Tools import Utils

MY_LICENSE = Utils.resource_path("licenses/COPYING")
PAHO_LICENSE = Utils.resource_path("licenses/paho.txt")
QT5_LICENSE = Utils.resource_path("licenses/qt5.txt")
BRIEFCASE_LICENSE = Utils.resource_path("licenses/briefcase.txt")
CRYPTOGRAPHY_LICENSE = Utils.resource_path("licenses/cryptography.txt")
PYOPENSSL_LICENSE = Utils.resource_path("licenses/pyopenssl.txt")
HUMANITY_ICONS_LICENSE = Utils.resource_path("licenses/humanity.txt")

# Set the local directory
localedir = Utils.resource_path("./locale")

# Set up your magic function
translate = gettext.translation('AboutDialog', localedir, fallback=True)
_ = translate.gettext


class AboutTabMain(QWidget):
    """Tells the user what this program is, which version it is and where it lives."""

    def __init__(self):
        super().__init__()

        # name, version and URL all come from the packaging metadata, so they
        # cannot drift away from what was actually built
        info = AppInfo.get_app_info()

        icon = QLabel()
        icon.setPixmap(Icons.load_icon(APP_ICON).pixmap(64))

        title = QLabel(info["name"])
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        title.setFont(title_font)

        version = QLabel(_("Version {0}").format(info["version"]))

        # a heading block: icon on the left, name and version stacked beside it
        heading_text = QVBoxLayout()
        heading_text.addWidget(title)
        heading_text.addWidget(version)
        heading_text.addStretch()

        heading = QHBoxLayout()
        heading.addWidget(icon)
        heading.addSpacing(12)
        heading.addLayout(heading_text)
        heading.addStretch()

        purpose = QLabel(_(
            "Easy MQTT Handler connects to an MQTT broker, listens for the messages you "
            "define and runs a command of your choice whenever one of them arrives.\n\n"
            "It can also publish messages of its own as soon as it connects, and have Home "
            "Assistant create matching entities for them automatically, so each machine can "
            "announce what belongs to it.\n\n"
            "It stays out of the way in the system tray while it works."))
        purpose.setWordWrap(True)

        # a real link, so the user can get to the project from here
        url = QLabel('<a href="{0}">{0}</a>'.format(info["url"]))
        url.setOpenExternalLinks(True)
        url.setTextInteractionFlags(Qt.TextBrowserInteraction)

        licence = QLabel(_("Released under the GNU General Public License v3 or later. "
                           "The full text is in the License tab."))
        licence.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addLayout(heading)
        layout.addSpacing(12)
        layout.addWidget(purpose)
        layout.addSpacing(12)
        layout.addWidget(url)
        layout.addSpacing(12)
        layout.addWidget(licence)
        layout.addStretch()
        self.setLayout(layout)


class LicenseTab(QWidget):

    def __init__(self, license_file):
        super().__init__()

        # create the multi-line text box
        self.text_box = QTextEdit(self)
        self.text_box.setReadOnly(True)

        # make it always fill the QWidget
        layout = QVBoxLayout()
        layout.addWidget(self.text_box)
        self.setLayout(layout)

        self.text_box.setText(Utils.load_license_file(license_file))


class AboutDialog(QWidget):

    def __init__(self, app):
        super().__init__()

        self.setWindowTitle(_("About Program"))

        # load the dialog icon
        self.setWindowIcon(Icons.load_icon(APP_ICON))

        # create tab container widget
        self.tab_widget = QTabWidget(self)

        # create the tabs
        self.main_tab = AboutTabMain()
        # the program's own licence, which used to sit on the About tab
        self.license_tab = LicenseTab(MY_LICENSE)
        self.paho_tab = LicenseTab(PAHO_LICENSE)
        self.qt_tab = LicenseTab(QT5_LICENSE)
        self.briefcase_tab = LicenseTab(BRIEFCASE_LICENSE)
        self.cryptography_tab = LicenseTab(CRYPTOGRAPHY_LICENSE)
        self.pyopenssl_tab = LicenseTab(PYOPENSSL_LICENSE)
        self.humanity_icons_tab = LicenseTab(HUMANITY_ICONS_LICENSE)

        # add them to the tab widget
        self.tab_widget.addTab(self.main_tab, _('About Easy MQTT Handler'))
        self.tab_widget.addTab(self.license_tab, _('License'))
        self.tab_widget.addTab(self.paho_tab, _('paho mqtt License'))
        self.tab_widget.addTab(self.qt_tab, _('Qt 5 License'))
        self.tab_widget.addTab(self.briefcase_tab, _('briefcase License'))
        self.tab_widget.addTab(self.cryptography_tab, _('cryptography License'))
        self.tab_widget.addTab(self.pyopenssl_tab, _('pyOpenSSL License'))
        self.tab_widget.addTab(self.humanity_icons_tab, _('Humanity Icons License'))

        self.close_button = QPushButton(_('Close'))
        self.close_button.clicked.connect(self.close)

        layout = QVBoxLayout()
        layout.addWidget(self.tab_widget)
        layout.addWidget(self.close_button)
        self.setLayout(layout)

        # resize and reposition about dialog
        self.width = app.primaryScreen().size().width() // 4
        self.height = (app.primaryScreen().size().height() // 4) + 75
        pos_x = app.primaryScreen().size().width() // 2
        pos_y = app.primaryScreen().size().height() // 2
        self.setGeometry(pos_x - (self.width // 2), pos_y - (self.height // 2), self.width, self.height)

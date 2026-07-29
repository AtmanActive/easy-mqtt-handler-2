#! /usr/bin/python3
"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  __main__.py
*
*  Main class of the program
*
*  Copyright (C) 2023 A. Zeil
"""
import os
import sys
import argparse

from PyQt5.QtWidgets import QApplication
from easy_mqtt_handler.qt.MainWindow import MainWindow
from easy_mqtt_handler.util import Fonts, Theme
from easy_mqtt_handler.util.MQTTSettings import MQTTSettings
from easy_mqtt_handler.util.Tools import Utils


def configured_theme():
    """The saved Theme choice, or None before the settings have been loaded."""
    if MQTTSettings._instance is None:
        return None
    return MQTTSettings.get_instance().theme


def configured_font_size():
    """The saved Font Size choice, or None before the settings have been loaded."""
    if MQTTSettings._instance is None:
        return None
    return MQTTSettings.get_instance().font_size


# entry point
if __name__ == "__main__":

    arguments = argparse.ArgumentParser(description="Easy MQTT Handler")
    arguments.add_argument("-mqtt-conf", "--mqtt-configuration-file", type=str, default="")
    arguments.add_argument("-payload-conf", "--payload-configuration-file", type=str, default="")
    arguments.add_argument("-startup-conf", "--startup-configuration-file", type=str, default="")
    args = arguments.parse_args()

    # create configuration folder, if it doesn't exist, yet
    Utils.create_path_if_not_exists(Utils.get_config_path())

    # show the window when there is nothing configured yet. this used to key off
    # having just created the config folder, which never happens in portable mode
    # because the "data" folder has to exist before it is picked up
    settings_in_use = args.mqtt_configuration_file if args.mqtt_configuration_file != "" \
        else Utils.get_settings_file()
    firstStart = not os.path.exists(settings_in_use)

    # create the application
    app = QApplication(sys.argv)

    # follow the saved Theme choice, or the OS when it is set to system, and
    # keep following it while we run
    theme_manager = Theme.install(app, theme_getter=configured_theme)

    # apply the saved Font Size to the whole application
    font_manager = Fonts.install(app, size_getter=configured_font_size)

    # create the main window; it lets the Theme and Font Size drop downs apply
    # changes live
    main_window = MainWindow(app, args.mqtt_configuration_file, args.payload_configuration_file,
                             args.startup_configuration_file, theme_manager, font_manager)

    # the settings did not exist when the managers were installed, so apply the
    # saved choices now that they are loaded
    theme_manager.sync_with_system()
    font_manager.apply_configured()

    # if this is our first run, show the main window
    if firstStart:
        main_window.show()
        # the window did not exist when the theme was installed, so style its
        # title bar now instead of waiting for the next poll
        theme_manager.refresh_titlebars()

    # run the application
    sys.exit(app.exec_())

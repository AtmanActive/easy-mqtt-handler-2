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
from easy_mqtt_handler.util import Theme
from easy_mqtt_handler.util.Tools import Utils


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

    # match the OS light/dark preference, and keep following it while we run
    theme_manager = Theme.install(app)

    # create the main window
    main_window = MainWindow(app, args.mqtt_configuration_file, args.payload_configuration_file,
                             args.startup_configuration_file)

    # if this is our first run, show the main window
    if firstStart:
        main_window.show()
        # the window did not exist when the theme was installed, so style its
        # title bar now instead of waiting for the next poll
        theme_manager.refresh_titlebars()

    # run the application
    sys.exit(app.exec_())

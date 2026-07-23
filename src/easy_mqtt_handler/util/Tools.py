"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  Tools.py
*
*  This class contains a collection of various utility functions
*
*  Copyright (C) 2023 A. Zeil
"""
import datetime
import os
import socket
import sys

from cryptography.hazmat.primitives import serialization
from OpenSSL import SSL
from pathlib import Path


class Utils:
    LICENSE_LOAD_ERROR = "License File couldn't be loaded, please check our Git Repository: " \
                         "https://github.com/AtmanActive/easy-mqtt-handler-2/"

    # a directory of this name sitting next to the executable turns on portable mode
    PORTABLE_DATA_DIRNAME = "data"

    # names the portable data directory outright, for bundles where the
    # interpreter does not sit beside the thing the user launches. The Linux
    # portable launcher sets it; on Windows the directory is found on its own.
    PORTABLE_DATA_ENV_VAR = "EASY_MQTT_HANDLER_DATA"

    DEFAULT_SETTINGS_FILENAME = "default-settings.json"
    DEFAULT_PAYLOADS_FILENAME = "default-payloads.json"
    DEFAULT_STARTUP_FILENAME = "default-startup-messages.json"

    @staticmethod
    def get_executable_directory():
        # for a packaged app this is the folder holding the .exe; when running from
        # source it is wherever the interpreter lives, which will not normally have
        # a "data" directory beside it, so portable mode simply stays off
        return os.path.dirname(os.path.abspath(sys.executable))

    @classmethod
    def get_portable_data_path(cls):
        """Return the adjacent "data" directory, or None when there isn't one.

        Its presence is what enables portable mode: we never create it, because
        creating it would permanently opt the user in. That holds for the
        environment variable too, which is ignored unless it names a directory
        that exists, so deleting the folder reverts to the per-user location.
        """
        named = os.environ.get(cls.PORTABLE_DATA_ENV_VAR, "").strip()
        if named:
            return named + os.sep if os.path.isdir(named) else None

        candidate = os.path.join(cls.get_executable_directory(), cls.PORTABLE_DATA_DIRNAME)
        if os.path.isdir(candidate):
            # callers concatenate filenames directly, so keep the trailing separator
            return candidate + os.sep
        return None

    @classmethod
    def is_portable(cls):
        return cls.get_portable_data_path() is not None

    @classmethod
    def get_config_path(cls):
        # a "data" folder next to the executable wins, so the app can be carried
        # around on a stick together with its configuration
        portable_path = cls.get_portable_data_path()
        if portable_path is not None:
            return portable_path

        # on windows, we want to store the configuration in %appdata%\easy-mqtt-handler, while
        # on *nix-based OSes we want to store the configuration in ~/.config/easy-mqtt-handler
        return os.path.expandvars("%appdata%\\easy-mqtt-handler\\") if os.name == "nt" else os.path.expanduser("~/.config/easy-mqtt-handler/")

    @classmethod
    def get_settings_file(cls):
        return cls.get_config_path() + cls.DEFAULT_SETTINGS_FILENAME

    @classmethod
    def get_payload_file(cls):
        return cls.get_config_path() + cls.DEFAULT_PAYLOADS_FILENAME

    @classmethod
    def get_startup_file(cls):
        return cls.get_config_path() + cls.DEFAULT_STARTUP_FILENAME

    @staticmethod
    def create_path_if_not_exists(path):
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            return True
        else:
            return False

    @staticmethod
    def get_timestamp():
        return datetime.datetime.now().strftime("%d.%m.%Y, %H:%M:%S")

    @staticmethod
    def load_license_file(license_file):
        if os.path.exists(license_file):
            try:
                with open(license_file, 'r') as sf:
                    return sf.read()
            # TODO: implement better exception handling
            except IOError:
                return Utils.LICENSE_LOAD_ERROR
        else:
            return Utils.LICENSE_LOAD_ERROR

    @staticmethod
    def resource_path(relative_path):
        base_path = getattr(sys, '_MEIPASS', str(Path(os.path.dirname(os.path.abspath(__file__))).parent.absolute()))
        return os.path.join(base_path, relative_path)

    # this function tries to establish a connection and initiate an SSL handshake to fetch the certificate chain from a
    # server. it returns False, should it not be able to do so for whatever reason
    @classmethod
    def get_certificate_chain(cls, host, port):
        try:
            ssl_context = SSL.Context(method=SSL.SSLv23_METHOD)
            ssl_connection = SSL.Connection(ssl_context,
                                            socket=socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM))
            # ssl_connection.settimeout(1)
            ssl_connection.setblocking(1)
            ssl_connection.connect((host, int(port)))
            ssl_connection.do_handshake()
            cert_chain = ssl_connection.get_peer_cert_chain()
            ssl_connection.close()

            pem_file_bytes = bytearray()
            for cert in cert_chain:
                pem_file_bytes = pem_file_bytes + cert.to_cryptography().public_bytes(serialization.Encoding.PEM)

            tmp_pem_file = f"{cls.get_config_path()}tmp.pem"

            with open(tmp_pem_file, 'wb') as pf:
                pf.write(pem_file_bytes)
                pf.close()

                return tmp_pem_file
        except:
            return False

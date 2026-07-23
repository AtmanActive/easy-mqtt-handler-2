"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/conftest.py
*
*  Shared pytest fixtures
*
*  Copyright (C) 2023 A. Zeil
"""
import pytest

from easy_mqtt_handler.util.MQTTPayloads import MQTTPayloads
from easy_mqtt_handler.util.MQTTSettings import MQTTSettings
from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages


def _clear_singletons():
    MQTTSettings._instance = None
    MQTTSettings._settings = {}
    MQTTPayloads._instance = None
    MQTTPayloads._payload_data = {}
    MQTTStartupMessages._instance = None
    MQTTStartupMessages._startup_data = []


# these config classes are singletons that keep their state on the class itself,
# so a leftover instance from a previous test would make the next constructor
# call raise. Reset them around every test.
@pytest.fixture(autouse=True)
def reset_singletons():
    _clear_singletons()
    yield
    _clear_singletons()

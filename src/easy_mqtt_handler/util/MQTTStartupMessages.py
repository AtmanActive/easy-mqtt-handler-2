"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  util/MQTTStartupMessages.py
*
*  Class to handle the MQTT messages that are published once a connection to
*  the broker has been established
*
*  Copyright (C) 2026 AtmanActive
"""
import json
import os
import re

# a message the user has not filled in a topic for cannot be published
REQUIRED_FIELD = "topic"

VALID_QOS_LEVELS = (0, 1, 2)

# Home Assistant listens for auto discovery below this prefix by default
HA_DISCOVERY_PREFIX = "homeassistant"

# the component decides which kind of entity Home Assistant creates
HA_DEFAULT_COMPONENT = "sensor"

# a handful of the components people are most likely to want; the field stays
# editable because Home Assistant supports many more
HA_COMMON_COMPONENTS = (
    "sensor", "binary_sensor", "switch", "light", "button",
    "number", "text", "select", "device_tracker",
)

# both of these end up as topic levels, so they must not contain a separator or
# a wildcard. Home Assistant expects object ids in this shape anyway.
HA_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class DiscoveryError(ValueError):
    """Raised when a row asks for discovery but cannot produce a valid one."""


class MQTTStartupMessages(object):
    @property
    def startup_data(self):
        return self._startup_data

    @startup_data.setter
    def startup_data(self, value):
        self._startup_data = value

    _instance = None
    _startup_file = ""

    _startup_data = []

    @staticmethod
    def get_instance():
        if MQTTStartupMessages._instance is None:
            MQTTStartupMessages()
        return MQTTStartupMessages._instance

    def __init__(self, filename):
        if MQTTStartupMessages._instance is not None:
            raise Exception("This is a Singleton Class. Only once instance allowed!")
        else:
            MQTTStartupMessages._instance = self
            self._startup_file = filename
            self._startup_data = self.load_startup_data()

    def load_startup_data(self):
        if os.path.exists(self._startup_file):
            try:
                # utf-8-sig so a file hand-edited in an editor that adds a BOM
                # still loads; it reads plain UTF-8 unchanged
                with open(self._startup_file, 'r', encoding='utf-8-sig') as sf:
                    loaded = json.load(sf)
                    # guard against a hand-edited file holding something else
                    return loaded if isinstance(loaded, list) else []
            # TODO: implement better exception handling
            except (IOError, ValueError):
                return []
        else:
            return []

    def save_startup_data(self):
        try:
            with open(self._startup_file, 'w', encoding='utf-8') as sf:
                json.dump(self._startup_data, sf)

                return True
        # TODO: implement better exception handling
        except:
            return False

    def publishable_messages(self):
        """Return only the entries that can actually be sent.

        Rows are created empty when the user clicks Add, and a half-filled row
        should never reach the broker, so anything without a topic is skipped.
        """
        messages = []
        for item in self._startup_data:
            if not isinstance(item, dict):
                continue
            topic = str(item.get(REQUIRED_FIELD, "")).strip()
            if topic == "":
                continue

            qos = item.get("qos", 0)
            try:
                qos = int(qos)
            except (TypeError, ValueError):
                qos = 0
            if qos not in VALID_QOS_LEVELS:
                qos = 0

            messages.append({
                "topic": topic,
                "payload": str(item.get("payload", "")),
                "qos": qos,
                "retain": bool(item.get("retain", False)),
                # Home Assistant auto discovery, all optional
                "ha_entity": str(item.get("ha_entity", "")).strip(),
                "ha_id": str(item.get("ha_id", "")).strip(),
                "ha_name": str(item.get("ha_name", "")).strip(),
            })
        return messages


def discovery_for(message):
    """Build the Home Assistant discovery message for a startup message.

    Returns None when the row does not ask for discovery, which is the case for
    every configuration written before this feature existed. Raises
    DiscoveryError when discovery was asked for but cannot be built.
    """
    ha_id = str(message.get("ha_id", "")).strip()
    if ha_id == "":
        # no id means the user does not want an entity created for this row
        return None

    if not HA_IDENTIFIER_PATTERN.match(ha_id):
        raise DiscoveryError(
            f"\"{ha_id}\" is not a usable HA ID, use only letters, digits, underscores and hyphens")

    component = str(message.get("ha_entity", "")).strip() or HA_DEFAULT_COMPONENT
    if not HA_IDENTIFIER_PATTERN.match(component):
        raise DiscoveryError(
            f"\"{component}\" is not a usable HA Entity, use only letters, digits, underscores and hyphens")

    # an unnamed entity is hard to find in Home Assistant, so fall back to the id
    name = str(message.get("ha_name", "")).strip() or ha_id

    payload = json.dumps({
        "name": name,
        "state_topic": message["topic"],
        "unique_id": ha_id,
    }, ensure_ascii=False)

    return {
        "topic": f"{HA_DISCOVERY_PREFIX}/{component}/{ha_id}/config",
        "payload": payload,
        "qos": message.get("qos", 0),
        # discovery has to be retained, otherwise the entity disappears from
        # Home Assistant the next time it restarts
        "retain": True,
    }

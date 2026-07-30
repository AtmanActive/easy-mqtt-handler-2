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

from easy_mqtt_handler.util.StartupPayload import DEFAULT_TYPE, PAYLOAD_TYPES, TYPE_REMOVE_HA_ENTITY

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

    @staticmethod
    def _as_message(item):
        """Turn one raw config row into a message dict, or None if unusable.

        A half-filled row should never reach the broker: an ordinary row needs
        a topic, and a removal row, which ignores the topic, needs an HA ID.
        """
        if not isinstance(item, dict):
            return None

        # how the payload should be interpreted; an unfamiliar value (or an
        # older config with none) falls back to a plain literal
        payload_type = str(item.get("type", DEFAULT_TYPE))
        if payload_type not in PAYLOAD_TYPES:
            payload_type = DEFAULT_TYPE

        topic = str(item.get(REQUIRED_FIELD, "")).strip()
        ha_id = str(item.get("ha_id", "")).strip()
        if payload_type == TYPE_REMOVE_HA_ENTITY:
            # the topic is ignored; the entity to remove comes from HA ID
            if ha_id == "":
                return None
        elif topic == "":
            return None

        qos = item.get("qos", 0)
        try:
            qos = int(qos)
        except (TypeError, ValueError):
            qos = 0
        if qos not in VALID_QOS_LEVELS:
            qos = 0

        return {
            "topic": topic,
            "type": payload_type,
            "payload": str(item.get("payload", "")),
            "qos": qos,
            "retain": bool(item.get("retain", False)),
            # Home Assistant auto discovery, all optional
            "ha_entity": str(item.get("ha_entity", "")).strip(),
            "ha_id": ha_id,
            "ha_name": str(item.get("ha_name", "")).strip(),
        }

    def publishable_and_duplicate_messages(self):
        """Split the publishable rows into the ones to act on and duplicates.

        Two rows that target the same MQTT topic are duplicates, wherever they
        sit in the list: the engine would act on the same topic twice. Only the
        first is kept; the rest are reported so the caller can note them and
        move on. Values and payloads are not part of the identity, because they
        are not what the row is indexed by in MQTT terms.
        """
        seen = set()
        unique = []
        duplicates = []
        for item in self._startup_data:
            message = self._as_message(item)
            if message is None:
                continue
            key = startup_target_topic(message)
            if key in seen:
                duplicates.append(message)
            else:
                seen.add(key)
                unique.append(message)
        return unique, duplicates

    def publishable_messages(self):
        """The rows to actually act on, with duplicates already dropped."""
        return self.publishable_and_duplicate_messages()[0]


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


def ha_removal_topic(message):
    """The discovery config topic to clear in order to remove an entity.

    Home Assistant deletes an entity when its retained discovery config is
    cleared, so removal means publishing an empty retained payload to exactly
    the topic discovery_for() would have used. Returns (topic, None), or
    (None, reason) when the row does not name a usable entity. Only HA Entity
    and HA ID are read; every other field on the row is ignored.
    """
    ha_id = str(message.get("ha_id", "")).strip()
    if ha_id == "":
        return None, "no HA ID given"
    if not HA_IDENTIFIER_PATTERN.match(ha_id):
        return None, f"\"{ha_id}\" is not a usable HA ID"

    component = str(message.get("ha_entity", "")).strip() or HA_DEFAULT_COMPONENT
    if not HA_IDENTIFIER_PATTERN.match(component):
        return None, f"\"{component}\" is not a usable HA Entity"

    return f"{HA_DISCOVERY_PREFIX}/{component}/{ha_id}/config", None


def startup_target_topic(message):
    """The MQTT topic a row acts on, used both as its identity and for logs.

    A removal row acts on the entity's discovery config topic; every other row
    acts on its own topic. This is what makes two rows count as the same, since
    it is what the engine actually does with them.
    """
    if message.get("type") == TYPE_REMOVE_HA_ENTITY:
        topic, _error = ha_removal_topic(message)
        return topic
    return message.get("topic", "")

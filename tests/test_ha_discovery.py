"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_ha_discovery.py
*
*  Tests for the Home Assistant auto discovery messages built from the
*  "Send on Startup" rows
*
*  Copyright (C) 2026 AtmanActive
"""
import json

import pytest

from easy_mqtt_handler.util.MQTTStartupMessages import (
    DiscoveryError, HA_DEFAULT_COMPONENT, MQTTStartupMessages, discovery_for)


def message(**overrides):
    base = {"topic": "your/random/topic", "payload": "42", "qos": 0, "retain": False,
            "ha_entity": "", "ha_id": "", "ha_name": ""}
    base.update(overrides)
    return base


def test_no_discovery_without_an_ha_id():
    assert discovery_for(message()) is None


def test_no_discovery_for_a_row_predating_the_feature():
    # configurations saved by earlier versions have none of the ha_ keys
    assert discovery_for({"topic": "a/b", "payload": "x", "qos": 0, "retain": False}) is None


def test_discovery_topic_follows_the_documented_format():
    discovery = discovery_for(message(ha_entity="sensor", ha_id="my_sensor"))

    assert discovery["topic"] == "homeassistant/sensor/my_sensor/config"


def test_discovery_payload_matches_the_documented_shape():
    discovery = discovery_for(message(topic="your/random/topic",
                                      ha_entity="sensor",
                                      ha_id="my_custom_sensor_001",
                                      ha_name="My Custom Sensor"))

    assert json.loads(discovery["payload"]) == {
        "name": "My Custom Sensor",
        "state_topic": "your/random/topic",
        "unique_id": "my_custom_sensor_001",
    }


def test_discovery_is_always_retained():
    # without retain the entity vanishes when Home Assistant restarts
    discovery = discovery_for(message(ha_id="x", retain=False))

    assert discovery["retain"] is True


def test_entity_type_defaults_to_sensor():
    discovery = discovery_for(message(ha_id="my_sensor"))

    assert discovery["topic"] == f"homeassistant/{HA_DEFAULT_COMPONENT}/my_sensor/config"


def test_other_components_are_honoured():
    discovery = discovery_for(message(ha_entity="binary_sensor", ha_id="door"))

    assert discovery["topic"] == "homeassistant/binary_sensor/door/config"


def test_name_falls_back_to_the_id():
    # an unnamed entity would be near impossible to find in Home Assistant
    discovery = discovery_for(message(ha_id="kitchen_temp"))

    assert json.loads(discovery["payload"])["name"] == "kitchen_temp"


def test_discovery_uses_the_rows_qos():
    discovery = discovery_for(message(ha_id="x", qos=2))

    assert discovery["qos"] == 2


def test_surrounding_whitespace_is_ignored():
    discovery = discovery_for(message(ha_entity="  switch  ", ha_id="  lamp  ", ha_name="  Lamp  "))

    assert discovery["topic"] == "homeassistant/switch/lamp/config"
    assert json.loads(discovery["payload"])["name"] == "Lamp"


def test_non_ascii_names_survive():
    discovery = discovery_for(message(ha_id="buero", ha_name="Büro Temperatur"))

    assert json.loads(discovery["payload"])["name"] == "Büro Temperatur"


@pytest.mark.parametrize("bad_id", [
    "with space", "with/slash", "with+plus", "with#hash", "with.dot", "ümlaut",
])
def test_an_unusable_ha_id_is_rejected(bad_id):
    # these would break the topic or confuse Home Assistant's object id rules
    with pytest.raises(DiscoveryError, match="HA ID"):
        discovery_for(message(ha_id=bad_id))


@pytest.mark.parametrize("bad_component", ["with space", "with/slash", "with#hash"])
def test_an_unusable_component_is_rejected(bad_component):
    with pytest.raises(DiscoveryError, match="HA Entity"):
        discovery_for(message(ha_entity=bad_component, ha_id="fine_id"))


def test_ha_fields_survive_a_round_trip_through_the_config_file(tmp_path):
    startup_file = tmp_path / "startup.json"
    messages = MQTTStartupMessages(str(startup_file))
    messages.startup_data = [{
        "topic": "desk/temp", "payload": "21", "qos": 0, "retain": True,
        "ha_entity": "sensor", "ha_id": "desk_temp", "ha_name": "Desk Temperature",
    }]

    assert messages.save_startup_data() is True

    reloaded = json.loads(startup_file.read_text(encoding="utf-8"))[0]
    assert reloaded["ha_id"] == "desk_temp"
    assert reloaded["ha_name"] == "Desk Temperature"
    assert reloaded["ha_entity"] == "sensor"


def test_publishable_messages_carry_the_ha_fields(tmp_path):
    messages = MQTTStartupMessages(str(tmp_path / "startup.json"))
    messages.startup_data = [{
        "topic": "desk/temp", "ha_entity": "sensor", "ha_id": "desk_temp", "ha_name": "Desk",
    }]

    published = messages.publishable_messages()[0]

    assert published["ha_entity"] == "sensor"
    assert published["ha_id"] == "desk_temp"
    assert published["ha_name"] == "Desk"


def test_publishable_messages_default_the_ha_fields_to_empty(tmp_path):
    messages = MQTTStartupMessages(str(tmp_path / "startup.json"))
    messages.startup_data = [{"topic": "desk/temp"}]

    published = messages.publishable_messages()[0]

    assert published["ha_entity"] == ""
    assert published["ha_id"] == ""
    assert published["ha_name"] == ""

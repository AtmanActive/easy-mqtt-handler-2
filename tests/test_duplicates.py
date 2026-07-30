"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_duplicates.py
*
*  Tests that both engines are immune to duplicate rows: a duplicate is skipped
*  and reported, wherever it sits in the list
*
*  Copyright (C) 2026 AtmanActive
"""
import pytest

from easy_mqtt_handler.util.MQTTPayloads import MQTTPayloads
from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages, startup_target_topic
from easy_mqtt_handler.util.MQTTWorkerThread import MQTTWorkerThread

from tests.test_startup_publish import FakeClient


# --- Send on Startup dedup --------------------------------------------------

def test_a_second_row_with_the_same_topic_is_a_duplicate(tmp_path):
    store = MQTTStartupMessages(str(tmp_path / "startup.json"))
    store.startup_data = [
        {"topic": "home/one", "type": "literal", "payload": "a"},
        {"topic": "home/one", "type": "literal", "payload": "b"},  # same topic
        {"topic": "home/two", "type": "literal", "payload": "c"},
    ]

    unique, duplicates = store.publishable_and_duplicate_messages()

    assert [m["topic"] for m in unique] == ["home/one", "home/two"]
    assert [m["topic"] for m in duplicates] == ["home/one"]


def test_the_first_occurrence_is_the_one_kept(tmp_path):
    store = MQTTStartupMessages(str(tmp_path / "startup.json"))
    store.startup_data = [
        {"topic": "t", "type": "literal", "payload": "first"},
        {"topic": "t", "type": "literal", "payload": "second"},
    ]

    unique = store.publishable_messages()

    assert len(unique) == 1
    assert unique[0]["payload"] == "first"


def test_a_duplicate_is_caught_no_matter_where_it_sits(tmp_path):
    store = MQTTStartupMessages(str(tmp_path / "startup.json"))
    store.startup_data = [
        {"topic": "a", "type": "literal", "payload": "1"},
        {"topic": "b", "type": "literal", "payload": "2"},
        {"topic": "c", "type": "literal", "payload": "3"},
        {"topic": "a", "type": "literal", "payload": "4"},  # far from the first
    ]

    unique, duplicates = store.publishable_and_duplicate_messages()

    assert [m["topic"] for m in unique] == ["a", "b", "c"]
    assert [m["topic"] for m in duplicates] == ["a"]


def test_the_payload_is_not_part_of_the_identity(tmp_path):
    # two rows with the same topic but different payloads are still duplicates
    store = MQTTStartupMessages(str(tmp_path / "startup.json"))
    store.startup_data = [
        {"topic": "t", "type": "built-in", "payload": "networking: hostname"},
        {"topic": "t", "type": "literal", "payload": "something else"},
    ]

    assert len(store.publishable_messages()) == 1


def test_two_removal_rows_for_the_same_entity_are_duplicates(tmp_path):
    store = MQTTStartupMessages(str(tmp_path / "startup.json"))
    store.startup_data = [
        {"type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "gone"},
        {"type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "gone"},
    ]

    unique, duplicates = store.publishable_and_duplicate_messages()

    assert len(unique) == 1
    assert len(duplicates) == 1


def test_removal_and_normal_rows_do_not_collide(tmp_path):
    store = MQTTStartupMessages(str(tmp_path / "startup.json"))
    store.startup_data = [
        {"topic": "home/light", "type": "literal", "payload": "ON"},
        {"type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "gone"},
    ]

    assert len(store.publishable_messages()) == 2


def test_startup_target_topic_is_the_config_topic_for_a_removal():
    topic = startup_target_topic({"type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "x"})

    assert topic == "homeassistant/sensor/x/config"


def test_the_send_engine_skips_and_reports_a_duplicate(tmp_path):
    from easy_mqtt_handler.util.MQTTSettings import MQTTSettings
    MQTTSettings(str(tmp_path / "settings.json"))
    store = MQTTStartupMessages(str(tmp_path / "startup.json"))
    store.startup_data = [
        {"topic": "t", "type": "literal", "payload": "a"},
        {"topic": "t", "type": "literal", "payload": "b"},
    ]

    worker = MQTTWorkerThread()
    logged = []
    worker.add_log_line.connect(logged.append)
    client = FakeClient()

    worker.send_startup_messages(client)

    # only the first went out
    assert [m["topic"] for m in client.published] == ["t"]
    assert any("duplicate startup row" in line and "\"t\"" in line for line in logged)


# --- Payload Handlers dedup -------------------------------------------------

def test_a_repeated_command_and_argument_is_a_duplicate(tmp_path):
    store = MQTTPayloads(str(tmp_path / "payloads.json"))
    store.payload_data = [
        {"payload_command": "notify", "payload_argument": "a", "command_to_run": "/one"},
        {"payload_command": "notify", "payload_argument": "a", "command_to_run": "/two"},
        {"payload_command": "notify", "payload_argument": "b", "command_to_run": "/three"},
    ]

    assert store.duplicate_command_keys() == [("notify", "a")]


def test_the_command_to_run_is_not_part_of_the_payload_identity(tmp_path):
    store = MQTTPayloads(str(tmp_path / "payloads.json"))
    store.payload_data = [
        {"payload_command": "c", "payload_argument": "x", "command_to_run": "/first"},
        {"payload_command": "c", "payload_argument": "x", "command_to_run": "/totally-different"},
    ]

    assert store.duplicate_command_keys() == [("c", "x")]


def test_a_payload_duplicate_is_reported_once_even_if_repeated_thrice(tmp_path):
    store = MQTTPayloads(str(tmp_path / "payloads.json"))
    store.payload_data = [
        {"payload_command": "c", "payload_argument": "x"},
        {"payload_command": "c", "payload_argument": "x"},
        {"payload_command": "c", "payload_argument": "x"},
    ]

    assert store.duplicate_command_keys() == [("c", "x")]


def test_no_payload_duplicates_when_all_unique(tmp_path):
    store = MQTTPayloads(str(tmp_path / "payloads.json"))
    store.payload_data = [
        {"payload_command": "a", "payload_argument": "1"},
        {"payload_command": "a", "payload_argument": "2"},
        {"payload_command": "b", "payload_argument": "1"},
    ]

    assert store.duplicate_command_keys() == []


def test_the_receiving_engine_runs_only_the_first_of_a_duplicate(tmp_path):
    # the router looks a command up and takes the first match, so a duplicate
    # simply never runs
    store = MQTTPayloads(str(tmp_path / "payloads.json"))
    store.payload_data = [
        {"payload_command": "c", "payload_argument": "x", "command_to_run": "/first",
         "command_line_arguments": ""},
        {"payload_command": "c", "payload_argument": "x", "command_to_run": "/second",
         "command_line_arguments": ""},
    ]

    from easy_mqtt_handler.util.MQTTWorkerThread import find_command_to_run
    assert find_command_to_run("c", "x") == "/first"


def test_duplicate_command_keys_survives_a_non_list(tmp_path):
    store = MQTTPayloads(str(tmp_path / "payloads.json"))
    store.payload_data = ""  # what an empty or unreadable file leaves behind

    assert store.duplicate_command_keys() == []

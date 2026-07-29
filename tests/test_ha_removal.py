"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_ha_removal.py
*
*  Tests for the "remove_ha_entity" row type: it publishes the entity's
*  removal and, once the broker confirms, asks for the row to be deleted
*
*  Copyright (C) 2026 AtmanActive
"""
import pytest

from easy_mqtt_handler.util.MQTTSettings import MQTTSettings
from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages, ha_removal_topic
from easy_mqtt_handler.util.MQTTWorkerThread import MQTTWorkerThread


# --- the removal topic ------------------------------------------------------

def test_removal_topic_matches_the_discovery_topic():
    topic, error = ha_removal_topic({"ha_entity": "sensor", "ha_id": "my_sensor"})

    assert error is None
    assert topic == "homeassistant/sensor/my_sensor/config"


def test_removal_topic_defaults_the_component_to_sensor():
    topic, _error = ha_removal_topic({"ha_id": "just_an_id"})

    assert topic == "homeassistant/sensor/just_an_id/config"


def test_removal_topic_honours_other_components():
    topic, _error = ha_removal_topic({"ha_entity": "binary_sensor", "ha_id": "door"})

    assert topic == "homeassistant/binary_sensor/door/config"


def test_removal_topic_needs_an_ha_id():
    topic, error = ha_removal_topic({"ha_entity": "sensor", "ha_id": ""})

    assert topic is None
    assert "HA ID" in error


@pytest.mark.parametrize("bad_id", ["with space", "with/slash", "with#hash"])
def test_removal_topic_rejects_an_unusable_id(bad_id):
    topic, error = ha_removal_topic({"ha_id": bad_id})

    assert topic is None
    assert "HA ID" in error


# --- the worker publishing the removal --------------------------------------

class FakeResult:
    def __init__(self, mid=1, rc=0):
        self.mid = mid
        self.rc = rc


class RecordingClient:
    def __init__(self, rc=0):
        self.published = []
        self._rc = rc
        self._next_mid = 1

    def publish(self, topic, payload, qos=0, retain=False):
        mid = self._next_mid
        self._next_mid += 1
        self.published.append({"topic": topic, "payload": payload, "qos": qos,
                               "retain": retain, "mid": mid})
        return FakeResult(mid=mid, rc=self._rc)


@pytest.fixture
def worker(tmp_path):
    MQTTSettings(str(tmp_path / "settings.json"))
    MQTTStartupMessages(str(tmp_path / "startup.json"))
    thread = MQTTWorkerThread()
    thread.logged = []
    thread.confirmed = []
    thread.add_log_line.connect(thread.logged.append)
    thread.ha_entity_removal_confirmed.connect(thread.confirmed.append)
    return thread


def test_a_removal_row_publishes_an_empty_retained_message(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "ignored", "type": "remove_ha_entity", "payload": "ignored",
         "qos": 0, "retain": False, "ha_entity": "sensor", "ha_id": "old_one"}]
    client = RecordingClient()

    worker.send_startup_messages(client)

    assert len(client.published) == 1
    published = client.published[0]
    assert published["topic"] == "homeassistant/sensor/old_one/config"
    assert published["payload"] == ""
    # retain must be on to clear the retained config, and QoS 1 so we get a PUBACK
    assert published["retain"] is True
    assert published["qos"] == 1


def test_a_removal_row_does_not_publish_a_discovery_or_a_normal_message(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "some/topic", "type": "remove_ha_entity", "payload": "hello",
         "ha_entity": "sensor", "ha_id": "old_one"}]
    client = RecordingClient()

    worker.send_startup_messages(client)

    topics = [m["topic"] for m in client.published]
    # only the removal, nothing on some/topic and no discovery create message
    assert topics == ["homeassistant/sensor/old_one/config"]


def test_a_removal_row_without_an_id_is_skipped(worker):
    # a half-filled removal row is left alone, like any other incomplete row,
    # because HA ID is what names the entity to remove
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "", "type": "remove_ha_entity", "payload": "", "ha_id": ""}]
    client = RecordingClient()

    worker.send_startup_messages(client)

    assert client.published == []


def test_a_removal_row_needs_no_topic(worker):
    # the whole point: an empty Topic must not stop the removal from happening
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "", "type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "orphan"}]
    client = RecordingClient()

    worker.send_startup_messages(client)

    assert [m["topic"] for m in client.published] == ["homeassistant/sensor/orphan/config"]


def test_the_removal_is_confirmed_on_puback(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "x", "type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "gone"}]
    client = RecordingClient()

    worker.send_startup_messages(client)
    # not confirmed until the broker acknowledges
    assert worker.confirmed == []

    mid = client.published[0]["mid"]
    worker.on_publish(client, None, mid)

    assert worker.confirmed == ["homeassistant/sensor/gone/config"]


def test_a_puback_for_an_unrelated_message_confirms_nothing(worker):
    # normal startup messages are QoS 0 and also raise on_publish; those must
    # not be mistaken for removal confirmations
    worker.on_publish(RecordingClient(), None, 999)

    assert worker.confirmed == []


def test_a_failed_removal_publish_is_not_tracked_for_confirmation(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "x", "type": "remove_ha_entity", "ha_entity": "sensor", "ha_id": "gone"}]
    client = RecordingClient(rc=4)  # the broker refused the publish

    worker.send_startup_messages(client)

    # nothing pending, so a later PUBACK cannot spuriously confirm it
    assert worker._pending_removals == {}
    assert any("Couldn't send Home Assistant removal" in line for line in worker.logged)


def test_a_removal_row_is_resolved_as_an_action_not_a_literal():
    # guard: if the resolver is ever asked, it must not offer the payload to send
    from easy_mqtt_handler.util.StartupPayload import resolve_startup_payload

    payload, note = resolve_startup_payload(
        {"type": "remove_ha_entity", "payload": "something"})

    assert payload is None
    assert "removal" in note

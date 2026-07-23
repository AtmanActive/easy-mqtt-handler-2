"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_startup_publish.py
*
*  Tests that the worker thread publishes the configured startup messages
*
*  Copyright (C) 2026 AtmanActive
"""
import json

import pytest

from easy_mqtt_handler.util.MQTTSettings import MQTTSettings
from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages
from easy_mqtt_handler.util.MQTTWorkerThread import MQTTWorkerThread


class FakeResult:
    def __init__(self, rc=0):
        self.rc = rc


class FakeClient:
    """Stands in for the paho client, recording what would be published."""

    def __init__(self, rc=0, raises=None):
        self.published = []
        self._rc = rc
        self._raises = raises

    def publish(self, topic, payload, qos=0, retain=False):
        if self._raises is not None:
            raise self._raises
        self.published.append({"topic": topic, "payload": payload, "qos": qos, "retain": retain})
        return FakeResult(self._rc)


@pytest.fixture
def worker(tmp_path):
    # the worker reads settings on construction, so it needs an instance present
    MQTTSettings(str(tmp_path / "settings.json"))
    MQTTStartupMessages(str(tmp_path / "startup.json"))

    thread = MQTTWorkerThread()
    thread.logged = []
    thread.add_log_line.connect(thread.logged.append)
    return thread


def test_nothing_is_published_when_no_messages_are_configured(worker):
    client = FakeClient()

    worker.send_startup_messages(client)

    assert client.published == []
    # and it stays quiet rather than logging about an empty list
    assert worker.logged == []


def test_configured_messages_are_published(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "home/light/set", "payload": "ON", "qos": 1, "retain": True},
        {"topic": "home/fan/set", "payload": "OFF", "qos": 0, "retain": False},
    ]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert client.published == [
        {"topic": "home/light/set", "payload": "ON", "qos": 1, "retain": True},
        {"topic": "home/fan/set", "payload": "OFF", "qos": 0, "retain": False},
    ]


def test_messages_are_published_in_configured_order(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "first"}, {"topic": "second"}, {"topic": "third"},
    ]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert [m["topic"] for m in client.published] == ["first", "second", "third"]


def test_empty_rows_are_skipped(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "", "payload": "never sent"},
        {"topic": "real/topic", "payload": "sent"},
    ]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert [m["topic"] for m in client.published] == ["real/topic"]


def test_a_broker_error_does_not_stop_the_remaining_messages(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "one"}, {"topic": "two"},
    ]
    # rc != 0 means paho refused the publish
    client = FakeClient(rc=4)

    worker.send_startup_messages(client)

    # both were still attempted, and the failures were reported
    assert len(client.published) == 2
    assert any("Couldn't send startup message" in line for line in worker.logged)


def test_an_exception_is_reported_and_does_not_propagate(worker):
    MQTTStartupMessages.get_instance().startup_data = [{"topic": "bad/topic"}]
    client = FakeClient(raises=ValueError("invalid topic"))

    # a broken startup message must not take the whole connection down
    worker.send_startup_messages(client)

    assert any("invalid topic" in line for line in worker.logged)


def test_discovery_is_published_before_its_message(worker):
    MQTTStartupMessages.get_instance().startup_data = [{
        "topic": "desk/temp", "payload": "21", "qos": 0, "retain": True,
        "ha_entity": "sensor", "ha_id": "desk_temp", "ha_name": "Desk Temperature",
    }]
    client = FakeClient()

    worker.send_startup_messages(client)

    # the entity has to exist before the value lands on its state topic
    assert [m["topic"] for m in client.published] == [
        "homeassistant/sensor/desk_temp/config",
        "desk/temp",
    ]
    assert json.loads(client.published[0]["payload"]) == {
        "name": "Desk Temperature",
        "state_topic": "desk/temp",
        "unique_id": "desk_temp",
    }
    assert client.published[0]["retain"] is True


def test_rows_without_an_ha_id_send_only_their_message(worker):
    MQTTStartupMessages.get_instance().startup_data = [{"topic": "plain/topic", "payload": "x"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert [m["topic"] for m in client.published] == ["plain/topic"]


def test_discovery_is_interleaved_per_row(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "a/one", "ha_id": "one"},
        {"topic": "b/two"},
        {"topic": "c/three", "ha_id": "three"},
    ]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert [m["topic"] for m in client.published] == [
        "homeassistant/sensor/one/config", "a/one",
        "b/two",
        "homeassistant/sensor/three/config", "c/three",
    ]


def test_an_unusable_ha_id_is_reported_but_the_message_still_goes_out(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "still/sent", "payload": "x", "ha_id": "not a valid id"},
    ]
    client = FakeClient()

    worker.send_startup_messages(client)

    # the primary job of the row must not be lost to a discovery problem
    assert [m["topic"] for m in client.published] == ["still/sent"]
    assert any("Skipping Home Assistant discovery" in line for line in worker.logged)


def test_a_failed_discovery_publish_does_not_stop_the_message(worker):
    MQTTStartupMessages.get_instance().startup_data = [{"topic": "t", "ha_id": "an_id"}]
    client = FakeClient(rc=4)

    worker.send_startup_messages(client)

    assert [m["topic"] for m in client.published] == ["homeassistant/sensor/an_id/config", "t"]
    assert any("Couldn't send Home Assistant discovery" in line for line in worker.logged)


class ConnectingClient(FakeClient):
    """A fake client that also records subscriptions, as on_connect needs."""

    def __init__(self):
        super().__init__()
        self.subscribed = []

    def subscribe(self, topic):
        self.subscribed.append(topic)


def test_on_connect_publishes_after_subscribing(worker, tmp_path):
    # this is the wiring that makes the feature actually happen at runtime
    MQTTSettings.get_instance().refresh_settings({
        "hostname": "broker.example.org", "port": "1883", "topic": "base",
    })
    MQTTStartupMessages.get_instance().startup_data = [{"topic": "startup/topic", "payload": "go"}]
    client = ConnectingClient()

    worker.on_connect(client, None, None, 0)

    assert client.subscribed == ["base/#"]
    assert [m["topic"] for m in client.published] == ["startup/topic"]

    # the messages go out before the app reports that it is listening
    joined = "\n".join(worker.logged)
    assert joined.index("startup message") < joined.index("Listening to Broker.")


def test_on_connect_publishes_nothing_when_the_list_is_empty(worker):
    MQTTSettings.get_instance().refresh_settings({
        "hostname": "broker.example.org", "port": "1883", "topic": "base",
    })
    client = ConnectingClient()

    worker.on_connect(client, None, None, 0)

    # unchanged behaviour: subscribe, then listen
    assert client.subscribed == ["base/#"]
    assert client.published == []
    assert "Listening to Broker." in worker.logged


def test_on_connect_does_not_publish_when_the_connection_failed(worker):
    MQTTStartupMessages.get_instance().startup_data = [{"topic": "startup/topic"}]
    client = ConnectingClient()

    # a non-zero result code means the broker rejected us
    worker.on_connect(client, None, None, 5)

    assert client.published == []


def test_activity_is_logged(worker):
    MQTTStartupMessages.get_instance().startup_data = [{"topic": "t", "payload": "p"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    joined = "\n".join(worker.logged)
    assert "1 startup message" in joined
    assert "All startup messages sent." in joined

"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_startup_publish_types.py
*
*  Tests that the worker resolves command and built-in rows before publishing,
*  and skips a row that cannot produce a value
*
*  Copyright (C) 2026 AtmanActive
"""
import socket
import stat
import sys

import pytest

from easy_mqtt_handler.util.MQTTSettings import MQTTSettings
from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages
from easy_mqtt_handler.util.MQTTWorkerThread import MQTTWorkerThread

from tests.test_startup_publish import FakeClient


@pytest.fixture
def worker(tmp_path, monkeypatch):
    MQTTSettings(str(tmp_path / "settings.json"))
    MQTTStartupMessages(str(tmp_path / "startup.json"))
    # a command with a relative path is looked for beside the configuration, so
    # point that at the temporary directory the tests write scripts into
    import easy_mqtt_handler.util.Tools as tools
    monkeypatch.setattr(tools.Utils, "get_config_path", staticmethod(lambda: str(tmp_path) + "/"))

    thread = MQTTWorkerThread()
    thread.logged = []
    thread.add_log_line.connect(thread.logged.append)
    return thread


def write_script(directory, name, output):
    if sys.platform.startswith("win"):
        path = directory / f"{name}.bat"
        path.write_text(f"@echo off\r\n@echo {output}\r\n", encoding="ascii")
    else:
        path = directory / name
        path.write_text(f'#!/bin/sh\necho "{output}"\n', encoding="ascii")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_a_literal_row_publishes_its_payload(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "t", "type": "literal", "payload": "ON"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert [(m["topic"], m["payload"]) for m in client.published] == [("t", "ON")]


def test_a_command_row_publishes_the_commands_output(worker, tmp_path):
    write_script(tmp_path, "emit", "value-from-command")
    payload = "emit.bat" if sys.platform.startswith("win") else "emit"
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "cmd/topic", "type": "command", "payload": payload}]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert [(m["topic"], m["payload"]) for m in client.published] == [
        ("cmd/topic", "value-from-command")]


def test_a_missing_command_is_skipped_and_logged(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "cmd/topic", "type": "command", "payload": "no-such-program"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert client.published == []
    assert any("Skipping startup message" in line and "was not found" in line
               for line in worker.logged)


def test_a_built_in_row_publishes_the_computed_value(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "host/topic", "type": "built-in", "payload": "networking: hostname"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert [(m["topic"], m["payload"]) for m in client.published] == [
        ("host/topic", socket.gethostname())]


def test_an_environment_row_publishes_the_variables_value(worker, monkeypatch):
    monkeypatch.setenv("EMH_PUBLISH_VAR", "from-environment")
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "env/topic", "type": "environment", "payload": "EMH_PUBLISH_VAR"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert [(m["topic"], m["payload"]) for m in client.published] == [
        ("env/topic", "from-environment")]


def test_an_unset_environment_row_is_skipped_and_logged(worker, monkeypatch):
    monkeypatch.delenv("EMH_PUBLISH_VAR", raising=False)
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "env/topic", "type": "environment", "payload": "EMH_PUBLISH_VAR"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert client.published == []
    assert any("Skipping startup message" in line and "is not set" in line
               for line in worker.logged)


def test_an_unavailable_built_in_is_skipped(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "x", "type": "built-in", "payload": "no such built-in"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert client.published == []
    assert any("Skipping startup message" in line for line in worker.logged)


def test_a_disk_row_publishes_a_size(worker, monkeypatch, tmp_path):
    import shutil

    from easy_mqtt_handler.util import StartupPayload as sp
    monkeypatch.setattr(sp, "discover_disks", lambda: [("TestDisk", str(tmp_path))])

    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "disk/free", "type": "built-in", "payload": "disks: disk 1 free size B"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    expected = str(shutil.disk_usage(str(tmp_path)).free)
    assert [(m["topic"], m["payload"]) for m in client.published] == [("disk/free", expected)]


def test_a_missing_disk_row_is_skipped_and_logged(worker, monkeypatch):
    from easy_mqtt_handler.util import StartupPayload as sp
    monkeypatch.setattr(sp, "discover_disks", lambda: [("only", "/only")])

    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "disk/x", "type": "built-in", "payload": "disks: disk 4 total size B"}]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert client.published == []
    assert any("Skipping startup message" in line and "disk 4 is not connected" in line
               for line in worker.logged)


def test_a_skipped_row_does_not_stop_the_others(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "first", "type": "command", "payload": "missing"},
        {"topic": "second", "type": "literal", "payload": "still-sent"},
    ]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert [(m["topic"], m["payload"]) for m in client.published] == [("second", "still-sent")]


def test_a_skipped_row_does_not_announce_a_home_assistant_entity(worker):
    # no value to report, so the entity should not be created either
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "x", "type": "command", "payload": "missing",
         "ha_id": "should_not_appear"},
    ]
    client = FakeClient()

    worker.send_startup_messages(client)

    assert client.published == []


def test_a_built_in_row_still_announces_its_entity(worker):
    MQTTStartupMessages.get_instance().startup_data = [
        {"topic": "host/topic", "type": "built-in", "payload": "networking: hostname",
         "ha_id": "the_hostname"},
    ]
    client = FakeClient()

    worker.send_startup_messages(client)

    topics = [m["topic"] for m in client.published]
    assert "homeassistant/sensor/the_hostname/config" in topics
    # discovery is announced before the value it describes
    assert topics.index("homeassistant/sensor/the_hostname/config") < topics.index("host/topic")

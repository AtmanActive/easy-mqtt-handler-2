"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_startup_messages.py
*
*  Tests for the "Send on Startup" message store and its publish filtering
*
*  Copyright (C) 2026 AtmanActive
"""
import json

import pytest

from easy_mqtt_handler.util.MQTTStartupMessages import MQTTStartupMessages
from easy_mqtt_handler.util.Tools import Utils


def test_missing_file_yields_no_messages(tmp_path):
    messages = MQTTStartupMessages(str(tmp_path / "absent.json"))

    assert messages.startup_data == []
    assert messages.publishable_messages() == []


def test_messages_read_back_from_disk(tmp_path):
    startup_file = tmp_path / "startup.json"
    startup_file.write_text(json.dumps([
        {"topic": "home/light/set", "payload": "ON", "qos": 1, "retain": True},
    ]), encoding="utf-8")

    messages = MQTTStartupMessages(str(startup_file))

    assert messages.startup_data[0]["topic"] == "home/light/set"

    published = messages.publishable_messages()
    assert len(published) == 1
    # only assert the publishing fields, so adding further optional ones later
    # does not break this test
    assert {key: published[0][key] for key in ("topic", "payload", "qos", "retain")} == {
        "topic": "home/light/set", "payload": "ON", "qos": 1, "retain": True,
    }


def test_round_trip_through_save(tmp_path):
    startup_file = tmp_path / "startup.json"
    messages = MQTTStartupMessages(str(startup_file))
    messages.startup_data = [{"topic": "a/b", "payload": "1", "qos": 2, "retain": False}]

    assert messages.save_startup_data() is True
    assert json.loads(startup_file.read_text(encoding="utf-8")) == [
        {"topic": "a/b", "payload": "1", "qos": 2, "retain": False},
    ]


def test_rows_without_a_topic_are_not_published(tmp_path):
    # clicking "Add Message" creates an empty row; it must never be sent
    messages = MQTTStartupMessages(str(tmp_path / "startup.json"))
    messages.startup_data = [
        {"topic": "", "payload": "ignored", "qos": 0, "retain": False},
        {"topic": "   ", "payload": "also ignored", "qos": 0, "retain": False},
        {"topic": "kept/topic", "payload": "sent", "qos": 0, "retain": False},
    ]

    published = messages.publishable_messages()

    assert len(published) == 1
    assert published[0]["topic"] == "kept/topic"


def test_topics_are_stripped(tmp_path):
    messages = MQTTStartupMessages(str(tmp_path / "startup.json"))
    messages.startup_data = [{"topic": "  home/light/set  ", "payload": "ON"}]

    assert messages.publishable_messages()[0]["topic"] == "home/light/set"


def test_absent_payload_qos_and_retain_get_defaults(tmp_path):
    messages = MQTTStartupMessages(str(tmp_path / "startup.json"))
    messages.startup_data = [{"topic": "only/topic"}]

    published = messages.publishable_messages()
    assert len(published) == 1
    assert {key: published[0][key] for key in ("topic", "payload", "qos", "retain")} == {
        "topic": "only/topic", "payload": "", "qos": 0, "retain": False,
    }


@pytest.mark.parametrize("bad_qos", ["", "x", None, 5, -1, 3])
def test_invalid_qos_falls_back_to_zero(tmp_path, bad_qos):
    # paho raises on an out-of-range QoS, which would abort the whole connect
    messages = MQTTStartupMessages(str(tmp_path / "startup.json"))
    messages.startup_data = [{"topic": "t", "payload": "p", "qos": bad_qos}]

    assert messages.publishable_messages()[0]["qos"] == 0


def test_qos_given_as_text_is_accepted(tmp_path):
    messages = MQTTStartupMessages(str(tmp_path / "startup.json"))
    messages.startup_data = [{"topic": "t", "payload": "p", "qos": "2"}]

    assert messages.publishable_messages()[0]["qos"] == 2


def test_non_list_file_contents_are_ignored(tmp_path):
    # a hand-edited file holding an object rather than a list must not crash
    startup_file = tmp_path / "startup.json"
    startup_file.write_text(json.dumps({"topic": "not/a/list"}), encoding="utf-8")

    assert MQTTStartupMessages(str(startup_file)).startup_data == []


def test_malformed_json_is_ignored(tmp_path):
    startup_file = tmp_path / "startup.json"
    startup_file.write_text("{ this is not json", encoding="utf-8")

    assert MQTTStartupMessages(str(startup_file)).startup_data == []


def test_file_with_a_utf8_bom_still_loads(tmp_path):
    startup_file = tmp_path / "startup.json"
    startup_file.write_text(json.dumps([{"topic": "bom/topic"}]), encoding="utf-8-sig")

    assert MQTTStartupMessages(str(startup_file)).startup_data[0]["topic"] == "bom/topic"


def test_stray_non_dict_entries_are_skipped(tmp_path):
    messages = MQTTStartupMessages(str(tmp_path / "startup.json"))
    messages.startup_data = ["nonsense", 42, {"topic": "good/topic"}]

    assert [m["topic"] for m in messages.publishable_messages()] == ["good/topic"]


def test_is_a_singleton(tmp_path):
    MQTTStartupMessages(str(tmp_path / "startup.json"))

    with pytest.raises(Exception, match="Singleton"):
        MQTTStartupMessages(str(tmp_path / "other.json"))


def test_startup_file_lives_beside_the_other_config_files():
    startup = Utils.get_startup_file()

    assert startup.endswith(Utils.DEFAULT_STARTUP_FILENAME)
    # it is a separate file, not shared with the payload handlers
    assert startup != Utils.get_payload_file()
    assert startup != Utils.get_settings_file()

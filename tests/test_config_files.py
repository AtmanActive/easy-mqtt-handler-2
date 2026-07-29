"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_config_files.py
*
*  Tests for the JSON-backed settings and payload stores
*
*  Copyright (C) 2023 A. Zeil
"""
import json

import pytest

from easy_mqtt_handler.util.MQTTPayloads import MQTTPayloads
from easy_mqtt_handler.util.MQTTSettings import MQTTSettings


def test_settings_read_back_from_disk(tmp_path):
    settings_file = tmp_path / "mqtt.json"
    settings_file.write_text(json.dumps({
        "hostname": "broker.example.org",
        "port": "8883",
        "username": "someone",
        "topic": "home/#",
        "enable_ssl": True,
    }), encoding="utf-8")

    settings = MQTTSettings(str(settings_file))

    assert settings.hostname == "broker.example.org"
    assert settings.port == "8883"
    assert settings.username == "someone"
    assert settings.topic == "home/#"
    assert settings.enable_ssl is True


def test_settings_absent_keys_are_none(tmp_path):
    settings_file = tmp_path / "mqtt.json"
    settings_file.write_text(json.dumps({"hostname": "broker.example.org"}), encoding="utf-8")

    settings = MQTTSettings(str(settings_file))

    assert settings.password is None
    assert settings.server_certificate_file is None


def test_theme_defaults_to_system_when_absent(tmp_path):
    # every settings file written before this option has no theme key
    settings_file = tmp_path / "mqtt.json"
    settings_file.write_text(json.dumps({"hostname": "broker.example.org"}), encoding="utf-8")

    assert MQTTSettings(str(settings_file)).theme == "system"


@pytest.mark.parametrize("choice", ["system", "light", "dark"])
def test_theme_reads_back_a_valid_choice(tmp_path, choice):
    settings_file = tmp_path / "mqtt.json"
    settings_file.write_text(json.dumps({"theme": choice}), encoding="utf-8")

    assert MQTTSettings(str(settings_file)).theme == choice


def test_an_unfamiliar_theme_value_is_treated_as_system(tmp_path):
    # a hand-edited file could hold anything; it must not break theming
    settings_file = tmp_path / "mqtt.json"
    settings_file.write_text(json.dumps({"theme": "chartreuse"}), encoding="utf-8")

    assert MQTTSettings(str(settings_file)).theme == "system"


def test_theme_round_trips_through_save(tmp_path):
    settings_file = tmp_path / "mqtt.json"
    settings = MQTTSettings(str(settings_file))
    settings.refresh_settings({"hostname": "localhost", "theme": "dark"})

    assert settings.save_settings() is True
    assert json.loads(settings_file.read_text(encoding="utf-8"))["theme"] == "dark"


def test_font_size_defaults_to_default_when_absent(tmp_path):
    settings_file = tmp_path / "mqtt.json"
    settings_file.write_text(json.dumps({"hostname": "broker.example.org"}), encoding="utf-8")

    assert MQTTSettings(str(settings_file)).font_size == "default"


@pytest.mark.parametrize("choice", ["xxsmall", "xsmall", "small", "default", "large", "xlarge", "xxlarge"])
def test_font_size_reads_back_a_valid_choice(tmp_path, choice):
    settings_file = tmp_path / "mqtt.json"
    settings_file.write_text(json.dumps({"font_size": choice}), encoding="utf-8")

    assert MQTTSettings(str(settings_file)).font_size == choice


def test_an_unfamiliar_font_size_is_treated_as_default(tmp_path):
    settings_file = tmp_path / "mqtt.json"
    settings_file.write_text(json.dumps({"font_size": "enormous"}), encoding="utf-8")

    assert MQTTSettings(str(settings_file)).font_size == "default"


def test_font_size_round_trips_through_save(tmp_path):
    settings_file = tmp_path / "mqtt.json"
    settings = MQTTSettings(str(settings_file))
    settings.refresh_settings({"hostname": "localhost", "font_size": "large"})

    assert settings.save_settings() is True
    assert json.loads(settings_file.read_text(encoding="utf-8"))["font_size"] == "large"


def test_settings_ssl_flags_default_to_false_on_missing_file(tmp_path):
    # a fresh install has no settings file at all
    settings = MQTTSettings(str(tmp_path / "not-created-yet.json"))

    assert settings.enable_ssl is False
    assert settings.enable_client_ssl_auth is False
    assert settings.allow_insecure_ssl is False


def test_settings_round_trip_through_save(tmp_path):
    settings_file = tmp_path / "mqtt.json"
    settings = MQTTSettings(str(settings_file))
    settings.refresh_settings({"hostname": "localhost", "port": "1883"})

    assert settings.save_settings() is True
    assert json.loads(settings_file.read_text(encoding="utf-8")) == {
        "hostname": "localhost",
        "port": "1883",
    }


def test_settings_load_from_a_file_with_a_utf8_bom(tmp_path):
    # portable mode puts this file next to the executable, where users edit it;
    # several Windows editors prepend a BOM when saving
    settings_file = tmp_path / "mqtt.json"
    settings_file.write_text(
        json.dumps({"hostname": "broker.example.org"}), encoding="utf-8-sig")

    assert MQTTSettings(str(settings_file)).hostname == "broker.example.org"


def test_settings_round_trip_preserves_non_ascii(tmp_path):
    settings_file = tmp_path / "mqtt.json"
    settings = MQTTSettings(str(settings_file))
    settings.refresh_settings({"topic": "haus/wohnzimmer/temperatur/°C"})

    assert settings.save_settings() is True
    assert json.loads(settings_file.read_text(encoding="utf-8"))["topic"] \
        == "haus/wohnzimmer/temperatur/°C"


def test_payloads_load_from_a_file_with_a_utf8_bom(tmp_path):
    payload_file = tmp_path / "payloads.json"
    payload_file.write_text(
        json.dumps({"home/switch": {"command": "echo on"}}), encoding="utf-8-sig")

    assert MQTTPayloads(str(payload_file)).payload_data["home/switch"]["command"] == "echo on"


def test_settings_is_a_singleton(tmp_path):
    MQTTSettings(str(tmp_path / "mqtt.json"))

    with pytest.raises(Exception, match="Singleton"):
        MQTTSettings(str(tmp_path / "other.json"))


def test_payloads_read_back_from_disk(tmp_path):
    payload_file = tmp_path / "payloads.json"
    payload_file.write_text(json.dumps({
        "home/switch": {"payload": "ON", "command": "echo on"},
    }), encoding="utf-8")

    payloads = MQTTPayloads(str(payload_file))

    assert payloads.payload_data["home/switch"]["command"] == "echo on"


def test_payloads_round_trip_through_save(tmp_path):
    payload_file = tmp_path / "payloads.json"
    payloads = MQTTPayloads(str(payload_file))
    payloads.payload_data = {"home/light": {"payload": "OFF", "command": "echo off"}}

    assert payloads.save_payload_data() is True
    assert json.loads(payload_file.read_text(encoding="utf-8")) == {
        "home/light": {"payload": "OFF", "command": "echo off"},
    }


def test_payloads_is_a_singleton(tmp_path):
    MQTTPayloads(str(tmp_path / "payloads.json"))

    with pytest.raises(Exception, match="Singleton"):
        MQTTPayloads(str(tmp_path / "other.json"))

"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_startup_payload.py
*
*  Tests for resolving a "Send on Startup" row into the payload it publishes:
*  literal text, the output of a command, or a built-in value
*
*  Copyright (C) 2026 AtmanActive
"""
import datetime
import os
import re
import stat
import struct
import sys

import pytest

from easy_mqtt_handler.util import StartupPayload as sp


# --- literal ----------------------------------------------------------------

def test_a_literal_is_sent_verbatim():
    assert sp.resolve_startup_payload({"type": "literal", "payload": "ON"}) == ("ON", None)


def test_a_row_without_a_type_is_treated_as_literal():
    # this is every configuration written before the feature existed
    assert sp.resolve_startup_payload({"payload": "hello"}) == ("hello", None)


def test_an_unknown_type_is_treated_as_literal():
    assert sp.resolve_startup_payload({"type": "nonsense", "payload": "x"}) == ("x", None)


# --- built-in ---------------------------------------------------------------

def test_the_offered_built_ins_match_the_registry():
    keys = sp.builtin_keys()

    # the four that were asked for by name must all be there
    for expected in ("time: now unixtime", "time: last boot full ISO",
                     "networking: hostname", "networking: 1st IP address"):
        assert expected in keys
    # and there are no duplicates
    assert len(keys) == len(set(keys))
    # every registered built-in is offered
    assert set(keys) == set(sp.BUILTIN_RESOLVERS)


def test_the_built_ins_are_offered_in_alphabetical_order():
    # the list only grows, so it must stay sorted for the drop down to be scannable
    keys = sp.builtin_keys()

    assert keys == sorted(keys)


# the environment-describing values chosen for this release
CHOSEN_SYSTEM_BUILTINS = [
    "system: operating system name",
    "system: operating system release",
    "system: operating system full version",
    "system: operating system platform summary",
    "system: machine architecture",
    "system: machine word size",
    "system: machine CPU count",
    "system: logged in username",
    "time: timezone name",
    "time: UTC offset",
    "time: uptime duration",
]


@pytest.mark.parametrize("key", CHOSEN_SYSTEM_BUILTINS)
def test_the_chosen_system_built_ins_are_registered(key):
    assert key in sp.builtin_keys()


@pytest.mark.parametrize("key", CHOSEN_SYSTEM_BUILTINS)
def test_each_chosen_built_in_resolves_or_skips_cleanly(key):
    value, note = sp.resolve_startup_payload({"type": "built-in", "payload": key})

    assert (value is None) != (note is None), key


def test_no_built_in_shells_out(monkeypatch):
    """A built-in must never run an external program; that is what "command" is
    for. platform.architecture(), for one, would run "file" on Unix."""
    import subprocess

    def forbidden(*_a, **_k):
        raise AssertionError("a built-in spawned a subprocess")

    monkeypatch.setattr(subprocess, "Popen", forbidden)

    for key in sp.builtin_keys():
        sp.resolve_startup_payload({"type": "built-in", "payload": key})


def test_word_size_matches_the_interpreter():
    value, _note = sp.resolve_startup_payload(
        {"type": "built-in", "payload": "system: machine word size"})

    assert value == f"{struct.calcsize('P') * 8}bit"


def test_operating_system_name_is_reported():
    import platform

    value, _note = sp.resolve_startup_payload(
        {"type": "built-in", "payload": "system: operating system name"})

    assert value == platform.system()


def test_cpu_count_is_a_positive_integer():
    value, note = sp.resolve_startup_payload(
        {"type": "built-in", "payload": "system: machine CPU count"})

    # os.cpu_count() can in principle be None, in which case it skips cleanly
    if value is not None:
        assert value.isdigit() and int(value) >= 1
    else:
        assert "not available" in note


def test_utc_offset_is_well_formed():
    value, _note = sp.resolve_startup_payload(
        {"type": "built-in", "payload": "time: UTC offset"})

    assert re.match(r"^[+-]\d{2}:\d{2}$", value)


def test_uptime_duration_is_present_when_boot_is_known():
    boot_value, _b = sp.resolve_startup_payload(
        {"type": "built-in", "payload": "time: last boot full ISO"})
    uptime_value, uptime_note = sp.resolve_startup_payload(
        {"type": "built-in", "payload": "time: uptime duration"})

    if boot_value is not None:
        # a machine whose boot time is known also has an uptime
        assert uptime_value is not None
        # H:MM:SS, optionally prefixed with a day count
        assert re.search(r"\d+:\d{2}:\d{2}$", uptime_value)
    else:
        assert uptime_value is None


def test_username_matches_getpass():
    import getpass

    value, _note = sp.resolve_startup_payload(
        {"type": "built-in", "payload": "system: logged in username"})

    assert value == getpass.getuser()


def test_every_built_in_resolves_or_skips_cleanly():
    # none may raise; each returns either a value or a skip reason
    for key in sp.builtin_keys():
        value, note = sp.resolve_startup_payload({"type": "built-in", "payload": key})
        assert (value is None) != (note is None), key


def test_unix_time_is_an_integer_string():
    value, _note = sp.resolve_startup_payload({"type": "built-in", "payload": "time: now unixtime"})

    assert value.isdigit()


def test_full_iso_round_trips():
    value, _note = sp.resolve_startup_payload({"type": "built-in", "payload": "time: now full ISO"})

    # must be parseable back into a datetime
    datetime.datetime.fromisoformat(value)


def test_date_iso_looks_like_a_date():
    value, _note = sp.resolve_startup_payload({"type": "built-in", "payload": "time: now date ISO"})

    assert re.match(r"^\d{4}-\d{2}-\d{2}$", value)


def test_time_iso_looks_like_a_time():
    value, _note = sp.resolve_startup_payload({"type": "built-in", "payload": "time: now time ISO"})

    assert re.match(r"^\d{2}:\d{2}:\d{2}$", value)


def test_boot_is_earlier_than_launch_which_is_not_after_now():
    boot = sp.boot_datetime()
    if boot is None:
        pytest.skip("boot time is not available on this machine")

    assert boot <= sp.LAUNCH_DATETIME <= datetime.datetime.now()


def test_hostname_is_reported():
    import socket

    value, _note = sp.resolve_startup_payload({"type": "built-in", "payload": "networking: hostname"})

    assert value == socket.gethostname()


def test_first_ip_address_is_present():
    value, note = sp.resolve_startup_payload({"type": "built-in", "payload": "networking: 1st IP address"})

    # a machine running the tests has at least one address, even if loopback
    assert value is not None, note
    assert re.match(r"^\d+\.\d+\.\d+\.\d+$", value)


def test_a_missing_ip_slot_is_skipped_with_a_reason():
    # asking for an address the machine does not have must skip, not crash
    addresses = sp.local_ipv4_addresses()
    key = "networking: 3rd IP address"
    value, note = sp.resolve_startup_payload({"type": "built-in", "payload": key})

    if len(addresses) >= 3:
        assert value is not None
    else:
        assert value is None
        assert "not available" in note


def test_an_unknown_built_in_is_skipped_with_a_reason():
    value, note = sp.resolve_startup_payload({"type": "built-in", "payload": "does not exist"})

    assert value is None
    assert "unknown built-in" in note


def test_ip_list_prefers_non_loopback():
    # loopback is only ever returned when it is all there is
    addresses = sp.local_ipv4_addresses()
    if any(not a.startswith("127.") for a in addresses):
        assert not addresses[0].startswith("127.")


# --- command ----------------------------------------------------------------

def _write_script(directory, name, body, output=""):
    """Write a tiny runnable script for the current platform."""
    if sys.platform.startswith("win"):
        path = directory / f"{name}.bat"
        lines = ["@echo off"]
        if output:
            lines.append(f"@echo {output}")
        lines.append(body)
        path.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")
    else:
        path = directory / name
        lines = ["#!/bin/sh"]
        if output:
            lines.append(f'echo "{output}"')
        lines.append(body)
        path.write_text("\n".join(lines) + "\n", encoding="ascii")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_a_command_sends_its_output(tmp_path):
    script = _write_script(tmp_path, "emit", "", output="the-output")

    value, note = sp.resolve_startup_payload(
        {"type": "command", "payload": str(script)}, [str(tmp_path)])

    assert value == "the-output"
    assert note is None


def test_a_relative_command_is_found_in_the_search_directory(tmp_path):
    script = _write_script(tmp_path, "emit", "", output="relative-output")

    value, _note = sp.resolve_startup_payload(
        {"type": "command", "payload": script.name}, [str(tmp_path)])

    assert value == "relative-output"


def test_a_missing_command_is_skipped_with_a_reason(tmp_path):
    value, note = sp.resolve_startup_payload(
        {"type": "command", "payload": "not-here"}, [str(tmp_path)])

    assert value is None
    assert "was not found" in note


def test_a_command_with_no_output_is_skipped(tmp_path):
    script = _write_script(tmp_path, "silent", "")

    value, note = sp.resolve_startup_payload(
        {"type": "command", "payload": str(script)}, [str(tmp_path)])

    assert value is None
    assert "no output" in note


def test_an_empty_command_path_is_skipped(tmp_path):
    value, note = sp.resolve_startup_payload({"type": "command", "payload": "   "}, [str(tmp_path)])

    assert value is None
    assert "no command" in note


def test_command_output_is_stripped(tmp_path):
    # trailing newline from echo must not travel with the payload
    script = _write_script(tmp_path, "emit", "", output="trimmed")

    value, _note = sp.resolve_startup_payload(
        {"type": "command", "payload": str(script)}, [str(tmp_path)])

    assert value == value.strip()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="relies on a POSIX non-zero exit")
def test_a_nonzero_exit_with_no_output_mentions_the_code(tmp_path):
    script = _write_script(tmp_path, "fail", "exit 3")

    value, note = sp.resolve_startup_payload(
        {"type": "command", "payload": str(script)}, [str(tmp_path)])

    assert value is None
    assert "exit code 3" in note


def test_an_absolute_directory_is_not_treated_as_a_command(tmp_path):
    # a directory is not a program, so it must be reported as not found
    value, note = sp.resolve_startup_payload(
        {"type": "command", "payload": str(tmp_path)}, [str(tmp_path)])

    assert value is None
    assert "was not found" in note


# --- environment ------------------------------------------------------------

def test_environment_is_one_of_the_offered_types():
    assert "environment" in sp.PAYLOAD_TYPES


def test_a_set_environment_variable_is_sent(monkeypatch):
    monkeypatch.setenv("EMH_TEST_VAR", "the-value")

    assert sp.resolve_startup_payload(
        {"type": "environment", "payload": "EMH_TEST_VAR"}) == ("the-value", None)


def test_an_unset_environment_variable_is_skipped_with_a_reason(monkeypatch):
    monkeypatch.delenv("EMH_TEST_VAR", raising=False)

    value, note = sp.resolve_startup_payload(
        {"type": "environment", "payload": "EMH_TEST_VAR"})

    assert value is None
    assert "is not set" in note


def test_an_empty_environment_variable_is_skipped(monkeypatch):
    # set but empty, so there is nothing worth publishing
    monkeypatch.setenv("EMH_TEST_VAR", "")

    value, note = sp.resolve_startup_payload(
        {"type": "environment", "payload": "EMH_TEST_VAR"})

    assert value is None
    assert "is empty" in note


def test_an_empty_environment_name_is_skipped():
    value, note = sp.resolve_startup_payload({"type": "environment", "payload": "  "})

    assert value is None
    assert "no environment variable" in note


def test_the_environment_variable_name_is_stripped(monkeypatch):
    monkeypatch.setenv("EMH_TEST_VAR", "trimmed-name")

    value, _note = sp.resolve_startup_payload(
        {"type": "environment", "payload": "  EMH_TEST_VAR  "})

    assert value == "trimmed-name"


def test_an_environment_value_is_sent_verbatim_including_spaces(monkeypatch):
    monkeypatch.setenv("EMH_TEST_VAR", "  keep inner  ")

    value, _note = sp.resolve_startup_payload(
        {"type": "environment", "payload": "EMH_TEST_VAR"})

    # the value itself is not trimmed, only the variable name is
    assert value == "  keep inner  "

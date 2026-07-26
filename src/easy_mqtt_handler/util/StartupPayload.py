"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  util/StartupPayload.py
*
*  Works out what a "Send on Startup" row actually publishes. A row is one of
*  three types:
*
*    literal   - the Payload is sent verbatim, the original behaviour
*    command   - the Payload is a path to a program; it is run and its output
*                is sent
*    built-in  - the Payload names a value this program can produce itself,
*                such as the current time or the machine's IP address
*
*  Resolution happens when the messages are sent, not when they are saved,
*  because these values change from one run to the next.
*
*  Copyright (C) 2026 AtmanActive
"""
import datetime
import getpass
import os
import platform
import socket
import struct
import subprocess
import sys
import time

# the choices offered in the Type column
TYPE_LITERAL = "literal"
TYPE_COMMAND = "command"
TYPE_BUILTIN = "built-in"
TYPE_ENVIRONMENT = "environment"
PAYLOAD_TYPES = (TYPE_LITERAL, TYPE_COMMAND, TYPE_BUILTIN, TYPE_ENVIRONMENT)
DEFAULT_TYPE = TYPE_LITERAL

# a command that has not produced anything within this long is abandoned, so a
# hung program cannot stall the connection for good
COMMAND_TIMEOUT_SECONDS = 10

# fixed at import, which is close enough to when the program was launched to
# serve as "last launch"
LAUNCH_DATETIME = datetime.datetime.now()


# --- time helpers -----------------------------------------------------------

def _format_moment(when, layout):
    """Render a datetime in one of the four offered layouts."""
    if layout == "unixtime":
        return str(int(when.timestamp()))
    if layout == "full ISO":
        return when.isoformat(timespec="seconds")
    if layout == "date ISO":
        return when.date().isoformat()
    if layout == "time ISO":
        return when.time().isoformat(timespec="seconds")
    return None


def _now():
    return datetime.datetime.now()


def _last_launch():
    return LAUNCH_DATETIME


def boot_datetime():
    """When the operating system last booted, as a local datetime, or None.

    Read without running any external program, so it stays a genuine built-in:
    Linux exposes the exact moment in /proc/stat, and every platform offers a
    clock counting from boot that the current time can be measured against.
    """
    # Linux records the boot instant directly, which is the most accurate source
    try:
        with open("/proc/stat", "r", encoding="ascii") as stat:
            for line in stat:
                if line.startswith("btime "):
                    return datetime.datetime.fromtimestamp(int(line.split()[1]))
    except (OSError, ValueError):
        pass

    uptime_seconds = _uptime_seconds()
    if uptime_seconds is None:
        return None
    return datetime.datetime.now() - datetime.timedelta(seconds=uptime_seconds)


def _uptime_seconds():
    """Seconds since boot, from whichever clock the platform provides."""
    if sys.platform.startswith("win"):
        try:
            import ctypes

            # milliseconds since boot, unaffected by clock changes
            return ctypes.windll.kernel32.GetTickCount64() / 1000.0
        except (OSError, AttributeError, ValueError):
            return None

    # CLOCK_BOOTTIME (Linux) counts through suspend; CLOCK_UPTIME_RAW is the
    # macOS equivalent. Fall back to the plain monotonic clock elsewhere.
    for clock_name in ("CLOCK_BOOTTIME", "CLOCK_UPTIME_RAW", "CLOCK_MONOTONIC"):
        clock = getattr(time, clock_name, None)
        if clock is None:
            continue
        try:
            return time.clock_gettime(clock)
        except (OSError, AttributeError, ValueError):
            continue
    return None


# --- networking helpers -----------------------------------------------------

def local_ipv4_addresses():
    """The machine's IPv4 addresses, most externally useful first.

    Loopback is dropped unless it is the only thing available, so "1st IP
    address" is the address other machines would actually reach.
    """
    addresses = []

    # the address the OS would use to reach the outside world. connecting a UDP
    # socket does not send anything, it just picks a route.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        addresses.append(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()

    # anything else the hostname resolves to
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in addresses:
                addresses.append(address)
    except OSError:
        pass

    external = [a for a in addresses if not a.startswith("127.")]
    return external or addresses


def _nth_ipv4(index):
    addresses = local_ipv4_addresses()
    return addresses[index] if index < len(addresses) else None


def _hostname():
    return socket.gethostname()


# --- system helpers ---------------------------------------------------------

def _machine_word_size():
    """The pointer size as a string like "64bit".

    Deliberately derived from the interpreter rather than from
    platform.architecture(), which shells out to the "file" command on
    Unix and so would not be a genuine built-in.
    """
    return f"{struct.calcsize('P') * 8}bit"


def _cpu_count():
    count = os.cpu_count()
    return str(count) if count else None


def _timezone_name():
    return datetime.datetime.now().astimezone().tzname()


def _utc_offset():
    """The local offset from UTC, like "+02:00"."""
    offset = datetime.datetime.now().astimezone().utcoffset()
    if offset is None:
        return None
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    hours, remainder = divmod(abs(total_seconds), 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}"


def _uptime_duration():
    """How long the machine has been up, like "1 day, 2:03:04"."""
    boot = boot_datetime()
    if boot is None:
        return None
    elapsed = datetime.datetime.now() - boot
    # whole seconds only; the microseconds are noise here
    return str(datetime.timedelta(seconds=int(elapsed.total_seconds())))


# --- the registry -----------------------------------------------------------

def _build_registry():
    """Assemble the ordered map of built-in name to the function producing it."""
    registry = {}

    sources = (("now", _now), ("last launch", _last_launch), ("last boot", boot_datetime))
    layouts = ("unixtime", "full ISO", "date ISO", "time ISO")

    for source_label, source in sources:
        for layout in layouts:
            key = f"time: {source_label} {layout}"
            # bind the loop variables per iteration
            registry[key] = (lambda src=source, lay=layout:
                             _format_moment(src(), lay) if src() is not None else None)

    registry["networking: hostname"] = _hostname
    registry["networking: 1st IP address"] = lambda: _nth_ipv4(0)
    registry["networking: 2nd IP address"] = lambda: _nth_ipv4(1)
    registry["networking: 3rd IP address"] = lambda: _nth_ipv4(2)

    # platform.system/release/version/machine read uname and environment, not
    # an external program, so they stay genuine built-ins
    registry["system: operating system name"] = platform.system
    registry["system: operating system release"] = platform.release
    registry["system: operating system full version"] = platform.version
    registry["system: operating system platform summary"] = platform.platform
    registry["system: machine architecture"] = platform.machine
    registry["system: machine word size"] = _machine_word_size
    registry["system: machine CPU count"] = _cpu_count
    registry["system: logged in username"] = getpass.getuser

    registry["time: timezone name"] = _timezone_name
    registry["time: UTC offset"] = _utc_offset
    registry["time: uptime duration"] = _uptime_duration

    return registry


BUILTIN_RESOLVERS = _build_registry()


def builtin_keys():
    """Every built-in value name, sorted for presentation.

    The list only grows as more built-ins are added, so it is kept in
    alphabetical order rather than insertion order, which is easier to scan in
    the drop down. Resolution is a dictionary lookup, so this order is purely
    for display.
    """
    return sorted(BUILTIN_RESOLVERS.keys())


# --- resolution -------------------------------------------------------------

def _resolve_builtin(name):
    resolver = BUILTIN_RESOLVERS.get(name)
    if resolver is None:
        return None, f"unknown built-in value \"{name}\""

    try:
        value = resolver()
    except Exception as error:  # noqa: BLE001 - a resolver must never take down a send
        return None, f"built-in value \"{name}\" could not be read: {error}"

    if value is None or str(value) == "":
        return None, f"built-in value \"{name}\" is not available on this machine"
    return str(value), None


def _find_command(path, search_dirs):
    """Locate the program named by a row, or None when it does not exist."""
    if os.path.isabs(path):
        return path if os.path.isfile(path) else None

    for base in search_dirs:
        candidate = os.path.join(base, path)
        if os.path.isfile(candidate):
            return candidate
    return None


def _resolve_command(path, search_dirs):
    path = path.strip()
    if path == "":
        return None, "no command given"

    resolved = _find_command(path, search_dirs)
    if resolved is None:
        return None, f"command \"{path}\" was not found"

    try:
        completed = subprocess.run(
            [resolved],
            capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"command \"{path}\" could not be run: {error}"

    output = completed.stdout.strip()
    if output == "":
        # nothing to send, so the row is skipped; mention a non-zero exit as the
        # likely reason
        if completed.returncode != 0:
            return None, f"command \"{path}\" produced no output (exit code {completed.returncode})"
        return None, f"command \"{path}\" produced no output"

    return output, None


def _resolve_environment(name):
    name = name.strip()
    if name == "":
        return None, "no environment variable given"

    value = os.environ.get(name)
    if value is None:
        return None, f"environment variable \"{name}\" is not set"
    # set but empty: treated the same as a command that produced nothing, so an
    # empty payload is never published by accident
    if value == "":
        return None, f"environment variable \"{name}\" is empty"
    return value, None


def resolve_startup_payload(message, search_dirs=None):
    """Work out the payload a row should publish.

    Returns (payload, note). A payload of None means the row is skipped, and
    note then explains why, for the log. On a successful resolution note is
    None. The type is honoured; anything unrecognised is treated as literal,
    which is also what every configuration written before this feature does.
    """
    payload_type = message.get("type", DEFAULT_TYPE)
    payload = str(message.get("payload", ""))

    if payload_type == TYPE_COMMAND:
        return _resolve_command(payload, search_dirs or [os.getcwd()])
    if payload_type == TYPE_BUILTIN:
        return _resolve_builtin(payload)
    if payload_type == TYPE_ENVIRONMENT:
        return _resolve_environment(payload)
    return payload, None

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
import re
import shutil
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
# not a way of producing a payload, but an action: remove the Home Assistant
# entity named by HA Entity and HA ID. Handled specially by the worker; every
# other field on the row is ignored.
TYPE_REMOVE_HA_ENTITY = "remove_ha_entity"
PAYLOAD_TYPES = (TYPE_LITERAL, TYPE_COMMAND, TYPE_BUILTIN, TYPE_ENVIRONMENT, TYPE_REMOVE_HA_ENTITY)
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


# --- disks ------------------------------------------------------------------

# the values offered for each discovered disk, in the wording asked for
DISK_FIELDS = ("name", "total size B", "used size B", "free size B",
               "used percentage", "free percentage")

DISK_KEY_PATTERN = re.compile(
    r"^disks: disk (?P<index>\d+) (?P<field>"
    + "|".join(re.escape(field) for field in DISK_FIELDS)
    + r")$")

# only real, local filesystems are listed. network and pseudo filesystems are
# left out on purpose: a value from them is rarely wanted, and a dead network
# mount could otherwise block startup while its size is read.
_LINUX_LOCAL_FILESYSTEMS = frozenset({
    "ext2", "ext3", "ext4", "xfs", "btrfs", "f2fs", "jfs", "reiserfs",
    "vfat", "exfat", "ntfs", "ntfs3", "fuseblk", "zfs", "ufs",
    "hfs", "hfsplus", "apfs",
})


def _unescape_proc_mount(field):
    # /proc/mounts escapes space, tab, newline and backslash as octal
    for code, char in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
        field = field.replace(code, char)
    return field


def _discover_windows_drives():
    drives = []
    try:
        import ctypes
        import string

        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        # keep only fixed and removable disks; skip network (4) and CD-ROM (5)
        wanted_types = (2, 3)
        for position, letter in enumerate(string.ascii_uppercase):
            if not (bitmask >> position) & 1:
                continue
            root = f"{letter}:\\"
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(root) in wanted_types:
                    drives.append((root, root))
            except (OSError, ValueError):
                continue
    except (OSError, AttributeError, ImportError, ValueError):
        pass
    return drives


def _physical_disk_of(device):
    """The physical disk a block device belongs to, e.g. /dev/sda2 -> /dev/sda.

    A partition, or a btrfs subvolume, of one disk maps back to that disk, so
    that a partition such as /home is not reported as a disk of its own. A whole
    disk, an LVM volume, or anything unrecognised is returned unchanged and so
    counts as its own disk.
    """
    if not device.startswith("/dev/"):
        return device

    name = device[len("/dev/"):]
    # nvme0n1p2, mmcblk0p1: the disk name ends in a digit, so a partition is
    # marked off with a "p"
    match = re.match(r"^([a-z]+\d+(?:n\d+)?)p\d+$", name)
    if match:
        return "/dev/" + match.group(1)
    # sda2, vdb3, hda1: the disk name ends in letters, so the partition is just
    # the trailing number
    match = re.match(r"^([a-z]+)\d+$", name)
    if match:
        return "/dev/" + match.group(1)
    return device


def _parse_proc_mounts(text):
    """Parse /proc/mounts into (mountpoint, device, filesystem) rows."""
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        rows.append((_unescape_proc_mount(parts[1]), parts[0], parts[2]))
    return rows


def _real_disk_mounts(rows):
    """One mountpoint per physical disk, from parsed /proc/mounts rows.

    Only filesystems that live on a real block device are considered, which
    drops pseudo, network and bind-style mounts. Every partition or subvolume of
    a single physical disk is collapsed to one entry, represented by its
    root-most mountpoint, so that a disk shows up once no matter how it is
    carved up.
    """
    chosen = {}
    for mountpoint, device, filesystem in rows:
        if filesystem not in _LINUX_LOCAL_FILESYSTEMS:
            continue
        # a real disk is mounted from a /dev node; a bind mount or a pseudo
        # filesystem is not
        if not device.startswith("/dev/"):
            continue
        disk = _physical_disk_of(device)
        current = chosen.get(disk)
        if current is None or len(mountpoint) < len(current):
            chosen[disk] = mountpoint
    return [(mountpoint, mountpoint) for mountpoint in sorted(chosen.values())]


def _discover_linux_mounts():
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return []
    return _real_disk_mounts(_parse_proc_mounts(text))


def _discover_macos_mounts():
    # the boot volume plus whatever is mounted under /Volumes; deduplication by
    # device id below removes the boot volume's /Volumes alias
    mounts = [("/", "/")]
    try:
        for entry in sorted(os.listdir("/Volumes")):
            path = os.path.join("/Volumes", entry)
            if os.path.isdir(path):
                mounts.append((path, path))
    except OSError:
        pass
    return mounts


def discover_disks():
    """The connected disks, as an ordered list of (name, mountpoint).

    Enumeration only; the sizes are read later, per disk, so building the list
    stays cheap and a single unreadable disk cannot spoil the whole list. The
    order is stable (sorted by mountpoint) so that "disk 1" means the same disk
    throughout a run. Never raises.
    """
    if sys.platform.startswith("win"):
        raw = _discover_windows_drives()
    elif sys.platform == "darwin":
        raw = _discover_macos_mounts()
    else:
        raw = _discover_linux_mounts()

    disks = []
    seen_devices = set()
    for name, mountpoint in sorted(raw, key=lambda pair: pair[1]):
        try:
            device = os.stat(mountpoint).st_dev
        except OSError:
            # a mountpoint that cannot even be stat'd is skipped
            continue
        # the same filesystem reached through two mountpoints is one disk
        if device in seen_devices:
            continue
        seen_devices.add(device)
        disks.append((name, mountpoint))
    return disks


def disk_builtin_keys():
    """The built-in names for the disks connected right now."""
    keys = []
    for index in range(1, len(discover_disks()) + 1):
        for field in DISK_FIELDS:
            keys.append(f"disks: disk {index} {field}")
    return keys


def _resolve_disk(name):
    match = DISK_KEY_PATTERN.match(name)
    if match is None:
        return None, f"unknown built-in value \"{name}\""

    index = int(match.group("index"))
    field = match.group("field")

    disks = discover_disks()
    # the machine may have had more disks on a previous run; that is expected
    # and simply skipped rather than being an error
    if index < 1 or index > len(disks):
        return None, f"disk {index} is not connected"

    disk_name, mountpoint = disks[index - 1]
    if field == "name":
        return disk_name, None

    try:
        usage = shutil.disk_usage(mountpoint)
    except OSError as error:
        return None, f"disk {index} (\"{disk_name}\") could not be read: {error}"

    if field == "total size B":
        return str(usage.total), None
    if field == "used size B":
        return str(usage.used), None
    if field == "free size B":
        return str(usage.free), None

    if usage.total <= 0:
        return None, f"disk {index} (\"{disk_name}\") reports a total size of zero"
    if field == "used percentage":
        return f"{usage.used / usage.total * 100:.1f}", None
    if field == "free percentage":
        return f"{usage.free / usage.total * 100:.1f}", None

    return None, f"unknown built-in value \"{name}\""


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
    the drop down. The disk entries are worked out fresh each time, because how
    many disks there are can change between runs.
    """
    return sorted(list(BUILTIN_RESOLVERS.keys()) + disk_builtin_keys())


# --- resolution -------------------------------------------------------------

def _resolve_builtin(name):
    resolver = BUILTIN_RESOLVERS.get(name)
    if resolver is None:
        # the disk values are not in the static registry, since they depend on
        # what is connected right now
        if name.startswith("disks: "):
            return _resolve_disk(name)
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
    if payload_type == TYPE_REMOVE_HA_ENTITY:
        # an action, not a payload; the worker deals with it before ever asking
        # here, so this only guards against it being sent as a literal by mistake
        return None, "handled as a Home Assistant entity removal"
    return payload, None

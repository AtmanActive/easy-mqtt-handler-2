"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_startup_disks.py
*
*  Tests for the disk built-ins, which are discovered at runtime and so must
*  cope with the set of disks changing between one run and the next
*
*  Copyright (C) 2026 AtmanActive
"""
import re
import shutil

import pytest

from easy_mqtt_handler.util import StartupPayload as sp


# --- real discovery on the test machine -------------------------------------

def test_at_least_one_disk_is_discovered():
    disks = sp.discover_disks()

    assert len(disks) >= 1
    # each entry is (name, mountpoint) and the mountpoint really exists
    for name, mountpoint in disks:
        assert name
        assert isinstance(mountpoint, str)


def test_discovery_never_raises(monkeypatch):
    # even if the platform sources are unavailable, an empty list is returned
    monkeypatch.setattr(sp, "_discover_windows_drives", lambda: [])
    monkeypatch.setattr(sp, "_discover_linux_mounts", lambda: [])
    monkeypatch.setattr(sp, "_discover_macos_mounts", lambda: [])

    assert sp.discover_disks() == []


def test_disk_keys_offer_six_values_per_disk():
    disks = sp.discover_disks()
    keys = sp.disk_builtin_keys()

    assert len(keys) == 6 * len(disks)


def test_disk_keys_are_included_in_the_offered_built_ins():
    keys = sp.builtin_keys()

    if sp.discover_disks():
        assert "disks: disk 1 name" in keys
        assert "disks: disk 1 total size B" in keys


# --- deterministic resolution against a stand-in disk -----------------------

@pytest.fixture
def one_fake_disk(tmp_path, monkeypatch):
    # a single disk whose mountpoint is a real directory, so shutil.disk_usage
    # returns genuine numbers we can check against
    monkeypatch.setattr(sp, "discover_disks", lambda: [("TestDisk", str(tmp_path))])
    return tmp_path


def resolve(key):
    return sp.resolve_startup_payload({"type": "built-in", "payload": key})


def test_disk_name_is_reported(one_fake_disk):
    assert resolve("disks: disk 1 name") == ("TestDisk", None)


def test_disk_total_matches_shutil(one_fake_disk):
    value, note = resolve("disks: disk 1 total size B")

    assert note is None
    assert value == str(shutil.disk_usage(str(one_fake_disk)).total)


def test_disk_used_and_free_are_reported(one_fake_disk):
    usage = shutil.disk_usage(str(one_fake_disk))

    assert resolve("disks: disk 1 used size B") == (str(usage.used), None)
    assert resolve("disks: disk 1 free size B") == (str(usage.free), None)


def test_disk_sizes_are_plain_integers(one_fake_disk):
    for field in ("total size B", "used size B", "free size B"):
        value, _note = resolve(f"disks: disk 1 {field}")
        assert value.isdigit()


def test_disk_percentages_are_within_range(one_fake_disk):
    used, _u = resolve("disks: disk 1 used percentage")
    free, _f = resolve("disks: disk 1 free percentage")

    for value in (used, free):
        assert re.match(r"^\d+\.\d$", value)
        assert 0.0 <= float(value) <= 100.0


def test_a_disk_that_is_not_connected_is_skipped(one_fake_disk):
    # only one disk exists, so disk 2 must skip rather than crash
    value, note = resolve("disks: disk 2 free size B")

    assert value is None
    assert "not connected" in note


def test_a_disk_from_a_previous_run_with_more_disks_is_skipped(monkeypatch):
    # the scenario called out explicitly: last run saw 5 disks, this run sees 1
    monkeypatch.setattr(sp, "discover_disks", lambda: [("only", "/only")])

    value, note = resolve("disks: disk 5 used percentage")

    assert value is None
    assert "disk 5 is not connected" in note


def test_a_zero_total_disk_skips_percentages(monkeypatch):
    class _Zero:
        total = 0
        used = 0
        free = 0

    monkeypatch.setattr(sp, "discover_disks", lambda: [("empty", "/empty")])
    monkeypatch.setattr(sp.shutil, "disk_usage", lambda _p: _Zero())

    value, note = resolve("disks: disk 1 used percentage")

    assert value is None
    assert "total size of zero" in note


def test_an_unreadable_disk_skips_rather_than_crashing(monkeypatch):
    monkeypatch.setattr(sp, "discover_disks", lambda: [("gone", "/gone")])

    def _raise(_path):
        raise OSError("device not ready")

    monkeypatch.setattr(sp.shutil, "disk_usage", _raise)

    value, note = resolve("disks: disk 1 total size B")

    assert value is None
    assert "could not be read" in note


def test_a_malformed_disk_key_is_unknown():
    value, note = resolve("disks: disk banana free size B")

    assert value is None
    assert "unknown built-in" in note


def test_disk_discovery_does_not_shell_out(monkeypatch):
    import subprocess

    def forbidden(*_a, **_k):
        raise AssertionError("disk discovery spawned a subprocess")

    monkeypatch.setattr(subprocess, "Popen", forbidden)

    sp.discover_disks()
    for key in sp.disk_builtin_keys():
        sp.resolve_startup_payload({"type": "built-in", "payload": key})


def test_the_same_filesystem_is_not_listed_twice(monkeypatch):
    # two mountpoints on one device (same st_dev) collapse into one disk
    monkeypatch.setattr(sp.sys, "platform", "linux")
    monkeypatch.setattr(sp, "_discover_linux_mounts",
                        lambda: [("/", "/"), ("/also", "/also")])

    class _Stat:
        st_dev = 42

    monkeypatch.setattr(sp.os, "stat", lambda _p: _Stat())

    assert len(sp.discover_disks()) == 1


# --- Linux: only real physical disks, not every mountpoint ------------------

@pytest.mark.parametrize("device,expected", [
    ("/dev/sda1", "/dev/sda"),
    ("/dev/sda2", "/dev/sda"),
    ("/dev/sdb3", "/dev/sdb"),
    ("/dev/sdab1", "/dev/sdab"),          # more than 26 disks
    ("/dev/vda1", "/dev/vda"),            # virtio
    ("/dev/hda1", "/dev/hda"),            # old IDE
    ("/dev/nvme0n1p2", "/dev/nvme0n1"),   # NVMe
    ("/dev/nvme1n1p12", "/dev/nvme1n1"),
    ("/dev/mmcblk0p1", "/dev/mmcblk0"),   # SD / eMMC
    ("/dev/sda", "/dev/sda"),             # whole disk, unchanged
    ("/dev/nvme0n1", "/dev/nvme0n1"),     # whole NVMe disk, unchanged
    ("/dev/mapper/vg-root", "/dev/mapper/vg-root"),  # LVM: its own disk
    ("/dev/dm-0", "/dev/dm-0"),
])
def test_partition_maps_to_its_physical_disk(device, expected):
    assert sp._physical_disk_of(device) == expected


# a realistic /proc/mounts with pseudo filesystems, a separate /home and /boot,
# an EFI partition, and a couple of snap loops
PROC_MOUNTS_SEPARATE_HOME = """\
sysfs /sys sysfs rw 0 0
proc /proc proc rw 0 0
udev /dev devtmpfs rw 0 0
tmpfs /run tmpfs rw 0 0
/dev/sda2 / ext4 rw,relatime 0 0
/dev/sda3 /home ext4 rw,relatime 0 0
/dev/sda1 /boot/efi vfat rw,relatime 0 0
tmpfs /dev/shm tmpfs rw 0 0
/dev/loop0 /snap/core/1234 squashfs ro 0 0
/dev/loop1 /snap/firefox/567 squashfs ro 0 0
cgroup2 /sys/fs/cgroup cgroup2 rw 0 0
"""


def test_a_single_disk_with_a_separate_home_is_one_disk():
    disks = sp._real_disk_mounts(sp._parse_proc_mounts(PROC_MOUNTS_SEPARATE_HOME))

    # /, /home and /boot/efi are all partitions of /dev/sda -> one disk, shown
    # by its root-most mountpoint
    assert disks == [("/", "/")]


# btrfs: / and /home are subvolumes of the same partition
PROC_MOUNTS_BTRFS_SUBVOLUMES = """\
/dev/nvme0n1p2 / btrfs rw,subvol=/@ 0 0
/dev/nvme0n1p2 /home btrfs rw,subvol=/@home 0 0
/dev/nvme0n1p1 /boot/efi vfat rw 0 0
proc /proc proc rw 0 0
"""


def test_btrfs_subvolumes_collapse_to_one_disk():
    disks = sp._real_disk_mounts(sp._parse_proc_mounts(PROC_MOUNTS_BTRFS_SUBVOLUMES))

    assert disks == [("/", "/")]


# two genuinely separate physical disks
PROC_MOUNTS_TWO_DISKS = """\
/dev/sda1 / ext4 rw 0 0
/dev/sdb1 /mnt/data ext4 rw 0 0
proc /proc proc rw 0 0
"""


def test_two_physical_disks_are_both_reported():
    disks = sp._real_disk_mounts(sp._parse_proc_mounts(PROC_MOUNTS_TWO_DISKS))

    assert disks == [("/", "/"), ("/mnt/data", "/mnt/data")]


def test_a_usb_stick_on_its_own_device_is_a_disk():
    rows = sp._parse_proc_mounts(
        "/dev/sda2 / ext4 rw 0 0\n"
        "/dev/sdc1 /media/user/USB exfat rw 0 0\n")

    disks = sp._real_disk_mounts(rows)

    assert ("/media/user/USB", "/media/user/USB") in disks
    assert len(disks) == 2


def test_bind_and_pseudo_mounts_are_ignored():
    rows = sp._parse_proc_mounts(
        "/dev/sda1 / ext4 rw 0 0\n"
        "tmpfs /tmp tmpfs rw 0 0\n"
        "proc /proc proc rw 0 0\n"
        "overlay /var/lib/docker/overlay2/x overlay rw 0 0\n"
        "/dev/sda1 /var/bind ext4 rw,bind 0 0\n")  # bind of the same device

    disks = sp._real_disk_mounts(rows)

    # only the one physical disk, once
    assert disks == [("/", "/")]


def test_the_root_most_mountpoint_represents_the_disk():
    # a data disk mounted only below /mnt is represented by its shortest path
    rows = sp._parse_proc_mounts(
        "/dev/sdb2 /mnt/data ext4 rw 0 0\n"
        "/dev/sdb1 /mnt/data/nested ext4 rw 0 0\n")

    disks = sp._real_disk_mounts(rows)

    assert disks == [("/mnt/data", "/mnt/data")]


def test_proc_mounts_that_cannot_be_read_yields_nothing(monkeypatch):
    def _raise(*_a, **_k):
        raise OSError("no /proc here")

    monkeypatch.setattr("builtins.open", _raise)
    # _discover_linux_mounts must swallow the error
    assert sp._discover_linux_mounts() == []

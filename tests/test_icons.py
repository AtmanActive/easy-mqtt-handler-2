"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_icons.py
*
*  Guards against icon assets drifting out of sync with their paths
*
*  Copyright (C) 2026 AtmanActive
"""
import os

import pytest

from easy_mqtt_handler.util import Icons

# every module-level constant in Icons is a path to an asset
ICON_CONSTANTS = sorted(
    name for name in dir(Icons)
    if name.isupper() and isinstance(getattr(Icons, name), str)
)


def test_icon_constants_were_discovered():
    assert ICON_CONSTANTS, "no icon path constants found in Icons module"


@pytest.mark.parametrize("constant", ICON_CONSTANTS)
def test_icon_file_exists(constant):
    # QIcon silently yields a blank icon for a missing file, so a typo in one of
    # these paths would otherwise go unnoticed until someone looked at the GUI
    path = getattr(Icons, constant)
    assert os.path.exists(path), f"{constant} points at a missing file: {path}"

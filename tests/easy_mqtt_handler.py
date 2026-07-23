"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/easy_mqtt_handler.py
*
*  Test entry point used by `briefcase dev --test` and `briefcase run --test`.
*  Briefcase runs this as a module; it hands control straight to pytest.
*
*  Copyright (C) 2023 A. Zeil
"""
import os
import sys

import pytest

returncode = pytest.main(["-vv", "--no-header", os.path.dirname(__file__)])

exit_code = 0 if returncode == pytest.ExitCode.OK else 1

# briefcase decides pass/fail by scanning our output for this marker rather than
# by reading the process exit status, so it has to be printed explicitly
print(f">>>>>>>>>> EXIT {exit_code} <<<<<<<<<<")

sys.exit(exit_code)

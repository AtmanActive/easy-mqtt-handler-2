"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tests/test_release_readiness.py
*
*  Checks the things a release depends on, so that a release build fails here
*  rather than halfway through publishing
*
*  Copyright (C) 2026 AtmanActive
"""
import subprocess
import sys
from pathlib import Path

import tasks

ROOT = Path(__file__).parent.parent


def run_task(*args):
    return subprocess.run([sys.executable, str(ROOT / "tasks.py"), *args],
                          cwd=ROOT, capture_output=True, text=True)


def test_changelog_documents_the_current_version():
    # releasing a version nobody wrote a changelog entry for is a mistake worth
    # catching before the artifacts are built
    _app_name, _formal_name, version = tasks.read_briefcase_metadata()

    assert f"# Version {version}" in (ROOT / "CHANGELOG").read_text(encoding="utf-8")


def test_release_notes_are_not_empty():
    result = run_task("release-notes")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() != ""


def test_release_notes_stop_at_the_previous_version():
    result = run_task("release-notes")

    # only this version's entry, not the whole file
    assert "# Version " not in result.stdout


def test_release_notes_warn_about_unsigned_downloads():
    # every published build is unsigned, so the warning must never be forgotten
    result = run_task("release-notes")

    assert "unsigned downloads" in result.stdout.lower()
    for platform_hint in ("SmartScreen", "Gatekeeper", "AppImage"):
        assert platform_hint in result.stdout


def test_release_notes_keep_the_changelog_entry_above_the_footer():
    result = run_task("release-notes")

    # the version's own notes must come first, not be buried under boilerplate
    assert result.stdout.index("[") < result.stdout.index("A note on unsigned downloads")


def test_metadata_reader_agrees_with_pyproject():
    app_name, formal_name, version = tasks.read_briefcase_metadata()

    assert app_name == "easy-mqtt-handler"
    assert formal_name and version


def test_requirements_cover_the_build_tools():
    # the CI runner installs only this file before building and testing
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()

    for tool in ("briefcase", "pytest", "babel"):
        assert tool in requirements, f"{tool} missing from requirements.txt"


def test_a_translation_compiler_is_available():
    # without one the build silently ships untranslated strings
    assert tasks.have_po_compiler()


def test_build_python_falls_back_when_there_is_no_project_venv(monkeypatch, tmp_path):
    """A CI runner installs the requirements into its own interpreter.

    Requiring a project venv made every packaging step fail on all three
    platforms, because there is no .venv on a runner and never will be.
    """
    monkeypatch.setattr(tasks, "VENV_DIR", tmp_path / "does-not-exist")

    assert tasks.build_python() == sys.executable


def test_build_python_prefers_the_project_venv(monkeypatch, tmp_path):
    venv = tmp_path / ".venv"
    bindir = venv / ("Scripts" if tasks.os.name == "nt" else "bin")
    bindir.mkdir(parents=True)
    interpreter = bindir / ("python.exe" if tasks.os.name == "nt" else "python")
    interpreter.write_text("", encoding="utf-8")
    monkeypatch.setattr(tasks, "VENV_DIR", venv)

    assert tasks.build_python() == str(interpreter)

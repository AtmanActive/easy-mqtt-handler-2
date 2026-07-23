#! /usr/bin/env python3
"""
SPDX-License-Identifier: GPL-3.0-or-later
*
*  tasks.py
*
*  Cross-platform task runner for easy MQTT handler 2. Replaces the original
*  Makefile and src/scripts/*.sh, which only ran on Linux/macOS.
*
*  Usage: python tasks.py <task> [--help]
*
*  Copyright (C) 2023 A. Zeil
*  Copyright (C) 2026 AtmanActive
"""
import argparse
import datetime
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
APP_PACKAGE = ROOT / "src" / "easy_mqtt_handler"
LOCALE_DIR = APP_PACKAGE / "locale"
TEMPLATE_DIR = LOCALE_DIR / "templates"
ICON_DIR = APP_PACKAGE / "assets" / "app-icon"
VENV_DIR = ROOT / ".venv"
DIST_DIR = ROOT / "dist"

# the folder that switches the app into portable mode, shipped inside the zip
PORTABLE_DATA_DIRNAME = "data"

PORTABLE_DATA_README = """\
Easy MQTT Handler 2 - portable configuration folder
===================================================

This folder is what makes Easy MQTT Handler run in portable mode.

While it sits next to "Easy MQTT Handler 2.exe", the program keeps all of its
configuration in here instead of in your Windows user profile:

    default-settings.json           connection settings
    default-payloads.json           your payload handlers
    default-startup-messages.json   messages published on connecting

Each file appears the first time you save something into it, so do not worry if
the folder stays empty or only holds some of them.

You can move or copy the whole program folder anywhere, including a USB stick,
and your configuration travels with it.

Delete this folder if you would rather have the program store its settings in
%appdata%\\easy-mqtt-handler\\ like a normally installed copy.

This readme is only here so that the folder survives unzipping; some archive
tools silently drop empty folders. You can delete this file, but keep the folder.
"""

# marker that identifies a source file carrying translatable strings
TRANSLATION_MARKER = "translate = gettext.translation"

ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)
# the .ico bundles only the small sizes; .icns wants the full set
ICO_SIZES = (16, 32, 48, 64)

LINUX_TARGETS = (
    "archlinux:latest",
    "debian:11", "debian:12",
    "ubuntu:18.04", "ubuntu:20.04", "ubuntu:22.04",
    "fedora:36", "fedora:37", "fedora:38",
    "almalinux:7", "almalinux:8", "almalinux:9",
)


def info(message):
    print(f"[*] {message}")


def ok(message):
    print(f"[+] {message}")


def fail(message):
    print(f"[-] {message}", file=sys.stderr)
    sys.exit(1)


def venv_executable(name):
    """Locate an executable inside the project venv, honouring the platform layout."""
    bindir = VENV_DIR / ("Scripts" if os.name == "nt" else "bin")
    suffix = ".exe" if os.name == "nt" else ""
    candidate = bindir / f"{name}{suffix}"
    if not candidate.exists():
        fail(f"{name} not found in {bindir}. Run: python tasks.py venv")
    return str(candidate)


def require_tool(name, hint):
    """Resolve an external command, failing with an actionable message."""
    path = shutil.which(name)
    if path is None:
        fail(f"Dependency '{name}' not found on PATH. {hint}")
    ok(f"Found dependency: {name}")
    return path


def run(command, **kwargs):
    """Run a command and abort on a non-zero exit status.

    The original shell scripts captured stdout and compared it to 0, which meant
    failures were silently reported as successes. Check the exit code instead.
    """
    result = subprocess.run(command, cwd=ROOT, **kwargs)
    if result.returncode != 0:
        fail(f"Command failed with exit code {result.returncode}: {' '.join(str(c) for c in command)}")
    return result


def briefcase(*args):
    run([venv_executable("briefcase"), *args])


# --- tasks ------------------------------------------------------------------

def task_venv(_args):
    """Create the virtual environment and install requirements."""
    if not VENV_DIR.exists():
        info(f"Creating virtual environment in {VENV_DIR}")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        info("Virtual environment already exists, reusing it")

    python = venv_executable("python")
    run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    ok("Environment ready")


def task_clean(_args):
    """Remove build output, caches and compiled translations."""
    for directory in ("build", "dist", "logs", ".briefcase", ".pytest_cache",
                      "src/easy_mqtt_handler.dist-info"):
        target = ROOT / directory
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            ok(f"Removed {directory}/")

    if TEMPLATE_DIR.exists():
        shutil.rmtree(TEMPLATE_DIR, ignore_errors=True)
        ok("Removed translation templates")

    for cache in ROOT.rglob("__pycache__"):
        if VENV_DIR in cache.parents:
            continue
        shutil.rmtree(cache, ignore_errors=True)

    for mo_file in LOCALE_DIR.rglob("*.mo"):
        mo_file.unlink()

    ok("Clean complete (the .venv was left in place; delete it manually if needed)")


def translatable_sources():
    """Find app sources that install their own gettext translator."""
    sources = []
    for py_file in APP_PACKAGE.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        if TRANSLATION_MARKER in py_file.read_text(encoding="utf-8"):
            sources.append(py_file)
    return sorted(sources)


def task_translation_templates(_args):
    """Regenerate the .pot templates from the app sources."""
    require_tool("xgettext", "Install GNU gettext (Windows: winget install mlocati.GetText).")
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    sources = translatable_sources()
    if not sources:
        fail(f"No source files containing '{TRANSLATION_MARKER}' were found")

    for source in sources:
        pot_file = TEMPLATE_DIR / f"{source.stem}.pot"
        info(f"Generating {pot_file.relative_to(ROOT)}")
        run([
            "xgettext",
            "--language=Python",
            "--from-code=UTF-8",
            "--no-wrap",
            "--output", str(pot_file),
            # posix separators keep the emitted "#:" references identical
            # whether the templates are regenerated on Windows or Linux
            source.relative_to(ROOT).as_posix(),
        ])
        _rewrite_pot_header(pot_file)
        ok(f"Generated {pot_file.relative_to(ROOT)}")

    ok(f"All done, {len(sources)} template(s) written")


def _rewrite_pot_header(pot_file):
    """Swap xgettext's placeholder preamble for the project's own header."""
    lines = pot_file.read_text(encoding="utf-8").splitlines()

    # everything before the first source reference is the generated preamble
    body_start = next((i for i, line in enumerate(lines) if line.startswith("#:")), len(lines))

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M%z")
    header = [
        f"# easy MQTT handler 2 - translation file - {pot_file.stem}.po",
        "# SPDX-License-Identifier: GPL-3.0-or-later",
        "# Copyright (C) 2023 A. Zeil",
        "",
        "#",
        'msgid ""',
        'msgstr ""',
        f'"POT-Creation-Date: {timestamp}\\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        '"Generated-By: xgettext\\n"',
        "",
    ]
    pot_file.write_text("\n".join(header + lines[body_start:]) + "\n", encoding="utf-8")


def task_compile_translations(_args):
    """Compile every .po file into its binary .mo counterpart."""
    require_tool("msgfmt", "Install GNU gettext (Windows: winget install mlocati.GetText).")

    po_files = sorted(LOCALE_DIR.rglob("*.po"))
    if not po_files:
        fail(f"No .po files found under {LOCALE_DIR}")

    for po_file in po_files:
        mo_file = po_file.with_suffix(".mo")
        # --check-format catches mismatched placeholders between msgid and msgstr.
        # Header checking is deliberately left off: the existing .po files predate
        # this runner and are missing optional metadata fields.
        run(["msgfmt", "--check-format", "--output-file", str(mo_file), str(po_file)])
        ok(f"Compiled {po_file.relative_to(ROOT)}")

    ok(f"All done, {len(po_files)} translation(s) compiled")


def find_imagemagick():
    """Locate the ImageMagick binary, verifying it really is ImageMagick.

    ImageMagick 7 ships as `magick`; only the older Unix builds use the bare name
    `convert`. On Windows `convert.exe` is the built-in FAT-to-NTFS filesystem
    utility in System32, so a naive PATH lookup finds the wrong program entirely.
    """
    for name in ("magick", "convert"):
        candidate = shutil.which(name)
        if candidate is None:
            continue
        try:
            probe = subprocess.run([candidate, "-version"], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            continue
        if "imagemagick" in probe.stdout.lower():
            ok(f"Found dependency: ImageMagick ({candidate})")
            return candidate

    fail("ImageMagick not found on PATH. Install it "
         "(Windows: winget install ImageMagick.ImageMagick).")


def task_icons(_args):
    """Rebuild the PNG/ICO/ICNS icons from the master SVG."""
    # inkscape rasterises the SVG; ImageMagick only assembles the multi-size .ico
    require_tool("inkscape", "Install Inkscape (Windows: winget install Inkscape.Inkscape).")
    magick = find_imagemagick()

    svg = ICON_DIR / "app-icon.svg"
    if not svg.exists():
        fail(f"Master icon not found: {svg}")

    info("Removing old icon files")
    for size in ICON_SIZES:
        (ICON_DIR / f"app-icon-{size}.png").unlink(missing_ok=True)
    (ICON_DIR / "app-icon.ico").unlink(missing_ok=True)

    for size in ICON_SIZES:
        png = ICON_DIR / f"app-icon-{size}.png"
        run(["inkscape", "-w", str(size), "-h", str(size), str(svg), "-o", str(png)])
        ok(f"Rendered {png.name}")

    ico_inputs = [str(ICON_DIR / f"app-icon-{size}.png") for size in ICO_SIZES]
    run([magick, *ico_inputs, str(ICON_DIR / "app-icon.ico")])
    ok("Rendered app-icon.ico")

    # png2icns is Linux-only; on other platforms leave the committed .icns alone
    if shutil.which("png2icns"):
        icns_inputs = [str(ICON_DIR / f"app-icon-{s}.png") for s in ICON_SIZES if s != 64]
        run(["png2icns", str(ICON_DIR / "app-icon.icns"), *icns_inputs])
        ok("Rendered app-icon.icns")
    else:
        info("png2icns not found; keeping the existing app-icon.icns (macOS icon unchanged)")


def task_test(_args):
    """Run the test suite."""
    run([venv_executable("python"), "-m", "pytest"])


def task_dev(_args):
    """Run the app from source."""
    briefcase("dev")


def ensure_translations_compiled(args):
    """Compile translations if they are missing.

    The .mo files are generated artifacts and stay out of git, so a fresh clone
    has none. Without this the app still builds, but silently falls back to the
    untranslated source strings.
    """
    po_count = len(list(LOCALE_DIR.rglob("*.po")))
    if len(list(LOCALE_DIR.rglob("*.mo"))) >= po_count:
        return

    if shutil.which("msgfmt") is None:
        info("WARNING: translations are not compiled and msgfmt is unavailable; "
             "the build will fall back to untranslated strings")
        return

    info("Compiled translations are missing, building them first")
    task_compile_translations(args)


def target_args(args):
    """Build the optional 'platform [format]' argument pair for briefcase."""
    if args.format and not args.platform:
        fail("--format requires --platform (e.g. --platform linux --format appimage)")
    return [a for a in (args.platform, args.format) if a]


def task_build(args):
    """Build the app (use --platform/--format to target appimage, macOS, ...)."""
    ensure_translations_compiled(args)
    # --update re-copies the app sources into the bundle. Without it briefcase
    # reuses whatever was copied when the bundle was first created, which would
    # silently ship stale code and miss the .mo files compiled just above.
    briefcase("build", *target_args(args), "--update")


def task_package(args):
    """Package a distributable artifact (honours --platform/--format)."""
    ensure_translations_compiled(args)
    briefcase("package", *target_args(args), "--update", "--adhoc-sign")


def read_briefcase_metadata():
    """Return (app_name, formal_name, version) straight from pyproject.toml."""
    with open(ROOT / "pyproject.toml", "rb") as handle:
        config = tomllib.load(handle)

    briefcase = config["tool"]["briefcase"]
    apps = briefcase["app"]
    # there is exactly one app defined; read its key rather than hardcoding it
    app_name = next(iter(apps))
    return app_name, apps[app_name]["formal_name"], briefcase["version"]


def windows_bundle_dir(app_name):
    """The folder briefcase builds the Windows app into."""
    return ROOT / "build" / app_name / "windows" / "app" / "src"


def task_package_portable(args):
    """Build the Windows portable .zip (self-contained, with a data folder)."""
    if not sys.platform.startswith("win"):
        fail("The portable zip is a Windows artifact and must be built on Windows.")

    # reuse the normal build so the zip always contains a current app
    args.platform = "windows"
    task_build(args)

    app_name, formal_name, version = read_briefcase_metadata()
    bundle = windows_bundle_dir(app_name)
    if not bundle.is_dir():
        fail(f"Windows app bundle not found at {bundle}")

    label = f"{formal_name}-{version}-Portable"
    archive = DIST_DIR / f"{label}.zip"
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    archive.unlink(missing_ok=True)

    info(f"Building {archive.name}")
    file_count = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle.rglob("*")):
            relative = path.relative_to(bundle)
            # a data folder from local testing must not leak into the release
            if relative.parts and relative.parts[0] == PORTABLE_DATA_DIRNAME:
                continue
            if path.is_dir():
                continue
            zf.write(path, Path(label) / relative)
            file_count += 1

        # ship the portable marker folder with a readme inside it, because an
        # empty directory is dropped by some unzip tools and the folder is
        # exactly what enables portable mode
        zf.writestr(
            str(Path(label) / PORTABLE_DATA_DIRNAME / "README.txt"),
            PORTABLE_DATA_README,
        )
        file_count += 1

    size_mb = archive.stat().st_size / (1024 * 1024)
    ok(f"Packaged {archive.relative_to(ROOT)} ({file_count} files, {size_mb:.1f} MiB)")
    ok(f"Unzips to a single folder: {label}\\")


def task_build_all_linux(_args):
    """Package for every supported Linux distribution."""
    for target in LINUX_TARGETS:
        info(f"Packaging for {target}")
        briefcase("package", "--target", target)


TASKS = {
    "venv": task_venv,
    "clean": task_clean,
    "translation-templates": task_translation_templates,
    "compile-translations": task_compile_translations,
    "icons": task_icons,
    "test": task_test,
    "dev": task_dev,
    "build": task_build,
    "package": task_package,
    "package-portable": task_package_portable,
    "build-all-linux": task_build_all_linux,
}


def main():
    parser = argparse.ArgumentParser(
        description="Cross-platform task runner for easy MQTT handler 2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(f"  {name:<24} {func.__doc__}" for name, func in TASKS.items()),
    )
    parser.add_argument("task", choices=TASKS.keys(), help="the task to run")
    parser.add_argument("--platform", help="briefcase platform override (e.g. windows, linux, macOS)")
    parser.add_argument("--format", help="briefcase output format (e.g. app, appimage, flatpak)")
    args = parser.parse_args()

    TASKS[args.task](args)


if __name__ == "__main__":
    main()

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
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
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

PORTABLE_DATA_README_TEMPLATE = """\
Easy MQTT Handler 2 - portable configuration folder
===================================================

This folder is what makes Easy MQTT Handler run in portable mode.

While it sits next to {neighbour}, the program keeps all of its
configuration in here instead of in {home_location}:

    default-settings.json           connection settings
    default-payloads.json           your payload handlers
    default-startup-messages.json   messages published on connecting

Each file appears the first time you save something into it, so do not worry if
the folder stays empty or only holds some of them.

You can move or copy the whole program folder anywhere, including a USB stick,
and your configuration travels with it.

Delete this folder if you would rather have the program store its settings in
{home_location} like a normally installed copy.

This readme is only here so that the folder survives unpacking; some archive
tools silently drop empty folders. You can delete this file, but keep the folder.
"""


# Sits at the top of the Linux portable archive, where the Windows zip has its
# .exe. It exists because the bundled interpreter lives in usr/bin, several
# levels below the folder the user unpacked, so the data folder beside this
# script has to be pointed out explicitly.
LINUX_PORTABLE_LAUNCHER = """\
#!/bin/sh
# Easy MQTT Handler 2 - portable launcher
#
# Runs the program with its configuration kept in the "data" folder next to
# this script, instead of in ~/.config/easy-mqtt-handler/.
#
# Delete the "data" folder if you would rather use the normal per-user
# location; this launcher then behaves like an ordinary installed copy.

here=$(dirname "$(readlink -f "$0")")

EASY_MQTT_HANDLER_DATA="$here/data"
export EASY_MQTT_HANDLER_DATA

exec "$here/AppRun" "$@"
"""


def portable_data_readme(neighbour, home_location):
    return PORTABLE_DATA_README_TEMPLATE.format(neighbour=neighbour, home_location=home_location)

# Appended to every release's notes. It applies to every build we publish, so it
# lives here rather than being retyped into the CHANGELOG for each version,
# where it would eventually be forgotten.
RELEASE_NOTES_FOOTER = """

---

### A note on unsigned downloads

These files are not code signed, so your system will warn you the first time you run them.
That warning is expected and does not mean there is anything wrong with the download.

- **Windows** — SmartScreen shows "Windows protected your PC". Choose **More info**, then **Run anyway**.
- **macOS** — Gatekeeper will not open the app on a double click. Right click it, choose **Open**, and
  confirm. You only need to do this once.
- **Linux** — make the AppImage executable before running it: `chmod +x *.AppImage`

Code signing requires paid certificates from Microsoft and Apple, which this project does not have.
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


def venv_python():
    """Path to the project venv's interpreter, whether or not it exists yet."""
    bindir = VENV_DIR / ("Scripts" if os.name == "nt" else "bin")
    suffix = ".exe" if os.name == "nt" else ""
    return bindir / f"python{suffix}"


def build_python():
    """The interpreter that has the build requirements installed.

    A local checkout normally keeps them in the project venv. A CI runner has no
    project venv and installs them straight into the interpreter running this
    script, so fall back to that rather than insisting on a venv that will
    never exist there.
    """
    candidate = venv_python()
    return str(candidate) if candidate.exists() else sys.executable


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
    # invoked as a module rather than as the console script, so it always comes
    # from the same environment as the interpreter we picked
    python = build_python()

    if not briefcase.checked:
        probe = subprocess.run([python, "-c", "import briefcase"], capture_output=True)
        if probe.returncode != 0:
            fail(f"briefcase is not installed for {python}. "
                 f"Run: python tasks.py venv, or pip install -r requirements.txt")
        briefcase.checked = True

    run([python, "-m", "briefcase", *args])


briefcase.checked = False


# --- tasks ------------------------------------------------------------------

def task_venv(_args):
    """Create the virtual environment and install requirements."""
    if not VENV_DIR.exists():
        info(f"Creating virtual environment in {VENV_DIR}")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        info("Virtual environment already exists, reusing it")

    # deliberately the venv's own interpreter: this task exists to populate it
    python = str(venv_python())
    if not Path(python).exists():
        fail(f"The virtual environment at {VENV_DIR} has no interpreter.")

    run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    ok("Environment ready")


def remove_tree(target, description):
    """Delete a directory, reporting honestly whether it actually went.

    Windows refuses to remove a directory any process is sitting in, and
    ignoring that produced a "Clean complete" message with the directory still
    there, which then broke the next build in a confusing way.
    """
    if not target.exists():
        return True

    shutil.rmtree(target, ignore_errors=True)
    if target.exists():
        info(f"WARNING: could not remove {description}; something is using it. "
             f"Close anything open in {target} and try again.")
        return False

    ok(f"Removed {description}")
    return True


def task_clean(_args):
    """Remove build output, caches and compiled translations."""
    failed = []
    for directory in ("build", "dist", "logs", ".briefcase", ".pytest_cache",
                      "src/easy_mqtt_handler.dist-info"):
        if not remove_tree(ROOT / directory, f"{directory}/"):
            failed.append(directory)

    if not remove_tree(TEMPLATE_DIR, "translation templates"):
        failed.append(str(TEMPLATE_DIR))

    for cache in ROOT.rglob("__pycache__"):
        if VENV_DIR in cache.parents:
            continue
        shutil.rmtree(cache, ignore_errors=True)

    for mo_file in LOCALE_DIR.rglob("*.mo"):
        mo_file.unlink()

    if failed:
        fail("Clean did not finish: " + ", ".join(failed))

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


def compile_po_with_msgfmt(po_file, mo_file):
    # --check-format catches mismatched placeholders between msgid and msgstr.
    # Header checking is deliberately left off: the existing .po files predate
    # this runner and are missing optional metadata fields.
    run(["msgfmt", "--check-format", "--output-file", str(mo_file), str(po_file)])


def compile_po_with_babel(po_file, mo_file):
    """Pure Python .po compilation, for machines without GNU gettext.

    Keeps the build working on a bare CI runner, where installing gettext
    differs per platform and is especially awkward on Windows.
    """
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    with open(po_file, "r", encoding="utf-8") as handle:
        catalog = read_po(handle)
    with open(mo_file, "wb") as handle:
        write_mo(handle, catalog)


def have_po_compiler():
    """True when translations can be compiled by some means."""
    if shutil.which("msgfmt") is not None:
        return True
    try:
        import babel  # noqa: F401
    except ImportError:
        return False
    return True


def pick_po_compiler():
    """Return (compile function, description), preferring GNU gettext."""
    if shutil.which("msgfmt") is not None:
        return compile_po_with_msgfmt, "msgfmt"

    try:
        import babel  # noqa: F401
    except ImportError:
        fail("Neither msgfmt nor babel is available. Install GNU gettext "
             "(Windows: winget install mlocati.GetText), or 'pip install babel'.")

    return compile_po_with_babel, "babel"


def task_compile_translations(_args):
    """Compile every .po file into its binary .mo counterpart."""
    compile_po, compiler_name = pick_po_compiler()
    ok(f"Compiling translations with {compiler_name}")

    po_files = sorted(LOCALE_DIR.rglob("*.po"))
    if not po_files:
        fail(f"No .po files found under {LOCALE_DIR}")

    for po_file in po_files:
        compile_po(po_file, po_file.with_suffix(".mo"))
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
    run([build_python(), "-m", "pytest"])


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

    if not have_po_compiler():
        info("WARNING: translations are not compiled and neither msgfmt nor babel is "
             "available; the build will fall back to untranslated strings")
        return

    info("Compiled translations are missing, building them first")
    task_compile_translations(args)


def target_args(args):
    """Build the optional 'platform [format]' argument pair for briefcase."""
    if args.format and not args.platform:
        fail("--format requires --platform (e.g. --platform linux --format appimage)")
    return [a for a in (args.platform, args.format) if a]


def bundle_exists(platform=None):
    """True when briefcase has already created a bundle we could update.

    briefcase writes a briefcase.toml into every bundle it creates, so its
    presence is the reliable signal.
    """
    app_name, _formal_name, _version = read_briefcase_metadata()
    base = ROOT / "build" / app_name
    if not base.is_dir():
        return False

    if platform is None:
        return any(base.rglob("briefcase.toml"))

    # only the requested platform counts; a Windows bundle says nothing about
    # whether a Linux one has been created
    for entry in base.iterdir():
        if entry.is_dir() and entry.name.lower() == platform.lower():
            return any(entry.rglob("briefcase.toml"))
    return False


def ensure_bundle_created(args):
    """Create the bundle first when there is not one yet.

    briefcase can create it as part of build/package, but doing so in the same
    invocation fails on Windows while stamping the freshly written stub binary.
    Creating it as its own step is reliable, and it means build and package can
    always pass --update, which is what keeps them from shipping stale sources.
    """
    if bundle_exists(args.platform):
        return

    # briefcase refuses to create over an existing directory, so a bundle left
    # half-built by an interrupted run would block every later build until it
    # was deleted by hand
    if args.platform:
        app_name, _formal_name, _version = read_briefcase_metadata()
        base = ROOT / "build" / app_name
        if base.is_dir():
            for entry in base.iterdir():
                if entry.is_dir() and entry.name.lower() == args.platform.lower():
                    info(f"Discarding an incomplete {args.platform} bundle")
                    if not remove_tree(entry, f"incomplete {args.platform} bundle"):
                        fail(f"Cannot rebuild while {entry} is in use.")

    info("No bundle for this target yet, creating it first")
    briefcase("create", *target_args(args), "--no-input")


def task_build(args):
    """Build the app (use --platform/--format to target appimage, macOS, ...)."""
    ensure_translations_compiled(args)
    ensure_bundle_created(args)
    briefcase("build", *target_args(args), "--update", "--no-input")


def task_package(args):
    """Package a distributable artifact (honours --platform/--format)."""
    ensure_translations_compiled(args)
    ensure_bundle_created(args)
    briefcase("package", *target_args(args), "--update", "--adhoc-sign", "--no-input")


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
            portable_data_readme('"Easy MQTT Handler 2.exe"',
                                 "%appdata%\\easy-mqtt-handler\\"),
        )
        file_count += 1

    size_mb = archive.stat().st_size / (1024 * 1024)
    ok(f"Packaged {archive.relative_to(ROOT)} ({file_count} files, {size_mb:.1f} MiB)")
    ok(f"Unzips to a single folder: {label}\\")


def linux_appdir(app_name, formal_name):
    """The self-contained directory tree briefcase builds the Linux app into."""
    return ROOT / "build" / app_name / "linux" / "appimage" / f"{formal_name}.AppDir"


def keep_apprun_executable(entry):
    """Make sure AppRun stays runnable.

    The launcher execs it, so an AppRun without its executable bit makes the
    whole archive useless. Cheap insurance against the build tree being
    produced somewhere that does not carry the bit.
    """
    if entry.name.endswith("/AppRun"):
        entry.mode |= 0o111
    return entry


def add_tar_bytes(tar, arcname, text, mode=0o644):
    """Write a generated text file straight into the archive."""
    payload = text.encode("utf-8")
    entry = tarfile.TarInfo(arcname)
    entry.size = len(payload)
    entry.mode = mode
    tar.addfile(entry, io.BytesIO(payload))


def task_package_portable_linux(args):
    """Build the Linux portable .tar.gz: the app folder plus a data folder."""
    if sys.platform.startswith("win"):
        fail("The Linux portable archive has to be built on Linux.")

    # the AppDir is a complete, relocatable copy of the app, the closest Linux
    # equivalent of the folder the Windows portable zip is made from. Build it
    # via the AppImage target, which is what fills it in and bundles the
    # libraries, but ship the folder rather than the .AppImage: an AppImage has
    # its own portable convention and should not be wrapped in ours.
    args.platform = "linux"
    args.format = "appimage"
    task_build(args)

    app_name, formal_name, version = read_briefcase_metadata()
    appdir = linux_appdir(app_name, formal_name)
    if not appdir.is_dir():
        fail(f"No AppDir at {appdir}; the Linux build step must run first.")

    label = f"{formal_name}-{version}-Portable"
    archive = DIST_DIR / f"{label}.tar.gz"
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    archive.unlink(missing_ok=True)

    info(f"Building {archive.name}")
    file_count = 0
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(appdir.rglob("*")):
            relative = path.relative_to(appdir)
            # never carry a data folder left behind by local testing
            if relative.parts and relative.parts[0] == PORTABLE_DATA_DIRNAME:
                continue
            # recursive=False so each entry is added exactly once, and so that
            # symlinks are stored as symlinks rather than followed
            tar.add(path, arcname=f"{label}/{relative.as_posix()}",
                    recursive=False, filter=keep_apprun_executable)
            if path.is_file():
                file_count += 1

        # the launcher, which is what makes this behave like the Windows zip:
        # the interpreter lives in usr/bin, so it cannot find a data folder at
        # the top of the tree by itself
        add_tar_bytes(tar, f"{label}/{formal_name}",
                      LINUX_PORTABLE_LAUNCHER, mode=0o755)

        add_tar_bytes(tar, f"{label}/{PORTABLE_DATA_DIRNAME}/README.txt",
                      portable_data_readme(f'"{formal_name}"',
                                           "~/.config/easy-mqtt-handler/"))
        file_count += 2

    size_mb = archive.stat().st_size / (1024 * 1024)
    ok(f"Packaged {archive.relative_to(ROOT)} ({file_count} files, {size_mb:.1f} MiB)")
    ok(f"Unpacks to a single folder: {label}/")


def platform_label(artifact_dir_name):
    """The word that goes into a filename for a per-platform artifact folder.

    Upload names have to be unique, so a platform producing more than one kind
    of package uploads as e.g. "linux-appimage" and "linux-flatpak". Only the
    platform belongs in the released filename; which format it is, is already
    plain from the extension.
    """
    return artifact_dir_name.lower().split("-", 1)[0]


# briefcase follows Debian's convention: name_version-revision~vendor-codename_abi.deb
DEB_NAME_PATTERN = re.compile(
    r"^(?P<app>[^_]+)"
    r"_(?P<version>[^-_]+)"
    r"-(?P<revision>\d+)"
    r"~(?P<vendor>[^-_]+)"
    r"-(?P<codename>[^_]+)"
    r"_(?P<abi>[^.]+)"
    r"\.deb$"
)


def canonical_deb_name(filename, formal_name):
    """Rename a .deb into the scheme the other artifacts use.

    Debian's convention uses underscores and starts with the lower case package
    name, so left alone it sorts away from every other download in the release
    listing. The vendor, codename and architecture are kept, because for a .deb
    they say which distribution it is actually for. dpkg reads the package
    metadata rather than the filename, so renaming is safe.
    """
    match = DEB_NAME_PATTERN.match(filename)
    if match is None:
        return filename

    canonical = formal_name.replace(" ", ".")
    return (f"{canonical}-{match['version']}-linux"
            f"-{match['vendor']}-{match['codename']}-{match['abi']}.deb")


def normalise_app_name(filename, formal_name):
    """Spell the application name the same way in every artifact filename.

    The Linux tools name their output "Easy_MQTT_Handler_2" while the others
    keep the spaces, which GitHub then turns into dots when the file is
    attached. The result was a release listing that did not sort by platform.
    Only the leading name is rewritten, so an architecture such as x86_64 keeps
    its underscore.
    """
    canonical = formal_name.replace(" ", ".")

    variants = (canonical,
                formal_name,
                formal_name.replace(" ", "_"),
                formal_name.replace(" ", "-"))

    # longest first, so a variant that is a prefix of another cannot win early
    for variant in sorted(variants, key=len, reverse=True):
        if filename.startswith(variant):
            return canonical + filename[len(variant):]

    return filename


def add_platform_to_name(filename, platform, version):
    """Put the platform into an artifact filename, right after the version.

    Users should be able to tell what a download is for from its name, rather
    than having to know that .dmg means macOS and .AppImage means Linux.
    """
    if platform.lower() in filename.lower():
        # already labelled, so do not label it twice
        return filename

    marker = f"-{version}"
    if marker in filename:
        return filename.replace(marker, f"{marker}-{platform}", 1)

    # no version in the name, so fall back to just before the extension
    stem, dot, extension = filename.rpartition(".")
    if dot:
        return f"{stem}-{platform}.{extension}"
    return f"{filename}-{platform}"


def task_collect_release(args):
    """Gather the per-platform build artifacts into one folder, named by platform."""
    source = ROOT / (args.source or "artifacts")
    destination = ROOT / (args.dest or "release")

    if not source.is_dir():
        fail(f"No artifacts directory at {source}")

    _app_name, formal_name, version = read_briefcase_metadata()

    destination.mkdir(parents=True, exist_ok=True)

    collected = 0
    # each subdirectory is one platform's upload, named by the build matrix
    for platform_dir in sorted(source.iterdir()):
        if not platform_dir.is_dir():
            continue
        platform = platform_label(platform_dir.name)

        for artifact in sorted(platform_dir.rglob("*")):
            if not artifact.is_file():
                continue
            # the .deb rewrite already places the platform, and
            # add_platform_to_name leaves a name that mentions it alone
            new_name = add_platform_to_name(
                normalise_app_name(
                    canonical_deb_name(artifact.name, formal_name), formal_name),
                platform, version)
            shutil.copy2(artifact, destination / new_name)
            ok(f"{artifact.name}  ->  {new_name}")
            collected += 1

    if collected == 0:
        fail(f"No files found under {source}")

    ok(f"Collected {collected} file(s) into {destination.relative_to(ROOT)}/")


def task_release_notes(_args):
    """Print the CHANGELOG section for the current version, for release notes."""
    _app_name, _formal_name, version = read_briefcase_metadata()

    changelog = ROOT / "CHANGELOG"
    if not changelog.is_file():
        fail(f"No CHANGELOG found at {changelog}")

    heading = f"# Version {version}"
    lines = changelog.read_text(encoding="utf-8").splitlines()

    try:
        start = lines.index(heading) + 1
    except ValueError:
        fail(f"CHANGELOG has no section titled \"{heading}\". "
             f"Add one before releasing {version}.")

    # the section runs until the next version heading
    end = start
    while end < len(lines) and not lines[end].startswith("# Version "):
        end += 1

    body = "\n".join(lines[start:end]).strip()
    if body == "":
        fail(f"The \"{heading}\" section of the CHANGELOG is empty.")

    # printed rather than written to a file, so the caller decides where it goes
    print(body)
    print(RELEASE_NOTES_FOOTER)


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
    "package-portable-linux": task_package_portable_linux,
    "collect-release": task_collect_release,
    "release-notes": task_release_notes,
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
    parser.add_argument("--source", help="collect-release: directory holding the per-platform artifacts")
    parser.add_argument("--dest", help="collect-release: directory to gather the renamed files into")
    args = parser.parse_args()

    TASKS[args.task](args)


if __name__ == "__main__":
    main()

# Making a release

Releases are built by GitHub Actions, on GitHub's own Windows, Linux and macOS machines, so you do not
need any of those three operating systems yourself.

**The workflow never runs on its own.** It has no push, pull request or tag trigger. It only starts when
you ask it to, so an ordinary commit never builds or publishes anything.

## Before you start

1. Set the new version in `pyproject.toml`. That file is the single place the version is defined;
   everything else, including the artifact filenames and the About window, reads it from there.
2. Add a matching `# Version <version>` section to the `CHANGELOG`. The workflow turns that section into
   the release notes, and the test suite fails if it is missing, so you cannot forget it.
   A standing note explaining the warnings users see for unsigned downloads is appended automatically,
   so it does not need repeating in the CHANGELOG. It lives in `RELEASE_NOTES_FOOTER` in `tasks.py`.
3. Commit and push both.

## Running it

1. Go to the **Actions** tab of the repository.
2. Pick **Build and release** in the list on the left.
3. Press **Run workflow**, and choose:
   * **Create the release as a draft** — on by default. The release is prepared but not visible to anyone
     else, so you can download the files and try them before publishing. Recommended.
   * **Mark the release as a pre-release** — off by default.
4. Press the green **Run workflow** button.

The three platforms build in parallel. Expect it to take a while, mostly waiting for the Linux AppImage.

When it finishes, the release is waiting under **Releases**, tagged `v<version>`. If you left the draft
option on, open it, check the files, and press **Publish release** when you are happy.

## What it produces

Every file carries its platform in the name, so nobody has to work out which download is theirs from
the file extension:

| Platform | File | Notes |
|---|---|---|
| Windows | `Easy MQTT Handler 2-<version>-windows.msi` | Normal installer |
| Windows | `Easy MQTT Handler 2-<version>-windows-Portable.zip` | Self-contained, see [portable mode](../README.md#portable-mode) |
| Linux | `Easy_MQTT_Handler_2-<version>-linux-x86_64.AppImage` | Runs on most modern distributions |
| Linux | `Easy MQTT Handler 2-<version>-linux-Portable.tar.gz` | The app folder plus a `data` folder, see [portable mode](../README.md#portable-mode) |
| Linux | `Easy MQTT Handler 2-<version>-linux.flatpak` | Install with `flatpak install <file>` |
| macOS | `Easy MQTT Handler 2-<version>-macos.dmg` | Apple Silicon |

The portable `.tar.gz` deliberately contains the app folder rather than the AppImage. It is the direct
counterpart of the Windows portable `.zip`: the whole program in one directory, with a `data` folder
next to a launcher. AppImages already have their own convention for keeping configuration beside
themselves, so wrapping one in ours would give two competing mechanisms in the same download.

The Linux builds are separate jobs, so if one of them breaks the other is still produced. They upload
under the names `linux-appimage` and `linux-flatpak`, because GitHub requires upload names to be unique,
but only the word `linux` reaches the released filename.

The Flatpak is built against the freedesktop runtime pinned in `pyproject.toml`. A new major version of
that runtime comes out every August and is supported for two years, so `flatpak_runtime_version` needs
looking at roughly once a year.

The renaming happens in the `collect-release` task, not in the packaging tools, so the names briefcase
produces are left alone. GitHub replaces the spaces with dots when the files are attached, so what
users finally see is `Easy.MQTT.Handler.2-<version>-windows.msi`.

## Things worth knowing

* **Nothing is code signed.** Windows SmartScreen will warn on first run, and macOS will refuse to open
  the app until you right-click it and choose Open. Fixing this needs paid signing certificates from
  Microsoft and Apple, and their secrets added to the repository.
* **The macOS build is Apple Silicon only**, because that is what GitHub's macOS runners are. It will run
  on Intel Macs through Rosetta. A native Intel build would need a second runner added to the matrix.
* **Re-running for the same version** adds the files to the existing release instead of failing, which is
  useful if one platform failed and you fixed it. It does not create a second release.
* **If one platform fails the other two still finish**, so you can see whether the problem is specific to
  one operating system. The release step only runs if all three succeeded.

## Building the same things locally

The workflow does not do anything you cannot do yourself; it runs the same `tasks.py` commands:

	python tasks.py venv
	python tasks.py test
	python tasks.py package                  # installer for the machine you are on
	python tasks.py package-portable         # Windows portable .zip
	python tasks.py package-portable-linux   # Linux portable .tar.gz (builds the AppImage first)
	python tasks.py release-notes            # prints the CHANGELOG section for this version

See [BUILDING.md](BUILDING.md) and [PACKAGING.md](PACKAGING.md) for the details.

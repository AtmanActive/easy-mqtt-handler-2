# Building Easy MQTT Handler

If you only want to produce a release for all three platforms, you do not need to build anything by
hand: see [RELEASING.md](RELEASING.md), which uses GitHub Actions to do it for you.

## The task runner

All build steps are driven by `tasks.py` in the repo root, which runs the same way on
Windows, Linux and macOS:

		python tasks.py --help
		python tasks.py venv
		python tasks.py test
		python tasks.py package

The `make` targets described below are thin wrappers around it, so on Linux and macOS
you can keep using `make`. On Windows, call `tasks.py` directly.

***

## Building on Linux

### Dependencies
Usually, the only dependency you will need for building on Linux is Python 3(.11). While there are a lot more dependencies
you shouldn't have to worry about them, as the build system we're using (briefcase) should set them all up for you.
All the provided steps have been tested on Ubuntu 23.04 (64bit). They may or may not work with other Linux distributions and versions. 
Please open a pull request to the documentation should you discover there are more steps needed for 
other Linux flavors. Just install Python3 with the package manager of your choice, and you should be ready to go.

In case you are having problems with the briefcase build system, you can still try to install dependencies in an 
automated fashion via `make activate-venv`. If even this is no option (maybe because of the very unlikely reason that 
your system doesn't even offer `make`), you can also try to install them via `pip install -r requirements.txt`.
All the listed commands should be executed inside the repos root directory.

### Building an AppImage executable

You can also easily build an [AppImage](https://appimage.org/) (which is a sort of _almost_ self-contained binary) via:
`make build-linux-appimage`

Once **briefcase** finished packaging you can find the installer's **.AppImage** file in the **dist** subdirectory

### Mass Building for Linux (experimental!)

You can try to build packages for a lot of different Linux distributions at the same time. It's not guaranteed to work,
and you will definitely need some more dependencies (especially podman or docker). Right now the `briefcase` build
system is configured to build for Arch Linux (latest) & Debian 11, 12 & Ubuntu 18.04, 20.04, 22.04 & Fedora 36, 37, 38 &
AlmaLinux 7, 8, 9. Check the `LINUX_TARGETS` list in `tasks.py` and consult the `briefcase` documentation if
you want to build for other targets.

You can simply execute `make build-all-linux` in the repos root directory to call the briefcase build system and 
build for all configured targets at once.

***

## Building on Windows

### Dependencies
Usually, the only dependency you will need for building on Windows is Python 3(.11). While there are a lot more dependencies
you shouldn't have to worry about them, as the build system we're using (briefcase) should set them all up for you.
All the provided steps have been tested on Windows 10 (64bit). They may or may not work with other Windows versions. 
Please open a pull request to the documentation should you discover there are more steps needed for 
other Windows versions. You should download and install the latest Python 3(.11) installer from: 
https://www.python.org/downloads/ (select the amd64 installer)

***

### Building

Follow all the steps of **Packaging**, but instead of executing **briefcase package** use **briefcase build**, e.g.:

		C:\[..]> python tasks.py venv
		C:\[..]> python tasks.py build

Once briefcase finished you should find your fresh build in the **build** subdirectory.

If you want to build the German translations into the app you also need GNU gettext on
your `PATH` (`winget install mlocati.GetText`). `tasks.py build` compiles the `.po` files
automatically when it finds gettext; without it the app still builds, but falls back to
the untranslated source strings.

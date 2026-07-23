# Replacing the program icon

The process of changing the program's icon is actually quite simple, but there are some prerequisites. 

First of all make sure that you've got `imagemagick` and `inkscape` installed, plus `icnsutils`
if you want to regenerate the macOS icon. On Windows you can get the first two via
`winget install ImageMagick.ImageMagick` and `winget install Inkscape.Inkscape`.

`icnsutils` (which provides `png2icns`) is packaged for Linux only. On Windows and macOS the
task skips the `.icns` step and leaves the committed macOS icon untouched, so regenerate the
icons on a Linux machine if you need that file rebuilt too.

Now open and edit the file `./src/easy_mqtt_handler/assets/app-icon/app-icon.svg`.
Invest all the creativity you can spare and create a new icon. Once done, you should save the file and close your 
image editing tool.

The last step should be actually the easiest one: inside the repos root directory just execute
`python tasks.py icons` (or `make regenerate-icons`).
That's it! Afterwards, you should see a lot of different versions of your new icon inside `./src/easy_mqtt_handler/assets/app-icon/`.

If you now build or package the tool again, or even just launch it via Python, you should see your new icon in the tray, already.

If you think you've created a way much nicer icon than I did (and I totally wouldn't blame you!), feel free to contribute it:
just make sure that you've read and understood the guideline on contributing and create a pull request with the content
of your [appicon](../src/easy_mqtt_handler/assets/app-icon/) directory. 
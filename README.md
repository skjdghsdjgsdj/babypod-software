# BabyPod

This repository is just for the CircuitPython code that runs on the hardware. See the [`babypod-hardware`](https://github.com/skjdghsdjgsdj/babypod-hardware/) repository for what a BabyPod is and how to build one.

## User guide

### Controls

| Button                | Effect                                                                                                                                                                                             |
|-----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| <kbd>⊙ Center</kbd>   | <ul><li>Power on (brief press when BabyPod is off)</li><li>Power off (press and hold 3 seconds)</lil><li>Accept current selection</li><li>Toggle checkbox on/off</li><li>Dismiss message</li></ul> |
| <kbd>↻ Rotation</kbd> | <ul><li>Move selection up/down</li><li>Increase/decrease number</li></ul>                                                                                                                          |
| <kbd>◀ Left</kbd>     | <ul><li>Go back/cancel</li><li>Abort current timer</li><li>Change settings (home screen only)</li></ul>                                                                                            |
| <kbd>▶ Right</kbd>    | <ul><li>Accept selection/save</li><li>Dismiss message</li></ul>                                                                                                                                    |
| <kbd>▲ Up</kbd>       | <ul><li>Move selection up</li><li>Increase number</li></ul>                                                                                                                                        |
| <kbd>▼ Down</kbd>     | <ul><li>Move selection down</li><li>Decrease number</li><li>Force reset (press and hold)</li></ul>                                                                                                 |
| Reset (via paperclip) | Hardware reset                                                                                                                                                                                     |

Holding <kbd>⊙ Center</kbd> to turn off the BabyPod and holding <kbd>▼ Down</kbd> to reset it only work when the BabyPod is waiting for input from you, like showing a menu or running a timer. If the BabyPod is busy doing something, like loading data from or sending data to Baby Buddy, wait for the operation to complete. A hard reset by poking a paperclip in the hole below the rotary encoder will always work.

The orange LED by the USB C port is illuminated when the battery is charging. If it is not illuminated, the battery is fully charged or the USB C cable isn't inserted fully, is faulty, or is connected to a bad power supply.

The soft power control options with pressing or holding <kbd>⊙ Center</kbd> are only enabled if `USE_SOFT_POWER_CONTROL` is enabled in `settings.toml.` Additionally, enabling this option will make the BabyPod shut off automatically after five minutes of inactivity except during timers.

### Messages

The percentage at top-right is the battery level.

The last feeding on the main menu, if shown, denotes the last feeding method:

| Label | Meaning      |
|-------|--------------|
| `R`   | Right breast |
| `L`   | Left breast  |
| `RL`  | Both breasts |
| `B`   | Bottle       |
| `S`   | Solid food   |

Various messages are shown at startup and during typical usage:

| Message              | Meaning                                                                                                                        |
|----------------------|--------------------------------------------------------------------------------------------------------------------------------|
| Starting up...       | Initial code is booting up.                                                                                                    |
| Connecting...        | Establishing Wi-Fi connection (DHCP, etc.). This doesn't necessarily mean connected to Baby Buddy yet, just the Wi-Fi network. |
| Going offline        | Wi-Fi connection failed so offline mode was forced.                                                                            |
| Low battery!         | Battery is less than 15% charged.                                                                                              |
| Getting feeding...   | Getting most recent feeding from Baby Buddy to show on the main menu                                                           |
| Setting clock...     | Syncing the RTC; happens if clock was never set or about once daily                                                            |
| Getting children...  | Getting child list from Baby Buddy. The first one is used. This only appears once unless you clear NVRAM.                      |
| Saving...            | Sending data to Baby Buddy or SD card, depending on whether you're online or offline.                                          |
| Canceling...         | Deleting the currently active timer                                                                                            |
| Checking status...   | Checking for a currently running timer, or starting a new one if it doesn't exist                                              |
| Checking timers...   | Seeing if there's a known timer running so the main menu can be skipped and that timer resumed                                 |
| Checking messages... | Checking notes if there's a message of the day                                                                                 |

### Sounds

The piezo makes some chimes and beeps to keep you informed. Remember you can turn off the piezo in the settings.

| Sound              | Reason                                                                                                                                                                                                                                                                                                                        |
|--------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Startup            | The BabyPod is starting up                                                                                                                                                                                                                                                                                                    |
| Low battery        | Battery is less than 15% charged                                                                                                                                                                                                                                                                                              |
| Success            | Saving data was successful, either to Baby Buddy (if online) or to the SD card (if offline)                                                                                                                                                                                                                                   |
| Error              | Something went wrong, most likely a failed request to Baby Buddy                                                                                                                                                                                                                                                              |
| Idle warning       | The BabyPod is on, but no timer is running and it's been left idle, so you're being reminded to turn off the BabyPod if not in use.                                                                                                                                                                                           |
| Chime              | Happens every minute during tummy time, or 15 minutes into feeding and then every minute after 30 minutes have elapsed during feeding. The tummy time chime is to keep track of your baby's progress without watching the screen. The feeding timer is to remind you it's still running and about the time to switch breasts. |
| Info               | The BabyPod is going offline because the Wi-Fi connection failed. You will need to manually go online later; it won't try on its own.                                                                                                                                                                                         |
| Shutdown           | You held <kbd>⊙ Center</kbd> for three seconds so the BabyPod is shutting down.                                                                                                                                                                                                                                               |
| Message of the Day | There's a message of the day available                                                                                                                                                                                                                                                                                        |

### User settings

The user of the BabyPod can configure some of its settings directly through its interface (i.e., not just through `settings.toml`). To access settings, from the home screen, press <kbd>◀ Left</kbd>.

Some options aren't shown if hardware support isn't available or something is configured in `settings.toml`.

| Setting          | Default | Effect                                                                     | Notes                                                                 |
|------------------|---------|----------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Play sounds      | On      | Enables (on) or disables (off) sounds played through the piezo             |                                                                       |
| Off after timers | Off     | Shut down (on) or keep powered on (off) the BabyPod after a timer is saved | Only shown on devices with soft power control enabled                 |
| Offline          | Off     | Enters (on) or leaves (off) offline mode; see that section below           | Only shown on devices with offline support (hardware RTC and SD card) |

Settings are persisted to NVRAM so they remain in effect across power cycles and battery discharges.

### Offline usage

You should go offline when:

* Using BabyPod away from home
* You don't have an internet connection
* Baby Buddy is down
* Your Wi-Fi connection fails (this switches to offline automatically)

To go offline:

1. On the main menu, press <kbd>◀ Left</kbd> to enter settings.
2. Scroll down to Offline and press <kbd>⊙ Center</kbd> to check it.
3. Press <kbd>▶ Right</kbd> to save.

The main menu will now show ◀☐ at the bottom-right indicating that you're offline.

To go back online, repeat the same steps as above but uncheck the Offline checkbox. The BabyPod will show a progress bar as it reconnects to Baby Buddy and replays everything that happened while you were offline. Once complete, the main menu will now show ◀✓ to show that you're online.

Don't go offline unless you need to. By staying online, you sync data regularly to Baby Buddy.

If you don't see the offline option, your BabyPod is missing either the RTC or the SD card reader, or they failed to initialize.

### Message of the day

You can push a message of the day (MOTD) to a BabyPod. The message can be up to 20 characters in length. To do this:

1. Create a new note in Baby Buddy with your desired text.
2. Tag it with "BabyPod MOTD", creating the tag if it doesn't exist.

BabyPod will consume the MOTD by checking notes every few hours for a note with that tag. If it finds one, it shows a modal to the user with a special chime. The note is deleted so it doesn't get consumed twice. If multiple BabyPods connect to the same instance of Baby Buddy, the first one to pull the note wins.

BabyPod will only try to consume MOTDs if online, there's an RTC available, and it's been a while since the last check. Remember the character LCD only supports a small subset of characters so don't try Unicode emojis or anything outside the lower ASCII character set.

## For developers

### Technical details for offline usage

#### Real-time clock (RTC)
When online, the RTC gets set automatically using `adafruit.io`'s `time` service in the following situations:
- If the date/time is not plausible (year is older than 2024 or newer than 2040). If the device is offline when this happens, this is an error scenario as the RTC's date/time must be plausible for offline support to make sense.
- If there is no record of when the RTC was last set or it's been more than 24 hours since the RTC was last set, unless the device is offline in which case the RTC is assumed to be accurate for now.
- If `NVRAMValues.FORCE_RTC_UPDATE` is `True`, mainly for debugging's sake and it should be set to `False` or entirely unset otherwise.

The Adafruit service is used instead of NTP because the former will autodetect your timezone. It is important that your local timezone match Baby Buddy's timezone or all your offline events will be off by several hours. The RTC cannot be set through the user interface. Instead, all syncing happens through the Adafruit service.

Remember that RTC devices need their own external power source, usually a button-cell battery like a CR1220 battery. Additionally, Adafruit warns users that the battery must be inserted into the breakout board *even if it's dead* or the device may behave unpredictably. However, the RTC battery will likely last for years.

A BabyPod can't work 100% offline in perpetuity. As a strict minimum, it must be online at least once to sync the RTC. More realistically, it needs to be online periodically to sync changes back to Baby Buddy or the BabyPod will be a mostly useless device.

#### Offline activation
Offline is activated:
- By checking "Offline" in the user settings
- If the Wi-Fi connection fails at startup

Offline is deactivated (device goes back online):
- By unchecking "Offline" in the user settings and once all buffered events replay successfully
- If the RTC was never set. You'll need to reboot the BabyPod for it to try an RTC sync again.
- If the required hardware for offline isn't found or fails to initialize

#### Online vs. offline
The main differences between running online vs. offline are:
- When offline, actions that would result in a `POST` instead get serialized to JSON. When flipping the offline option back to online, all the serialized requests get replayed back to the server in the order they were logged.
- Most obviously, when offline the Wi-Fi connection is skipped when powering up. Of course, that means startup is faster too.
- When offline, actions that would result in a `GET` usually have locally stored equivalents, For example, when online, the last feeding time is retrieved from the server and shown on the main menu. When offline, it's pulled from a local state file.
- Timers won't be synced back to the server. However, timed events (feedings, etc.) will have the start and end times captured via the RTC so times and durations will be correct once synced back to the server. That means if you have some automation set up to detect active timers, that automation won't see any timers running locally on an offline BabyPod. It also means if you power off the BabyPod while a timer is running, it will only resume if you were online when the timer was started and when you powered back on.

On the main menu, the bottom-right navigation shows a check if online and unchecked box if offline. That doesn't necessarily mean a positively confirmed connection to the server, just that the offline option is enabled or disabled.

### Building and Deploying

If you want to make changes to the code or use code newer than the latest formal release, do this.

#### `settings.toml`
You need a `settings.toml` at the root of the `CIRCUITPY` drive. The [CircuitPython documentation](https://docs.circuitpython.org/en/latest/docs/environment.html) describes the format of the file.

Here are the possible keys for `settings.toml`. Strings must be quoted and `int`s aren't.

| Key                              | Purpose                                                                                                                                        | Required?                          |
|----------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------|
| `CIRCUITPY_WIFI_SSID_DEFER`      | Your Wi-Fi's SSID (network name)                                                                                                               | Yes, unless `wifi.json` is defined |
| `CIRCUITPY_WIFI_PASSWORD_DEFER`  | Your Wi-Fi's password                                                                                                                          | Yes, unless `wifi.json` is defined |
| `CIRCUITPY_WIFI_INITIAL_CHANNEL` | Your Wi-Fi's access point channel number, or 0 to autodetect with a slower startup penalty                                                     | No                                 |
| `CIRCUITPY_WIFI_TIMEOUT`         | Wi-Fi connection timeout in seconds, or omit for a default of 10                                                                               | No                                 |
| `BABYBUDDY_BASE_URL`             | Baby Buddy's API endpoint URL including trailing slash, like `http://10.1.2.3/api/`                                                            | Yes                                |
| `BABYBUDDY_AUTH_TOKEN`           | Your API user's [authorization token](https://docs.baby-buddy.net/api/#authentication)                                                         | Yes                                |
| `ADAFRUIT_AIO_USERNAME`          | Your `adafruit.io` [API user's username](https://io.adafruit.com/api/docs/#authentication)                                                     | Yes, if your device has an RTC     |
| `ADAFRUIT_AIO_KEY`               | Your `adafruit.io` [API user's key](https://io.adafruit.com/api/docs/#authentication)                                                          | Yes, if your device has an RTC     |
| `DEVICE_NAME`                    | Device name as it should appear in some notes posted to the API; defaults to "BabyPod"                                                         | No                                 |
| `BACKLIGHT_COLOR_FULL`           | Backlight color to use when just powered on or there's been recent user input, expressed as an `int`; defaults to `0xFFFFFF` (white)           | No                                 |
| `BACKLIGHT_COLOR_DIM`            | Backlight color to use when there hasn't been user input for a little while, expressed as an `int`; defaults to `0x808080` (white, but dimmer) | No                                 |
| `BACKLIGHT_COLOR_ERROR`          | Backlight color to use when showing an error message, expressed as an `int`; defaults to `0xFF0000` (red)                                      | No                                 |
| `BACKLIGHT_COLOR_SUCCESS`        | Backlight color to use when showing a success message, expressed as an `int`; defaults to `0x00FF00` (green)                                   | No                                 |
| `USE_SOFT_POWER_CONTROL`         | Whether or not soft power control is enabled. The latest hardware builds require this to be `1` so that's what is by default.                  | Yes                                |

Note the Wi-Fi related settings have a suffix of `_DEFER`. This is because you *don't* want CircuitPython connecting to Wi-Fi automatically as that precedes `code.py` starting and therefore the user doesn't get any startup feedback. Don't use the default CircuitPython Wi-Fi setting names!

Rather than defining the various Wi-Fi settings in `settings.toml`, you can instead put them in a file named `/wifi.json` that looks like this:

```
[
	{
		"ssid": "...",
		"password": ...",
		"channel": n
	},
	...
]
```
List the networks in order of connection preference. The channel number is optional; specify it to only connect on the given channel or omit it entirely for any channel. If both the values in `settings.toml` and the file `/wifi.json` are provided, then the former is attempted first, then the latter.

If you have multiple Wi-Fi networks defined, that implies you're using the BabyPod in multiple physical locations. That further implies that your Baby Buddy instance is accessible on the internet given a LAN address at home won't work when you're at work, for example, short of a VPN or other setup. Keep that in mind if you intend on using your BabyPod in multiple locations.

#### Build environment

These instructions assume you've already built a BabyPod per the instructions at [the hardware repository](https://github.com/skjdghsdjgsdj/babypod-hardware/), including copying a release to the `CIRCUITPY` drive along with setting up `settings.toml`. That is, you have a functioning BabyPod already, and now you want to change the code on it.

To make code changes, you need to do the following to build and deploy them.

1. Clone BabyPod's software GitHub repository first: `git clone https://github.com/skjdghsdjgsdj/babypod-software.git`
	
2. If there is a version of `mpy-cross` compatible with your version of CircuitPython available to [download](https://adafruit-circuit-python.s3.amazonaws.com/index.html?prefix=bin/mpy-cross/), you can use that. If not, compile your own `mpy-cross` executable and put it in your `$PATH`:
	1. [Download and build CircuitPython 9](https://learn.adafruit.com/building-circuitpython), including building submodules. You have to do a full clone; you can't do `git clone --depth` or you'll miss tags and the build will fail. Be sure to use the exact same version that's flashed to the Feather.
	2. [Build `mpy-cross`](https://learn.adafruit.com/building-circuitpython?view=all#build-circuitpython) and put the resulting binary that ends up in `circuitpython/mpy-cross/build/mpy-cross` in your `$PATH`, like copying it to `/usr/local/bin`.
	3. You can delete the cloned `circuitpython` repository if you don't plan on building `mpy-cross` again or doing CircuitPython upgrades.

3. Plug in the Feather to a USB port and verify the `CIRCUITPY` drive shows up. The power switch, if you have one wired across `EN` and `GND`, must be on. Some Feathers don't show up as local drives because they lack the USB support for it. In those cases, the build script won't work right and you'll have to copy files another way, which is usually by Wi-Fi or the serial console. Refer to that Feather's documentation for details.

If you update CircuitPython on the Feather, you will likely need to build a corresponding new `mpy-cross`.

#### macOS and Linux

1. On Linux, edit `build-and-deploy.py` to point to the correct path for your `CIRCUITPY` drive. For now, it assumes you're on macOS. You may also need to edit `/dev/tty.usbmodem*` to point to the correct serial console for CircuitPython. Feel free to make the script less dumb and submit a pull request so others can build on Linux or macOS automatically without needing to edit the script.
2. With the Feather plugged in and turned on, run `build-and-deploy.py`. This script will
	1. Run `mpy-cross` with optimizations on all `.py` files in the project, except for the entry point `code.py`.
	2. With each resulting `.mpy` compiled output, copy it to the Feather's `lib/` directory.
	3. Copy `code.py` to the root of the Feather.
    4. Reboot the Feather.

The build script supports several arguments:
- `--no-compile`: instead of building files with `mpy-cross`, just copy the source `.py` files. This is useful for debugging so errors don't always show as line 1 of a file, but execution is slower. You should only use `--no-compile` when debugging. `code.py` doesn't get compiled regardless.
- `--modules example1 example2`: only builds or copies the given files. For example, use `--modules code` to just copy `code.py`, or `--modules code sdcard` to just copy `code.py` and build/copy `sdcard.py`.
- `--clean`: deletes everything from `lib/` on the `CIRCUITPY` drive and repopulates it with the required Adafruit libraries. This is useful if using `--no-compile` after using compiled files, or vice versa, to ensure the `.py` or `.mpy` files are being used correctly without duplicates. It can take a minute or two to finish.
- `--no-reboot`: don't attempt to reboot the Feather after copying files.
- `--output /path/to/output/`: use the specified path instead of the `CIRCUITPY` drive.
- `--build-release-zip filename.zip`: create a zip file with the given filename containing all compiled files, `code.py`, and `settings.toml.example`; overrides other options.

To set up a brand new BabyPod, all you should need to do is:
1. Erase the flash then re-flash CircuitPython.
2. Create a valid `settings.toml`.
3. Run `build-and-deploy.py --clean` to build all the BabyPod files and also copy the necessary Adafruit modules.

#### Windows

I haven't tried, but you should be able to modify `build-and-deploy.py` with Windows paths. I'm not sure how you can programmatically reboot the Feather without a `tty` device, though.

#### Caveats

##### Manual reboot needed

Unlike CircuitPython's default behavior, the Feather won't reboot automatically when you copy a file to the `CIRCUITPY` drive. This is deliberate to avoid a storm of reboots as compiled files are copied to the Feather. Instead, you can reboot the Feather by:

- With a serial console open, like [`tio`](https://formulae.brew.sh/formula/tio) on macOS, press Ctrl-C to abort the currently running code, then `Ctrl-D` to reboot the Feather. This keeps you connected to the console and importantly means you don't miss any console messages as the Feather starts back up. This is what the build script does too, just programmatically. 
- Running `build-and-deploy.py` which, by default, will reboot the Feather upon completion. Passing `--no-reboot` disables this behavior. The Feather might not reboot via this script unless you have a serial console connected via USB.
- Cycling the power switch, assuming you have one wired across `EN` and `GND`. Not ideal if you have a serial console open because it'll disconnect and even if it reconnects you may miss some startup messages, but if CircuitPython says it "crashed hard", then you need to do this.
- Press the Feather's reset button or jumping the `RESET` pin to `GND`, if accessible.

### Code design and architectural principles

#### General
- Load only the necessary libraries and load them just in time. CircuitPython is slow at importing modules. The build process compiles as much as it can to `.mpy` files for faster loading.
- Get something shown on the display as quickly as possible so the user knows the device powered on properly.
- Try to use one codebase for most Feathers and let the code discover its own environment rather than needing to override pins, I2C addresses, etc. for different hardware.
- Provide abstractions for the devices, and in cases where there could be different hardware variants like different battery monitor chips, use polymorphism to hide the underlying hardware from the application.
- Keep a given screen simple. For example, don't make vertical menus scrollable such that they have more than four items and you have to scroll to see them. Instead, make a user experience flow that negates the need for scrolling.
- There is a global exception handler in `code.py`. If there is an exception raised that isn't caught elsewhere in the call stack, then it's printed to the console and the system sleeps for a minute to allow for a USB debugging window. Then `microcontroller.reset()` is called to force a reboot. This provides some protection against crashes that happen on BabyPods with soft power control where it's inconvenient to reset the Feather given you need a paperclip. Of course that's by design considering, if you have to hard reset the Feather often, something is going quite wrong.

#### Files
| File                     | Purpose                                                                                                                                                                                                                                                                     |
|--------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `api.py`                 | Connectivity to Wi-Fi and Baby Buddy                                                                                                                                                                                                                                        |
| `battery_monitor.py`     | Abstraction of LC709203F and MAX17048 battery monitors with autoselection of the appropriate chip. Current hardware builds use MAX17048 so LC709203F might eventually be deprecated and then removed.                                                                       |
| `build-and-deploy.py`    | Build script that uses `mpy-cross` to compile the code and copy it to the `CIRCUITPY` drive. This doesn't end up on the BabyPod itself, just your computer.                                                                                                                 |
| `code.py`                | CircuitPython's entry point                                                                                                                                                                                                                                                 |
| `devices.py`             | Dependency injection of the various device abstractions instead of passing a million arguments around                                                                                                                                                                       |
| `external_rtc.py`        | Abstraction of the real-time clock (RTC)                                                                                                                                                                                                                                    |
| `flow.py`                | Drives the UX                                                                                                                                                                                                                                                               |
| `lcd.py`                 | Abstraction of the LCD text and backlight including defining special characters like arrows. Implementations cover the Sparkfun LCD and the Adafruit character backpack, but the former is used for new builds as it's much simpler to wire, faster to render, and cheaper. |
| `nvram.py`               | Persists values in NVRAM across reboots                                                                                                                                                                                                                                     |
| `offline_event_queue.py` | Queue that buffers up API requests that would happen if the device was online and serializes them to JSON on the microSD card                                                                                                                                               |
| `offline_state.py`       | Stores some state needed for offline use to the microSD card, like last feeding that happened locally and when the RTC was last synced                                                                                                                                      |
| `periodic_chime.py`      | Logic for when to periodically nudge the user during feedings, tummy times, etc.                                                                                                                                                                                            |
| `piezo.py`               | Abstraction of the piezo, including allowing playback of tones by name rather than specifying them externally                                                                                                                                                               |
| `power_control.py`       | Provides soft shutdown and wakeup capability, if so enabled in `settings.toml`                                                                                                                                                                                              |
| `sdcard.py`              | Abstraction of the microSD card reader                                                                                                                                                                                                                                      |
| `settings.py`            | User-accessible settings backed by NVRAM values                                                                                                                                                                                                                             |
| `settings.toml.example`  | A template for creating your own `settings.toml`, necessary for configuration for all BabyPods.                                                                                                                                                                             |
| `ui_components.py`       | Definition of various UI components, detailed below                                                                                                                                                                                                                         |
| `user_input.py`          | Abstraction of the rotary encoder, which takes into account the 90° physical rotation when mounted in the enclosure                                                                                                                                                         |
| `util.py`                | Helper methods, like a workaround for [a CircuitPython bug that doesn't support UTC ISO-formatted timestamps](https://github.com/adafruit/Adafruit_CircuitPython_datetime/issues/22)                                                                                        |

#### UI Components

| Class                | Purpose                                                                                        |
|----------------------|------------------------------------------------------------------------------------------------|
| `UIComponent`        | Base class                                                                                     |
| `ActiveTimer`        | A timer that counts up in real-time, including periodic piezo chimes                           |
| `NumericSelector`    | Input for a float with upper/lower bounds and increment counts                                 |
| `VerticalMenu`       | User selection a single menu item from up to four options                                      |
| `VerticalCheckboxes` | Like `VerticalMenu`, but each item is preceded with a checkbox                                 |
| `BooleanPrompt`      | Like `VerticalMenu`, but allows for one selection of exactly two options and returns a boolean |
| `ProgressBar`        | Shows a progress bar; unlike the other components, `render_and_wait()` doesn't block           |
| `Modal`              | Shows a message and a Dismiss button                                                           |

### Tips and Tricks

#### Feeding menu simplification

You can hide types of feeding options (breast milk, fortified breast milk, formula, and solid food) with a bitmask stored in NVRAM. If only one is enabled, that type is autoselected and the user isn't prompted at all for the food type.

The values are:

| Food type             | Value |
|-----------------------|-------|
| Breast milk           | `0x1` |
| Fortified breast milk | `0x2` |
| Formula               | `0x4` |
| Solid food            | `0x8` |

Calculate the bitmask of the options you want by adding the values. For example, to only show the two types of breast milk, use `0x1 + 0x2`, or to show just breast milk, use `0x1`. Then, in the REPL serial console, store the value in NVRAM like this:

```
import nvram
nvram.NVRAMValues.ENABLED_FOOD_TYPES_MASK.write(value)
```

...where `value` is the bitmask. There's no user interface to do this for now, but being in NVRAM, this will persist across reboots.

#### Accessing the microSD card for debugging
Sometimes when developing for the BabyPod you want to see what's actually written on the SD card. Newer hardware revisions use an embedded SD card rather than a removable one in a reader, so you can't just plug it into your computer. Even if you _are_ using a removable card, you'd have to disassemble the BabyPod to get at it.

So, you can read and write to and from the SD card via the REPL console. To do this:
- With the BabyPod on and connected by USB, [open a serial console](https://learn.adafruit.com/welcome-to-circuitpython/kattni-connecting-to-the-serial-console).
- Press Ctrl-C to enter the REPL.
- Run the following to mount the microSD card to `/sd`:
  ```
  import sdcard
  sdcard.SDCard()
  ```
- Do whatever you want to files in `/sd`. For example, to delete the offline state:
  ```
  import os
  os.unlink("/sd/state.json")
  ```
  
If you are writing files this way, remember to flush file handles or your changes may not get persisted to the filesystem.

## Known limitations and bugs

Please contribute and submit pull requests if you can help!

- `build-and-deploy.py` assumes a macOS environment. Linux is pretty close if not identical, but untested. Windows will be very different unless you're doing some travesty like Cygwin.
- If the LCD fails to initialize, you won't see any error on the screen...obviously. But there's also no error tone or other suggestion to the user that initialization failed other than a blank screen. The LCD will also fail to initialize if I2C is broken somehow, which could be caused by another device in the chain like the rotary encoder or RTC.
- Startup takes a few seconds, mostly due to waiting for Wi-Fi to connect and loading imports. Startup is a bit faster if waking from deep sleep vs. a cold start.
- Wi-Fi is periodically slow to connect as are network requests in general. Sometimes it takes a couple seconds, but other times 10 or 15 seconds.
- The rotary encoder doesn't always respond on the first input. There is retry logic in the abstraction for that reason.
- Some things are hardcoded, like chime intervals during active timers, instead of either user-configurable or defined in `settings.toml`. Considering babies, you know, change over time, this isn't ideal because things like breast feedings can take a different amount of time as the baby grows and the hardcoded times aren't as useful.
- Only one child is supported. If multiple are defined in Baby Buddy, the first is used. If the child ID changes after the BabyPod first detects it, the value it stored in NVRAM will be wrong and needs to be manually cleared to be rediscovered.
- Writing to the Adafruit LCD is slow, but not unbearably so. The Sparkfun LCD is faster and is used for new builds, so this isn't really relevant anymore.
- On MAX17048 battery monitor chips, the battery percent isn't immediately available and is hidden until the chip reports a plausible (non-None, >0) value. If the BabyPod starts up really quickly, mainly when offline, the main menu might not show the battery level.
- If no battery is connected, it may get reported as 100% or other clearly implausible numbers. This only poses a problem when you're debugging because in normal use, you'd have a battery connected.
- The Adafruit ESP32-S3 Feathers don't allow CircuitPython to read the `VBUS` pin to know if the battery is charging, so the battery monitor reports an indeterminate `None` status instead of `True` or `False`. On such Feathers, the BabyPod will nag you to turn it off even if it's plugged in and charging. A partial workaround is checking for a USB *data* connection, and if one exists, assuming the battery is charging. Some other Feathers do support reading this pin, notably the Unexpected Maker ESP32-S3 Feather.
- Presumably, the code doesn't know if the battery health is degrading or knowing when it's degraded enough to need replacement. Perhaps there's a way of tracking charging cycles and guessing, even if the battery monitor chip can't tell?
- Baby Buddy should be set to your local timezone, not UTC, and if you're travelling across time zones, the data could be confusing. This is particularly important when working offline.

## Wishlist

Please contribute and submit pull requests if you can help! But some of these things I'm not sure CircuitPython can do.

- Have the build process somehow merge everything but `code.py` into a single `.mpy` to make imports faster, or not necessary in the first place.
- Connect to Wi-Fi asynchronously! The slowest part of startup is usually waiting for Wi-Fi, but every selection from the main menu will need a connection; may as well let the menu render and then connect to Wi-Fi in the background so the experience seems faster.
- Support multiple children, although if there's only one, don't require the user to select him/her. Also add a way for the selected child to be changed easily if the ID changes in Baby Buddy. Right now, the API is queried for the list of children, but if there's more than one, only the first is used, and if the ID changes, you need to clear the NVRAM value manually for the ID to be rediscovered.
- Have the build process burn all the code into the CircuitPython image, and the imports go from slow to near-instant. That's no small feat but could be really useful. Speaking from experience, it's a colossal pain to set up a CircuitPython build environment for ESP32.
- Better error handling and recovery.
- Use interrupts for rotary encoder events instead of polling in a loop. I really want this one, but CircuitPython's design team has made it clear they prefer `async` vs. true interrupts, which isn't really the same thing. The rotary encoder breakout board does support actual hardware interrupts, but you still need to poll for one instead of just being...well, interrupted.
- On devices with multiple CPU cores, use secondary cores for multithreading to do things in the background, like API requests. Same caveat as above: I don't think it'll happen. The second core in the ESP32-S3 is not used by CircuitPython userspace code.
- Localization stuff:
  - Fluid ounces are the assumed unit for pumping. Baby Buddy itself seems unitless, so this could be a localization option for `settings.toml` to change the units shown in the pumping interface. 0.5 increments are used too, so changing units might call for a different increment.
  - Support 24-hour time in addition to AM/PM. Probably straightforward to do, actually, but only if someone actually requests it.
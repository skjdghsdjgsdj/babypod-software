# BabyPod

This repository is just for the CircuitPython code that runs on the hardware. See the [`babypod-hardware`](https://github.com/skjdghsdjgsdj/babypod-hardware/) repository for the hardware setup and more general information about the project.

You need to install [Baby Buddy](https://docs.baby-buddy.net/setup/deployment/) for this to work. It can be installed on your local network or on the internet (AWS, etc.), so long as it's reachable through your Wi-Fi network. BabyPod can work offline, but not indefinitely; it's still intended to sync at least periodically, if not in real-time, with Baby Buddy.

## Features

### General
- Simple text-based interface that can be scrolled with the rotary encoder's wheel or the up/down buttons. Select and Right buttons are usually interchangeable, and Left usually means cancel or back. The design objective is you can give the BabyPod to someone with no experience using it and they can understand how it works easily.
- Backlight color and piezo are used for interface feedback, like successful saving of data back to Baby Buddy, reporting of errors, periodic chimes during timers, low battery warnings, etc.
- Some user-configurable options are exposed directly through the interface instead of messing with `settings.toml`, like turning off the piezo if it bothers your baby. The values are stored in NVRAM to persist across reboots.
- Battery percentage shown on most screens and updates periodically.
- Backlight dims after inactivity to save power, although you should turn off the BabyPod when not using it anyway.
- Information is contextual and non-relevant information isn't shown. For example, when feeding solid food, no bottle options are shown.
- Support for both hard power switches wired across `EN` and `GND` and a soft power switch by holding the center button to enter deep sleep and pressing it to wake.

### Offline support
In scenarios where you're away from your predefined Wi-Fi location, you can go offline. When you go offline, actions get buffered to JSON files on a microSD card, and when you go online, they get replayed. You should only go offline when you're forced to; otherwise, in the event the microSD card gets corrupted or there's some other issue, you could lose all the buffered actions you took while offline.

Successful events replays are deleted from the microSD card as each one is successfully replayed when going back online. If a specific event fails to play back, playback will stop at that point in history and subsequent events are kept on the microSD card, and the device stays offline.

#### Hardware requirements
For offline support to be available, the BabyPod must both have the following additional hardware which is assumed in the hardware build documentation:

- A PCF8523-based real-time clock (RTC) at I2C address `0x68`.
- An SPI-based microSD card reader, or [something that looks like one to CircuitPython](https://www.adafruit.com/product/4899) with the `CS` pin wired to `D10` and a FAT32-formatted microSD card inserted. The capacity and speed are pretty much irrelevant because only a few hundred KB of JSON are likely to be written.

You have two options for controlling power. They are mutually exclusive!

- Connect the `INT` pin on the rotary encoder to `D11`. If these pins aren't wired together, then pressing and holding the center button does nothing and you must have a separate hard power switch.
- Wire a [physical switch](https://www.adafruit.com/product/3870) across `EN` and `GND`. When `EN` and `GND` are connected, the 3.3V regulator is disabled and power is cut to the Feather's processor. However, STEMMA QT devices stay on! To avoid this, wire the first device normally connected to the STEMMA QT port to `3V` (red), `GND` (black), `SDA` (blue), and `SCL` (yellow).

If you don't wire either if these power options, the BabyPod will stay on until the battery drains! If you wire both, then both will work, but it will be confusing because you can turn off the BabyPod with the hard power switch but it won't turn back on with soft power control.

If either the RTC isn't available or the microSD reader fails to initialize, offline support is disabled (the user isn't shown the option) and the BabyPod is forced to be online.

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

### Feedings
- Record feedings, including start and end times, food types, which breasts(s) were used for feeding, etc.
- A live timer that runs to keep track of how long the current feeding session has been, with chimes at every 15 minutes as a reminder to switch breasts, then every minute once 30 minutes have elapsed in case you forgot to stop the timer.
- Last feeding is shown on the main menu for quick reference.

### Diaper changes
- Record diaper changes, including if they were wet, solid or both.

### Pumping
- Record pumping sessions, including amount pumped.

### Tummy Time
- Record tummy time sessions, including durations.

### Sleep
- Record sleep (naps and night sleep). Baby Buddy's settings are authoritative on whether the sleep counts as a nap or not.

### Options
User-configurability that persists across power cycles of:

- Switching between online and offline (online by default)
- Enabling or disabling the piezo (on by default)

## Building and Deploying

### `settings.toml`
You need a `settings.toml` at the root of the `CIRCUITPY` drive. The [CircuitPython documentation](https://docs.circuitpython.org/en/latest/docs/environment.html) describes the format of the file.

Here are the possible keys for `settings.toml`. Strings must be quoted and `int`s aren't.

| Key                              | Purpose                                                                                                                                                                                                                                                                                                                                                                                               | Required?                          |
|----------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------|
| `CIRCUITPY_WIFI_SSID_DEFER`      | Your Wi-Fi's SSID (network name)                                                                                                                                                                                                                                                                                                                                                                      | Yes, unless `wifi.json` is defined |
| `CIRCUITPY_WIFI_PASSWORD_DEFER`  | Your Wi-Fi's password                                                                                                                                                                                                                                                                                                                                                                                 | Yes, unless `wifi.json` is defined                                |
| `CIRCUITPY_WIFI_INITIAL_CHANNEL` | Your Wi-Fi's access point channel number, or 0 to autodetect with a slower startup penalty                                                                                                                                                                                                                                                                                                            | No                                 |
| `CIRCUITPY_WIFI_TIMEOUT`         | Wi-Fi connection timeout in seconds, or omit for a default of 10                                                                                                                                                                                                                                                                                                                                      | No                                 |
| `BABYBUDDY_BASE_URL`             | Baby Buddy's API endpoint URL including trailing slash, like `http://10.1.2.3/api/`                                                                                                                                                                                                                                                                                                                   | Yes                                |
| `BABYBUDDY_AUTH_TOKEN`           | Your API user's [authorization token](https://docs.baby-buddy.net/api/#authentication)                                                                                                                                                                                                                                                                                                                | Yes                                |
| `ADAFRUIT_AIO_USERNAME`          | Your `adafruit.io` [API user's username](https://io.adafruit.com/api/docs/#authentication)                                                                                                                                                                                                                                                                                                            | Yes, if your device has an RTC     |
| `ADAFRUIT_AIO_KEY`               | Your `adafruit.io` [API user's key](https://io.adafruit.com/api/docs/#authentication)                                                                                                                                                                                                                                                                                                                 | Yes, if your device has an RTC     |
| `DEVICE_NAME`                    | Device name as it should appear in some notes posted to the API; defaults to "BabyPod"                                                                                                                                                                                                                                                                                                                | No                                 |
| `BACKLIGHT_COLOR_FULL`           | Backlight color to use when just powered on or there's been recent user input, expressed as an `int`; defaults to `0xFFFFFF` (white)                                                                                                                                                                                                                                                                  | No                                 |
| `BACKLIGHT_COLOR_DIM`            | Backlight color to use when there hasn't been user input for a little while, expressed as an `int`; defaults to `0x808080` (white, but dimmer)                                                                                                                                                                                                                                                        | No                                 |
| `BACKLIGHT_COLOR_ERROR`          | Backlight color to use when showing an error message, expressed as an `int`; defaults to `0xFF0000` (red)                                                                                                                                                                                                                                                                                             | No                                 |
| `BACKLIGHT_COLOR_SUCCESS`        | Backlight color to use when showing a success message, expressed as an `int`; defaults to `0x00FF00` (green)                                                                                                                                                                                                                                                                                          | No                                 |

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

### Requirements

These instructions assume you've already built a BabyPod per the instructions at [the hardware repository](https://github.com/skjdghsdjgsdj/babypod-hardware/), including copying a release to the `CIRCUITPY` drive along with setting up `settings.toml`. That is, you have a functioning BabyPod already, and now you want to change the code on it.

To make code changes, you need to do the following to build and deploy them.

1. Clone BabyPod's software GitHub repository first: `git clone https://github.com/skjdghsdjgsdj/babypod-software.git`
	
2. If there is a version of `mpy-cross` compatible with your version of CircuitPython available to [download](https://adafruit-circuit-python.s3.amazonaws.com/index.html?prefix=bin/mpy-cross/), you can use that. If not, compile your own `mpy-cross` executable and put it in your `$PATH`:
	1. [Download and build CircuitPython 9](https://learn.adafruit.com/building-circuitpython), including building submodules. You have to do a full clone; you can't do `git clone --depth` or you'll miss tags and the build will fail. Be sure to use the exact same version that's flashed to the Feather.
	2. [Build `mpy-cross`](https://learn.adafruit.com/building-circuitpython?view=all#build-circuitpython) and put the resulting binary that ends up in `circuitpython/mpy-cross/build/mpy-cross` in your `$PATH`, like copying it to `/usr/local/bin`.
	3. You can delete the cloned `circuitpython` repository if you don't plan on building `mpy-cross` again or doing CircuitPython upgrades.

3. Plug in the Feather to a USB port and verify the `CIRCUITPY` drive shows up. The power switch, if you have one wired across `EN` and `GND`, must be on. Some Feathers don't show up as local drives because they lack the USB support for it. In those cases, the build script won't work right and you'll have to copy files another way, which is usually by Wi-Fi or the serial console. Refer to that Feather's documentation for details.

If you update CircuitPython on the Feather, you will likely need to build a corresponding new `mpy-cross`.

### macOS and Linux

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

### Windows

I haven't tried, but you should be able to modify `build-and-deploy.py` with Windows paths. I'm not sure how you can programmatically reboot the Feather without a `tty` device, though.

### Caveats

#### Manual reboot needed

Unlike CircuitPython's default behavior, the Feather won't reboot automatically when you copy a file to the `CIRCUITPY` drive. This is deliberate to avoid a storm of reboots as compiled files are copied to the Feather. Instead, you can reboot the Feather by:

- With a serial console open, like [`tio`](https://formulae.brew.sh/formula/tio) on macOS, press Ctrl-C to abort the currently running code, then `Ctrl-D` to reboot the Feather. This keeps you connected to the console and importantly means you don't miss any console messages as the Feather starts back up. This is what the build script does too, just programmatically. 
- Running `build-and-deploy.py` which, by default, will reboot the Feather upon completion. Passing `--no-reboot` disables this behavior. The Feather might not reboot via this script unless you have a serial console connected via USB.
- Cycling the power switch, assuming you have one wired across `EN` and `GND`. Not ideal if you have a serial console open because it'll disconnect and even if it reconnects you may miss some startup messages, but if CircuitPython says it "crashed hard", then you need to do this.
- Press the Feather's reset button or jumping the `RESET` pin to `GND`, if accessible.

## Code design and architectural principles

### General
- Load only the necessary libraries and load them just in time. CircuitPython is slow at importing modules. The build process compiles as much as it can to `.mpy` files for faster loading.
- Get something shown on the display as quickly as possible so the user knows the device powered on properly.
- Try to use one codebase for most Feathers and let the code discover its own environment rather than needing to override pins, I2C addresses, etc. for different hardware.
- Provide abstractions for the devices, and in cases where there could be different hardware variants like different battery monitor chips, use polymorphism to hide the underlying hardware from the application.
- Keep a given screen simple. For example, don't make vertical menus scrollable such that they have more than four items and you have to scroll to see them. Instead, make a user experience flow that negates the need for scrolling.
- There is a global exception handler in `code.py`. If there is an exception raised that isn't caught elsewhere in the call stack, then it's printed to the console and the system sleeps for a minute to allow for a USB debugging window. Then `microcontroller.reset()` is called to force a reboot. This provides some protection against crashes that happen on BabyPods with soft power control because there's no exposed reset button and USB debugging might not be available, thus requiring you to unscrew the BabyPod and physically press the Feather's reset button.

### Files
| File                     | Purpose                                                                                                                                                                              |
|--------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `api.py`                 | Connectivity to Wi-Fi and Baby Buddy                                                                                                                                                 |
| `battery_monitor.py`     | Abstraction of LC709203F and MAX17048 battery monitors with autoselection of the appropriate chip                                                                                    |
| `build-and-deploy.py`    | Build script that uses `mpy-cross` to compile the code and copy it to the `CIRCUITPY` drive                                                                                          |
| `code.py`                | CircuitPython's entry point                                                                                                                                                          |
| `devices.py`             | Dependency injection of the various device abstractions instead of passing a million arguments around                                                                                |
| `external_rtc.py`        | Abstraction of the real-time clock (RTC)                                                                                                                                             |
| `flow.py`                | Drives the UX                                                                                                                                                                        |
| `lcd.py`                 | Abstraction of the LCD text and backlight including defining special characters like arrows                                                                                          |
| `nvram.py`               | Persists values in NVRAM across reboots                                                                                                                                              |
| `offline_event_queue.py` | Queue that buffers up API requests that would happen if the device was online and serializes them to JSON on the microSD card                                                        |
| `offline_state.py`       | Stores some state needed for offline use to the microSD card, like last feeding that happened locally and when the RTC was last synced                                               |
| `periodic_chime.py`      | Logic for when to periodically nudge the user during feedings, tummy times, etc.                                                                                                     |
| `piezo.py`               | Abstraction of the piezo, including allowing playback of tones by name rather than specifying them externally                                                                        |
| `power_control.py`       | Provides soft shutdown and wakeup capability, if so enabled in `settings.toml`                                                                                                       |
| `sdcard.py`              | Abstraction of the microSD card reader                                                                                                                                               |
| `settings.py`            | User-accessible settings backed by NVRAM values                                                                                                                                      |
| `ui_components.py`       | Definition of various UI components, detailed below                                                                                                                                  |
| `user_input.py`          | Abstraction of the rotary encoder, which takes into account the 90° physical rotation when mounted in the enclosure                                                                  |
| `util.py`                | Helper methods, like a workaround for [a CircuitPython bug that doesn't support UTC ISO-formatted timestamps](https://github.com/adafruit/Adafruit_CircuitPython_datetime/issues/22) |

### UI Components

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

## Tips and Tricks

### Feeding menu simplification

You can hide types of feeding options (breast milk, fortified breast milk, formula, and solid food) with a bitmask stored in NVRAM. If only one is enabled, the user isn't prompted at all for the food type.

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

...where `value` is the bitmask. There's no user interface to do this for now, but being in NVRAM, this will
persist across reboots.

### Accessing the microSD card for debugging
Most obviously, you can always just remove the microSD card from your device, if it's accessible and powered off, then put it in your computer. But if that's not feasible, like you don't want to disassemble the BabyPod from its enclosure, you can access the microSD card via the REPL console. You also might be using a [device with non-removable storage](https://www.adafruit.com/product/4899).

To do this:
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

- `build-and-deploy.py` assumes a macOS environment.
- Startup takes a few seconds, mostly due to waiting for Wi-Fi to connect and loading imports. Startup is a bit faster if waking from deep sleep vs. a cold start.
- Wi-Fi is periodically slow to connect as are network requests in general. Sometimes it takes a couple seconds, but other times 10 or 15 seconds.
- The rotary encoder doesn't always respond on the first input. There is retry logic in the abstraction for that reason.
- Some things are hardcoded, like chime intervals during active timers, instead of either user-configurable or defined in `settings.toml`.
- Only one child is supported. If multiple are defined in Baby Buddy, the first is used.
- Writing to the Adafruit LCD is slow, but not unbearably so. The Sparkfun LCD is faster.
- On MAX17048 battery monitor chips, the battery percent isn't immediately available and is hidden until the chip reports a plausible (non-None, >0) value.
- If no battery is connected, it may get reported as 100% or other clearly implausible numbers. This only poses a problem when you're debugging because in normal use, you'd have a battery connected.
- Some Feathers don't allow CircuitPython to read the `VBUS` pin to know if the battery is charging, so the battery monitor reports an indeterminate `None` status instead of `True` or `False`. On such Feathers, the BabyPod will nag you to turn it off even if it's plugged in and charging. A partial workaround is checking for a USB *data* connection, and if one exists, assuming the battery is charging.
- Presumably, the code doesn't know if the battery health is degrading or knowing when it's degraded enough to need replacement. Perhaps there's a way of tracking charging cycles and guessing, even if the battery monitor chip can't tell?
- Baby Buddy should be set to your local timezone, not UTC, and if you're travelling across time zones, the data could be confusing. This is particularly important when working offline.

## Wishlist

Please contribute and submit pull requests if you can help! But some of these things I'm not sure CircuitPython can do.

- Have the build process somehow merge everything but `code.py` into a single `.mpy` to make imports faster, or not necessary in the first place.
- Connect to Wi-Fi asynchronously! The slowest part of startup is usually waiting for Wi-Fi, but every selection from the main menu will need a connection; may as well let the menu render and then connect to Wi-Fi in the background so the experience seems faster.
- Support multiple children, although if there's only one, don't require the user to select him/her. Right now, the API is queried for the list of children, but if there's more than one, only the first is used.
- Have the build process burn all the code into the CircuitPython image, and the imports go from slow to near-instant. That's no small feat but could be really useful.
- Better error handling and recovery.
- Use interrupts for rotary encoder events instead of polling in a loop. I really want this one, but CircuitPython's design seems antithetical to interrupts. The encoder breakout board does support interrupts, but you still need to poll for one instead of just being...well, interrupted.
- On devices with multiple CPU cores, use secondary cores for multithreading to do things in the background, like API requests. Same caveat as above: I don't think it'll happen.
- Localization stuff:
  - Fluid ounces are the assumed unit for pumping. Baby Buddy itself seems unitless, so this could be a localization option for `settings.toml` to change the units shown in the pumping interface. 0.5 increments are used too, so changing units might call for a different increment.
  - Support 24-hour time in addition to AM/PM.
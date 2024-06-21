# BabyPod

This repository is just for the CircuitPython code that runs on the hardware. See the [`babypod-hardware`](https://github.com/skjdghsdjgsdj/babypod-hardware/) repository for the hardware setup and more general information about the project.

You need to install [Baby Buddy](https://docs.baby-buddy.net/setup/deployment/) for this to work. It can be installed on your local network or on the internet (AWS, etc.), so long as it's reachable through your Wi-Fi network. BabyPod can work offline, but not indefinitely; it's still intended to sync at least periodically, if not in real-time, with Baby Buddy.

## Features

### General
- Simple text-based interface that can be scrolled with the rotary encoder's wheel or the up/down buttons. Select and Right buttons are usually interchangeable, and Left usually means cancel or back. The design objective is you can give the BabyPod to someone with no experience using it and they can understand how it works easily.
- Backlight color and piezo are used for interface feedback, like successful saving of data back to Baby Buddy, reporting of errors, periodic chimes during timers, low battery warnings, etc.
- Some user-configurable options are exposed directly through the interface instead of messing with `settings.toml`, like turning off the piezo if it bothers your baby. The values are stored in NVRAM to persist across reboots. Protip: don't turn off the backlight on [backlight-negative LCDs](https://www.adafruit.com/product/498).
- Battery percentage shown on most screens and updates periodically.
- Backlight dims after inactivity to save power, although you should turn off the BabyPod when not using it anyway.
- Information is contextual and non-relevant information isn't shown. For example, when feeding solid food, no bottle options are shown.

### Offline support
In scenarios where you're away from your predefined Wi-Fi location, you can go offline. When you go offline, actions get buffered to JSON files on a microSD card, and when you go online, they get replayed. You should only go offline when you're forced to; otherwise, in the event the microSD card gets corrupted or there's some other issue, you could lose all the buffered actions you took while offline.

Successful events replays are deleted from the microSD card as each one is successfully replayed when going back online. If a specific event fails to play back, playback will stop at that point in history and subsequent events are kept on the microSD card, and the device stays offline.

#### Hardware requirements
For offline support to be available, the BabyPod must both have the following additional hardware. The easy way to get both these things is by using an [Adalogger FeatherWing](https://www.adafruit.com/product/2922). However, you can use other breakout boards if you want, so long as they meet the criteria.
- A PCF8523-based real-time clock (RTC) at I2C address `0x68`.
- An SPI-based microSD card reader with the `CS` pin wired to `D10` and a FAT32-formatted microSD card inserted. The capacity and speed are pretty much irrelevant because only a few hundred KB of JSON are likely to be written.

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
- Timers won't be synced back to the server. However, timed events (feedings, etc.) will have the start and end times captured via the RTC so times and durations will be correct once synced back to the server. That means if you have some automation set up to detect active timers, that automation won't see any timers running locally on an offline BabyPod.

On the main menu, the bottom-right navigation shows a check if online and unchecked box if offline. That doesn't necessarily mean a positively confirmed connection to the server, just that the offline option is enabled or disabled.

### Feedings
- Record feedings, including start and end times, food types, which breasts(s) were used for feeding, etc.
- A live timer that runs to keep track of how long the current feeding session has been, with chimes at every 15 minutes as a reminder to switch breasts, then every minute once 30 minutes have elapsed in case you forgot to stop the timer.

### Diaper changes
- Record diaper changes, including if they were wet, solid or both.

### Pumping
- Record pumping sessions, including amount pumped.

### Tummy Time
- Record tummy time sessions, including durations.

### Options
User-configurability that persists across power cycles of:

- Switching between online and offline (online by default)
- Enabling or disabling the piezo (on by default)
- LCD backlight at max brightness then dimming after timeout (default), or dim by default

## Building and Deploying

### `settings.toml`
You need a `settings.toml` at the root of the `CIRCUITPY` drive. The [CircuitPython documentation](https://docs.circuitpython.org/en/latest/docs/environment.html) describes the format of the file.

Here are the possible keys for `settings.toml`. Strings must be quoted and `int`s aren't.

| Key                              | Purpose                                                                                    | Required?                      |
|----------------------------------|--------------------------------------------------------------------------------------------|--------------------------------|
| `CIRCUITPY_WIFI_SSID_DEFER`      | Your Wi-Fi's SSID (network name)                                                           | Yes                            |
| `CIRCUITPY_WIFI_PASSWORD_DEFER`  | Your Wi-Fi's password                                                                      | Yes                            |
| `CIRCUITPY_WIFI_INITIAL_CHANNEL` | Your Wi-Fi's access point channel number, or 0 to autodetect with a slower startup penalty | No                             |
| `CIRCUITPY_WIFI_TIMEOUT`         | Wi-Fi connection timeout in seconds, or omit for a default of 10                           | No                             |
| `BABYBUDDY_BASE_URL`             | Baby Buddy's API endpoint URL including trailing slash, like `http://10.1.2.3/api/`        | Yes                            |
| `BABYBUDDY_AUTH_TOKEN`           | Your API user's [authorization token](https://docs.baby-buddy.net/api/#authentication)     | Yes                            |
| `ADAFRUIT_AIO_USERNAME`          | Your `adafruit.io` [API user's username](https://io.adafruit.com/api/docs/#authentication) | Yes, if your device has an RTC |
| `ADAFRUIT_AIO_KEY`               | Your `adafruit.io` [API user's key](https://io.adafruit.com/api/docs/#authentication)      | Yes, if your device has an RTC |

Note the Wi-Fi related settings have a suffix of `_DEFER`. This is because you *don't* want CircuitPython connecting to Wi-Fi automatically as that precedes `code.py` starting and therefore the user doesn't get any startup feedback. Don't use the default CircuitPython Wi-Fi setting names!

### Requirements

These instructions assume you've already built a BabyPod per the instructions at [the hardware repository](https://github.com/skjdghsdjgsdj/babypod-hardware/), including copying a release to the `CIRCUITPY` drive along with setting up `settings.toml`. That is, you have a functioning BabyPod already, and now you want to change the code on it.

To make code changes, you need to do the following to build and deploy them.

1. Clone BabyPod's software GitHub repository first: `git clone https://github.com/skjdghsdjgsdj/babypod-software.git`

2. Plug in the Feather to a USB port and verify the `CIRCUITPY` drive shows up. The power switch must be on. Some Feathers don't show up as local drives because they lack the USB support for it. In those cases, the build script won't work right and you'll have to copy files another way, which is usually by Wi-Fi or the serial console. Refer to that Feather's documentation for details.
	
3. Compile your own `mpy-cross` executable and put it in your `$PATH`. As of this documentation, there's no prebuilt `mpy-cross` for CircuitPython 9, and older releases are not backwards-compatible. Fortunately you only need to build `mpy-cross` once because it takes a long time. To do this:
	1. [Download and build CircuitPython 9](https://learn.adafruit.com/building-circuitpython), including building submodules. Note you have to do a full clone; you can't do `git clone --depth` or you'll miss tags and the build will fail. Be sure to use the exact same version that's flashed to the Feather.
	2. [Build `mpy-cross`](https://learn.adafruit.com/building-circuitpython?view=all#build-circuitpython) and put the resulting binary that ends up in `circuitpython/mpy-cross/build/mpy-cross` in your `$PATH`, like copying it to `/usr/local/bin`.
	3. You can delete the cloned `circuitpython` repository if you don't plan on building `mpy-cross` again or doing CircuitPython upgrades.

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
- `--modules`: only builds or copies the given files. For example, use `--modules code` to just copy `code.py`, or `--modules code sdcard` to just copy `code.py` and build/copy `sdcard.py`.
- `--clean`: deletes everything from `lib/` on the `CIRCUITPY` drive and repopulates it with the required Adafruit libraries. This is useful if using `--no-compile` after using compiled files, or vice versa, to ensure the `.py` or `.mpy` files are being used correctly without duplicates. It can take a minute or two to finish.
- `--no-reboot`: don't attempt to reboot the Feather after copying files.

To set up a brand new BabyPod, all you should need to do is:
1. Erase the flash then re-flash CircuitPython.
2. Create a valid `settings.toml`.
3. Run `build-and-deploy.py --clean` to build all the BabyPod files and also copy the necessary Adafruit modules.

### Windows

I haven't tried, but you should be able to modify `build-and-deploy.py` with Windows paths. I'm not sure how you can programmatically reboot the Feather without a `tty` device, though.

### Caveats

#### Manual reboot needed

Unlike CircuitPython's default behavior, the Feather won't reboot automatically when you copy a file to the `CIRCUITPY` drive. This is deliberate to avoid a storm of reboots as compiled files are copied to the Feather. Instead, you can reboot the Feather by:

- Running `build-and-deploy.py` which, by default, will reboot the Feather upon completion. Passing `--no-reboot` disables this behavior.
- With a serial console open, like [`tio`](https://formulae.brew.sh/formula/tio) on macOS, press Ctrl-C to abort the currently running code, then `Ctrl-D` to reboot the Feather. This keeps you connected to the console and importantly means you don't miss any console messages as the Feather starts back up. This is what the build script does too, just programmatically.
- Cycling the power switch. Not ideal if you have a serial console open because it'll disconnect and even if it reconnects you may miss some startup messages, but if CircuitPython says it "crashed hard", then you need to do this.
- Press the Feather's reset button, if it's accessible.

## Code design and architectural principles

### General
- Load only the necessary libraries and load them just in time. CircuitPython is slow at importing modules. The build process compiles as much as it can to `.mpy` files for faster loading.
- Get something shown on the display as quickly as possible so the user knows the device powered on properly.
- Try to use one codebase for most Feathers and let the code discover its own environment rather than needing to override pins, I2C addresses, etc. for different hardware.
- Provide abstractions for the devices, and in cases where there could be different hardware variants like different battery monitor chips, use polymorphism to hide the underlying hardware from the application.
- Keep a given screen simple. For example, don't make vertical menus scrollable such that they have more than four items and you have to scroll to see them. Instead, make a user experience flow that negates the need for scrolling.

### Files
| File                     | Purpose                                                                                                                                |
|--------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| `api.py`                 | Connectivity to Wi-Fi and Baby Buddy                                                                                                   |
| `backlight.py`           | Abstraction of the LCD's RGB backlight                                                                                                 |
| `battery_monitor.py`     | Abstraction of LC709203F and MAX17048 battery monitors with autoselection of the appropriate chip                                      |
| `build-and-deploy.py`    | Build script that uses `mpy-cross` to compile the code and copy it to the `CIRCUITPY` drive                                            |
| `code.py`                | CircuitPython's entry point                                                                                                            |
| `devices.py`             | Dependency injection of the various device abstractions instead of passing a million arguments around                                  |
| `external_rtc.py`        | Abstraction of the real-time clock (RTC)                                                                                               |
| `flow.py`                | Drives the UX                                                                                                                          |
| `lcd.py`                 | Abstraction of the LCD (just the text, not the backlight) including defining special characters like arrows                            |
| `nvram.py`               | Persists values in NVRAM across reboots                                                                                                |
| `offline_event_queue.py` | Queue that buffers up API requests that would happen if the device was online and serializes them to JSON on the microSD card          |
| `offline_state.py`       | Stores some state needed for offline use to the microSD card, like last feeding that happened locally and when the RTC was last synced |
| `periodic_chime.py`      | Logic for when to periodically nudge the user during feedings, tummy times, etc.                                                       |
| `piezo.py`               | Abstraction of the piezo, including allowing playback of tones by name rather than specifying them externally                          |
| `sdcard.py`              | Abstraction of the microSD card reader                                                                                                 |
| `ui_components.py`       | Definition of various UI components, detailed below                                                                                    |
| `user_input.py`          | Abstraction of the rotary encoder, which takes into account the 90° physical rotation when mounted in the enclosure                    |

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
import microcontroller
microcontroller.nvm[5] = value
```

...where `value` is the bitmask. There's no user interface to do this for now, but being in NVRAM, this will
persist across reboots.

### Accessing the microSD card for debugging
Most obviously, you can always just remove the microSD card from your device, if it's accessible and powered off, then put it in your computer. But if that's not feasible, like you don't want to disassemble the BabyPod from its enclosure, you can access the microSD card via the REPL console.

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
- Startup takes a few seconds, mostly due to waiting for Wi-Fi to connect and loading imports.
- Wi-Fi is periodically slow to connect as are network requests in general. Sometimes it takes a couple seconds, but other times 10 or 15 seconds.
- The rotary encoder doesn't always respond on the first input. There is retry logic in the abstraction for that reason.
- Some things are hardcoded, like chime intervals during active timers, instead of either user-configurable or defined in `settings.toml`.
- Only one child is supported. If multiple are defined in Baby Buddy, the first is used.
- Writing to the LCD is pretty slow, presumably because it's done via I2C. In theory the LCD backpack isn't needed and the LCD can be wired directly to the Feather, but I presume it would be a huge mess of wires shoved into the enclosure, even beyond what's already in there. On the plus side, removal of the LCD backpack could allow a bigger battery and therefore less frequent charging. It might be better to wire the LCD using SPI instead of I2C.
- The chime interval during feeding can slowly drift a bit instead of actually chiming precisely at the value passed to an `ActiveTimer`..
- On MAX17048 battery monitor chips, the battery percent isn't immediately available and is hidden until the chip reports a plausible (non-None, >0) value.
- Some Feathers don't allow CircuitPython to read the `VBUS` pin to know if the battery is charging, so the battery monitor reports an indeterminate `None` status instead of `True` or `False`. On such Feathers, the BabyPod will nag you to turn it off even if it's plugged in and charging.
- Weird stuff might happen if you start an action on one BabyPod and continue it on another, like starting a feeding on one and trying to end it on another. This could especially be the case when using a BabyPod offline while still saving events to the server.
- Presumably, the code doesn't know if the battery health is degrading or knowing when it's degraded enough to need replacement. Perhaps there's a way of tracking charging cycles and guessing, even if the battery monitor chip can't tell?
- Baby Buddy should be set to your local timezone, not UTC, and if you're travelling across time zones, the data could be confusing. This is particularly important when working offline.

## Wishlist

Please contribute and submit pull requests if you can help! But some of these things I'm not sure CircuitPython can do.

- Connect to Wi-Fi asynchronously! The slowest part of startup is usually waiting for Wi-Fi, but every selection from the main menu will need a connection; may as well let the menu render and then connect to Wi-Fi in the background so the experience seems faster.
- Support multiple children, although if there's only one, don't require the user to select him/her. Right now, the API is queried for the list of children, but if there's more than one, only the first is used.
- Have the build process burn all the code into the CircuitPython image, and the imports go from slow to near-instant. That's no small feat but could be really useful.
- Better error handling and recovery. There's pretty much none right now except for showing a generic error for uncaught exceptions. There's little retry logic for most things.
- Remove the need for a physical power switch and instead put the device to deep sleep after a few minutes of inactivity (except during timers), and use the rotary encoder or a button on it to wake the device.
- Allow defining multiple Wi-Fi networks when travelling between trusted networks, like your own home and a family member's.
- Remember the last item selected in vertical menus.
- Use interrupts for rotary encoder events instead of polling in a loop. I really want this one, but CircuitPython's design seems antithetical to interrupts.
- On devices with multiple CPU cores, use secondary cores for multithreading to do things in the background, like API requests. Same caveat as above: I don't think it'll happen.
- Track pumping durations, not just total amounts; depends on a [pending Baby Buddy API issue](https://github.com/babybuddy/babybuddy/issues/826).
- Fluid ounces are the assumed unit for pumping. Baby Buddy itself seems unitless, so this could be a localization option for `settings.toml` to change the units shown in the pumping interface. 0.5 increments are used too, so changing units might call for a different increment.
- Support 24-hour time in addition to AM/PM.
- Buffer events even when online in case they fail to submit to the server and can therefore be replayed later.

# BabyPod

This repository is just for the CircuitPython code that runs on the hardware. See the [`babypod-hardware`](https://github.com/skjdghsdjgsdj/babypod-hardware/) repository for the hardware setup and more general information about the project.

You need to install [Baby Buddy](https://docs.baby-buddy.net/setup/deployment/) for this to work. It can be installed on your local network or on the internet (AWS, etc.), so long as it's reachable through your Wi-Fi network.

## Features

### General
- Simple text-based interface that can be scrolled with the rotary encoder's wheel or the up/down buttons. Select and Right buttons are usually interchangable, and Left usually means cancel or back. Protip: the rotary encoder is physically rotated 90° when mounted in the enclosure, so the abstraction for it accounts for that.
- Backlight color and piezo are used for positive interface feedback, like successful saving of data back to Baby Buddy, reporting of errors, periodic chimes during timers, etc.
- Some user-configurable options are exposed directly through the interface instead of messing with `settings.toml`, like turning off the piezo if it bothers your baby. The values are stored in NVRAM to persist across reboots. Protip: don't turn off the backlight on [backlight-negative LCDs](https://www.adafruit.com/product/498).
- Battery percentage shown on most screens and updates periodically.
- Backlight dims after inactivity to save power, although you should turn off the BabyPod when not using it anyway.
- Information is contextual and non-relevant information isn't shown. For example, when feeding solid food, no bottle options are shown.
- If you start doing a thing and forget to start a timer, usually it's fine: for example, you can record a feeding _ex post facto_ and it'll get logged with zero duration.

### Feedings
- Record feedings, including start and end times, food types, which breasts(s) were used for feeding, etc.
- A live timer that runs to keep track of how long the current feeding session has been, with chimes at every 15 minutes as a reminder to switch breasts.

### Diaper changes
- Record diaper changes, including if they were wet, solid or both.

### Pumping
- Record pumping sessions, including amount pumped.

### Tummy Time
- Record tummy time sessions, including durations.

### Options
User-configurability that persists across power cycles of:

- Enabling or disabling the piezo (on by default)
- LCD backlight at max brightness then dimming after timeout (default), or dim by default

## Building and Deploying

### Requirements

These instructions assume you've already built a BabyPod per the instructions at [the hardware repository](https://github.com/skjdghsdjgsdj/babypod-hardware/), including copying a release to the `CIRCUITPY` drive along with setting up `settings.toml`. That is, you have a functioning BabyPod already, and now you want to change the code on it.

To make code changes, you need to do the following to build and deploy them.

1. Clone BabyPod's software GitHub repository first:
```
git clone https://github.com/skjdghsdjgsdj/babypod-software.git
```

2. Plug in the Feather to a USB port and verify the `CIRCUITPY` drive shows up. The power switch must be on.

	Some Feathers don't show up as local drives because they lack the USB support for it. In those cases, the build script won't work right and you'll have to copy files another way, which is usually by Wi-Fi or the serial console. Refer to that Feather's documentation for details.
	
3. Compile your own `mpy-cross` executable and put it in your `$PATH`. As of this documentation, there's no prebuilt `mpy-cross` for CircuitPython 9, and they are not backwards-compatible. Fortunately you only need to do this one because it takes a long time. To do this:
	1. [Download and build CircuitPython 9](https://learn.adafruit.com/building-circuitpython), including building submodules. Note you have to do a full clone; you can't do `git clone --depth` or you'll miss tags and the build will fail.
	2. [Build `mpy-cross`](https://learn.adafruit.com/building-circuitpython?view=all#build-circuitpython) and put the resulting binary that ends up in `circuitpython/mpy-cross/build/mpy-cross` in your `$PATH`, like copying it to `/usr/local/bin`.
	3. You can delete the cloned `circuitpython` repository if you don't plan on building `mpy-cross` again or doing CircuitPython upgrades.

### macOS and Linux

1. On Linux, edit `build-and-deploy.sh` to point to the correct path for your `CIRCUITPY` drive. For now, it assumes you're on macOS. Feel free to make the script less dumb and submit a pull request so others can build on Linux or macOS automatically without needing to edit the script.
2. With the Feather plugged in and turned on, run `build-and-deploy.sh`. This script will
	1. Run `mpy-cross` with optimizations on all `.py` files in the project, except for the entry point `code.py`.
	2. With each resulting `.mpy` compiled output, copy it to the Feather's `lib/` directory.
	3. Copy `code.py` to the root of the Feather.

	You can also pass a module name to `build-and-deploy.sh` to build and deploy just that one library, like `build-and-deploy.sh api`. Passing `code` just copies `code.py` and nothing else. Omitting all arguments is a full build and deploy.

### Windows

I haven't tried. You can make your own PowerShell script possibly that does something similar to `build-and-deploy.sh`. You can also copy the `.py` files for debugging's sake as described below.

### Caveats

#### Manual reboot needed

Unlike CircuitPython's default behavior, the Feather won't reboot automatically when you deploy a change. This is deliberate to avoid a storm of reboots as compiled files are copied to the Feather. Instead, you can reboot the Feather by:

- The preferable approach: with a serial console open, like [`tio`](https://formulae.brew.sh/formula/tio) on macOS, press Ctrl-C to abort the currently running code, then `Ctrl-D` to reboot the Feather. This keeps you connected to the console and importantly means you don't miss any console messages as the Feather starts back up.
- Cycling the power switch. Not ideal if you have a serial console open because it'll disconnect and even if it reconnects you may miss some startup messages.
- Press the Feather's reset button, if it's accessible.

#### Debugging

`.mpy` files don't have line numbers, so if you get errors within the compiled output, they always show up as line 1. For debugging's sake, you can straight up copy the project `.py` files directly to the `CIRCUITPY` drive instead of building them. But keep in mind:

- You must delete `.mpy` files from the Feather that have the same name because they get loaded first. For example, if you're debugging `api.py`, delete `api.mpy` from the Feather.
- `.py` files are slower to load, so you only want to do this for debugging, not day-to-day use of BabyPod.
- `mpy-cross`'s version and CircuitPython's version are linked and often CircuitPython upgrades have breaking changes that require recompiling `mpy-cross`. If you upgrade CircuitPython on the Feather, you may need to rebuild `mpy-cross` too or you'll get errors about incompatible `.mpy` files.
- Be careful when deleting `.mpy` files when debugging to keep all the Adafruit libraries intact. Some of them don't have an `adafruit_` prefix, like `simpleio.mpy`.

#### `.gitignore`

The names of libraries created during the build process in `lib/` are already defined in `.gitignore`. Not all files are ignored because the Adafruit libraries are always needed. If you end up adding a new `.py` file that results in a new `lib/...mpy` file, you should add that resulting `.mpy` to `.gitignore` so compiled output doesn't get committed.

## Code design and architectural principles

### General
- Load only the necessary libraries and load them just in time. CircuitPython is slow at importing modules. The build process compiles as much as it can to `.mpy` files for faster loading.
- Get something shown on the display as quickly as possible so the user knows the device powered on properly.
- Try to use one codebase for most Feathers and let the code discover its own environment rather than needing to override pins, I2C addresses, etc. for different hardware.
- Provide abstractions for the devices, and in cases where there could be different hardware variants like different battery monitor chips, use polymorphism to hide the underlying hardware from the application.
- Keep a given screen simple. For example, don't make vertical menus scrollable such that they have more than four items and you have to scroll to see them. Instead, make a user experience flow that negates the need for scrolling. The idea is you can hand Baby Buddy to a helper (family member, doula, nurse, etc.) and (s)he finds it straightforward to use.

### Files
| File | Purpose |
| ---- | ------- |
| `api.py` | Connectivity to Wi-Fi and Baby Buddy |
| `backlight.py` | Abstraction of the LCD's RGB backlight |
| `battery_monitor.py` | Abstraction of LC709203F and MAX17048 battery monitors with autoselection of the appropriate chip |
| `build-and-deploy.sh` | Bash script that uses `mpy-cross` to compile the code and copy it to the `CIRCUITPY` drive |
| `code.py` | CircuitPython's entry point |
| `flow.py` | Drives the UX |
| `lcd_special_chars_module.py` | Abstraction of the LCD (just the text, not the backlight) including defining special characters like arrows |
| `nvram.py` | Persists values in NVRAM across reboots |
| `piezo.py` | Abstraction of the piezo, including allowing playback of tones by name rather than specifying them externally |
| `rotary_encoder.py` | Abstraction of the rotary encoder, which takes into account the 90° physical rotation when mounted in the enclosure |
| `ui_components.py` | Definition of various UI components, detailed below |

### UI Components

| Class | Purpose |
| ----- | ------- |
| `UIComponent` | Base class |
| `ActiveTimer` | A timer that counts up in real-time, including periodic piezo chimes |
| `NumericSelector` | Input for a float with upper/lower bounds and increment counts |
| `VerticalMenu` | User selection a single menu item from up to four options |
| `VerticalCheckboxes` | Like `VerticalMenu`, but each item is preceded with a checkbox |
| `BooleanPrompt`| Like `VerticalMenu`, but allows for one selection of exactly two options and returns a boolean |

## Known limitations and bugs

Please contribute and submit pull requests if you can help!

- `build-and-deploy.sh` assumes a macOS environment.
- Startup takes a few seconds, mostly due to waiting for Wi-Fi to connect and loading imports.
- Wi-Fi is peridically slow to connect as are network requests in general. Sometimes it takes a couple seconds, but other times 10 or 15 seconds.
- The rotary encoder doesn't always respond on the first input. There is retry logic in the abstraction for that reason.
- Some things are hardcoded, like chime intervals during active timers, instead of either user-configurable or defined in `settings.toml`.
- The child ID is hardcoded to 1.
- Writing to the LCD is pretty slow, presumably because it's done via I2C. In theory the LCD backpack isn't needed and the LCD can be wired directly to the Feather, but I presume it would be a huge mess of wires shoved into the enclosure, even beyond what's already in there. On the plus side, removal of the LCD backpack could allow a bigger battery and therefore less frequent charging.
- The chime interval during feeding can slowly drift a bit instead of actually chiming precisely at the value passed to an `ActiveTimer`..
- On MAX17048 battery monitor chips, the battery percent isn't immediately available and is hidden until the chip reports a plausible (non-None, >0) value.
- Some Feathers don't allow CircuitPython to read the `VBUS` pin to know if the battery is charging, so the battery monitor reports an indeterminate `None` status instead of `True` or `False`. On such Feathers, the BabyPod will nag you to turn it off even if it's plugged in and charging.
- Weird stuff might happen if you start an action on one BabyPod and continue it on another, like starting a feeding on one and trying to end it on another.
- Presumably, the code doesn't know if the battery health is degrading or knowing when it's degraded enough to need replacement. Perhaps there's a way of tracking charging cycles and guessing, even if the battery monitor chip can't tell?
- Baby Buddy should be set to your local timezone, not UTC, and if you're travelling across time zones, the data could be confusing. Note that the code has no idea what the _current_ time is, only how much time has elapsed since startup via `time.monotonic()`.

## Wishlist

Please contribute and submit pull requests if you can help! But some of these things I'm not sure CircuitPython can do.

- Connect to Wi-Fi asynchronously! The slowest part of startup is usually waiting for Wi-Fi, but every selection from the main menu will need a connection; may as well let the menu render and then connect to Wi-Fi in the background so the experience seems faster.
- Support multiple children, although if there's only one, don't require the user to select him/her. This can be autodiscovered via an API call, but it might be best to force a single child ID in `settings.toml` to avoid the call at startup.
- Have the build process burn all the code into the CircuitPython image, and the imports go from slow to near-instant. That's no small feat but could be really useful.
- Better error handling and recovery. There's pretty much none right now except for showing a generic error for uncaught exceptions. There's no retry logic or offline batching.
- Remove the need for a physical power switch and instead put the device to deep sleep after a few minutes of inactivity (except during timers), and use the rotary encoder or a button on it to wake the device.
- Allow defining multiple Wi-Fi networks when travelling between trusted networks, like your own home and a family member's.
- Remember the last item selected in vertical menus.
- Use interrupts for rotary encoder events instead of polling in a loop.
- On devices with multiple CPU cores, use secondary cores for multithreading to do things in the background, like API requests.
- Track pumping durations, not just total amounts.
- Color support for diaper changes...maybe. I didn't include it because they should be very consistent, and when not, you can just go to Baby Buddy and update the entry manually.
- Fluid ounces are the assumed unit for pumping. Baby Buddy itself seems unitless, so this could be a localization option for `settings.toml` to change the units shown in the pumping interface. 0.5 increments are used too, so changing units might call for a different increment.
- Support 24-hour time in addition to AM/PM.

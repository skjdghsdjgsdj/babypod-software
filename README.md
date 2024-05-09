# BabyPod

This repository is just for the CircuitPython code that runs on the hardware. See the [`babypod-hardware`](https://github.com/skjdghsdjgsdj/babypod-hardware/) repository for the hardware setup and more general information about the project.

You need to install [Baby Buddy](https://docs.baby-buddy.net/setup/deployment/) for this to work. It can be installed on your local network or on the internet (AWS, etc.), so long as it's reachable through your Wi-Fi network.

## Features

### General
- Simple text-based interface that can be scrolled with the rotary encoder's wheel or the up/down buttons. Select and Right buttons are usually interchangable, and Left usually means cancel or back. Protip: the rotary encoder is physically rotated 90° when mounted in the enclosure, so the abstraction for it accounts for that.
- Backlight color and piezo are used for positive interface feedback, like successful saving of data back to Baby Buddy, reporting of errors, periodic chimes during timers, etc.
- Some user-configurable options are exposed directly through the interface instead of messing with `settings.toml`, like turning off the piezo if it bothers your baby.
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
| `options.py` | Defines and persists user preferences |
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
- Add an explicit low battery warning.
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

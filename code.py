"""
Entry point.
"""

# don't reboot when USB storage is changed
import supervisor
supervisor.runtime.autoreload = False

# watchdog auto-reboot
import watchdog
import microcontroller
microcontroller.watchdog.timeout = 20
microcontroller.watchdog.mode = watchdog.WatchDogMode.RESET
microcontroller.watchdog.feed()

# warn if the stack size is too small
import os
if not os.getenv("CIRCUITPY_PYSTACK_SIZE") or int(os.getenv("CIRCUITPY_PYSTACK_SIZE")) <= 1536:
	print("Warning: CIRCUITPY_PYSTACK_SIZE is too small! If you get \"pystack exhausted\" errors, it needs to be increased.")

try:
	# see if soft power control is available
	from power_control import PowerControl
	use_soft_power_control = PowerControl.is_available()
	print(f"Soft power control is {'available' if use_soft_power_control else 'unavailable'}")

	# see why it woke up; if it's a TimeAlarm, it's likely because there was a soft shutdown and the battery needs to be
	# refreshed periodically
	just_refresh_shutdown_screen = False
	if use_soft_power_control:
		import alarm
		from alarm.time import TimeAlarm
		just_refresh_shutdown_screen = use_soft_power_control and isinstance(alarm.wake_alarm, TimeAlarm)

	# init I2C and at a higher frequency than default
	from busio import I2C
	import board
	i2c = I2C(sda = board.SDA, scl = board.SCL, frequency = 100000)

	# set up piezo, but only play the sound if this is a normal startup
	piezo = None
	if not just_refresh_shutdown_screen:
		from piezo import Piezo
		piezo = Piezo()
		piezo.tone("startup")

	# get LCD set up, but only turn on the backlight and show startup message if this is a normal startup
	from lcd import LCD
	lcd = LCD.get_instance(i2c)
	if not just_refresh_shutdown_screen:
		from lcd import BacklightColors
		lcd.backlight.set_color(BacklightColors.DEFAULT)
		lcd.write_centered("Starting up...")

	# turn off Neopixel
	from digitalio import DigitalInOut, Direction
	neopixel = DigitalInOut(board.NEOPIXEL)
	neopixel.direction = Direction.OUTPUT
	neopixel.value = False

	# init rotary encoder
	from user_input import RotaryEncoder
	rotary_encoder = RotaryEncoder(i2c)

	# init battery monitor
	from battery_monitor import BatteryMonitor
	battery_monitor = BatteryMonitor.get_instance(i2c)

	# set up soft power control if enabled in settings.toml; otherwise assume a hard power switch across EN and GND
	if use_soft_power_control:
		power_control = PowerControl(piezo, lcd, rotary_encoder, battery_monitor)
	else:
		power_control = None

	# if woke up because of a periodic battery refresh, do so
	if just_refresh_shutdown_screen:
		power_control.shutdown(silent = True)
	# otherwise continue normal startup to main menu and whatnot
	else:
		sdcard = None
		rtc = None
		if not just_refresh_shutdown_screen:
			from external_rtc import ExternalRTC
			if ExternalRTC.exists(i2c):
				from sdcard import SDCard
				try:
					sdcard = SDCard()
				except Exception as e:
					print(f"Error while trying to mount SD card, assuming hardware is missing: {e}")
					from nvram import NVRAMValues
					NVRAMValues.OFFLINE.write(False)

					lcd.clear()
					lcd.backlight.set_color(BacklightColors.ERROR)
					lcd.write_centered("SD card failure!")
					import time
					time.sleep(2)
					lcd.backlight.set_color(BacklightColors.DEFAULT)

				rtc = ExternalRTC(i2c)

		from devices import Devices
		devices = Devices(
			rotary_encoder = rotary_encoder,
			piezo = piezo,
			lcd = lcd,
			battery_monitor = battery_monitor,
			sdcard = sdcard,
			rtc = rtc,
			power_control = power_control
		)
		from flow import Flow

		Flow(devices = devices).start()
except KeyboardInterrupt:
	pass # don't care about Ctrl-C, just exit
except Exception as e:
	print(f"Uncaught {type(e).__name__}: {str(e)}")
	import traceback
	traceback.print_exception(e)
	print("Keeping alive for five minutes to allow for USB debugging")
	import time
	start = time.monotonic()
	while time.monotonic() - start <= 60 * 5:
		microcontroller.watchdog.feed()
		time.sleep(5)

	print("Resetting")
	microcontroller.reset()
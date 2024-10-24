"""
Soft power control (deep sleep). Hard power control is a switch wired across EN and GND.
"""

import time

import alarm
import board
import digitalio
import microcontroller
from adafruit_seesaw import seesaw

from battery_monitor import BatteryMonitor
from lcd import LCD
from nvram import NVRAMValues
from piezo import Piezo
from user_input import RotaryEncoder

# noinspection PyBroadException
try:
	from typing import Optional
except:
	pass

class PowerControl:
	"""
	Soft power control to enter to and exit from deep sleep. Note the I2C bus stays powered so the rotary encoder can
	still generate interrupts to exit deep sleep.
	"""

	def __init__(self,
		piezo: Piezo,
		lcd: LCD,
		encoder: RotaryEncoder,
		battery_monitor: Optional[BatteryMonitor] = None,
		interrupt_pin: microcontroller.Pin = board.D11,
		seesaw_pin: int = 1
	 ):
		"""
		:param piezo: Piezo for playing shutdown sound
		:param lcd: LCD for writing shutdown messages
		:param encoder: Rotary encoder to use for waking up
		:param battery_monitor: Battery monitor to use for checking charging state
		:param interrupt_pin: Interrupt pin to which the rotary encoder's INT is wired
		:param seesaw_pin: Virtual pin on the rotary encoder to use for generating interrupts; 1 is the center button
		"""

		self.encoder = encoder
		self.lcd = lcd
		self.interrupt_pin = interrupt_pin
		self.seesaw_pin = seesaw_pin
		self.piezo = piezo
		self.battery_monitor = battery_monitor

	def init_center_button_interrupt(self) -> None:
		"""
		Sets up the rotary encoder to generate interrupts and clears any existing ones so the next one can exit from
		deep sleep.
		"""

		# set up the interrupt which is connected to D11
		mask = 1 << self.seesaw_pin

		self.encoder.seesaw.pin_mode(self.seesaw_pin, seesaw.Seesaw.INPUT_PULLUP)
		self.encoder.seesaw.set_GPIO_interrupts(mask, True)

		# clear any interrupt so the next one wakes up D11
		self.encoder.seesaw.digital_read_bulk(mask)

	def lcd_shutdown(self) -> None:
		"""
		Clears the LCD, turns off its backlight, and renders just the battery percent and a message for the power
		button.
		"""

		self.lcd.backlight.off()
		self.lcd.clear()
		self.lcd.write_bottom_left_aligned(self.lcd[LCD.CENTER] + " Power")

		if self.battery_monitor is not None:
			# try a few times in case the battery monitor isn't ready, but then give up
			percent = None
			start = time.monotonic()
			while percent is None and time.monotonic() - start <= 5:
				percent = self.battery_monitor.get_percent()
				if percent is not None:
					self.lcd.write_right_aligned(f"{percent}%")
					break
				time.sleep(0.2)

	def enter_deep_sleep(self) -> None:
		"""
		Enters deep sleep immediately. The wake alarms are:

		* A time alarm if the battery charge state is known: 60 seconds if charging, or
		  NVRAMValues.SOFT_SHUTDOWN_BATTERY_REFRESH_INTERVAL if not or unknown.
		* A pin alarm so the rotary encoder, center button by default, triggers the hardwired interrupt pin

		I2C power is preserved so the rotary encoder can generate interrupts. The watchdog is disabled too.

		Given this method enters deep sleep, it never returns.
		"""

		# wake up every few minutes to refresh the battery display, assuming there's a battery monitor
		time_alarm = None
		if self.battery_monitor is not None:
			from alarm.time import TimeAlarm
			interval = 60 if self.battery_monitor.is_charging() else NVRAMValues.SOFT_SHUTDOWN_BATTERY_REFRESH_INTERVAL
			time_alarm = TimeAlarm(monotonic_time = time.monotonic() + interval)

		# keep I2C_PWR on during deep sleep so the rotary encoder can still generate interrupts
		i2c_power = digitalio.DigitalInOut(board.I2C_POWER)
		i2c_power.switch_to_output(True)

		# wake up when D11 gets an interrupt from the rotary encoder
		from alarm.pin import PinAlarm
		pin_alarm = PinAlarm(self.interrupt_pin, pull = False, value = False)

		# disable the watchdog
		microcontroller.watchdog.mode = None

		# enter deep sleep
		if time_alarm is not None and pin_alarm is not None:
			print(f"Entering deep sleep; will wake up from PinAlarm or TimeAlarm in {int(time_alarm.monotonic_time - time.monotonic())} seconds")
			alarm.exit_and_deep_sleep_until_alarms(pin_alarm, time_alarm, preserve_dios = [i2c_power])
		elif time_alarm is None and pin_alarm is not None:
			print("Entering deep sleep; only wakeup source will be PinAlarm")
			alarm.exit_and_deep_sleep_until_alarms(pin_alarm, preserve_dios = [i2c_power])
		elif time_alarm is not None and pin_alarm is None:
			print(f"Entering deep sleep; will wake up only from TimeAlarm in {int(time_alarm.monotonic_time - time.monotonic())} seconds")
			alarm.exit_and_deep_sleep_until_alarms(time_alarm, preserve_dios = [i2c_power])
		else:
			raise ValueError("No alarm defined for deep sleep")

		raise RuntimeError("Deep sleep failed")

	def shutdown(self, silent: bool = False) -> None:
		"""
		Soft shutdown the BabyPod: play the shutdown sound, show a "Powering off" message, and then enter deep sleep.
		There is a brief delay from calling this method to actually entering deep sleep so, if the rotary encoder
		button is still being held, it doesn't immediately wake up again.

		Because this ultimately calls enter_deep_sleep(), it never returns.

		:param silent: True to just enter deep sleep immediately with no warning message or piezo sounds
		"""

		if not silent:
			self.piezo.tone("shutdown")
			self.lcd.clear()
			self.lcd.write_centered("Powering off...")

			time.sleep(3) # give the user time to let go of the button, or it'll just wake immediately

		self.init_center_button_interrupt()

		self.lcd_shutdown()
		self.enter_deep_sleep()

	@staticmethod
	def is_available():
		"""
		Checks if this device supports soft power control.

		:return: True if USE_SOFT_POWER_CONTROL in settings.toml evaluates to True
		"""
		import os
		return bool(os.getenv("USE_SOFT_POWER_CONTROL"))
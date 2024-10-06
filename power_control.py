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
	def __init__(self,
		piezo: Piezo,
		lcd: LCD,
		encoder: RotaryEncoder,
		battery_monitor: Optional[BatteryMonitor] = None,
		interrupt_pin: microcontroller.Pin = board.D11,
		seesaw_pin: int = 1
	 ):
		self.encoder = encoder
		self.lcd = lcd
		self.interrupt_pin = interrupt_pin
		self.seesaw_pin = seesaw_pin
		self.piezo = piezo
		self.battery_monitor = battery_monitor

	def init_center_button_interrupt(self) -> None:
		# set up the interrupt which is connected to D11
		mask = 1 << self.seesaw_pin

		self.encoder.seesaw.pin_mode(self.seesaw_pin, seesaw.Seesaw.INPUT_PULLUP)
		self.encoder.seesaw.set_GPIO_interrupts(mask, True)
		print("Enabled interrupt for center button")

		# clear any interrupt so the next one wakes up D11
		self.encoder.seesaw.digital_read_bulk(1 << self.seesaw_pin)
		print("Cleared encoder read queue")

	def lcd_shutdown(self) -> None:
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
		# wake up every few minutes to refresh the battery display, assuming there's a battery monitor
		time_alarm = None
		if self.battery_monitor is not None:
			print("Creating time alarm")
			from alarm.time import TimeAlarm
			interval = 60 if self.battery_monitor.is_charging() else NVRAMValues.SOFT_SHUTDOWN_BATTERY_REFRESH_INTERVAL
			time_alarm = TimeAlarm(monotonic_time = time.monotonic() + interval)

		# keep I2C_PWR on during deep sleep so the rotary encoder can still generate interrupts
		i2c_power = digitalio.DigitalInOut(board.I2C_POWER)
		i2c_power.switch_to_output(True)
		print("Preserved I2C_POWER")

		# wake up when D11 gets an interrupt from the rotary encoder
		from alarm.pin import PinAlarm
		pin_alarm = PinAlarm(self.interrupt_pin, pull = False, value = False)
		print("Created pin alarm")

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
		if not silent:
			self.piezo.tone("shutdown")
		self.lcd.clear()
		self.lcd.write_centered("Powering off...")

		self.init_center_button_interrupt()

		print("Waiting a few seconds for deep sleep")
		time.sleep(3) # give the user time to let go of the button, or it'll just wake immediately

		self.lcd_shutdown()
		self.enter_deep_sleep()
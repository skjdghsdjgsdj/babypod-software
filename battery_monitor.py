import time

import board
import digitalio
from busio import I2C
from adafruit_max1704x import MAX17048
from adafruit_lc709203f import LC709203F, LC709203F_CMD_APA
import supervisor

class BatteryMonitor:
	def __init__(self, i2c: I2C):
		self.last_percent = None
		self.i2c = i2c
		self.device = None

		if hasattr(board, "VBUS"):
			self.charging_pin = digitalio.DigitalInOut(board.VBUS)
			self.charging_pin.direction = digitalio.Direction.INPUT
		else:
			self.charging_pin = None

	def init_device(self) -> None:
		if self.device is None:
			self.device = self.init_raw_device()

	def init_raw_device(self):
		raise NotImplementedError()

	def is_charging(self) -> bool:
		if supervisor.runtime.usb_connected:
			return True

		if self.charging_pin is not None:
			return self.charging_pin.value

		return False

	def get_current_percent(self) -> float:
		raise NotImplementedError()

	def get_percent(self) -> int:
		self.init_device()

		self.last_percent = self.get_current_percent()

		if self.last_percent is None:
			print("Couldn't get battery percent; it might not be stabilized yet")
		else:
			self.last_percent = int(round(min(max(self.last_percent, 0), 100)))

			if self.last_percent <= 0:
				self.last_percent = None

		return self.last_percent

	@staticmethod
	def get_instance(i2c: I2C):
		attempts = 0
		while attempts <= 20:
			while not i2c.try_lock():
				pass
			i2c_address_list = i2c.scan()
			i2c.unlock()

			attempts += 1

			if 0x0b in i2c_address_list:
				return LC709203FBatteryMonitor(i2c)
			elif 0x36 in i2c_address_list:
				return MAX17048BatteryMonitor(i2c)

			print("Battery monitor I2C device detection found nothing, retrying")
			time.sleep(0.2)

		print("Couldn't find a battery monitor on I2C bus")
		return None

class MAX17048BatteryMonitor(BatteryMonitor):
	def init_raw_device(self) -> MAX17048:
		return MAX17048(self.i2c)

	def get_current_percent(self) -> float:
		return self.device.cell_percent

	def is_charging(self) -> bool:
		self.init_device()

		is_charging = super().is_charging()
		if not is_charging:
			charge_rate = self.device.charge_rate
			is_charging = charge_rate > 0.05

		return is_charging

class LC709203FBatteryMonitor(BatteryMonitor):
	# pack size adjustment values: https://www.mouser.com/datasheet/2/308/LC709203F_D-1810548.pdf
	BATTERY_LC709203F_AMA = 0x33

	def init_raw_device(self) -> LC709203F:
		device = LC709203F(self.i2c)
		# noinspection PyProtectedMember
		device._write_word(LC709203F_CMD_APA, LC709203FBatteryMonitor.BATTERY_LC709203F_AMA)

		return device

	def get_current_percent(self) -> float:
		return self.device.cell_percent
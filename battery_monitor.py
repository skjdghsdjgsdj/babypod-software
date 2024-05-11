import board
import digitalio

class BatteryMonitor:
	def __init__(self, i2c):
		self.last_percent = None
		self.i2c = i2c
		self.device = None

		if hasattr(board, "VBUS"):
			self.charging_pin = digitalio.DigitalInOut(board.VBUS)
			self.charging_pin.direction = digitalio.Direction.INPUT
		else:
			self.charging_pin = None

	def init_device(self):
		if self.device is None:
			self.device = self.init_raw_device()

	def init_raw_device(self):
		raise NotImplementedError()

	def is_charging(self):
		return None if self.charging_pin is None else self.charging_pin.value

	def get_current_percent(self):
		raise NotImplementedError()

	def get_percent(self):
		self.init_device()

		self.last_percent = self.get_current_percent()

		if self.last_percent is None:
			print("Couldn't get battery percent; it might not be stabilized yet")
		else:
			self.last_percent = int(round(min(max(self.last_percent, 0), 100)))

			if self.last_percent <= 0:
				print(f"Battery percent {self.last_percent}% is implausible; hiding for now until it stabilizes")
				self.last_percent = None

		return self.last_percent

	@staticmethod
	def get_instance(i2c):
		while not i2c.try_lock():
			pass
		i2c_address_list = i2c.scan()
		i2c.unlock()

		if 0x0b in i2c_address_list:
			print("Detected LC709203F battery monitor")
			return LC709203FBatteryMonitor(i2c)
		elif 0x36 in i2c_address_list:
			print("Detected MAX17048 battery monitor")
			return MAX17048BatteryMonitor(i2c)
		else:
			raise ValueError("Couldn't find a battery monitor on I2C bus")

class MAX17048BatteryMonitor(BatteryMonitor):
	def init_raw_device(self):
		import adafruit_max1704x
		return adafruit_max1704x.MAX17048(self.i2c)

	def get_current_percent(self):
		return self.device.cell_percent

	def is_charging(self):
		self.init_device()
		charge_rate = self.device.charge_rate
		return charge_rate > 0

class LC709203FBatteryMonitor(BatteryMonitor):
	def init_raw_device(self):
		# pack size adjustment values: https://www.mouser.com/datasheet/2/308/LC709203F_D-1810548.pdf
		BATTERY_LC709203F_AMA = 0x33

		from adafruit_lc709203f import LC709203F, LC709203F_CMD_APA
		device = LC709203F(self.i2c)
		# noinspection PyProtectedMember
		device._write_word(LC709203F_CMD_APA, BATTERY_LC709203F_AMA)

		return device

	def get_current_percent(self):
		return self.device.cell_percent
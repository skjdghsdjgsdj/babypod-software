import board
import digitalio
import supervisor
from adafruit_lc709203f import LC709203F, LC709203F_CMD_APA
from adafruit_max1704x import MAX17048
from busio import I2C

from util import I2CDeviceAutoSelector


class BatteryMonitor:
	"""
	Abstraction for a battery monitor, a.k.a. "fuel gauge", to measure the charge level of the attached battery.
	Supports both LC709203F and MAX17048 battery monitors, although the latter is more common. A battery size of
	2500 mAh is assumed.

	The battery monitor hardware is connected by I2C, but that could mean built directly into the board (i.e. Feather)
	or connected externally via STEMMA QT/QWIIC/I2C pins.

	This is an abstract class. Get instances using get_instance().
	"""

	def __init__(self, i2c: I2C):
		"""
		Use get_instance() instead of this constructor to automatically construct a battery monitor of the correct
		implementation and to check if one exists on the I2C bus in the first place.

		:param i2c: I2C bus that has a battery monitor
		"""

		self.last_percent = None
		self.i2c = i2c
		self.device = None

		if hasattr(board, "VBUS"):
			self.charging_pin = digitalio.DigitalInOut(board.VBUS)
			self.charging_pin.direction = digitalio.Direction.INPUT
		else:
			self.charging_pin = None

	def init_device(self) -> None:
		"""
		Initializes the underlying hardware device used by this instance, if not already initialized. Subclasses must
		implement init_raw_device() to define the device.
		"""

		if self.device is None:
			self.device = self.init_raw_device()

	def init_raw_device(self):
		"""
		Initializes the underlying hardware device used by this instance. In this abstract class, this method raises a
		NotImplementedError.

		:return: Underlying hardware device used by this instance
		"""

		raise NotImplementedError()

	def is_charging(self) -> bool:
		"""
		Checks if the battery is charging. The default implementation assumes the battery is charging if any of the
		following conditions are true:

		* USB data is connected, like a serial terminal or USB mass storage
		* The charging_pin attribute is not None and its value is True

		Otherwise returns False because the charging state is either not charging or not known.

		Subclasses may override this method based on how their underlying hardware checks if the battery is charging,
		but should call this base method first and return True if it does too.

		:return: True if the battery is charging, False if not or indeterminate
		"""

		if supervisor.runtime.usb_connected:
			return True

		if self.charging_pin is not None:
			return self.charging_pin.value

		return False

	def get_current_percent(self) -> float:
		"""
		Gets the charge percent of the battery (0..100). In this abstract class, raises NotImplementedError() and must
		be overridden by subclasses.

		:return: Charge percent of the battery
		"""
		raise NotImplementedError()

	def get_percent(self) -> int:
		"""
		Initializes the battery monitor hardware if necessary, gets the current charge percent, and normalizes the
		response to be from 0% to 100%. Returns charge percent or None if it isn't known yet; for example, the hardware
		hasn't finished initializing yet.

		:return: Battery charge percent (0...100) or None if unknown or the charge is 0% and therefore implausible
		"""

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
		"""
		Gets a concrete instance of a battery monitor by scanning the I2C bus for a compatible battery monitor, or None
		if one isn't found. Multiple attempts are made with a brief delay between each attempt in case the hardware
		isn't immediately available on the I2C bus, but eventually gives up after repeated failures.

		:param i2c: I2C bus that contains a battery monitor
		:return: Concrete instance of a battery monitor or None if not found
		"""

		try:
			return I2CDeviceAutoSelector(i2c = i2c).get_device(address_map = {
				0x0b: lambda _: LC709203FBatteryMonitor(i2c),
				0x36: lambda _: MAX17048BatteryMonitor(i2c)
			})
		except Exception as e:
			print(f"Failed to get battery monitor: {e}")
			return None

class MAX17048BatteryMonitor(BatteryMonitor):
	"""
	An implementation of BatteryMonitor based on a MAX17048. Most new Adafruit Feathers seem to use this.
	"""

	def init_raw_device(self) -> MAX17048:
		"""
		Creates a MAX17048 instance.

		:return: MAX17048 instance
		"""
		return MAX17048(self.i2c)

	def get_current_percent(self) -> float:
		"""
		Queries the MAX17048 for its cell percentage.

		:return: Battery charge percent
		"""
		return self.device.cell_percent

	def is_charging(self) -> bool:
		"""
		Returns True if the base class does, and if not, returns True if the charge rate exceeds 5%/hr or False if not.

		:return: True if the battery is likely charging, False if not or indeterminite
		"""

		self.init_device()

		is_charging = super().is_charging()
		if not is_charging:
			charge_rate = self.device.charge_rate
			is_charging = charge_rate > 0.05

		return is_charging

class LC709203FBatteryMonitor(BatteryMonitor):
	"""
	An implementation of BatteryMonitor based on a LC709203F. Older Adafruit Feathers seem to use this.
	"""

	# pack size adjustment values: https://www.mouser.com/datasheet/2/308/LC709203F_D-1810548.pdf
	BATTERY_LC709203F_AMA = 0x33

	def init_raw_device(self) -> LC709203F:
		"""
		Creates a LC709203F instance and configures it for a 2500 mAh battery.

		:return: LC709203F instance
		"""
		device = LC709203F(self.i2c)
		# noinspection PyProtectedMember
		device._write_word(LC709203F_CMD_APA, LC709203FBatteryMonitor.BATTERY_LC709203F_AMA)

		return device

	def get_current_percent(self) -> float:
		"""
		Queries the LC709203F for its cell percentage.

		:return: Battery charge percent
		"""
		return self.device.cell_percent
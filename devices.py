from busio import I2C

from battery_monitor import BatteryMonitor
from external_rtc import ExternalRTC
from lcd import LCD
from piezo import Piezo
from power_control import PowerControl
from sdcard import SDCard
from user_input import RotaryEncoder
from util import Util

# noinspection PyBroadException
try:
	from typing import Optional, Dict, Callable, Any, List
except:
	pass
	# ignore, just for IDE's sake, not supported on board

class Devices:
	"""
	Dependency injection object for containing various hardware devices instead of passing them all around
	individually.
	"""

	def __init__(self,
				 rotary_encoder: RotaryEncoder,
				 piezo: Piezo,
				 lcd: LCD,
				 battery_monitor: Optional[BatteryMonitor],
				 sdcard: Optional[SDCard],
				 rtc: Optional[ExternalRTC],
				 power_control: Optional[PowerControl]):
		"""
		:param rotary_encoder: Rotary encoder instance
		:param piezo: Piezo instance
		:param lcd: LCD instance
		:param battery_monitor: Battery monitor instance, or None if no hardware is available
		:param sdcard: SD card instance, or None if no hardware is available
		:param rtc: RTC instance, or None if no hardware is available
		:param power_control: Power control instance, or None if this device doesn't have soft power control
		"""
		self.rotary_encoder = rotary_encoder
		self.piezo = piezo
		self.lcd = lcd
		self.battery_monitor = battery_monitor
		self.sdcard = sdcard
		self.rtc = rtc
		self.power_control = power_control

class I2CDeviceAutoSelector:
	def __init__(self, i2c: I2C):
		self.i2c = i2c

	def known_addresses(self) -> List[int]:
		while not self.i2c.try_lock():
			pass
		i2c_address_list = self.i2c.scan()
		self.i2c.unlock()

		return i2c_address_list

	def address_exists(self, address: int) -> bool:
		return address in self.known_addresses()

	def get_device(self,
		address_map: Dict[int, Callable[[int], Any]],
		max_attempts: int = 20,
		delay_between_attempts: float = 0.2
	) -> Any:
		return Util.try_repeatedly(
			max_attempts = max_attempts,
			delay_between_attempts = delay_between_attempts,
			method = lambda: self.try_get_device(address_map = address_map)
		)

	def try_get_device(self, address_map: Dict[int, Callable[[int], Any]]) -> Any:
		address_list = self.known_addresses()

		for address, method in address_map.items():
			if address in address_list:
				return method(address)

		raise RuntimeError(f"No matching I2C device found")
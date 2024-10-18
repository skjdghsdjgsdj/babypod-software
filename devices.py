from battery_monitor import BatteryMonitor
from external_rtc import ExternalRTC
from lcd import LCD
from piezo import Piezo
from power_control import PowerControl
from sdcard import SDCard
from user_input import RotaryEncoder

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


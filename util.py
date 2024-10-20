import time

import adafruit_datetime
import traceback
from busio import I2C

# noinspection PyBroadException
try:
	from typing import Callable, Optional, Any, List, Dict, TypeVar
	I2CDevice = TypeVar("I2CDevice")
	AttemptResponse = TypeVar("AttemptResponse")
except:
	TypeVar = lambda: None
	I2CDevice = lambda: None

class Util:
	"""
	Utility methods.
	"""

	@staticmethod
	def format_elapsed_time(elapsed: float) -> str:
		"""
		Takes a duration and makes a human-readable version of it.

		:param elapsed: Seconds elapsed
		:return: Like "1h 23m 56s" for 5,036 seconds
		"""

		if elapsed < 60:
			return f"{elapsed:.0f} sec"
		elif elapsed < 60 * 60:
			return f"{(elapsed // 60):.0f} min {(int(elapsed) % 60):.0f} sec"
		else:
			return f"{(elapsed // 60 // 60):.0f} hr {(elapsed // 60 % 60):.0f} min {(int(elapsed) % 60):.0f} sec"

	@staticmethod
	def to_datetime(as_str: str) -> adafruit_datetime.datetime:
		"""
		A workaround for a CircuitPython bug that fails to parse ISO times that end with "Z":
		https://github.com/adafruit/Adafruit_CircuitPython_datetime/issues/22

		:param as_str: Date/time as an ISO string
		:return: adafruit_datetime.datetime.fromisoformat(as_str), but if as_str ends with "Z", replace the "Z" with
		"-00:00" to emulate UTC and a format that it does parse
		"""

		if as_str[-1] == "Z":
			print(f"Warning: applying workaround for unsupported datetime format {as_str}")
			as_str = as_str[:-1] + "-00:00"
		return adafruit_datetime.datetime.fromisoformat(as_str)

	@staticmethod
	def datetime_to_time_str(datetime_obj: adafruit_datetime.datetime) -> str:
		"""
		Takes a datetime and converts its time component to a time string, like "1:23a".

		:param datetime_obj: Date/time to convert
		:return: Time string
		"""
		hour = datetime_obj.hour
		minute = datetime_obj.minute
		meridian = "a"

		if hour == 0:
			hour = 12
		elif hour == 12:
			meridian = "p"
		elif hour > 12:
			hour -= 12
			meridian = "p"

		return f"{hour}:{minute:02}{meridian}"

	@staticmethod
	def format_battery_percent(percent: int) -> str:
		"""
		Battery percent formatted as a string
		:param percent: Battery percent (0..100)
		:return: Battery percent formatted as a string
		"""
		return f"{percent}%"

	@staticmethod
	def try_repeatedly(
			method: Callable[[], AttemptResponse],
			max_attempts: int = 3,
			delay_between_attempts: float = 0,
			quiet: bool = False
	) -> AttemptResponse:
		"""
		Try doing something a few times in a row and give up if it fails repeatedly.

		:param method: Try doing this thing. If doing the thing fails, this method must throw an exception.
		:param max_attempts: How many times to try doing the thing until it doesn't throw an exception.
		:param delay_between_attempts: Wait this many seconds between retry attempts
		:return: Whatever method returned
		"""

		assert delay_between_attempts >= 0
		attempts = 0
		while True:
			try:
				return method()
			except Exception as e:
				attempts += 1
				if attempts > max_attempts:
					raise e

				if not quiet:
					print(f"Attempt #{attempts} of {max_attempts} failed with {type(e).__name__}, trying again to invoke: {method}")
					traceback.print_exception(e)
				if delay_between_attempts > 0:
					time.sleep(delay_between_attempts)


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
		address_map: Dict[int, Callable[[int], I2CDevice]],
		max_attempts: int = 20,
		delay_between_attempts: float = 0.2
	) -> I2CDevice:
		return Util.try_repeatedly(
			max_attempts = max_attempts,
			delay_between_attempts = delay_between_attempts,
			method = lambda: self.try_get_device(address_map = address_map),
			quiet = True
		)

	def try_get_device(self, address_map: Dict[int, Callable[[int], I2CDevice]]) -> I2CDevice:
		address_list = self.known_addresses()

		for address, method in address_map.items():
			if address in address_list:
				device = method(address)
				print(f"Using {type(device).__name__} on address {hex(address)}")
				return device

		raise RuntimeError(f"No matching I2C device found")

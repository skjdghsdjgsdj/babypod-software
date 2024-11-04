"""
Static utility methods.
"""

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
		elapsed = int(elapsed)

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
	def duration_to_seconds(duration: str) -> int:
		"""
		Takes a duration in the form h:mm:ss and converts to a total number of seconds. If there are milliseconds, they
		are truncated.

		:param duration: Duration as a string
		:return: Duration as total number of seconds
		"""

		duration_parts = duration.split(":")

		hours = int(duration_parts[0])
		minutes = int(duration_parts[1])
		seconds = int(float(duration_parts[2]))

		return (hours * 60 * 60) + (minutes * 60) + seconds

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
		:param quiet: Don't print anything if an attempt fails
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
	"""
	Finds and returns devices on the I2C bus.
	"""

	def __init__(self, i2c: I2C):
		"""
		:param i2c: I2C bus
		"""
		self.i2c = i2c

	def known_addresses(self) -> List[int]:
		"""
		Lists all known addresses on the I2C bus by locking, scanning, and unlocking it.
		:return: All discovered addresses on I2C bus
		"""

		while not self.i2c.try_lock():
			pass
		i2c_address_list = self.i2c.scan()
		self.i2c.unlock()

		return i2c_address_list

	def address_exists(self, address: int) -> bool:
		"""
		Checks if the I2C bus has a device with the given address.

		TODO this should use busio.I2C.probe() in CircuitPython 9.2

		:param address: Device's address
		:return: True if such a device exists and responds
		"""

		return address in self.known_addresses()

	def get_device(self,
		address_map: Dict[int, Callable[[int], I2CDevice]],
		max_attempts: int = 20,
		delay_between_attempts: float = 0.2
	) -> I2CDevice:
		"""
		Searches the I2C bus for a set of known addresses and, once one is found on the bus that is in the list provided,
		initializes an object given that address.
		:param address_map: Map of I2C addresses to methods that, given that address, can construct an I2CDevice
		:param max_attempts: If the address isn't found or fails to initialize, try again this many times before giving
		up and raising an exception.
		:param delay_between_attempts: Wait this many seconds between attempts to create the I2CDevice
		:return: An initialized I2CDevice for the first address found
		"""

		return Util.try_repeatedly(
			max_attempts = max_attempts,
			delay_between_attempts = delay_between_attempts,
			method = lambda: self.try_get_device(address_map = address_map),
			quiet = True
		)

	def try_get_device(self, address_map: Dict[int, Callable[[int], I2CDevice]]) -> I2CDevice:
		"""
		Attempt to initialize an I2C device given a list of addresses and means of constructing devices. This is a
		one shot method that raises a RuntimeError no device with the given address exists.

		:param address_map: Map of I2C addresses to methods that, given that address, can construct an I2CDevice
		:return: Initialized I2CDevice for the first address found
		"""

		address_list = self.known_addresses()

		for address, method in address_map.items():
			if address in address_list:
				device = method(address)
				print(f"Using {type(device).__name__} on address {hex(address)}")
				return device

		raise RuntimeError(f"No matching I2C device found")

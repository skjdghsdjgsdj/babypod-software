import adafruit_datetime

class Util:
	"""
	Utility methods.
	"""

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
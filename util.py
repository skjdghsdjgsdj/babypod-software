import adafruit_datetime

class Util:
	@staticmethod
	def to_datetime(as_str: str) -> adafruit_datetime.datetime:
		# workaround for https://github.com/adafruit/Adafruit_CircuitPython_datetime/issues/22
		if as_str[-1] == "Z":
			print(f"Warning: applying workaround for unsupported datetime format {as_str}")
			as_str = as_str[:-1] + "-00:00"
		return adafruit_datetime.datetime.fromisoformat(as_str)
import adafruit_rgbled
import board
import os

from nvram import NVRAMValues

class BacklightColor:
	def __init__(self, name: str, default_value):
		value = os.getenv(name)
		if value is None:
			value = default_value

		if not isinstance(value, int) and not isinstance(value, tuple):
			raise TypeError(value)

		self.color = value

	def invert(self):
		if isinstance(self.color, int):
			return 0xFFFFFF - self.color

		if isinstance(self.color, tuple):
			r, g, b = self.color
			return 255 - r, 255 - g, 255 - b

	def __str__(self):
		return str(self.color)

class BacklightColors:
	DEFAULT = BacklightColor("BACKLIGHT_COLOR_FULL", (255, 255, 255))
	DIM = BacklightColor("BACKLIGHT_COLOR_DIM", (128, 128, 128))
	IDLE_WARNING = BacklightColor("BACKLIGHT_COLOR_IDLE_WARNING", (255, 128, 128))
	ERROR = BacklightColor("BACKLIGHT_COLOR_ERROR", (255, 0, 0))
	SUCCESS = BacklightColor("BACKLIGHT_COLOR_SUCCESS", (0, 255, 0))

class Backlight:
	TIMEOUT = 30

	def __init__(self):
		# noinspection PyUnresolvedReferences
		self.backlight = adafruit_rgbled.RGBLED(board.D9, board.D5, board.D6)

		if NVRAMValues.OPTION_BACKLIGHT.get():
			self.set_color(BacklightColors.DEFAULT)
		else:
			self.off()

	def set_color(self, color: BacklightColor) -> None:
		if NVRAMValues.OPTION_BACKLIGHT.get():
			self.backlight.color = color.invert()

	def off(self) -> None:
		print(f"Disabling backlight")
		self.backlight.color = (255, 255, 255) # inverted
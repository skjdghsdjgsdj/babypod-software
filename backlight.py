import time
import adafruit_rgbled
import board
import os

class BacklightColor:
	def __init__(self, name, default_value):
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

BacklightColor.DEFAULT = BacklightColor("BACKLIGHT_COLOR_FULL", (255, 255, 255))
BacklightColor.DIM = BacklightColor("BACKLIGHT_COLOR_DIM", (128, 128, 128))
BacklightColor.IDLE_WARNING = BacklightColor("BACKLIGHT_COLOR_IDLE_WARNING", (255, 128, 128))
BacklightColor.ERROR = BacklightColor("BACKLIGHT_COLOR_ERROR", (255, 0, 0))
BacklightColor.SUCCESS = BacklightColor("BACKLIGHT_COLOR_SUCCESS", (0, 255, 0))

class Backlight:
	TIMEOUT = 30

	def __init__(self, is_option_enabled: bool = True):
		self.is_option_enabled = is_option_enabled
		self.backlight = adafruit_rgbled.RGBLED(board.D9, board.D5, board.D6)

		if is_option_enabled:
			self.set_color(BacklightColor.DEFAULT)
		else:
			self.off()

	def set_color(self, color: BacklightColor):
		if self.is_option_enabled:
			self.backlight.color = color.invert()

	def off(self):
		print(f"Disabling backlight")
		self.backlight.color = (255, 255, 255) # inverted
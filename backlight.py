# noinspection PyBroadException
try:
	from typing import Optional
except:
	# don't care
	pass

import adafruit_rgbled
import board
import os

from nvram import NVRAMValues

class BacklightColor:
	def __init__(self, color: tuple[int, int, int]):
		self.color = color

	@staticmethod
	def from_setting(name: str, default_value: tuple[int, int, int]):
		value = os.getenv(name)
		color = BacklightColor.int_to_tuple(int(value)) if value else default_value

		return BacklightColor(color)

	@staticmethod
	def int_to_tuple(color: int) -> tuple[int, int, int]:
		# adapted from https://github.com/todbot/circuitpython-tricks?tab=readme-ov-file#convert-rgb-tuples-to-int-and-back-again
		# noinspection PyTypeChecker
		return tuple(color.to_bytes(3, "big"))

	def invert(self):
		(r, g, b) = self.color
		return 255 - r, 255 - g, 255 - b

	def mask(self, level: float):
		r, g, b = self.color
		return int(r * level), int(g * level), int(b * level)

	def __str__(self):
		r, g, b = self.color
		return f"({r}, {g}, {b})"

class BacklightColors:
	DEFAULT = BacklightColor.from_setting("BACKLIGHT_COLOR_FULL", (255, 255, 255))
	DIM = BacklightColor.from_setting("BACKLIGHT_COLOR_DIM", (128, 128, 128))
	IDLE_WARNING = BacklightColor.from_setting("BACKLIGHT_COLOR_IDLE_WARNING", (255, 128, 128))
	ERROR = BacklightColor.from_setting("BACKLIGHT_COLOR_ERROR", (255, 0, 0))
	SUCCESS = BacklightColor.from_setting("BACKLIGHT_COLOR_SUCCESS", (0, 255, 0))

class Backlight:
	@staticmethod
	def get_instance():
		return CharacterLCDBacklight()

	def set_color(self, color: BacklightColor) -> None:
		pass # do nothing unless a child class overrides it

	def set_level(self, level: float) -> None:
		if level < 0 or level > 1:
			raise ValueError(f"Backlight level must be >= 0 and <= 1 (0% to 100%), not {level}")
		pass # do nothing unless a child class overrides it

	def off(self) -> None:
		pass # do nothing unless a child class overrides it

class CharacterLCDBacklight(Backlight):
	def __init__(self):
		self.color: Optional[BacklightColor] = None
		self.backlight = None

		if NVRAMValues.BACKLIGHT.get():
			self.set_color(BacklightColors.DEFAULT)
		else:
			self.off()

	def init_backlight(self):
		if self.backlight is None:
			self.backlight = adafruit_rgbled.RGBLED(board.D9, board.D5, board.D6)

		return self.backlight

	def set_color(self, color: BacklightColor) -> None:
		if NVRAMValues.BACKLIGHT.get():
			self.init_backlight().color = color.invert()

		self.color = color

	def set_level(self, level: float) -> None:
		self.set_color(BacklightColor(self.color.mask(level)))

	def off(self):
		print(f"Disabling backlight")
		self.init_backlight().color = (255, 255, 255) # inverted
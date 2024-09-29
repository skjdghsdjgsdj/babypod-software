from lcd import LCD, AdafruitCharacterLCDBackpack, SparkfunSerLCD
from sparkfun_serlcd import Sparkfun_SerLCD

# noinspection PyBroadException
try:
	from typing import Optional, cast
except:
	# don't care
	pass

import adafruit_rgbled
import board
import os

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
	def __init__(self, lcd: LCD):
		self.lcd = lcd
		self.color: Optional[BacklightColor] = None
		self.device = self.init_device()
		self.set_color(BacklightColors.DEFAULT)

	@staticmethod
	def get_instance(lcd: LCD):
		if isinstance(lcd, AdafruitCharacterLCDBackpack):
			return AdafruitCharacterLCDBackpackBacklight(lcd)
		elif isinstance(lcd, SparkfunSerLCD):
			return SparkfunSerLCDBacklight(lcd)

		raise NotImplementedError(f"Don't know how to get backlight for {type(lcd).__name__}")

	def set_color(self, color: BacklightColor) -> None:
		self.set_color_impl(color)
		self.color = color

	def set_color_impl(self, color: BacklightColor):
		pass

	def off(self) -> None:
		pass # do nothing unless a child class overrides it

	def init_device(self):
		raise NotImplementedError()

class SparkfunSerLCDBacklight(Backlight):
	def __init__(self, lcd: SparkfunSerLCD):
		super().__init__(lcd)

	def init_device(self):
		return self.lcd.device

	def set_color_impl(self, color: BacklightColor):
		r, g, b = color.color
		self.device.set_backlight_rgb(r, g, b)

class AdafruitCharacterLCDBackpackBacklight(Backlight):
	def __init__(self, lcd: AdafruitCharacterLCDBackpack):
		super().__init__(lcd)

	def init_device(self):
		return adafruit_rgbled.RGBLED(board.D9, board.D5, board.D6)

	def set_color_impl(self, color: BacklightColor) -> None:
		self.device.color = color.invert()

	def off(self):
		print(f"Disabling backlight")
		self.init_device().color = (255, 255, 255) # inverted
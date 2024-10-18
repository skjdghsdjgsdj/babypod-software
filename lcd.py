from adafruit_character_lcd.character_lcd import Character_LCD
from adafruit_character_lcd.character_lcd_i2c import Character_LCD_I2C

from util import I2CDeviceAutoSelector
from nvram import NVRAMValues
from sparkfun_serlcd import Sparkfun_SerLCD, Sparkfun_SerLCD_I2C

# noinspection PyBroadException
try:
	from typing import List
except:
	pass

from busio import I2C

# noinspection PyBroadException
try:
	from typing import Optional
except:
	# don't care
	pass

import adafruit_rgbled
import board
import os

class BacklightColor:
	"""
	Defines a backlight color (RGB).
	"""

	def __init__(self, color: tuple[int, int, int]):
		"""
		:param color: Color as an RGB tuple with each channel 0..255
		"""
		self.color = color

	@staticmethod
	def from_setting(name: str, default_value: tuple[int, int, int]):
		"""
		Gets an instance of a backlight color from its value defined as an int, like 0xFF0000 for red, in settings.toml
		with the given name, or if one isn't defined, creates one from the given color tuple.

		:param name: Value in settings.toml that might contain a backlight color expressed as an int
		:param default_value: Color to use if settings.toml doesn't contain that value
		:return: BackgroundColor instance with the appropriate color
		"""

		value = os.getenv(name)
		color = BacklightColor.int_to_tuple(int(value)) if value else default_value

		return BacklightColor(color)

	@staticmethod
	def int_to_tuple(color: int) -> tuple[int, int, int]:
		"""
		Converts a color expressed as an int, like 0xFF0000 for red, to an RGB color tuple like (255, 0, 0).

		:param color: color expressed as an int
		:return: color expressed as an RGB tuple
		"""

		# adapted from https://github.com/todbot/circuitpython-tricks?tab=readme-ov-file#convert-rgb-tuples-to-int-and-back-again
		# noinspection PyTypeChecker
		return tuple(color.to_bytes(3, "big"))

	def invert(self) -> tuple[int, int, int]:
		"""
		Inverts the given color; for each channel, 255 - value. Some backlights have a common anode instead of cathode
		and therefore the color must be inverted before it gets applied.

		:return: Inverted color tuple
		"""

		(r, g, b) = self.color
		return 255 - r, 255 - g, 255 - b

	def __str__(self):
		"""
		Convenience method for printing this color in strings.

		:return: This color like "(255, 0, 0)" for red
		"""

		r, g, b = self.color
		return f"({r}, {g}, {b})"

	def __eq__(self, other):
		return self.color == other.color

class BacklightColors:
	"""
	Enum-like class of potential backlight colors auto-populated from their settings or defaults if no settings are
	defined.

	* DEFAULT: normal state
	* DIM: DEFAULT, but dimmer due to inactivity
	* ERROR: something went wrong (uncaught exception, etc.)
	* SUCCESS: something went right (successful POST to API, etc.)
	* OFF: off entirely; this one can't be defined in a setting and is always (0, 0, 0)
	"""

	DEFAULT = BacklightColor.from_setting("BACKLIGHT_COLOR_FULL", (255, 255, 255))
	DIM = BacklightColor.from_setting("BACKLIGHT_COLOR_DIM", (128, 128, 128))
	ERROR = BacklightColor.from_setting("BACKLIGHT_COLOR_ERROR", (255, 0, 0))
	SUCCESS = BacklightColor.from_setting("BACKLIGHT_COLOR_SUCCESS", (0, 255, 0))
	OFF = BacklightColor((0, 0, 0))

class Backlight:
	"""
	Abstract class to control the LCD's backlight.
	"""

	def __init__(self):
		self.color: Optional[BacklightColor] = None

	def set_color(self, color: BacklightColor, only_if_current_color_is: Optional[BacklightColor] = None) -> None:
		"""
        Sets the color of the backlight. Subclasses must implement set_color_impl() that does the hardware calls.

        :param color: Color to set
        :param only_if_current_color_is: Only do the color change if the current backlight color is this
        """

		if self.color is None or only_if_current_color_is is None or self.color == only_if_current_color_is:
			self.set_color_impl(color)
			self.color = color

	def set_color_impl(self, color: BacklightColor):
		"""
		Set the color of the backlight in hardware. In this abstract class, throws NotImplementedError()
		:param color: Color to set
		"""

		raise NotImplementedError()

	def off(self) -> None:
		"""
		Turns off the backlight.
		"""
		self.set_color(BacklightColors.OFF)

class AdafruitCharacterLCDBackpackBacklight(Backlight):
	"""
	Implementation of Backlight that controls an RGB LED and for which the color must be inverted. Adafruit RGB-backlit
	LCDs like https://www.adafruit.com/product/498 act like this. The backlight is assumed to be wired as:

	* Red: D9
	* Green: D5
	* Blue: D6
	"""

	def __init__(self):
		super().__init__()
		self.device: Optional[adafruit_rgbled.RGBLED] = None

	def set_color_impl(self, color: BacklightColor) -> None:
		if self.device is None:
			self.device = adafruit_rgbled.RGBLED(board.D9, board.D5, board.D6)
		self.device.color = color.invert()

class SparkfunSerLCDBacklight(Backlight):
	"""
	Implementation of Backlight that controls the backlight on a Sparkfun SerLCD:
	https://www.sparkfun.com/products/16398
	"""

	def __init__(self, lcd: Sparkfun_SerLCD):
		"""
		:param lcd: Instance of Sparkfun_SerLCD hardware
		"""
		super().__init__()
		self.device = lcd

	def set_color_impl(self, color: BacklightColor):
		r, g, b = color.color
		self.device.set_fast_backlight_rgb(r, g, b)

class LCD:
	"""
	Abstraction of a 20x4 character LCD with backlight.

	This class defines some special characters. Use this as literal bytes in strings for them to show up on the LCD;
	for example, write RIGHT + "Test" for a right arrow and the string "Test."

	* UP_DOWN: an up/down error to hint that up and down can be pressed to increase or decrease a value
	* CHECKED: a checkmark
	* UNCHECKED: an unchecked checkbox
	* CHARGING: device is charging (not used right now)
	* RIGHT: right arrow
	* LEFT: left arrow
	* CENTER: center button hint
	* BLOCK: a solid block used in progress bars

	Don't construct these; use LCD.get_instance() to auto-detect one.
	"""

	UP_DOWN = 0
	CHECKED = 1
	UNCHECKED = 2
	CHARGING = 3
	RIGHT = 4
	LEFT = 5
	CENTER = 6
	BLOCK = 7

	COLUMNS = 20
	LINES = 4

	def __init__(self, backlight: Backlight):
		"""
		:param backlight: Backlight instance to control this LCD's backlight color
		"""
		self.backlight = backlight
		for key, value in LCD.CHARS.items():
			self.create_special_char(key, value)

	def write(self, message: str, coords: tuple[int, int] = (0, 0)) -> None:
		"""
		Writes a message to the LCD at the given coordinates. The actual writing is delegated to write_impl() in
		subclasses. Text that exceeds the width of the display minus the starting X coordinate might wrap on some LCDs
		or be truncated on others, but generally the behavior is undefined and you should avoid writing long strings
		this way. Same deal with newline characters and especially characters outside the lower ASCII character set.

		:param message: Text to write
		:param coords: Coordinates (x, y) to write at. (0, 0) is top-left.
		"""
		LCD.validate_coords(coords)
		self.write_impl(message, coords)

	def write_impl(self, message: str, coords: tuple[int, int]) -> None:
		"""
		To be implemented by subclasses to write to the LCD hardware. Abstract implementation raises
		NotImplementedError.

		:param message: Text to write
		:param coords: Coordinates (x, y) to write at. (0, 0) is top-left.
		"""
		raise NotImplementedError()

	def write_centered(self, text: str, erase_if_shorter_than: int = None, y_delta: int = 0) -> None:
		"""
		Writes a message horizontally and vertically centered in the LCD.
		:param text: Text to write
		:param erase_if_shorter_than: If the given text has fewer than this many characters, erase this many characters
		(write a space to them)
		:param y_delta: Adjust the y position by this amount, like 1 to move down by one line from centered
		"""
		if erase_if_shorter_than is not None and len(text) < erase_if_shorter_than:
			self.write_centered(" " * erase_if_shorter_than, y_delta = y_delta)

		coords = (max(int(LCD.COLUMNS / 2 - len(text) / 2), 0), max(int(LCD.LINES / 2) - 1 + y_delta, 0))
		self.write(text, coords)

	def write_right_aligned(self, text: str, y: int = 0) -> None:
		"""
		Writes a message right-aligned.

		:param text: Text to write
		:param y: y coordinate to write at
		"""
		if len(text) >= LCD.COLUMNS:
			raise ValueError(f"Text exceeds {LCD.COLUMNS} chars: {text}")

		self.write(text, (LCD.COLUMNS - len(text), y))

	def write_bottom_right_aligned(self, text: str, y_delta: int = 0) -> None:
		"""
		Writes a message at the bottom-right of the LCD.

		:param text: Message to write
		:param y_delta: move the message this many lines up from the bottom of the LCD
		"""
		self.write_right_aligned(text, LCD.LINES - 1 - y_delta)

	def write_bottom_left_aligned(self, text: str, y_delta: int = 0) -> None:
		"""
		Writes a message at the bottom-left of the LCD.

		:param text: Message to write
		:param y_delta: move the message this many lines up from the bottom of the LCD
		"""
		self.write(text, (0, LCD.LINES - 1 - y_delta))

	def clear(self) -> None:
		"""
		Clears the display. Abstract method and must be overridden by child classes.
		"""
		raise NotImplementedError()

	def __getitem__(self, special_char: int) -> str:
		"""
		Convenience method to get a character instance of the given special character, like LCD.RIGHT.
		:param special_char: LCD special character, like LCD.RIGHT.
		:return: A character instance that can be concatenated to or embedded in a string
		"""
		return chr(special_char)

	def create_special_char(self, special_char: int, data: List[int]) -> None:
		"""
		Initializes a special character in the LCD device to a given bitmap (of sorts). Abstract method and must be
		implemented by child classes.

		:param special_char: Special character, like LCD.RIGHT.
		:param data: Pixel data (see https://www.quinapalus.com/hd44780udg.html and LCD.CHARS)
		"""
		raise NotImplementedError()

	@staticmethod
	def validate_coords(coords: tuple[int, int]) -> None:
		"""
		Validates that the given (x, y) are within the bounds of the LCD and if not raises ValueError.
		:param coords: (x, y) tuple of coordinates; (0, 0) is top-left
		"""

		x, y = coords
		if x < 0 or x >= LCD.COLUMNS:
			raise ValueError(f"x ({x}) must be >= 0 and < {LCD.COLUMNS}")

		if y < 0 or y >= LCD.LINES:
			raise ValueError(f"y ({y}) must be >= 0 and < {LCD.LINES}")

	@staticmethod
	def get_instance(i2c: I2C):
		"""
		Gets a concrete instance of LCD given what's found on the I2C bus. If one isn't immediately found, then
		repeated scan attempts are made with a brief delay but then eventually gives up and raises a RuntimeError.

		:param i2c: I2C bus that has an LCD on it
		:return: Concrete LCD instance
		"""

		return I2CDeviceAutoSelector(i2c).get_device(
			address_map = {
				0x20: lambda _: AdafruitCharacterLCDBackpack(Character_LCD_I2C(i2c, LCD.COLUMNS, LCD.LINES)),
				0x72: lambda _: SparkfunSerLCD(Sparkfun_SerLCD_I2C(i2c))
			}
		)

# https://www.quinapalus.com/hd44780udg.html
# LCD uses 5x8 pixel chars and supports up to 8 custom chars
LCD.CHARS = {
	LCD.UP_DOWN: [0x4, 0xe, 0x1f, 0x0, 0x0, 0x1f, 0xe, 0x4],
	LCD.UNCHECKED: [0x0, 0x1f, 0x11, 0x11, 0x11, 0x1f, 0x0, 0x0],
	LCD.CHECKED: [0x0, 0x1, 0x3, 0x16, 0x1c, 0x8, 0x0, 0x0],
	LCD.CHARGING: [0x4, 0xe, 0x1b, 0x0, 0xe, 0xa, 0xe, 0xe],
	LCD.RIGHT: [0x10, 0x18, 0x1c, 0x1e, 0x1c, 0x18, 0x10, 0x0],
	LCD.LEFT: [0x2, 0x6, 0xe, 0x1e, 0xe, 0x6, 0x2, 0x0],
	LCD.CENTER: [0x0, 0xe, 0x11, 0x15, 0x11, 0xe, 0x0, 0x0],
	LCD.BLOCK: [0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f, 0x1f]
}

class SparkfunSerLCD(LCD):
	"""
	An implementation of LCD for a Sparkfun SerLCD (https://www.sparkfun.com/products/16398).
	"""

	def __init__(self, lcd: Sparkfun_SerLCD):
		"""
		:param lcd: Sparkfun_SerLCD hardware instance
		"""

		self.device = lcd
		super().__init__(SparkfunSerLCDBacklight(lcd))
		if not NVRAMValues.HAS_CONFIGURED_SPARKFUN_LCD:
			self.device.command(0x2F) # turn off command messages
			self.device.command(0x31) # disable splash screen
			NVRAMValues.HAS_CONFIGURED_SPARKFUN_LCD.write(True)

	def write_impl(self, message: str, coords: tuple[int, int]) -> None:
		x, y = coords
		self.device.set_cursor(x, y)
		self.device.write(message)

	def clear(self) -> None:
		self.device.clear()

	def create_special_char(self, special_char: int, data: List[int]) -> None:
		self.device.create_character(special_char, data)

class AdafruitCharacterLCDBackpack(LCD):
	"""
	An implementation of LCD that uses the Adafruit LCD backpack (https://www.adafruit.com/product/292).
	"""

	def __init__(self, lcd: Character_LCD):
		"""
		:param lcd: Character_LCD hardware instance
		"""

		self.device = lcd
		super().__init__(AdafruitCharacterLCDBackpackBacklight())

	def create_special_char(self, special_char: int, data: List[int]) -> None:
		self.device.create_char(special_char, data)

	def write_impl(self, message: str, coords: tuple[int, int]):
		x, y = coords
		self.device.cursor_position(x, y)
		self.device.message = message

	def clear(self) -> None:
		self.device.clear()
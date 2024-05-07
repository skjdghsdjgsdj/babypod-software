import time
import adafruit_rgbled
import board

class Backlight:
	def __init__(self):
		self.backlight = adafruit_rgbled.RGBLED(board.D9, board.D5, board.D6)
		self.set_color(Backlight.OFF)

	def invert_color(self, color_tuple):
		r, g, b = color_tuple
		return (255 - r, 255 - g, 255 - b)

	def set_color(self, color):
		self.backlight.color = self.invert_color(color)
		self.color = color

	def get_midpoint(self, start, end, percent):
		return abs((start - end) * percent)

	def transition_color(self, color, duration = 0.5):
		assert(duration > 0)

		start = time.monotonic()
		end = start + duration

		start_r, start_g, start_b = self.color
		end_r, end_g, end_b = color

		while time.monotonic() <= end:
			percent = max(min(time.monotonic() - start, 1), 0)

			r, g, b = (
				self.get_midpoint(start_r, end_r, percent),
				self.get_midpoint(start_g, end_g, percent),
				self.get_midpoint(start_b, end_b, percent)
			)

			self.set_color((r, g, b))

		self.set_color(color)

#Backlight.OFF = (100, 0, 100)
Backlight.OFF = (70, 100, 70)
#Backlight.DEFAULT_COLOR = (255, 0, 255)
Backlight.DEFAULT_COLOR = (128, 255, 128)
Backlight.TIMEOUT = 30

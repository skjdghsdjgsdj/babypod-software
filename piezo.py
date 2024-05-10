import simpleio
import board
import time

class Piezo:
	def __init__(self, is_option_enabled: bool = True):
		self.is_option_enabled = is_option_enabled

	def tone(self, name):
		if self.is_option_enabled:
			data = Piezo.TONES[name]
			for i in range(0, len(data)):
				frequency, duration = data[i]
				if frequency is None:
					time.sleep(duration)
				else:
					simpleio.tone(board.A3, frequency, duration)

Piezo.TONES = {
	"startup": [
		[440, 0.1],
		[660, 0.1]
	],
	"success": [
		[660, 0.1],
		[None, 0.02],
		[660, 0.1],
		[None, 0.02],
		[660, 0.1],
		[880, 0.2]
	],
	"error": [
		[660, 0.2],
		[440, 0.4]
	],
	"idle_warning": [
		[700, 0.3]
	],
	"chime": [
		[440, 0.1],
		[None, 0.1],
		[440, 0.1]
	],
	"low_battery": [
		[660, 0.1],
		[550, 0.1],
		[440, 0.4]
	]
}
import simpleio
import board
import time

from nvram import NVRAMValues

class Piezo:
	TONES = {
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

	@staticmethod
	def tone(name: str) -> None:
		if NVRAMValues.OPTION_PIEZO.get():
			data = Piezo.TONES[name]
			for i in range(0, len(data)):
				frequency, duration = data[i]
				if frequency is None:
					time.sleep(duration)
				else:
					# noinspection PyUnresolvedReferences
					simpleio.tone(board.A3, frequency, duration)

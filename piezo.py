"""
Piezo tones.
"""

import simpleio
import board
import time

from nvram import NVRAMValues

class Piezo:
	"""
	Abstraction of the piezo.
	"""

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
			[700, 0.3],
			[None, 0.1],
			[700, 0.3],
			[None, 0.1],
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
		],
		"info": [
			[660, 0.1],
			[None, 0.3],
			[660, 0.1]
		],
		"shutdown": [
			[660, 0.1],
			[440, 0.1]
		],
		"motd": [
			[660, 0.2],
			[None, 0.05],
			[660, 0.1],
			[None, 0.05],
			[660, 0.1],
			[None, 0.05],
			[660, 0.3],
			[440, 0.3],
			[880, 0.3]
		]
	}

	@staticmethod
	def tone(name: str, pin = board.A3) -> None:
		"""
		Play something on the piezo. Note that this method blocks as the piezo plays, so if a given tone takes, say, 5
		seconds to play, this method blocks for the entire 5 seconds.

		:param name: Tone/melody/chime/etc. to play; use a string from the keys in Piezo.TONES, like "success"
		:param pin: PWM pin to which the piezo is connected
		"""

		if NVRAMValues.PIEZO.get():
			data = Piezo.TONES[name]
			for i in range(0, len(data)):
				frequency, duration = data[i]
				if frequency is None:
					time.sleep(duration)
				else:
					simpleio.tone(pin, frequency, duration)
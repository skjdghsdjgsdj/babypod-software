import simpleio
import board
import time

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

class PeriodicChime:
	def __init__(self, piezo: Piezo):
		self.last_chime = None
		self.piezo = piezo
		self.total_elapsed = None
		self.started_at = None

	def start(self):
		self.last_chime = time.monotonic()
		self.total_elapsed = 0
		self.started_at = time.monotonic()

	def chime_if_needed(self):
		now = time.monotonic()
		self.total_elapsed = now - self.started_at

		elapsed = now - self.last_chime
		if self.is_chime_time(elapsed):
			self.last_chime = time.monotonic()
			self.piezo.tone("chime")

	def is_chime_time(self, elapsed):
		raise NotImplementedError()

class ConsistentIntervalPeriodicChime(PeriodicChime):
	def __init__(self, piezo: Piezo, chime_at_seconds: int):
		super().__init__(piezo)
		if chime_at_seconds <= 0:
			raise ValueError("chime_interval_seconds must be > 0")
		self.chime_at_seconds = chime_at_seconds

	def is_chime_time(self, elapsed):
		return elapsed >= self.chime_at_seconds

class EscalatingIntervalPeriodicChime(ConsistentIntervalPeriodicChime):
	def __init__(self, piezo: Piezo, chime_at_seconds: int, escalating_chime_at_seconds: int, interval_once_escalated_seconds: int = 60):
		super().__init__(piezo, chime_at_seconds)
		self.escalating_chime_at_seconds = escalating_chime_at_seconds
		self.interval_once_escalated_seconds = interval_once_escalated_seconds

	def is_chime_time(self, elapsed):
		if super().is_chime_time(elapsed):
			return True

		if self.total_elapsed >= self.escalating_chime_at_seconds:
			adjusted_elapsed = int(self.total_elapsed - self.escalating_chime_at_seconds)
			return adjusted_elapsed % self.interval_once_escalated_seconds == 0

		return False
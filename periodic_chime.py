import time

from devices import Devices


class PeriodicChime:
	def __init__(self, devices: Devices):
		self.last_chime = None
		self.devices = devices
		self.total_elapsed = None
		self.started_at = None

	def start(self) -> None:
		self.last_chime = time.monotonic()
		self.total_elapsed = 0
		self.started_at = time.monotonic()

	def chime_if_needed(self) -> None:
		now = time.monotonic()
		self.total_elapsed = now - self.started_at

		elapsed = now - self.last_chime
		if self.is_chime_time(elapsed):
			self.last_chime = time.monotonic()
			self.devices.piezo.tone("chime")

	def is_chime_time(self, elapsed: float) -> bool:
		raise NotImplementedError()

class ConsistentIntervalPeriodicChime(PeriodicChime):
	def __init__(self, devices: Devices, chime_at_seconds: int):
		super().__init__(devices)
		if chime_at_seconds <= 0:
			raise ValueError("chime_interval_seconds must be > 0")
		self.chime_at_seconds = chime_at_seconds

	def is_chime_time(self, elapsed: float) -> bool:
		return elapsed >= self.chime_at_seconds

class EscalatingIntervalPeriodicChime(ConsistentIntervalPeriodicChime):
	def __init__(self, devices: Devices, chime_at_seconds: int, escalating_chime_at_seconds: int, interval_once_escalated_seconds: int = 60):
		super().__init__(devices, chime_at_seconds)
		self.escalating_chime_at_seconds = escalating_chime_at_seconds
		self.interval_once_escalated_seconds = interval_once_escalated_seconds
		self.last_escalated_chime_seconds = self.escalating_chime_at_seconds

	def is_chime_time(self, elapsed: float) -> bool:
		if super().is_chime_time(elapsed):
			return True

		if self.total_elapsed >= self.escalating_chime_at_seconds:
			elapsed_interval = self.total_elapsed - self.last_escalated_chime_seconds
			if elapsed_interval >= self.interval_once_escalated_seconds:
				self.last_escalated_chime_seconds = self.total_elapsed
				return True

		return False
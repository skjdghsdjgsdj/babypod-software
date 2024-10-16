import time

from devices import Devices

class PeriodicChime:
	"""
	Metadata for when and how often to play a chime as a timer is running.
	"""

	def __init__(self, devices: Devices):
		"""
		:param devices: Devices dependency injection
		"""
		self.last_chime = None
		self.devices = devices
		self.total_elapsed = None
		self.started_at = None

	def start(self) -> None:
		"""
		Start counting from now.
		"""

		self.last_chime = time.monotonic()
		self.total_elapsed = 0
		self.started_at = time.monotonic()

	def chime_if_needed(self) -> None:
		"""
		Checks how much time has elapsed and, if a chime is due, play it.
		"""

		now = time.monotonic()
		self.total_elapsed = now - self.started_at

		elapsed = now - self.last_chime
		if self.is_chime_time(elapsed):
			self.last_chime = time.monotonic()
			self.devices.piezo.tone("chime")

	def is_chime_time(self, elapsed: float) -> bool:
		"""
		Logic for if, now that the given number of seconds have elapsed, a chime should be played. Abstract method;
		must be implemented by child classes.

		:param elapsed: How many seconds have elapsed
		:return: True if a chime should be played right now, False if not
		"""

		raise NotImplementedError()

class ConsistentIntervalPeriodicChime(PeriodicChime):
	"""
	Chime at a consistent interval; i.e., every n seconds.
	"""

	def __init__(self, devices: Devices, chime_at_seconds: int):
		"""
		:param devices: Devices dependency injection
		:param chime_at_seconds: How many seconds to regularly chime at, like 30 to chime every 30 seconds
		"""

		super().__init__(devices)
		if chime_at_seconds <= 0:
			raise ValueError("chime_interval_seconds must be > 0")
		self.chime_at_seconds = chime_at_seconds

	def is_chime_time(self, elapsed: float) -> bool:
		"""
		:param elapsed: How many seconds have elapsed
		:return: True if elapsed >= self.chime_at_seconds
		"""
		return elapsed >= self.chime_at_seconds

class EscalatingIntervalPeriodicChime(ConsistentIntervalPeriodicChime):
	"""
	Chime every x seconds, but if a certain amount of time has passed, also chime every y seconds.
	"""

	def __init__(self, devices: Devices, chime_at_seconds: int, escalating_chime_at_seconds: int, interval_once_escalated_seconds: int = 60):
		"""
		:param devices: Devices dependency injection
		:param chime_at_seconds: Chime every n seconds
		:param escalating_chime_at_seconds: After this many seconds have passed, start chiming every
		interval_interval_once_escalated_seconds seconds
		:param interval_once_escalated_seconds: After escalating_chime_at_seconds seconds have elapsed, start chiming
		every n seconds
		"""

		super().__init__(devices, chime_at_seconds)
		self.escalating_chime_at_seconds = escalating_chime_at_seconds
		self.interval_once_escalated_seconds = interval_once_escalated_seconds
		self.last_escalated_chime_seconds = self.escalating_chime_at_seconds

	def is_chime_time(self, elapsed: float) -> bool:
		"""
		:param elapsed: Number of seconds elapsed
		:return: True if number of elapsed seconds calls for a chime; see the constructor's arguments for logic
		"""

		if super().is_chime_time(elapsed):
			return True

		if self.total_elapsed >= self.escalating_chime_at_seconds:
			elapsed_interval = self.total_elapsed - self.last_escalated_chime_seconds
			if elapsed_interval >= self.interval_once_escalated_seconds:
				self.last_escalated_chime_seconds = self.total_elapsed
				return True

		return False
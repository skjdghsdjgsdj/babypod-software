from nvram import NVRAMBooleanValue

# noinspection PyBroadException
try:
	from typing import Callable, Optional
except:
	pass

class Setting:
	"""
	A user-facing setting that gets presented ultimately as a checkbox.
	"""

	def __init__(self,
		name: str,
		backing_nvram_value: NVRAMBooleanValue,
		is_available: Callable[[], bool] = lambda: True,
		on_save: Callable[[bool], None] = lambda _: None
	):
		"""
		:param name: Name to show to the user. Be mindful of the length: it must be <= 18 characters to fit on the
		screen, and depending on which line it's shown on, might need to be even shorter so it doesn't run into other UI
		elements.
		:param backing_nvram_value: NVRAMBooleanValue that will be used to retrieve and save this setting
		:param is_available: True if this setting should be shown to the user, or False if not. False is normally for
		cases where underlying hardware isn't available; for example, "Offline" wouldn't be available if an RTC or SD
		card weren't available
		:param on_save: Extra actions to take when saving this setting and the value has changed. For example, when
		changing the offline setting, take extra actions to actually go offline. Don't write the NVRAM backing value in
		your function; that happens automatically.
		"""

		self.name = name
		self.is_available = is_available
		self.backing_nvram_value = backing_nvram_value
		self.on_save = on_save

	def __bool__(self) -> bool:
		"""
		:return: self.get(), literally
		"""
		return self.get()

	def get(self) -> bool:
		"""
		Gets the value of this setting as stored in NVRAM.

		:return: The backing value stored in NVRAM
		"""
		return self.backing_nvram_value.get()

	def save(self, value: bool) -> None:
		"""
		Invokes on_save if the value has changed and then regardless saves the value to NVRAM.

		:param value: New value of the setting
		"""

		if self.get() != value:
			self.on_save(value)
		self.backing_nvram_value.write(value)
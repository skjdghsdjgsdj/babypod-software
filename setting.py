from nvram import NVRAMBooleanValue

# noinspection PyBroadException
try:
	from typing import Callable, Optional
except:
	pass

class Setting:
	def __init__(self,
		name: str,
		backing_nvram_value: NVRAMBooleanValue,
		is_available: Callable[[], bool] = lambda: True,
		on_save: Callable[[bool], None] = lambda _: None
	):
		self.name = name
		self.is_available = is_available
		self.backing_nvram_value = backing_nvram_value
		self.on_save = on_save

	def __bool__(self) -> bool:
		return self.get()

	def get(self) -> bool:
		return self.backing_nvram_value.get()

	def save(self, value: bool) -> None:
		if self.get() != value:
			self.on_save(value)
		self.backing_nvram_value.write(value)
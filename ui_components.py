import math

from devices import Devices
from lcd import LCD
from periodic_chime import PeriodicChime
from user_input import RotaryEncoder, WaitTickListener
import time

# noinspection PyBroadException
try:
	from typing import Optional, Callable
except:
	pass
	# ignore, just for IDE's sake, not supported on board

class UIComponent:
	RIGHT = 0
	LEFT = 1

	def __init__(self,
		devices: Devices,
		allow_cancel: bool = True,
		cancel_text: str = None,
		cancel_align: int = None,
		before_wait_loop: Optional[Callable[[], None]] = None
	):
		self.devices = devices
		self.allow_cancel = allow_cancel
		self.cancel_align = cancel_align
		self.cancel_text = (self.devices.lcd[LCD.LEFT] + "Cancel") if cancel_text is None else cancel_text
		self.before_wait_loop = before_wait_loop

	def render_and_wait(self) -> None:
		if self.allow_cancel:
			col = 0 if self.cancel_align == UIComponent.LEFT else LCD.COLUMNS - len(self.cancel_text)
			self.devices.lcd.write(self.cancel_text, (col, LCD.LINES - 1))

	def render_save(self, y_delta: int = 0, message: str = "Save") -> None:
		save_message = message + self.devices.lcd[LCD.RIGHT]
		self.devices.lcd.write(save_message, (LCD.COLUMNS - len(save_message), LCD.LINES - y_delta - 1))

class Modal(UIComponent):
	def __init__(self, devices: Devices, message: str, dismiss_text: str = "Dismiss", before_wait_loop: Optional[Callable[[], None]] = None):
		super().__init__(devices = devices, allow_cancel = False, before_wait_loop = before_wait_loop)

		self.message = message
		self.dismiss_text = dismiss_text

	def render_and_wait(self) -> None:
		super().render_and_wait()

		self.devices.lcd.write_centered(self.message)

		self.render_save(message = self.dismiss_text)

		if self.before_wait_loop is not None:
			self.before_wait_loop()

		while True:
			button = self.devices.rotary_encoder.wait(listen_for_rotation = False)
			if button == RotaryEncoder.SELECT or button == RotaryEncoder.RIGHT:
				return

class ProgressBar(UIComponent):
	def __init__(self, devices: Devices, count: int, message: str):
		assert(count > 0)

		super().__init__(
			devices = devices,
			allow_cancel = False
		)

		self.count = count
		self.index = 0
		self.last_block_count = -1
		self.max_block_count = LCD.COLUMNS - len(str(self.count)) * 2 - 1
		self.message = message

	def set_index(self, index: int = 0) -> None:
		if index < 0:
			raise ValueError(f"Index must be >= 0, not {index}")

		if index >= self.count:
			raise ValueError(f"Index must be < {self.count}, not {index}")

		self.index = index

		self.render_progress()

	def render_progress(self) -> None:
		self.devices.lcd.write(
			message = str(self.index + 1),
			coords = (LCD.COLUMNS - len(str(self.count)) * 2 - 1, 2)
		)

		block_count = math.ceil(((self.index + 1) / self.count) * self.max_block_count) + 1

		if self.last_block_count == -1:
			self.devices.lcd.write(self.devices.lcd[LCD.BLOCK] * block_count, (0, 2))
			self.last_block_count = block_count
		elif block_count != self.last_block_count:
			extra_blocks = block_count - self.last_block_count
			self.devices.lcd.write(self.devices.lcd[LCD.BLOCK] * extra_blocks, (self.last_block_count - 1, 2))

	def render_and_wait(self) -> None:
		super().render_and_wait()

		self.devices.lcd.write_centered(self.message)
		self.devices.lcd.write_right_aligned("/" + str(self.count), 2)

		self.render_progress()

class ActiveTimer(UIComponent):
	def __init__(self,
		devices: Devices,
		allow_cancel: bool = True,
		cancel_text: str = None,
		periodic_chime: PeriodicChime = None,
		start_at: float = 0,
		before_wait_loop: Optional[Callable[[], None]] = None
	):
		super().__init__(
			devices = devices,
			allow_cancel = allow_cancel,
			cancel_text = cancel_text,
			cancel_align = UIComponent.LEFT,
			before_wait_loop = before_wait_loop
		)
		self.start = None
		self.periodic_chime = periodic_chime
		self.start_at = start_at

	def render_and_wait(self) -> Optional[bool]:
		super().render_and_wait()

		self.render_save()

		self.start = time.monotonic()
		if self.periodic_chime is not None:
			self.periodic_chime.start()

		class ActiveTimerWaitTickListener(WaitTickListener):
			def __init__(self, devices: Devices, start: float, periodic_chime: PeriodicChime):
				self.start = start
				self.last_message = None
				self.devices = devices
				self.periodic_chime = periodic_chime
				super().__init__(seconds = 1, on_tick = self.render_elapsed_time, recurring = True)
				self.render_elapsed_time(start)

			@staticmethod
			def format_elapsed_time(elapsed: float) -> str:
				if elapsed < 60:
					return f"{elapsed:.0f} sec"
				elif elapsed < 60 * 60:
					return f"{(elapsed // 60):.0f} min {(int(elapsed) % 60):.0f} sec"
				else:
					return f"{(elapsed // 60 // 60):.0f} hr {(elapsed // 60 % 60):.0f} min {(int(elapsed) % 60):.0f} sec"

			def render_elapsed_time(self, _: float) -> None:
				message = ActiveTimerWaitTickListener.format_elapsed_time(time.monotonic() - self.start)
				self.devices.lcd.write_centered(
					text = message,
					erase_if_shorter_than = None if self.last_message is None else len(self.last_message)
				)
				self.last_message = message

				if self.periodic_chime is not None:
					self.periodic_chime.chime_if_needed()

		wait_tick_listener = ActiveTimerWaitTickListener(
			devices = self.devices,
			start = self.start - self.start_at,
			periodic_chime = self.periodic_chime
		)

		if self.before_wait_loop is not None:
			self.before_wait_loop()

		while True:
			button = self.devices.rotary_encoder.wait(
				listen_for_rotation = False,
				extra_wait_tick_listeners = [wait_tick_listener]
			)
			if button == RotaryEncoder.LEFT and self.allow_cancel:
				return None
			elif button == RotaryEncoder.SELECT or button == RotaryEncoder.RIGHT:
				return True

class NumericSelector(UIComponent):
	def __init__(self,
		devices: Devices,
		value: float = None,
		step: float = 1,
		minimum: float = 0,
		maximum: float = None,
		allow_cancel: bool = True,
		cancel_text: str = None,
		row: int = 2,
		format_str: str = "%d",
		before_wait_loop: Optional[Callable[[], None]] = None
	):
		super().__init__(devices = devices, allow_cancel = allow_cancel, cancel_text = cancel_text, before_wait_loop = before_wait_loop)

		assert(0 <= row < LCD.LINES)
		assert(minimum is None or isinstance(minimum, (int, float)))
		assert(maximum is None or isinstance(maximum, (int, float)))
		assert(isinstance(step, (int, float)))
		assert(step > 0)
		assert(minimum is None or minimum % step == 0)
		assert(maximum is None or maximum % step == 0)

		if minimum is not None and maximum is not None:
			assert(minimum < maximum)

		if value is None:
			if minimum is not None:
				value = minimum
			elif maximum is not None:
				value = maximum
		else:
			assert(minimum is None or value >= minimum)
			assert(maximum is None or value <= maximum)
			assert(value % step == 0)

		self.range = (minimum, maximum)
		self.step = step
		self.selected_value = value
		self.row = row
		self.format_str = format_str

	def render_and_wait(self) -> Optional[float]:
		super().render_and_wait()
		super().render_save(1)

		self.devices.lcd.write(self.devices.lcd[LCD.UP_DOWN], (0, self.row))

		if self.before_wait_loop is not None:
			self.before_wait_loop()

		last_value = None
		while True:
			if last_value != self.selected_value:
				if last_value is not None:
					selected_strlen = len(self.format_str % self.selected_value)
					last_strlen = len(self.format_str % last_value)
					value_strlen_difference = last_strlen - selected_strlen
					if value_strlen_difference > 0:
						self.devices.lcd.write(
							message = " " * value_strlen_difference,
							coords = (1 + last_strlen - value_strlen_difference, self.row))

				self.devices.lcd.write(message = self.format_str % self.selected_value, coords = (1, self.row))

				last_value = self.selected_value

			button = self.devices.rotary_encoder.wait()
			if button == RotaryEncoder.LEFT and self.allow_cancel:
				return None
			if button == RotaryEncoder.UP or button == RotaryEncoder.CLOCKWISE:
				self.selected_value += self.step
			elif button == RotaryEncoder.DOWN or button == RotaryEncoder.COUNTERCLOCKWISE:
				self.selected_value -= self.step
			elif button == RotaryEncoder.SELECT or button == RotaryEncoder.RIGHT:
				return self.selected_value

			minimum, maximum = self.range
			if minimum is not None and self.selected_value < minimum:
				self.selected_value = minimum
			elif maximum is not None and self.selected_value > maximum:
				self.selected_value = maximum

class VerticalMenu(UIComponent):
	ANCHOR_TOP = 0
	ANCHOR_BOTTOM = 1

	def __init__(self,
				 devices: Devices,
				 options: list[str],
				 allow_cancel: bool = True,
				 cancel_text: str = None,
				 anchor: int = ANCHOR_BOTTOM,
				 before_wait_loop: Optional[Callable[[], None]] = None):
		super().__init__(devices = devices, allow_cancel = allow_cancel, cancel_text = cancel_text, before_wait_loop = before_wait_loop)

		self.options = options
		self.selected_row_index = None
		self.anchor = anchor

	def index_to_row(self, i: int) -> int:
		row = i
		if self.anchor == VerticalMenu.ANCHOR_BOTTOM:
			row += LCD.LINES - len(self.options)

		return row

	def move_selection(self, button: int) -> bool:
		if button == RotaryEncoder.UP or button == RotaryEncoder.COUNTERCLOCKWISE:
			self.move_selection_up(wrap = button == RotaryEncoder.UP)
			return True
		elif button == RotaryEncoder.DOWN or button == RotaryEncoder.CLOCKWISE:
			self.move_selection_down(wrap = button == RotaryEncoder.DOWN)
			return True

		return False

	def on_select_pressed(self) -> int:
		return self.selected_row_index

	def on_right_pressed(self) -> int:
		return self.selected_row_index

	def init_extra_ui(self) -> None:
		pass

	def format_menu_item(self, index, name) -> str:
		return name

	def render_and_wait(self) -> Optional[int]:
		super().render_and_wait()

		i = 0
		for value in self.options:
			# skip first column; arrow goes there
			item_str = self.format_menu_item(i, value)
			self.devices.lcd.write(item_str, (1, self.index_to_row(i)))
			i += 1

		self.move_arrow(0)

		self.init_extra_ui()

		if self.before_wait_loop is not None:
			self.before_wait_loop()

		while True:
			button = self.devices.rotary_encoder.wait()
			if not self.move_selection(button):
				if button == RotaryEncoder.LEFT and self.allow_cancel:
					return None
				elif button == RotaryEncoder.RIGHT:
					result = self.on_right_pressed()
					if result is not None:
						return result
				elif button == RotaryEncoder.SELECT:
					result = self.on_select_pressed()
					if result is not None:
						return result

	def move_selection_up(self, wrap: bool = True) -> None:
		row_index = self.selected_row_index - 1
		if row_index < 0:
			if wrap:
				row_index = len(self.options) - 1
			else:
				return

		self.move_arrow(row_index)

	def move_selection_down(self, wrap: bool = True) -> None:
		row_index = self.selected_row_index + 1
		if row_index >= len(self.options):
			if wrap:
				row_index = 0
			else:
				return

		self.move_arrow(row_index)

	def move_arrow(self, row_index: int) -> None:
		self.devices.lcd.write(message = self.devices.lcd[LCD.RIGHT], coords = (0, self.index_to_row(row_index)))

		if self.selected_row_index is not None and row_index != self.selected_row_index:
			self.devices.lcd.write(message = " ", coords = (0, self.index_to_row(self.selected_row_index)))

		self.selected_row_index = row_index

class VerticalCheckboxes(VerticalMenu):
	def __init__(self,
		devices: Devices,
		options: list[str],
		initial_states: list[bool],
		allow_cancel: bool = True,
		cancel_text: str = None,
		anchor: int = 1,
		before_wait_loop: Optional[Callable[[], None]] = None
	):
		super().__init__(
			devices = devices,
			options = options,
			allow_cancel = allow_cancel,
			cancel_text = cancel_text,
			anchor = anchor,
			before_wait_loop = before_wait_loop
		)

		assert(len(options) == len(initial_states))

		self.states = initial_states

	def get_checkbox_char(self, index: int) -> str:
		return self.devices.lcd[LCD.CHECKED] if self.states[index] else self.devices.lcd[LCD.UNCHECKED]

	def toggle_item(self, index: int) -> None:
		self.states[index] = not self.states[index]
		self.devices.lcd.write(self.get_checkbox_char(index), (1, self.index_to_row(index)))

	def on_select_pressed(self) -> None:
		self.toggle_item(self.selected_row_index)
		return None

	def on_right_pressed(self) -> list[bool]:
		return self.states

	def init_extra_ui(self) -> None:
		self.render_save(y_delta = 1 if self.allow_cancel else 0)

	def format_menu_item(self, index: int, name: str) -> str:
		return self.get_checkbox_char(index) + name

	def render_and_wait(self) -> list[int]:
		response = super().render_and_wait()
		return None if response is None else self.states

class BooleanPrompt(VerticalMenu):
	def __init__(
		self,
		devices: Devices,
		allow_cancel: bool = True,
		cancel_text: str = None,
		anchor: int = VerticalMenu.ANCHOR_BOTTOM,
		yes_text: str = "Yes",
		no_text: str = "No",
		before_wait_loop: Optional[Callable[[], None]] = None
	):
		if cancel_text is not None:
			print("cancel_text is not supported for boolean prompts; it will be ignored")

		super().__init__(
			devices = devices,
			options = [yes_text, no_text],
			allow_cancel = allow_cancel,
			cancel_text = None,
			anchor = anchor,
			before_wait_loop = before_wait_loop
		)

	def render_and_wait(self) -> Optional[bool]:
		selected_index = super().render_and_wait()

		if selected_index == 0:
			return True
		elif selected_index == 1:
			return False
		else:
			return None

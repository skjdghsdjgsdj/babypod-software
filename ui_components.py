import math

from devices import Devices
from lcd import LCD, BacklightColors, BacklightColor
from nvram import NVRAMValues
from periodic_chime import PeriodicChime
from user_input import RotaryEncoder, WaitTickListener
import time

from util import Util

# noinspection PyBroadException
try:
	from typing import Optional, Callable
	from abc import ABC, abstractmethod
except:
	class ABC:
		pass

	# noinspection PyUnusedLocal
	def abstractmethod(*args, **kwargs):
		pass

class UIComponent(ABC):
	"""
	Abstract class that represents a full screen user interface.
	"""

	RIGHT = 0
	LEFT = 1

	def __init__(self,
		devices: Devices,
		allow_cancel: bool = True,
		cancel_text: Optional[str] = None,
		cancel_align: Optional[int] = None,
		header: Optional[str] = None,
		save_text: Optional[str] = "Save",
		save_text_y_delta: int = 0
	):
		"""
		:param devices: Devices dependency injection
		:param allow_cancel: True to allow the user to cancel (go back) from this component, False if not
		:param cancel_text: UI hint to show to the user for cancelling this action
		:param cancel_align: Left (UIComponent.LEFT) or right (UIComponent.RIGHT) alignment of the cancel text
		"""

		self.devices = devices
		self.allow_cancel = allow_cancel
		self.cancel_align = cancel_align
		self.cancel_text = self.devices.lcd[LCD.LEFT] + ("Cancel" if cancel_text is None else cancel_text)
		self.header = header
		self.save_text = save_text
		self.save_text_y_delta = save_text_y_delta

	def render(self):
		"""
		Renders the UI. Child classes will greatly extend this method but should always call the base method.

		The base method:
		* Clears the screen
		* Renders the battery percent at the top-right, if available
		* Renders the Cancel and Save widgets, if applicable

		:return: self for call chaining
		"""
		self.devices.lcd.clear()

		if self.header is not None:
			self.devices.lcd.write(self.header)

		battery_percent = self.devices.battery_monitor.get_percent() if self.devices.battery_monitor else None
		if battery_percent is not None:
			self.devices.lcd.write_right_aligned(Util.format_battery_percent(battery_percent))

		if self.allow_cancel:
			if self.cancel_align == UIComponent.RIGHT:
				self.devices.lcd.write_bottom_right_aligned(self.cancel_text, 0 if self.save_text is None else 1)
			elif self.cancel_align == UIComponent.LEFT or self.cancel_align is None:
				self.devices.lcd.write_bottom_left_aligned(self.cancel_text)
			else:
				raise ValueError(f"Unknown alignment {self.cancel_align}")

		if self.save_text is not None:
			save_message = self.save_text + self.devices.lcd[LCD.RIGHT]
			self.devices.lcd.write_bottom_right_aligned(save_message, self.save_text_y_delta)

		return self

	def wait(self):
		"""
		Wait for user input and returns what the user inputted. How that's actually defined is up to a subclass to
		implement. The base method just throws RuntimeError.

		Some UIComponents don't wait, like progress bars or status messages, because the code is expected to keep
		doing things after rendering and no user input is expected.

		:return: Up to a subclass to define, but a good practice is to return None if the equivalent of cancelling the
		input was performed
		"""

		raise RuntimeError(f"UIComponents of type {type(self).__name__} are non-blocking")

	@staticmethod
	def refresh_battery_percent(devices: Devices, only_if_changed: bool = False) -> None:
		"""
		Refreshes the battery percentage shown at the top-right of the screen without clearing the entire screen.

		:param devices: Devices dependency injection
		:param only_if_changed: Only refresh the battery percentage if changed since it was last read
		"""

		if devices.battery_monitor is None:
			return

		last_percent = devices.battery_monitor.last_percent

		try:
			percent = devices.battery_monitor.get_percent()
		except Exception as e:
			import traceback
			traceback.print_exception(e)
			return

		if last_percent is None and percent is None:
			return

		message = Util.format_battery_percent(percent)

		if not only_if_changed or last_percent != percent:
			if last_percent is not None and percent < last_percent:
				current_len = len(message)
				last_len = len(Util.format_battery_percent(last_percent))
				char_count_difference = last_len - current_len

				if char_count_difference > 0:
					devices.lcd.write(" " * char_count_difference, (LCD.COLUMNS - last_len, 0))

			message = Util.format_battery_percent(percent)
			devices.lcd.write(message, (LCD.COLUMNS - len(message), 0))

class StatusMessage(UIComponent):
	"""
	Renders a message in full screen with no controls and without blocking.
	"""

	def __init__(self, devices: Devices, message: str):
		"""
		:param devices: Devices dependency injection
		:param message: Message to show (<= 20 characters)
		"""

		super().__init__(devices = devices, allow_cancel = False, save_text = None)
		self.message = message

	def render(self) -> UIComponent:
		super().render()
		self.devices.lcd.write_centered(self.message)
		return self

class Modal(UIComponent):
	"""
	A simple text dialog that must be dismissed by the user with no other actions or automatically closes after a
	defined number of seconds.
	"""

	def __init__(
			self,
			devices: Devices,
			message: str,
			save_text: str = "Dismiss",
			auto_dismiss_after_seconds: int = 0
		):
		"""
		:param devices: Devices dependency injection
		:param message: Message to show to the user; keep it <= 20 characters long
		:param auto_dismiss_after_seconds: 0 to keep the modal open indefinitely or > 0 to automatically dismiss the
		modal if it wasn't manually dismissed by the user by this many seconds.
		"""

		super().__init__(devices = devices, allow_cancel = False, save_text = save_text)

		self.auto_dismiss_after_seconds = auto_dismiss_after_seconds
		self.message = message

	def render(self) -> UIComponent:
		super().render()
		self.devices.lcd.write_centered(self.message)
		return self

	def wait(self) -> bool:
		"""
		Blocks for user input or, if auto_dismiss_after_seconds is > 0, that many seconds have elapsed with no input.

		:return: True if the user explicitly dismissed this modal using input or False if it just timed out instead
		"""

		class ModalDialogExpiredException(Exception):
			pass

		class AutoDismissWaitTickListener(WaitTickListener):
			"""
			Raises an exception after a specified timeout.
			"""

			def __init__(self, auto_dismiss_after_seconds: int):
				"""
				:param auto_dismiss_after_seconds: Raise an exception after this many seconds have elapsed
				"""

				super().__init__(auto_dismiss_after_seconds, self.dismiss_dialog)

			def dismiss_dialog(self, _: float) -> None:
				"""
				Raises a ModalDialogExpiredException.

				:param _: Ignored
				:return:
				"""

				raise ModalDialogExpiredException()

		extra_wait_tick_listeners = [] if self.auto_dismiss_after_seconds <= 0 else [AutoDismissWaitTickListener(self.auto_dismiss_after_seconds)]

		while True:
			try:
				button = self.devices.rotary_encoder.wait(
					listen_for_rotation = False,
					extra_wait_tick_listeners = extra_wait_tick_listeners
				)
			except ModalDialogExpiredException:
				return False

			if self.save_text is not None and (button == RotaryEncoder.SELECT or button == RotaryEncoder.RIGHT):
				return True

class NoisyBrightModal(Modal):
	"""
	A modal that can play a piezo tone and change the backlight color. Get it?
	"""

	def __init__(self,
				 devices: Devices,
				 message: str,
				 color: Optional[BacklightColor] = None,
				 piezo_tone: Optional[str] = None,
				 auto_dismiss_after_seconds: int = 0):
		"""
		:param devices: Devices dependency injection
		:param message: Message to show (<= 20 characters)
		:param color: Set the backlight to this color, or None to keep it as is
		:param piezo_tone: Play this piezo tone or None to not play anything
		:param auto_dismiss_after_seconds: 0 to keep the modal open indefinitely or > 0 to automatically dismiss the
		modal if it wasn't manually dismissed by the user by this many seconds.
		"""

		super().__init__(
			devices = devices,
			message = message,
			auto_dismiss_after_seconds = auto_dismiss_after_seconds
		)

		self.color = color
		self.piezo_tone = piezo_tone

	def render(self) -> UIComponent:
		super().render()
		if self.color is not None:
			self.devices.lcd.backlight.set_color(BacklightColors.DEFAULT)
		return self

	def wait(self) -> bool:
		if self.color is not None:
			self.devices.lcd.backlight.set_color(self.color)
		if self.piezo_tone is not None:
			self.devices.piezo.tone(self.piezo_tone)

		response = super().wait()

		if self.color is not None:
			self.devices.lcd.backlight.set_color(BacklightColors.DEFAULT)

		return response

class SuccessModal(NoisyBrightModal):
	"""
	A NoisyBrightModel that sets the backlight to BacklightColors.SUCCESS and plays "success" on the piezo.
	"""

	def __init__(self,
				 devices: Devices,
				 message: str = "Saved!"):
		"""
		:param devices: Devices dependency injection
		:param message: Message to show (<= 20 characters); "Saved!" by default
		"""

		super().__init__(
			devices = devices,
			message = message,
			auto_dismiss_after_seconds = 2,
			color = BacklightColors.SUCCESS,
			piezo_tone = "success"
		)

class ErrorModal(NoisyBrightModal):
	"""
	A NoisyBrightModel that sets the backlight to BacklightColors.ERROR and plays "error" on the piezo.
	"""

	def __init__(self,
				 devices: Devices,
				 message: str = "Error!",
				 auto_dismiss_after_seconds: int = 0):
		"""
		:param devices: Devices dependency injection
		:param message: Message to show (<= 20 characters); "Error!" by default
		:param auto_dismiss_after_seconds: 0 to keep the modal open indefinitely or > 0 to automatically dismiss the
		modal if it wasn't manually dismissed by the user by this many seconds.
		"""

		super().__init__(
			devices = devices,
			message = message,
			color = BacklightColors.ERROR,
			piezo_tone = "error",
			auto_dismiss_after_seconds = auto_dismiss_after_seconds
		)

class ProgressBar(UIComponent):
	"""
	Renders a full screen progress bar. This UI can't be wait()ed.
	"""

	def __init__(self, devices: Devices, count: int, message: str, header: Optional[str] = None):
		"""
		:param devices: Devices dependency injection
		:param count: Number of items that will be iterated over
		:param message: Message to show, like "Replaying events"
		:param header: UI header text or None to omit
		"""
		assert(count > 0)

		super().__init__(
			devices = devices,
			allow_cancel = False,
			header = header,
			save_text = None
		)

		self.count = count
		self.index = 0
		self.last_block_count = -1
		self.max_block_count = LCD.COLUMNS - len(str(self.count)) * 2 - 1
		self.message = message

	def set_index(self, index: int = 0) -> None:
		"""
		Sets the progress to this index; 0 is 0%, and self.count - 1 is 100%.

		:param index: index of the progress
		"""

		if index < 0:
			raise ValueError(f"Index must be >= 0, not {index}")

		if index >= self.count:
			raise ValueError(f"Index must be < {self.count}, not {index}")

		self.index = index

		self.render_progress()

	def render_progress(self) -> None:
		"""
		Updates the progress shown. As a consumer of this component, you probably want to use set_index().
		"""

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

	def render(self) -> UIComponent:
		"""
		Renders the progress bar in its initial state. Use set_index() to update it.
		"""

		super().render()

		self.devices.lcd.write_centered(self.message)
		self.devices.lcd.write_right_aligned("/" + str(self.count), 2)
		self.render_progress()

		return self

class ActiveTimer(UIComponent):
	"""
	Shows a timer that counts up. This UI can't be wait()ed.
	"""

	def __init__(self,
				 devices: Devices,
				 allow_cancel: bool = True,
				 cancel_text: str = None,
				 periodic_chime: PeriodicChime = None,
				 start_at: float = 0,
				 header: Optional[str] = None,
				 subtext: Optional[str] = None,
				 save_text: Optional[str] = "Save",
				 after_idle_for: Optional[tuple[int, Callable[[float], None]]] = None
	):
		"""
		:param devices: Devices dependency injection
		:param allow_cancel: True if this can be dismissed, False if not
		:param cancel_text: Widget text for dismissing the modal; gets prepended with a right arrow
		:param periodic_chime: Logic for how often to chime, or None for never
		:param start_at: Starting time in seconds of the timer, or 0 to start fresh
		:param header: UI header text
		:param save_text: Save widget text or None to omit
		:param after_idle_for: Do this thing after this many seconds have elapsed from inactivity; only triggers once
		"""

		super().__init__(
			devices = devices,
			allow_cancel = allow_cancel,
			cancel_text = cancel_text,
			cancel_align = UIComponent.LEFT,
			header = header,
			save_text = save_text
		)
		self.start = None
		self.periodic_chime = periodic_chime
		self.start_at = start_at
		self.save_text = save_text
		self.after_idle_for = after_idle_for
		self.subtext = subtext

	def render(self) -> UIComponent:
		super().render()
		if self.subtext is not None:
			self.devices.lcd.write_centered(self.subtext, y_delta = 1)
		return self

	def wait(self) -> Optional[bool]:
		"""
		Continuously update the timer as it runs and stop once appropriate input is given.

		:return: True if the user inputted "Save" or "None" if it was canceled.
		"""

		self.start = time.monotonic()
		if self.periodic_chime is not None:
			self.periodic_chime.start()

		class ActiveTimerWaitTickListener(WaitTickListener):
			"""
			A listener that updates the time as it increments.
			"""
			def __init__(self,
						 devices: Devices,
						 start: float,
						 periodic_chime: Optional[PeriodicChime]
			):
				"""
				:param devices: Devices dependency injection
				:param start: Start at this many seconds
				:param periodic_chime: Periodic chiming logic or None for no chimes
				"""

				self.start = start
				self.last_message = None
				self.devices = devices
				self.periodic_chime = periodic_chime
				super().__init__(seconds = 1, on_tick = self.render_elapsed_time, recurring = True)
				self.render_elapsed_time(start)

			def render_elapsed_time(self, _: float) -> None:
				"""
				Updates the elapsed time shown.

				:param _: Ignored
				"""

				elapsed = time.monotonic() - self.start
				message = Util.format_elapsed_time(elapsed)
				self.devices.lcd.write_centered(
					text = message,
					erase_if_shorter_than = None if self.last_message is None else len(self.last_message)
				)
				self.last_message = message

				if self.periodic_chime is not None:
					self.periodic_chime.chime_if_needed()

		listeners = [ActiveTimerWaitTickListener(
			devices = self.devices,
			start = self.start - self.start_at,
			periodic_chime = self.periodic_chime
		)]

		if self.after_idle_for is not None and self.devices.power_control and NVRAMValues.TIMERS_AUTO_OFF:
			seconds, callback = self.after_idle_for
			if seconds > 0:
				listeners.append(WaitTickListener(
					seconds = seconds,
					on_tick = callback,
					name = "Soft shutdown idle timeout"
				))

		while True:
			button = self.devices.rotary_encoder.wait(
				listen_for_rotation = False,
				extra_wait_tick_listeners = listeners
			)
			if button == RotaryEncoder.LEFT and self.allow_cancel:
				return None
			elif button == RotaryEncoder.SELECT or button == RotaryEncoder.RIGHT:
				return True

class NumericSelector(UIComponent):
	"""
	Lets the user enter a single numeric value.
	"""

	def __init__(self,
		devices: Devices,
		value: float = None,
		step: float = 1,
		minimum: float = 0,
		maximum: float = None,
		allow_cancel: bool = True,
		cancel_text: str = None,
		format_str: str = "%d",
		header: Optional[str] = None,
		save_text: Optional[str] = "Save"
	):
		"""
		:param devices: Devices dependency injection
		:param value: Initial value or None to use the minimum or maximum, whichever is defined first
		:param step: How much going up one notch in value increments the value
		:param minimum: Minimum allowed value or None for no lower bound
		:param maximum: Maximum allowed value or None for no upper bound
		:param allow_cancel: True if this can be dismissed, False if not
		:param cancel_text: Widget text for dismissing the modal; gets prepended with a right arrow
		:param format_str: Python format string to render the value
		:param header: UI header text
		"""

		super().__init__(
			devices = devices,
			allow_cancel = allow_cancel,
			cancel_text = cancel_text,
			header = header,
			save_text = save_text
		)

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
		self.format_str = format_str
		self.row = 1 if self.header else 0

	def render(self) -> UIComponent:
		super().render()
		self.devices.lcd.write(self.devices.lcd[LCD.UP_DOWN], (0, self.row))

		return self

	def wait(self) -> Optional[float]:
		"""
		Waits for the user to enter a number and save it.

		:return: The number entered or None if it was canceled
		"""

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
	"""
	Shows a list of menu items and allows the user to select one.
	"""

	def __init__(self,
				 devices: Devices,
				 options: list[str],
				 allow_cancel: bool = True,
				 cancel_align: int = None,
				 cancel_text: str = None,
				 header: Optional[str] = None,
				 save_text: Optional[str] = "Save",
				 initial_selection: int = 0):
		"""
		:param devices: Devices dependency injection
		:param options: List of values to present to the user; do not exceed 4 because the list doesn't scroll by design
		:param allow_cancel: True if this can be dismissed, False if not
		:param cancel_text: Widget text for dismissing the modal; gets prepended with a right arrow
		:param cancel_align: Alignment (UIComponent.LEFT or .RIGHT) of the Cancel widget
		:param header: UI header text
		:param save_text: Text of the Save widget or None to omit
		:param initial_selection: Index of the initial item to select
		"""

		if len(options) <= 0:
			raise ValueError("No options provided")
		if len(options) > LCD.LINES:
			raise ValueError(f"{len(options)} options provided but must be <= {LCD.LINES}")
		if len(options) == LCD.LINES:
			header = None # header won't fit because menu takes up the entire screen
		if len(options) >= LCD.LINES - 1:
			cancel_align = UIComponent.RIGHT

		super().__init__(
			devices = devices,
			allow_cancel = allow_cancel,
			cancel_text = cancel_text,
			cancel_align = cancel_align,
			header = header,
			save_text = save_text
		)

		self.options = options
		self.selected_row_index = None
		self.initial_selection = initial_selection

	def index_to_row(self, i: int) -> int:
		"""
		Maps a list index to its y coordinate.

		:param i: List index
		:return: y coordinate
		"""

		row = i
		if self.header is not None:
			row += 1

		return row

	def move_selection(self, button: int) -> bool:
		"""
		Moves the selection cursor up or down.

		:param button: button the user pressed or direction the rotary encoder turned
		:return: True if the selection actually moved so it needs to be rendered or False if there was no effect
		"""

		if button == RotaryEncoder.UP or button == RotaryEncoder.COUNTERCLOCKWISE:
			self.move_selection_up(wrap = button == RotaryEncoder.UP)
			return True
		elif button == RotaryEncoder.DOWN or button == RotaryEncoder.CLOCKWISE:
			self.move_selection_down(wrap = button == RotaryEncoder.DOWN)
			return True

		return False

	def on_select_pressed(self) -> int:
		"""
		Gets the currently selected row index

		:return: Selected row index
		"""

		return self.selected_row_index

	def on_right_pressed(self) -> int:
		"""
		Gets the currently selected row index

		:return: Selected row index
		"""

		return self.selected_row_index

	def format_menu_item(self, index, name) -> str:
		"""
		Extra formatting to apply to each menu item; base class just renders it as is but child classes might override
		this.

		:param index: menu item index
		:param name: menu item name
		:return: menu item name reformatted as necessary
		"""
		return name

	def render(self) -> UIComponent:
		super().render()

		i = 0
		for value in self.options:
			# skip first column; arrow goes there
			item_str = self.format_menu_item(i, value)
			self.devices.lcd.write(item_str, (1, self.index_to_row(i)))
			i += 1

		self.move_arrow(self.initial_selection)

		return self

	def wait(self) -> Optional[int]:
		"""
		Returns once the user selects a menu item.

		:return: Index of the item selected or None if canceled
		"""

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
		"""
		Moves the selection arrow up a row, or if already at the top and wrap is True, to the last menu item.

		:param wrap: True to wraparound the selection, False to not
		"""

		row_index = self.selected_row_index - 1
		if row_index < 0:
			if wrap:
				row_index = len(self.options) - 1
			else:
				return

		self.move_arrow(row_index)

	def move_selection_down(self, wrap: bool = True) -> None:
		"""
		Moves the selection arrow down a row, or if already at the bottom and wrap is True, to the first menu item.

		:param wrap: True to wraparound the selection, False to not
		"""

		row_index = self.selected_row_index + 1
		if row_index >= len(self.options):
			if wrap:
				row_index = 0
			else:
				return

		self.move_arrow(row_index)

	def move_arrow(self, row_index: int) -> None:
		"""
		Moves the selection arrow to the given row index.

		:param row_index: Menu item index
		"""

		self.devices.lcd.write(message = self.devices.lcd[LCD.RIGHT], coords = (0, self.index_to_row(row_index)))

		if self.selected_row_index is not None and row_index != self.selected_row_index:
			self.devices.lcd.write(message = " ", coords = (0, self.index_to_row(self.selected_row_index)))

		self.selected_row_index = row_index

class BooleanPrompt(VerticalMenu):
	def __init__(self,
		devices: Devices,
		header: str,
		yes_text: str = "Yes",
		no_text: str = "No",
		save_text: str = "Save"
	) -> None:
		super().__init__(
			devices = devices,
			options = [yes_text, no_text],
			allow_cancel = False,
			save_text = save_text,
			header = header
		)

	def wait(self) -> bool:
		response = super().wait()
		return response == 0

class VerticalCheckboxes(VerticalMenu):
	"""
	Like VerticalMenu, but each item is a checkbox that can be toggled.
	"""

	def __init__(self,
		devices: Devices,
		options: list[str],
		initial_states: list[bool],
		allow_cancel: bool = True,
		cancel_align: Optional[int] = None,
		cancel_text: str = None,
		header: Optional[str] = None,
		save_text: str = "Save"
	):
		super().__init__(
			devices = devices,
			options = options,
			allow_cancel = allow_cancel,
			cancel_align = cancel_align,
			cancel_text = cancel_text,
			header = header,
			save_text = save_text
		)

		assert(len(options) == len(initial_states))

		self.states = initial_states

	def get_checkbox_char(self, index: int) -> str:
		"""
		Gets the character to show for checked or unchecked state of the given item.

		:param index: Item index
		:return: Checkbox character based on the given item's state
		"""

		return self.devices.lcd[LCD.CHECKED] if self.states[index] else self.devices.lcd[LCD.UNCHECKED]

	def toggle_item(self, index: int) -> None:
		"""
		Inverts the current checked state of the given item.

		:param index: Item index
		"""

		self.states[index] = not self.states[index]
		self.devices.lcd.write(self.get_checkbox_char(index), (1, self.index_to_row(index)))

	def on_select_pressed(self) -> None:
		"""
		Inverts the currently checked state of the current item
		"""

		self.toggle_item(self.selected_row_index)
		return None

	def on_right_pressed(self) -> list[bool]:
		"""
		Creates a list of the checked states of all items.

		:return: All items' checked state ordered by the original order of all items
		"""

		return self.states

	def format_menu_item(self, index: int, name: str) -> str:
		"""
		Overridden to render the checkbox.

		:param index: Item index
		:param name: Item name
		:return: Item name preceded with a checkbox
		"""

		return self.get_checkbox_char(index) + name

	def wait(self) -> list[bool]:
		"""
		Returns a list of the state of each checkbox.

		:return: The checked state for each checkbox in the same order as the items provided during construction
		"""

		response = super().wait()
		return None if response is None else self.states
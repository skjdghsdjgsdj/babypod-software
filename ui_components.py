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
	"""
	Abstract class that represents a component--usually a full screen--of the UI on the LCD.
	"""

	RIGHT = 0
	LEFT = 1

	def __init__(self,
		devices: Devices,
		allow_cancel: bool = True,
		cancel_text: str = None,
		cancel_align: int = None,
		before_wait_loop: Optional[Callable[[], None]] = None
	):
		"""
		Child classes might not respect all these properties or may have somewhat different semantic meaning given the
		context for how they're used.

		:param devices: Devices dependency injection
		:param allow_cancel: True to allow the user to cancel (go back) from this component, False if not
		:param cancel_text: UI hint to show to the user for cancelling this action
		:param cancel_align: Left (UIComponent.LEFT) or right (UIComponent.RIGHT) alignment of the cancel text
		:param before_wait_loop: Function to call just before entering the blocking loop waiting for user input but
		after the UI is rendered
		"""

		self.devices = devices
		self.allow_cancel = allow_cancel
		self.cancel_align = cancel_align
		self.cancel_text = (self.devices.lcd[LCD.LEFT] + "Cancel") if cancel_text is None else cancel_text
		self.before_wait_loop = before_wait_loop

	def render_and_wait(self) -> None:
		"""
		Renders the UI and waits (blocks) for user input, although child classes will greatly extend this abstract
		method--and should always call the base implementation.

		:return: Nothing in the base method, but child classes usually will return something based on user input or
		None if the input was canceled.
		"""

		if self.allow_cancel:
			col = 0 if self.cancel_align == UIComponent.LEFT else LCD.COLUMNS - len(self.cancel_text)
			self.devices.lcd.write(self.cancel_text, (col, LCD.LINES - 1))

	def render_save(self, y_delta: int = 0, message: str = "Save") -> None:
		"""
		Renders the "Save" widget at the bottom-right of the screen.

		:param y_delta: Number of lines up from the bottom to render
		:param message: Message to show; defaults to "Save" and always gets prepended with a right arrow
		"""

		save_message = message + self.devices.lcd[LCD.RIGHT]
		self.devices.lcd.write(save_message, (LCD.COLUMNS - len(save_message), LCD.LINES - y_delta - 1))

class Modal(UIComponent):
	"""
	A simple text dialog that must be dismissed by the user with no other actions.
	"""

	def __init__(
			self,
			devices: Devices,
			message: str,
			dismiss_text: str = "Dismiss",
			before_wait_loop: Optional[Callable[[], None]] = None,
			auto_dismiss_after_seconds: int = 0
		):
		"""
		:param devices: Devices dependency injection
		:param message: Message to show to the user; keep it <= 20 characters long
		:param dismiss_text: Widget text for dismissing the modal; gets prepended with a right arrow
		:param before_wait_loop: Do this just before waiting for input
		:param auto_dismiss_after_seconds: 0 to keep the modal open indefinitely or > 0 to automatically dismiss the
		modal if it wasn't manually dismissed by the user by this many seconds
		"""
		super().__init__(devices = devices, allow_cancel = False, before_wait_loop = before_wait_loop)

		self.auto_dismiss_after_seconds = auto_dismiss_after_seconds
		self.message = message
		self.dismiss_text = dismiss_text

	def render_and_wait(self) -> bool:
		"""
		Shows the modal and waits until it is dismissed or times out.

		:return: True if the user explicitly dismissed the modal or False if it just timed out through inaction
		"""

		super().render_and_wait()

		self.devices.lcd.write_centered(self.message)

		self.render_save(message = self.dismiss_text)

		if self.before_wait_loop is not None:
			self.before_wait_loop()

		class ModalDialogExpiredException(Exception):
			pass

		class AutoDismissWaitTickListener(WaitTickListener):
			def __init__(self, auto_dismiss_after_seconds: int):
				super().__init__(auto_dismiss_after_seconds, self.dismiss_dialog)

			def dismiss_dialog(self, _: float):
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

			if button == RotaryEncoder.SELECT or button == RotaryEncoder.RIGHT:
				return True

class ProgressBar(UIComponent):
	"""
	Renders a full screen progress bar that can't be canceled.
	"""

	def __init__(self, devices: Devices, count: int, message: str):
		"""
		:param devices: Devices dependency injection
		:param count: Number of items that will be iterated over
		:param message: Message to show, like "Replaying events"
		"""
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

	def render_and_wait(self) -> None:
		"""
		Renders the progress bar. Unlike most other implementations of this method, this DOESN'T block for user input
		because you'll need to call set_index() repeatedly as progress is made.
		"""

		super().render_and_wait()

		self.devices.lcd.write_centered(self.message)
		self.devices.lcd.write_right_aligned("/" + str(self.count), 2)

		self.render_progress()

class ActiveTimer(UIComponent):
	"""
	Shows a timer that counts up.
	"""

	def __init__(self,
		devices: Devices,
		allow_cancel: bool = True,
		cancel_text: str = None,
		periodic_chime: PeriodicChime = None,
		start_at: float = 0,
		before_wait_loop: Optional[Callable[[], None]] = None
	):
		"""
		:param devices: Devices dependency injection
		:param allow_cancel: True if this can be dismissed, False if not
		:param cancel_text: Widget text for dismissing the modal; gets prepended with a right arrow
		:param periodic_chime: Logic for how often to chime, or None for never
		:param start_at: Starting time in seconds of the timer, or 0 to start fresh
		:param before_wait_loop: Function to call just before entering the blocking loop waiting for user input but
		after the UI is rendered
		"""

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
		"""
		Renders the timer and starts it counting up.

		:return: True if the user stopped the timer by saving it or None if it was canceled
		"""

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
		row: int = 2,
		format_str: str = "%d",
		before_wait_loop: Optional[Callable[[], None]] = None
	):
		"""
		:param devices: Devices dependency injection
		:param value: Initial value or None to use the minimum or maximum, whichever is defined first
		:param step: How much going up one notch in value increments the value
		:param minimum: Minimum allowed value or None for no lower bound
		:param maximum: Maximum allowed value or None for no upper bound
		:param allow_cancel: True if this can be dismissed, False if not
		:param cancel_text: Widget text for dismissing the modal; gets prepended with a right arrow
		:param row: y coordinate to render the input
		:param format_str: Python format string to render the value
		:param before_wait_loop: Function to call just before entering the blocking loop waiting for user input but
		after the UI is rendered
		"""

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
		"""
		Renders the UI and waits for the user to input the numeric value or cancel the input.

		:return: Entered numeric value or None if canceled
		"""

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
	"""
	Shows a list of menu items and allows the user to select one.
	"""

	ANCHOR_TOP = 0
	ANCHOR_BOTTOM = 1

	def __init__(self,
				 devices: Devices,
				 options: list[str],
				 allow_cancel: bool = True,
				 cancel_text: str = None,
				 anchor: int = ANCHOR_BOTTOM,
				 before_wait_loop: Optional[Callable[[], None]] = None):
		"""
		:param devices: Devices dependency injection
		:param options: List of values to present to the user; do not exceed 4 because the list doesn't scroll by design
		:param allow_cancel: True if this can be dismissed, False if not
		:param cancel_text: Widget text for dismissing the modal; gets prepended with a right arrow
		:param anchor: y anchor: either VerticalMenu.ANCHOR_TOP for top of the LCD or VerticalMenu.ANCHOR_BOTTOM for the
		bottom
		:param before_wait_loop: Function to call just before entering the blocking loop waiting for user input but
		after the UI is rendered
		"""

		super().__init__(devices = devices, allow_cancel = allow_cancel, cancel_text = cancel_text, before_wait_loop = before_wait_loop)

		self.options = options
		self.selected_row_index = None
		self.anchor = anchor

	def index_to_row(self, i: int) -> int:
		"""
		Maps a list index to its y coordinate.

		:param i: List index
		:return: y coordinate
		"""

		row = i
		if self.anchor == VerticalMenu.ANCHOR_BOTTOM:
			row += LCD.LINES - len(self.options)

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

	def init_extra_ui(self) -> None:
		"""
		Extra rendering to do; base class does nothing but subclasses might override this.
		"""
		pass

	def format_menu_item(self, index, name) -> str:
		"""
		Extra formatting to apply to each menu item; base class just renders it as is but child classes might override
		this.

		:param index: menu item index
		:param name: menu item name
		:return: menu item name reformatted as necessary
		"""
		return name

	def render_and_wait(self) -> Optional[int]:
		"""
		Shows the menu to the user and waits for them to select an item.

		:return: Index of selected item or None if canceled
		"""

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

class VerticalCheckboxes(VerticalMenu):
	"""
	Like VerticalMenu, but each item is a checkbox that can be toggled.
	"""

	def __init__(self,
		devices: Devices,
		options: list[str],
		initial_states: list[bool],
		allow_cancel: bool = True,
		cancel_text: str = None,
		anchor: int = 1,
		before_wait_loop: Optional[Callable[[], None]] = None
	):
		"""
		:param devices: Devices dependency injection
		:param options: List of values to present to the user; do not exceed 4 because the list doesn't scroll by design
		:param allow_cancel: True if this can be dismissed, False if not
		:param cancel_text: Widget text for dismissing the modal; gets prepended with a right arrow
		:param anchor: y anchor: either VerticalMenu.ANCHOR_TOP for top of the LCD or VerticalMenu.ANCHOR_BOTTOM for the
		bottom
		:param before_wait_loop: Function to call just before entering the blocking loop waiting for user input but
		after the UI is rendered
		"""

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

	def init_extra_ui(self) -> None:
		"""
		Renders a Save widget above the Cancel widget, if one exists.
		"""
		self.render_save(y_delta = 1 if self.allow_cancel else 0)

	def format_menu_item(self, index: int, name: str) -> str:
		"""
		Overridden to render the checkbox.

		:param index: Item index
		:param name: Item name
		:return: Item name preceded with a checkbox
		"""
		return self.get_checkbox_char(index) + name

	def render_and_wait(self) -> list[bool]:
		"""
		Renders the list of options and waits for selections to be made and then saved.

		:return: The state of each option or None if the input was canceled
		"""
		response = super().render_and_wait()
		return None if response is None else self.states

class BooleanPrompt(VerticalMenu):
	"""
	A boolean user input, like "Yes"/"No".
	"""

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
		"""
		:param devices: Devices dependency injection
		:param yes_text: The text that indicates True
		:param no_text: The text that indicates False
		:param allow_cancel: True if this can be dismissed, False if not
		:param cancel_text: Widget text for dismissing the modal; gets prepended with a right arrow
		:param anchor: y anchor: either VerticalMenu.ANCHOR_TOP for top of the LCD or VerticalMenu.ANCHOR_BOTTOM for the
		bottom
		:param before_wait_loop: Function to call just before entering the blocking loop waiting for user input but
		after the UI is rendered
		"""

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
		"""
		Shows the boolean input and waits for a response.

		:return: True if the True option was selected, False for False, or None if canceled.
		"""
		selected_index = super().render_and_wait()

		if selected_index == 0:
			return True
		elif selected_index == 1:
			return False
		else:
			return None

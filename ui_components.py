from lcd_special_chars_module import LCDSpecialChars
from rotary_encoder import RotaryEncoder
import time

class UIComponent:
	def __init__(self, flow, allow_cancel = True, cancel_text = None, cancel_align = None):
		self.flow = flow
		self.allow_cancel = allow_cancel
		self.cancel_align = cancel_align
		self.cancel_text = (self.flow.lcd_special_chars[LCDSpecialChars.LEFT] + "Cancel") if cancel_text is None else cancel_text

	def render_and_wait(self):
		(lcd_width, lcd_height) = self.flow.lcd_dimensions

		if self.allow_cancel:
			col = 0 if self.cancel_align == UIComponent.LEFT else lcd_width - len(self.cancel_text)
			self.flow.lcd.cursor_position(col, lcd_height - 1)
			self.flow.lcd.message = self.cancel_text

	def render_save(self, y_delta = 0):
		lcd_width, lcd_height = self.flow.lcd_dimensions

		save_message = "Save" + self.flow.lcd_special_chars[LCDSpecialChars.RIGHT]
		self.flow.lcd.cursor_position(lcd_width - len(save_message), lcd_height - y_delta - 1)
		self.flow.lcd.message = save_message

UIComponent.RIGHT = 0
UIComponent.LEFT = 1

class ActiveTimer(UIComponent):
	def __init__(self, flow, allow_cancel = True, cancel_text = None, chime_at_seconds = 15 * 60):
		super().__init__(flow, allow_cancel, cancel_text, cancel_align = UIComponent.LEFT)
		self.last_message = None
		self.start = None
		self.last_chime = None
		self.chime_at_seconds = chime_at_seconds

	def render_and_wait(self):
		self.flow.suppress_idle_warning = True

		super().render_and_wait()

		self.render_save()

		self.start = time.monotonic()
		self.last_chime = self.start

		while True:
			button = self.flow.rotary_encoder.wait(
				listen_for_rotation = False,
				on_wait_tick = self.render_elapsed_time,
				wait_tick = 1
			)
			if button == RotaryEncoder.LEFT and self.allow_cancel:
				self.flow.suppress_idle_warning = False
				return None
			elif button == RotaryEncoder.SELECT or button == RotaryEncoder.RIGHT:
				self.flow.suppress_idle_warning = False
				return True

	def render_elapsed_time(self, elapsed):
		self.flow.on_rotary_encoder_wait_tick(elapsed)

		message = self.format_elapsed_time(time.monotonic() - self.start)
		self.flow.render_centered_text(
			message,
			erase_if_shorter_than = None if self.last_message is None else len(self.last_message)
		)
		self.last_message = message

		if self.chime_at_seconds is not None:
			since_last_chime = time.monotonic() - self.last_chime

			if since_last_chime >= self.chime_at_seconds:
				self.last_chime = time.monotonic()
				self.flow.piezo.tone("chime")

	def format_elapsed_time(self, elapsed):
		if elapsed < 60:
			return f"{elapsed:.0f} sec"

		return f"{(elapsed // 60):.0f} min {(int(elapsed) % 60):.0f} sec"

class NumericSelector(UIComponent):
	def __init__(self, flow, value = None, step = 1, minimum = 0, maximum = None, allow_cancel = True, cancel_text = None, row = 2, format_str = "%d"):
		super().__init__(flow = flow, allow_cancel = allow_cancel, cancel_text = cancel_text)

		_, lcd_height = self.flow.lcd_dimensions

		assert(0 <= row < lcd_height)
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

	def render_and_wait(self):
		super().render_and_wait()

		self.flow.lcd.cursor_position(0, self.row)
		self.flow.lcd.message = chr(LCDSpecialChars.UP_DOWN)

		last_value = None
		while True:
			if last_value != self.selected_value:
				if last_value is not None:
					selected_strlen = len(self.format_str % self.selected_value)
					last_strlen = len(self.format_str % last_value)
					value_strlen_difference = last_strlen - selected_strlen
					if value_strlen_difference > 0:
						self.flow.lcd.cursor_position(1 + last_strlen - value_strlen_difference, self.row)
						self.flow.lcd.message = " " * value_strlen_difference

				self.flow.lcd.cursor_position(1, self.row)
				self.flow.lcd.message = self.format_str % self.selected_value

				last_value = self.selected_value

			button = self.flow.rotary_encoder.wait(on_wait_tick = self.flow.on_rotary_encoder_wait_tick)
			self.flow.on_rotary_encoder_activity()
			if button == RotaryEncoder.LEFT and self.allow_cancel:
				return None
			if button == RotaryEncoder.UP or button == RotaryEncoder.CLOCKWISE:
				self.selected_value += self.step
			elif button == RotaryEncoder.DOWN or button == RotaryEncoder.COUNTERCLOCKWISE:
				self.selected_value -= self.step
			elif button == RotaryEncoder.SELECT:
				return self.selected_value

			minimum, maximum = self.range
			if minimum is not None and self.selected_value < minimum:
				self.selected_value = minimum
			elif maximum is not None and self.selected_value > maximum:
				self.selected_value = maximum

class VerticalMenu(UIComponent):
	def __init__(self, flow, options, allow_cancel = True, cancel_text = None, anchor = 1):
		super().__init__(flow = flow, allow_cancel = allow_cancel, cancel_text = cancel_text)

		self.options = options
		self.selected_row_index = None
		self.anchor = anchor

	def index_to_row(self, i):
		_, lcd_height = self.flow.lcd_dimensions

		row = i
		if self.anchor == VerticalMenu.ANCHOR_BOTTOM:
			row += lcd_height - len(self.options)

		return row

	def move_selection(self, button):
		if button == RotaryEncoder.UP or button == RotaryEncoder.COUNTERCLOCKWISE:
			self.move_selection_up(wrap = button == RotaryEncoder.UP)
			return True
		elif button == RotaryEncoder.DOWN or button == RotaryEncoder.CLOCKWISE:
			self.move_selection_down(wrap = button == RotaryEncoder.DOWN)
			return True

		return False

	def on_select_pressed(self):
		return self.selected_row_index

	def on_right_pressed(self):
		return self.selected_row_index

	def init_extra_ui(self):
		pass

	def format_menu_item(self, index, name):
		return name

	def render_and_wait(self):
		super().render_and_wait()

		i = 0
		for value in self.options:
			self.flow.lcd.cursor_position(1, self.index_to_row(i)) # skip first column; arrow goes there
			self.flow.lcd.message = self.format_menu_item(i, value)
			i += 1

		self.move_arrow(0)

		self.init_extra_ui()

		while True:
			button = self.flow.rotary_encoder.wait(on_wait_tick = self.flow.on_rotary_encoder_wait_tick)
			self.flow.on_rotary_encoder_activity()
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

	def move_selection_up(self, wrap = True):
		row_index = self.selected_row_index - 1
		if row_index < 0:
			if wrap:
				row_index = len(self.options) - 1
			else:
				return

		self.move_arrow(row_index)

	def move_selection_down(self, wrap = True):
		row_index = self.selected_row_index + 1
		if row_index >= len(self.options):
			if wrap:
				row_index = 0
			else:
				return

		self.move_arrow(row_index)

	def move_arrow(self, row_index):
		self.flow.lcd.cursor_position(0, self.index_to_row(row_index))
		self.flow.lcd.message = self.flow.lcd_special_chars[LCDSpecialChars.RIGHT]

		if self.selected_row_index is not None and row_index != self.selected_row_index:
			self.flow.lcd.cursor_position(0, self.index_to_row(self.selected_row_index))
			self.flow.lcd.message = " "

		self.selected_row_index = row_index

VerticalMenu.ANCHOR_TOP = 0
VerticalMenu.ANCHOR_BOTTOM = 1

class VerticalCheckboxes(VerticalMenu):
	def __init__(self, flow, options, initial_states, allow_cancel = True, cancel_text = None, anchor = 1):
		super().__init__(flow = flow, options = options, allow_cancel = allow_cancel, cancel_text = cancel_text, anchor = anchor)

		assert(len(options) == len(initial_states))

		self.states = initial_states

	def get_checkbox_char(self, index):
		return chr(LCDSpecialChars.CHECKED if self.states[index] else LCDSpecialChars.UNCHECKED)

	def toggle_item(self, index):
		self.states[index] = not self.states[index]
		self.flow.lcd.cursor_position(1, self.index_to_row(index))
		self.flow.lcd.message = self.get_checkbox_char(index)

	def on_select_pressed(self):
		self.toggle_item(self.selected_row_index)
		return None

	def on_right_pressed(self):
		return self.states

	def init_extra_ui(self):
		self.render_save(y_delta = 1 if self.allow_cancel else 0)

	def format_menu_item(self, index, name):
		return self.get_checkbox_char(index) + name

class BooleanPrompt(VerticalMenu):
	def __init__(self, flow, allow_cancel = True, cancel_text = None, anchor = 1, yes_text = "Yes", no_text = "No"):
		super().__init__(options = [yes_text, no_text], flow = flow, allow_cancel = allow_cancel, cancel_text = None, anchor = anchor)

	def render_and_wait(self):
		selected_index = super().render_and_wait()

		if selected_index == 0:
			return True
		elif selected_index == 1:
			return False
		else:
			return None

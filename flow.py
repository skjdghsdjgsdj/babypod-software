import time
import traceback

from api import API
from backlight import Backlight
from options import Options
from ui_components import NumericSelector, VerticalMenu, VerticalCheckboxes, BooleanPrompt, ActiveTimer
from lcd_special_chars_module import LCDSpecialChars

class Flow:
	def __init__(self, lcd_dimensions, lcd, child_id, rotary_encoder, battery_monitor, backlight, piezo, options, lcd_special_chars):
		self.lcd_dimensions = lcd_dimensions
		self.lcd = lcd
		self.child_id = child_id
		self.rotary_encoder = rotary_encoder
		self.battery_monitor = battery_monitor
		self.backlight = backlight
		self.piezo = piezo
		self.options = options
		self.lcd_special_chars = lcd_special_chars
		self.idle_warning_tripped = False
		self.suppress_idle_warning = False

		Flow.FOOD_TYPES = [
			{
				"name": "Breast milk",
				"type": "breast milk",
				"methods": ["bottle", "both breasts", "left breast", "right breast"]
			},
			{
				"name": "Fort. breast milk",
				"type": "fortified breast milk",
				"methods": ["bottle"]
			},
			{
				"name": "Formula",
				"type": "formula",
				"methods": ["bottle"]
			},
			{
				"name": "Solid food",
				"type": "solid food",
				"methods": ["parent fed", "self fed"]
			}
		]

		Flow.FEEDING_METHODS = [
			{
				"name": "Bottle",
				"method": "bottle",
			},
			{
				"name": "L. breast",
				"method": "left breast"
			},
			{
				"name": "R. breast",
				"method": "right breast"
			},
			{
				"name": "Both breasts",
				"method": "both breasts"
			},
			{
				"name": "Parent-fed",
				"method": "parent fed"
			},
			{
				"name": "Self-fed",
				"method": "self fed"
			}
		]

		self.api = API(self.child_id)

	def on_rotary_encoder_wait_tick(self, idle_time):
		self.render_battery_percent(only_if_changed = True)

		if idle_time >= Backlight.TIMEOUT:
			self.set_backlight(Backlight.OFF)

		if not self.suppress_idle_warning and idle_time > Flow.IDLE_DISCHARGING_WARNING_INTERVAL and not self.battery_monitor.is_charging() and not self.idle_warning_tripped:
			self.idle_warning_tripped = True
			self.idle_warning()

	def idle_warning(self):
		if self.options.values[Options.PLAY_SOUNDS] or self.options.values[Options.BACKLIGHT]:
			color = self.backlight.color
			for i in range(0, 3):
				self.set_backlight((255, 255, 255))
				self.play_piezo("idle_warning")
				self.set_backlight(color)
				time.sleep(0.1)

	def on_rotary_encoder_activity(self):
		self.idle_warning_tripped = False
		self.set_backlight(Backlight.DEFAULT_COLOR)

	def clear_and_show_battery(self):
		self.lcd.clear()
		self.render_battery_percent()

	def set_backlight(self, color):
		if self.options.values[Options.BACKLIGHT]:
			self.backlight.set_color(color)

	def play_piezo(self, tone_name):
		if self.options.values[Options.PLAY_SOUNDS]:
			self.piezo.tone(tone_name)

	def start(self):
		self.lcd.clear()

		self.render_splash("Connecting...")
		self.api.connect()

		self.lcd.clear()

		while True:
			try:
				self.main_menu()
			except Exception as e:
				traceback.print_exception(e)
				self.render_splash("Error!")
				self.set_backlight((255, 0, 0))
				self.play_piezo("error")
				time.sleep(2)
				self.set_backlight(Backlight.DEFAULT_COLOR)
			finally:
				self.clear_and_show_battery()

	def render_header_text(self, text):
		self.lcd.cursor_position(0, 0)
		self.lcd.message = text

	def format_battery_percent(self, percent):
		return f"{percent}%"

	def render_battery_percent(self, only_if_changed = False):
		last_percent = self.battery_monitor.last_percent

		try:
			percent = self.battery_monitor.get_percent()
		except Exception as e:
			traceback.print_exception(e)
			return

		if last_percent is None and percent is None:
			return

		message = self.format_battery_percent(percent)

		if not only_if_changed or last_percent != percent:
			lcd_width, _ = self.lcd_dimensions

			if last_percent is not None and percent < last_percent:
				current_len = len(message)
				last_len = len(self.format_battery_percent(last_percent))
				char_count_difference = last_len - current_len

				if char_count_difference > 0:
					self.lcd.cursor_position(lcd_width - last_len, 0)
					self.lcd.message = " " * char_count_difference

			message = self.format_battery_percent(percent)
			self.lcd.cursor_position(lcd_width - len(message), 0)
			self.lcd.message = message

	def render_splash(self, text):
		self.clear_and_show_battery()
		self.render_centered_text(text)

	def render_centered_text(self, text, erase_if_shorter_than = None, y_delta = 0):
		if erase_if_shorter_than is not None and len(text) < erase_if_shorter_than:
			self.render_centered_text(" " * erase_if_shorter_than)

		lcd_width, lcd_height = self.lcd_dimensions

		self.lcd.cursor_position(max(int(lcd_width / 2 - len(text) / 2), 0), max(int(lcd_height / 2) - 1 + y_delta, 0))
		self.lcd.message = text

	def render_success_splash(self, text = "Saved!", hold_seconds = 1):
		self.render_splash(text)
		self.set_backlight((0, 255, 0))
		self.play_piezo("success")
		time.sleep(hold_seconds)
		self.set_backlight(Backlight.DEFAULT_COLOR)

	def main_menu(self):
		self.render_battery_percent()

		selected_index = VerticalMenu(options = [
			f"Feeding",
			"Diaper change",
			"Pumping",
			"Tummy time"
		], flow = self, cancel_text = self.lcd_special_chars[LCDSpecialChars.LEFT] + "Opt").render_and_wait()

		self.clear_and_show_battery() # preps for next menu

		if selected_index is None:
			self.settings()
		elif selected_index == 0:
			self.feeding()
		elif selected_index == 1:
			self.diaper()
		elif selected_index == 2:
			self.pumping()
		elif selected_index == 3:
			self.tummy_time()

		self.clear_and_show_battery()

	def settings(self):
		options = [None] * 2
		options[Options.PLAY_SOUNDS] = "Play sounds"
		options[Options.BACKLIGHT] = "Backlight"

		responses = VerticalCheckboxes(
			options = options,
			initial_states = [
				self.options.values[Options.PLAY_SOUNDS],
				self.options.values[Options.BACKLIGHT]
			], flow = self, anchor = VerticalMenu.ANCHOR_TOP).render_and_wait()

		if responses is not None:
			for i in range(0, len(responses)):
				new_value = responses[i]
				if new_value != self.options.values[i]:
					self.options.save(i, new_value)
					if i == Options.BACKLIGHT:
						self.backlight.set_color(Backlight.DEFAULT_COLOR if new_value else Backlight.OFF)

	def diaper(self):
		self.render_header_text("How was diaper?")

		selected_index = VerticalMenu(options = [
			"Wet",
			"Solid",
			"Both"
		], flow = self).render_and_wait()

		if selected_index is not None:
			is_wet = selected_index == 0 or selected_index == 2
			is_solid = selected_index == 1 or selected_index == 2

			self.render_splash("Saving...")
			self.api.post_change(is_wet = is_wet, is_solid = is_solid)
			self.render_success_splash()

	def pumping(self):
		self.render_header_text("How much pumped?")

		amount = NumericSelector(
			flow = self,
			minimum = 0,
			step = 0.5,
			format_str = "%.1f fl oz"
		).render_and_wait()

		if amount is not None:
			self.render_splash("Saving...")
			self.api.post_pumping(amount = amount)
			self.render_success_splash()

	def feeding_menu(self, timer_id = None):
		self.clear_and_show_battery()

		def get_name(item):
			return item["name"]

		selected_index = VerticalMenu(
			flow = self,
			options = list(map(get_name, Flow.FOOD_TYPES))
		).render_and_wait()

		if selected_index is None:
			return

		food_type_metadata = Flow.FOOD_TYPES[selected_index]
		food_type = food_type_metadata["type"]

		method = None
		if len(food_type_metadata["methods"]) == 1:
			method = food_type_metadata["methods"][0]
		else:
			method_names = []
			for allowed_method in food_type_metadata["methods"]:
				for available_method in Flow.FEEDING_METHODS:
					if available_method["method"] == allowed_method:
						method_names.append(available_method["name"])

			self.clear_and_show_battery()
			_, lcd_height = self.lcd_dimensions
			if len(method_names) < lcd_height:
				self.render_header_text("How was this fed?")

			selected_index = VerticalMenu(
				flow = self,
				options = method_names,
				anchor = VerticalMenu.ANCHOR_BOTTOM
			).render_and_wait()

			if selected_index is None:
				return

			selected_method_name = method_names[selected_index]
			for available_method in Flow.FEEDING_METHODS:
				if available_method["name"] == selected_method_name:
					method = available_method["method"]
					break

		self.render_splash("Saving...")
		self.api.post_feeding(timer_id = timer_id, food_type = food_type, method = method)
		self.render_success_splash()

	def feeding(self):
		self.render_splash("Checking status...")
		timer_id, duration = self.api.get_timer("feeding")
		self.clear_and_show_battery()

		last_feeding_str = ""
		try:
			last_feeding = self.api.get_last_feeding()
			if last_feeding is not None:
				hour = last_feeding.hour
				minute = last_feeding.minute
				meridian = "am"

				if hour == 0:
					hour = 12
				elif hour == 12:
					meridian = "pm"
				elif hour > 12:
					hour = hour - 12
					meridian = "pm"

				last_feeding_str = f"{hour}:{minute:02}{meridian}"
		except Exception as e:
			print(f"Failed to get last feeding: {e}")

		if timer_id is None:
			self.render_header_text("Start timer?")
			selected_index = VerticalMenu(options = [
				"Yes" if last_feeding_str is None else f"Yes ({last_feeding_str})",
				"No, record"
			], flow = self).render_and_wait()

			if selected_index == 0: # no timer and start one
				self.render_splash("Starting timer...")
				timer_id = self.api.start_timer("feeding")

				self.clear_and_show_battery()
				self.render_header_text("Feeding timer")
				response = ActiveTimer(self).render_and_wait()
				if response == True:
					self.clear_and_show_battery()
					return self.feeding_menu(timer_id)
				elif response == None:
					self.api.stop_timer(timer_id)
			elif selected_index == 1: # no timer but don't care, record with 0 duration
				return self.feeding_menu(timer_id)
		else:
			return self.feeding_menu(timer_id)

	def tummy_time(self):
		self.render_splash("Checking status...")
		timer_id, duration = self.api.get_timer("tummy_time")

		self.clear_and_show_battery()

		if timer_id is None:
			self.render_header_text("Start timer?")

			if BooleanPrompt(flow = self).render_and_wait():
				self.render_splash("Starting timer...")
				timer_id = self.api.start_timer("tummy_time")

				self.clear_and_show_battery()
				self.render_header_text("Tummy time")
				response = ActiveTimer(self, chime_at_seconds = 60).render_and_wait()
				if response == True:
					self.api.post_tummy_time(timer_id)
					self.render_success_splash()
				else:
					self.api.stop_timer(timer_id)
		else:
			self.render_header_text(f"Done? {duration}")
			if BooleanPrompt(flow = self).render_and_wait():
				self.render_splash("Saving...")
				self.api.post_tummy_time(timer_id)
				self.render_success_splash()

Flow.IDLE_DISCHARGING_WARNING_INTERVAL = 300

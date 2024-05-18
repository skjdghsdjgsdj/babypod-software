import time
import traceback

from api import API, Duration
from backlight import BacklightColors
from devices import Devices
from lcd import LCD
from nvram import NVRAMValues
from periodic_chime import EscalatingIntervalPeriodicChime, ConsistentIntervalPeriodicChime, PeriodicChime
from rotary_encoder import ActivityListener, WaitTickListener
from ui_components import NumericSelector, VerticalMenu, VerticalCheckboxes, ActiveTimer

class Flow:
	FOOD_TYPES = [
		{
			"name": "Breast milk",
			"type": "breast milk",
			"methods": ["left breast", "right breast", "both breasts", "bottle"]
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

	FEEDING_METHODS = [
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

	def __init__(self,
		child_id: int,
		devices: Devices
	):
		self.child_id = child_id
		self.devices = devices

		self.suppress_idle_warning = False

		self.api = API(self.child_id)

		self.devices.rotary_encoder.on_activity_listeners.append(ActivityListener(
			on_activity = self.on_rotary_encoder_activity
		))

		self.devices.rotary_encoder.on_wait_tick_listeners.extend([
			WaitTickListener(
				on_tick = self.on_backlight_dim_idle,
				seconds = NVRAMValues.BACKLIGHT_DIM_TIMEOUT.get()
			),
			WaitTickListener(
				on_tick = self.idle_warning,
				seconds = NVRAMValues.IDLE_WARNING.get(),
				recurring = True
			),
			WaitTickListener(
				on_tick = self.on_idle,
				seconds = 5,
				recurring = True
			)
		])

	def on_backlight_dim_idle(self, _: float) -> None:
		print("Dimming backlight due to inactivity")
		self.devices.backlight.set_color(BacklightColors.DIM)

	def on_idle(self, _: float) -> None:
		self.render_battery_percent(only_if_changed = True)

	def idle_warning(self, _: float) -> None:
		print("Idle; warning if not suppressed and is discharging")
		if not self.suppress_idle_warning and not self.devices.battery_monitor.is_charging():
			for i in range(0, 3):
				self.devices.backlight.set_color(BacklightColors.IDLE_WARNING)
				self.devices.piezo.tone("idle_warning")
				self.devices.backlight.set_color(BacklightColors.DEFAULT)
				time.sleep(0.1)

	def on_rotary_encoder_activity(self) -> None:
		self.devices.backlight.set_color(BacklightColors.DEFAULT)

	def clear_and_show_battery(self) -> None:
		self.devices.lcd.clear()
		self.render_battery_percent()

	def start(self):
		self.devices.lcd.clear()

		self.render_splash("Connecting...")
		self.api.connect()

		battery_percent = self.devices.battery_monitor.get_percent()
		if battery_percent is not None and battery_percent <= 15:
			self.devices.backlight.set_color(BacklightColors.ERROR)
			self.render_splash(f"Low battery!")
			self.devices.piezo.tone("low_battery")

			time.sleep(1.5)

			self.devices.backlight.set_color(BacklightColors.DEFAULT)

		self.devices.lcd.clear()

		while True:
			try:
				self.main_menu()
			except Exception as e:
				traceback.print_exception(e)
				self.render_splash("Error!")
				self.devices.backlight.set_color(BacklightColors.ERROR)
				self.devices.piezo.tone("error")
				time.sleep(2)
				self.devices.backlight.set_color(BacklightColors.DEFAULT)
			finally:
				self.clear_and_show_battery()

	def render_header_text(self, text: str) -> None:
		self.devices.lcd.write(text, (0, 0))

	@staticmethod
	def format_battery_percent(percent: int) -> str:
		return f"{percent}%"

	def render_battery_percent(self, only_if_changed: bool = False) -> None:
		last_percent = self.devices.battery_monitor.last_percent

		try:
			percent = self.devices.battery_monitor.get_percent()
		except Exception as e:
			traceback.print_exception(e)
			return

		if last_percent is None and percent is None:
			return

		message = self.format_battery_percent(percent)

		if not only_if_changed or last_percent != percent:
			if last_percent is not None and percent < last_percent:
				current_len = len(message)
				last_len = len(self.format_battery_percent(last_percent))
				char_count_difference = last_len - current_len

				if char_count_difference > 0:
					self.devices.lcd.write(" " * char_count_difference, (LCD.COLUMNS - last_len, 0))

			message = self.format_battery_percent(percent)
			self.devices.lcd.write(message, (LCD.COLUMNS - len(message), 0))

	def render_splash(self, text: str) -> None:
		self.clear_and_show_battery()
		self.devices.lcd.write_centered(text)

	def render_success_splash(self, text: str = "Saved!", hold_seconds: int = 1) -> None:
		self.render_splash(text)
		self.devices.backlight.set_color(BacklightColors.SUCCESS)
		self.devices.piezo.tone("success")
		time.sleep(hold_seconds)
		self.devices.backlight.set_color(BacklightColors.DEFAULT)

	def main_menu(self) -> None:
		self.render_splash("Getting feeding...")

		last_feeding, method = self.api.get_last_feeding()
		if last_feeding is not None:
			last_feeding_str = "Feed " + API.datetime_to_time_str(last_feeding)

			if method == "right breast":
				last_feeding_str += " R"
			elif method == "left breast":
				last_feeding_str += " L"
		else:
			last_feeding_str = "Feeding"

		self.clear_and_show_battery()

		selected_index = VerticalMenu(options = [
			last_feeding_str,
			"Diaper change",
			"Pumping",
			"Tummy time"
		], devices = self.devices, cancel_text = self.devices.lcd[LCD.LEFT] + "Opt").render_and_wait()

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

	def settings(self) -> None:
		options = [
			"Play sounds",
			"Use backlight"
		]

		responses = VerticalCheckboxes(
			options = options,
			initial_states = [
				NVRAMValues.OPTION_PIEZO.get(),
				NVRAMValues.OPTION_BACKLIGHT.get()
			], devices = self.devices, anchor = VerticalMenu.ANCHOR_TOP
		).render_and_wait()

		if responses is not None:
			NVRAMValues.OPTION_PIEZO.write(responses[0])
			NVRAMValues.OPTION_BACKLIGHT.write(responses[1])

			if NVRAMValues.OPTION_BACKLIGHT.get():
				self.devices.backlight.set_color(BacklightColors.DEFAULT)
			else:
				self.devices.backlight.off()

	def diaper(self) -> None:
		self.render_header_text("How was diaper?")

		selected_index = VerticalMenu(options = [
			"Wet",
			"Solid",
			"Both"
		], devices = self.devices).render_and_wait()

		if selected_index is not None:
			is_wet = selected_index == 0 or selected_index == 2
			is_solid = selected_index == 1 or selected_index == 2

			self.render_splash("Saving...")
			self.api.post_change(is_wet = is_wet, is_solid = is_solid)
			self.render_success_splash()

	def pumping(self):
		self.render_header_text("How much pumped?")

		amount = NumericSelector(
			devices = self.devices,
			minimum = 0,
			step = 0.5,
			format_str = "%.1f fl oz"
		).render_and_wait()

		if amount is not None:
			self.render_splash("Saving...")
			self.api.post_pumping(amount = amount)
			self.render_success_splash()


	def start_or_resume_timer(self, header_text: str, timer_name: str, periodic_chime: PeriodicChime = None, subtext: str = None) -> int:
		self.render_splash("Checking status...")
		timer_id, elapsed = self.api.get_timer(timer_name)

		if timer_id is None:
			elapsed = Duration(0)
			timer_id = self.api.start_timer(timer_name)

		self.clear_and_show_battery()
		self.render_header_text(header_text)

		if subtext is not None:
			self.devices.lcd.write(message = subtext, coords = (0, 2))

		self.suppress_idle_warning = True
		response = ActiveTimer(
			devices = self.devices,
			periodic_chime = periodic_chime,
			start_at = elapsed.seconds
		).render_and_wait()
		self.suppress_idle_warning = False

		if response is None:
			self.api.stop_timer(timer_id)
			return None # canceled

		return timer_id

	def feeding(self) -> None:
		saved = False
		while not saved:
			timer_id = self.start_or_resume_timer(
				header_text = "Feeding",
				timer_name = "feeding",
				periodic_chime = EscalatingIntervalPeriodicChime(
					devices = self.devices,
					chime_at_seconds = 60 * 15,
					escalating_chime_at_seconds = 60 * 30,
					interval_once_escalated_seconds = 60
				)
			)

			if timer_id is not None:
				saved = self.save_feeding(timer_id)
			else:
				return # canceled the timer

	def save_feeding(self, timer_id: int) -> bool:
		self.clear_and_show_battery()

		def get_name(item):
			return item["name"]

		selected_index = VerticalMenu(
			devices = self.devices,
			options = list(map(get_name, Flow.FOOD_TYPES))
		).render_and_wait()

		if selected_index is None:
			return False

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
			if len(method_names) < LCD.LINES:
				self.render_header_text("How was this fed?")

			selected_index = VerticalMenu(
				devices = self.devices,
				options = method_names,
				anchor = VerticalMenu.ANCHOR_BOTTOM
			).render_and_wait()

			if selected_index is None:
				return False

			selected_method_name = method_names[selected_index]
			for available_method in Flow.FEEDING_METHODS:
				if available_method["name"] == selected_method_name:
					method = available_method["method"]
					break

		self.render_splash("Saving...")
		self.api.post_feeding(timer_id = timer_id, food_type = food_type, method = method)
		self.render_success_splash()

		return True

	def tummy_time(self) -> None:
		timer_id = self.start_or_resume_timer(
			header_text = "Tummy time",
			timer_name = "tummy_time",
			periodic_chime = ConsistentIntervalPeriodicChime(
				devices = self.devices,
				chime_at_seconds = 60
			)
		)

		if timer_id is not None:
			self.render_splash("Saving...")
			self.api.post_tummy_time(timer_id)
			self.render_success_splash()
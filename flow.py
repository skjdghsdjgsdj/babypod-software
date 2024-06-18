import time
import traceback

from adafruit_datetime import datetime

from api import APIRequest, GetFirstChildIDAPIRequest, GetLastFeedingAPIRequest, PostChangeAPIRequest, Timer, \
	PostFeedingAPIRequest, PostPumpingAPIRequest, PostTummyTimeAPIRequest
from offline_event_queue import OfflineEventQueue
from backlight import BacklightColors
from devices import Devices
from lcd import LCD
from nvram import NVRAMValues
from offline_state import OfflineState
from periodic_chime import EscalatingIntervalPeriodicChime, ConsistentIntervalPeriodicChime, PeriodicChime
from user_input import ActivityListener, WaitTickListener
from ui_components import NumericSelector, VerticalMenu, VerticalCheckboxes, ActiveTimer

# noinspection PyBroadException
try:
	from typing import Optional
except:
	pass
	# ignore, just for IDE's sake, not supported on board

class Flow:
	FOOD_TYPES = [
		{
			"name": "Breast milk",
			"type": "breast milk",
			"methods": ["left breast", "right breast", "both breasts", "bottle"],
			"mask": 0x1
		},
		{
			"name": "Fort. breast milk",
			"type": "fortified breast milk",
			"methods": ["bottle"],
			"mask": 0x2
		},
		{
			"name": "Formula",
			"type": "formula",
			"methods": ["bottle"],
			"mask": 0x4
		},
		{
			"name": "Solid food",
			"type": "solid food",
			"methods": ["parent fed", "self fed"],
			"mask": 0x8
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

	def __init__(self, devices: Devices):
		self.requests = None
		self.child_id = None
		self.devices = devices

		self.suppress_idle_warning = False

		self.devices.user_input.on_activity_listeners.append(ActivityListener(
			on_activity = self.on_user_input
		))

		self.devices.user_input.on_wait_tick_listeners.extend([
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

		self.offline_state = OfflineState(self.devices.sdcard)
		self.offline_queue: Optional[OfflineEventQueue] = None

	def on_backlight_dim_idle(self, _: float) -> None:
		print("Dimming backlight due to inactivity")
		self.devices.backlight.set_color(BacklightColors.DIM)

	def on_idle(self, _: float) -> None:
		self.render_battery_percent(only_if_changed = True)

	def idle_warning(self, _: float) -> None:
		print("Idle; warning if not suppressed and is discharging")
		if not self.suppress_idle_warning and not self.devices.battery_monitor.is_charging():
			self.devices.piezo.tone("idle_warning")

	def on_user_input(self) -> None:
		self.devices.backlight.set_color(BacklightColors.DEFAULT)

	def clear_and_show_battery(self) -> None:
		self.devices.lcd.clear()
		self.render_battery_percent()

	def refresh_rtc(self) -> None:
		if NVRAMValues.OFFLINE:
			print("Going online for next reboot")
			NVRAMValues.OFFLINE.write(False)
			raise ValueError("RTC must be set before going offline")

		print("Syncing RTC")
		self.render_splash("Setting clock...")

		try:
			old_now = self.devices.rtc.now()
			self.devices.rtc.sync(self.requests)
			print(f"RTC updated to {self.devices.rtc.now()}, drift = {old_now - self.devices.rtc.now()}")

			self.offline_state.last_rtc_set = self.devices.rtc.now()
			self.offline_state.to_sdcard()
		except Exception as e:
			print(f"{e} when syncing RTC; forcing sync on next online boot")
			NVRAMValues.FORCE_RTC_UPDATE.write(True)
			raise e

	def auto_connect(self) -> None:
		if not NVRAMValues.OFFLINE:
			self.render_splash("Connecting...")
			# noinspection PyBroadException
			try:
				self.requests = APIRequest.connect()
			except Exception as e:
				print(f"Got {e} when trying to connect; going offline")
				self.render_splash("Going offline")
				self.devices.piezo.tone("info")
				time.sleep(1)
				NVRAMValues.OFFLINE.write(True)
		elif not self.devices.rtc:
			raise ValueError("External RTC is required for offline support")
		else:
			print("Working offline")

	def init_rtc(self) -> None:
		if self.devices.rtc:
			if NVRAMValues.FORCE_RTC_UPDATE:
				print("RTC update forced")
				NVRAMValues.FORCE_RTC_UPDATE.write(False)
				self.refresh_rtc()
			if not self.devices.rtc.now():
				print("RTC not set or is implausible")
				self.refresh_rtc()
			elif self.offline_state.last_rtc_set is None:
				print("Last RTC set date/time unknown; assuming now")
				self.offline_state.last_rtc_set = self.devices.rtc.now()
				self.offline_state.to_sdcard()
			else:
				last_rtc_set_delta = self.devices.rtc.now() - self.offline_state.last_rtc_set
				# noinspection PyUnresolvedReferences
				if last_rtc_set_delta.seconds >= 60 * 60 * 24:
					print("RTC last set more than a day ago")

					if NVRAMValues.OFFLINE:
						print("RTC will be updated next time device is online")
					else:
						self.refresh_rtc()
				else:
					print(f"RTC doesn't need updating: set to {self.devices.rtc.now()}, last refreshed {self.offline_state.last_rtc_set}")

	def init_battery(self):
		battery_percent = self.devices.battery_monitor.get_percent()
		if battery_percent is not None and battery_percent <= 15:
			self.devices.backlight.set_color(BacklightColors.ERROR)
			self.render_splash(f"Low battery!")
			self.devices.piezo.tone("low_battery")

			time.sleep(1.5)

			self.devices.backlight.set_color(BacklightColors.DEFAULT)

	def start(self):
		self.devices.lcd.clear()
		self.offline_state = OfflineState.from_sdcard(self.devices.sdcard)

		self.auto_connect()
		self.init_rtc()
		self.init_battery()

		self.devices.lcd.clear()

		child_id = NVRAMValues.CHILD_ID.get()
		if not child_id:
			self.render_splash("Getting children...")
			child_id = GetFirstChildIDAPIRequest().get_first_child_id()
			NVRAMValues.CHILD_ID.write(child_id, )
			self.devices.lcd.clear()

		self.child_id = child_id
		print(f"Using child ID {child_id}")

		self.offline_queue = OfflineEventQueue.from_sdcard(self.devices.sdcard, self.devices.rtc)

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

	@staticmethod
	def datetime_to_time_str(datetime_obj: datetime) -> str:
		hour = datetime_obj.hour
		minute = datetime_obj.minute
		meridian = "a"

		if hour == 0:
			hour = 12
		elif hour == 12:
			meridian = "p"
		elif hour > 12:
			hour -= 12
			meridian = "p"

		return f"{hour}:{minute:02}{meridian}"

	def main_menu(self) -> None:
		if NVRAMValues.OFFLINE:
			last_feeding = self.offline_state.last_feeding
			method = self.offline_state.last_feeding_method
		else:
			self.render_splash("Getting feeding...")
			last_feeding, method = GetLastFeedingAPIRequest(self.child_id).get_last_feeding()
			if self.offline_state.last_feeding != last_feeding or self.offline_state.last_feeding_method != method:
				self.offline_state.last_feeding = last_feeding
				self.offline_state.last_feeding_method = method
				self.offline_state.to_sdcard()

		if last_feeding is not None:
			last_feeding_str = "Feed " + Flow.datetime_to_time_str(last_feeding)

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
		],
			devices = self.devices,
			cancel_text = self.devices.lcd[LCD.LEFT] +
				(self.devices.lcd[LCD.UNCHECKED if NVRAMValues.OFFLINE else LCD.CHECKED])
		).render_and_wait()

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
			"Offline",
			"Sounds",
			"Backlight"
		]

		responses = VerticalCheckboxes(
			options = options,
			initial_states = [
				NVRAMValues.OFFLINE.get(),
				NVRAMValues.PIEZO.get(),
				NVRAMValues.BACKLIGHT.get()
			], devices = self.devices, anchor = VerticalMenu.ANCHOR_TOP
		).render_and_wait()

		if responses is not None:
			if NVRAMValues.OFFLINE and not responses[1]: # was offline, now back online
				self.render_splash("Syncing changes...")
				self.offline_queue.replay_all()

			NVRAMValues.OFFLINE.write(responses[0])
			NVRAMValues.PIEZO.write(responses[1])
			NVRAMValues.BACKLIGHT.write(responses[2])

			if NVRAMValues.BACKLIGHT.get():
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
			request = PostChangeAPIRequest(
				child_id = self.child_id,
				is_wet = is_wet,
				is_solid = is_solid
			)
			if NVRAMValues.OFFLINE:
				self.offline_queue.add(request)
			else:
				request.invoke()
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
			request = PostPumpingAPIRequest(
				child_id = self.child_id,
				amount = amount
			)
			if NVRAMValues.OFFLINE:
				self.offline_queue.add(request)
			else:
				request.invoke()
			self.render_success_splash()


	def start_or_resume_timer(self,
		header_text: str,
		timer_name: str,
		periodic_chime: PeriodicChime = None,
		subtext: str = None
	) -> Optional[Timer]:
		if NVRAMValues.OFFLINE:
			timer = Timer(name = timer_name, offline = True, rtc = self.devices.rtc)
			timer.started_at = self.devices.rtc.now()
		else:
			self.render_splash("Checking status...")
			timer = Timer(name = timer_name, offline = False)
			timer.start_or_resume()

		self.clear_and_show_battery()
		self.render_header_text(header_text)

		if subtext is not None:
			self.devices.lcd.write(message = subtext, coords = (0, 2))

		start_at = 0
		if self.devices.rtc:
			# noinspection PyUnresolvedReferences
			start_at = (self.devices.rtc.now() - timer.started_at).seconds

		self.suppress_idle_warning = True
		response = ActiveTimer(
			devices = self.devices,
			periodic_chime = periodic_chime,
			start_at = start_at
		).render_and_wait()
		self.suppress_idle_warning = False

		if response is None:
			timer.cancel()
			return None # canceled

		return timer

	def feeding(self) -> None:
		saved = False
		while not saved:
			timer = self.start_or_resume_timer(
				header_text = "Feeding",
				timer_name = "feeding",
				periodic_chime = EscalatingIntervalPeriodicChime(
					devices = self.devices,
					chime_at_seconds = 60 * 15,
					escalating_chime_at_seconds = 60 * 30,
					interval_once_escalated_seconds = 60
				)
			)

			if timer is not None:
				saved = self.save_feeding(timer)
			else:
				return # canceled the timer

	def save_feeding(self, timer: Timer) -> bool:
		self.clear_and_show_battery()

		def get_name(item):
			return item["name"]

		enabled_food_types = NVRAMValues.ENABLED_FOOD_TYPES_MASK.get()

		options = []
		for food_type in Flow.FOOD_TYPES:
			if food_type["mask"] & enabled_food_types:
				options.append(food_type)

		if not options:
			raise ValueError(f"All food types excluded by ENABLED_FOOD_TYPES_MASK bitmask {enabled_food_types}")

		if len(options) == 1:
			food_type_metadata = options[0]
		else:
			selected_index = VerticalMenu(
				devices = self.devices,
				options = list(map(get_name, options))
			).render_and_wait()

			if selected_index is None:
				return False

			food_type_metadata = options[selected_index]

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
		request = PostFeedingAPIRequest(
			child_id = self.child_id,
			timer = timer,
			food_type = food_type,
			method = method
		)
		if NVRAMValues.OFFLINE:
			self.offline_queue.add(request)
		else:
			request.invoke()

		self.offline_state.last_feeding = timer.started_at
		self.offline_state.last_feeding_method = method
		self.offline_state.to_sdcard()

		self.render_success_splash()

		return True

	def tummy_time(self) -> None:
		timer = self.start_or_resume_timer(
			header_text = "Tummy time",
			timer_name = "tummy_time",
			periodic_chime = ConsistentIntervalPeriodicChime(
				devices = self.devices,
				chime_at_seconds = 60
			)
		)

		if timer is not None:
			self.render_splash("Saving...")
			request = PostTummyTimeAPIRequest(child_id = self.child_id, timer = timer)
			if NVRAMValues.OFFLINE:
				self.offline_queue.add(request)
			else:
				request.invoke()
			self.render_success_splash()
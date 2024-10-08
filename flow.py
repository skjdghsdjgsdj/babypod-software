import os
import time
import traceback

import microcontroller
from adafruit_datetime import datetime

from api import GetFirstChildIDAPIRequest, GetLastFeedingAPIRequest, PostChangeAPIRequest, Timer, \
	PostFeedingAPIRequest, PostPumpingAPIRequest, PostTummyTimeAPIRequest, PostSleepAPIRequest, \
	APIRequestFailedException, GetAPIRequest, PostAPIRequest, DeleteAPIRequest, GetAllTimersAPIRequest, TimerAPIRequest, \
	ConnectionManager, ConsumeMOTDAPIRequest
from offline_event_queue import OfflineEventQueue
from devices import Devices
from lcd import LCD, BacklightColors
from nvram import NVRAMValues
from offline_state import OfflineState
from periodic_chime import EscalatingIntervalPeriodicChime, ConsistentIntervalPeriodicChime, PeriodicChime
from piezo import Piezo
from user_input import ActivityListener, WaitTickListener, ShutdownRequestListener, ResetRequestListener
from ui_components import NumericSelector, VerticalMenu, VerticalCheckboxes, ActiveTimer, ProgressBar, Modal

# noinspection PyBroadException
try:
	from typing import Optional, cast
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
		self.suppress_dim_timeout = False

		self.devices.rotary_encoder.on_activity_listeners.append(ActivityListener(
			on_activity = self.on_user_input
		))

		if self.devices.power_control is not None:
			self.devices.rotary_encoder.on_shutdown_requested_listeners.append(ShutdownRequestListener(
				on_shutdown_requested = self.on_shutdown_requested
			))

		self.devices.rotary_encoder.on_reset_requested_listeners.append(ResetRequestListener(
			on_reset_requested = self.on_reset_requested
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

		idle_shutdown = NVRAMValues.IDLE_SHUTDOWN.get()
		if self.devices.power_control and idle_shutdown:
			self.devices.rotary_encoder.on_wait_tick_listeners.append(WaitTickListener(
				on_tick = self.idle_shutdown,
				seconds = NVRAMValues.IDLE_SHUTDOWN.get()
			))

		if self.devices.rtc is None or self.devices.sdcard is None:
			self.offline_state = None
			self.offline_queue = None
		else:
			self.offline_state = OfflineState.from_sdcard(self.devices.sdcard)
			self.devices.rtc.offline_state = self.offline_state

			self.offline_queue = OfflineEventQueue.from_sdcard(self.devices.sdcard, self.devices.rtc)

		self.use_offline_feeding_stats = bool(NVRAMValues.OFFLINE)
		self.device_name = os.getenv("DEVICE_NAME") or "BabyPod"

		self.is_shutting_down = False

	def on_shutdown_requested(self) -> None:
		self.is_shutting_down = True
		self.devices.power_control.shutdown()

	def on_reset_requested(self) -> None:
		self.devices.piezo.tone("error")
		self.devices.lcd.clear()
		self.devices.lcd.backlight.set_color(BacklightColors.ERROR)
		self.devices.lcd.write_centered("Reset!")
		microcontroller.reset()

	def on_backlight_dim_idle(self, _: float) -> None:
		if not self.suppress_dim_timeout:
			print("Dimming backlight due to inactivity")
			self.devices.lcd.backlight.set_color(BacklightColors.DIM)

	def on_idle(self, _: float) -> None:
		self.render_battery_percent(only_if_changed = True)

	def idle_warning(self, _: float) -> None:
		if not self.suppress_idle_warning and self.devices.battery_monitor and not self.devices.battery_monitor.is_charging():
			print("Idle; warning not suppressed and is discharging")
			self.devices.piezo.tone("idle_warning")

	def idle_shutdown(self, _: float) -> None:
		if not self.suppress_idle_warning:
			print("Idle; soft shutdown")
			self.devices.power_control.shutdown(silent = True)

	def on_user_input(self) -> None:
		if not self.suppress_dim_timeout:
			self.devices.lcd.backlight.set_color(BacklightColors.DEFAULT)

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
			print(f"RTC updated to {self.devices.rtc.now()}")
			if old_now is not None:
				print(f"RTC drift: {old_now - self.devices.rtc.now()}")
		except Exception as e:
			print(f"{e} when syncing RTC; forcing sync on next online boot")
			NVRAMValues.FORCE_RTC_UPDATE.write(True)
			raise e

	def auto_connect(self) -> None:
		if not NVRAMValues.OFFLINE:
			self.render_splash("Connecting...")
			# noinspection PyBroadException
			try:
				print("Getting requests instance from ConnectionManager")
				self.requests = ConnectionManager.connect()
			except Exception as e:
				import traceback
				traceback.print_exception(e)
				if self.devices.rtc and self.devices.sdcard:
					self.offline()
				else:
					raise e # can't go offline automatically because there's no hardware support
		elif not self.devices.rtc:
			raise ValueError("External RTC is required for offline support")
		else:
			print("Working offline")

	def init_rtc(self) -> None:
		if self.devices.rtc:
			if NVRAMValues.FORCE_RTC_UPDATE:
				print("RTC update forced")
				self.refresh_rtc()
			elif not self.devices.rtc.now():
				print("RTC not set or is implausible")
				self.refresh_rtc()
			elif self.offline_state.last_rtc_set is None:
				print("Last RTC set date/time unknown; assuming now")
			else:
				now = self.devices.rtc.now()
				last_rtc_set_delta = now - self.offline_state.last_rtc_set
				print(f"RTC = {now}, last set = {self.offline_state.last_rtc_set} (delta = {last_rtc_set_delta.seconds} sec)")
				if last_rtc_set_delta.seconds >= 60 * 60 * 24 or last_rtc_set_delta.days >= 1:
					print("RTC last set more than a day ago")

					if NVRAMValues.OFFLINE:
						print("RTC will be updated next time device is online")
					else:
						print("RTC refresh interval expired")
						self.refresh_rtc()
				else:
					print(f"RTC doesn't need updating: set to {self.devices.rtc.now()}, last refreshed {self.offline_state.last_rtc_set}")

	def init_battery(self) -> None:
		if self.devices.battery_monitor:
			battery_percent = self.devices.battery_monitor.get_percent()
			if battery_percent is not None and battery_percent <= 15:
				self.devices.lcd.backlight.set_color(BacklightColors.ERROR)
				self.render_splash(f"Low battery!")
				self.devices.piezo.tone("low_battery")

				time.sleep(1.5)

				self.devices.lcd.backlight.set_color(BacklightColors.DEFAULT)

	def start(self) -> None:
		self.device_startup()

		self.init_child_id()
		self.jump_to_running_timer()
		self.check_motd()
		self.loop()

	def check_motd(self) -> None:
		if self.devices.rtc and not NVRAMValues.OFFLINE:
			now = self.devices.rtc.now()
			last_checked = self.offline_state.last_motd_check

			if last_checked is not None:
				delta = now - last_checked
				# noinspection PyUnresolvedReferences
				delta_seconds = delta.seconds + (delta.days * 60 * 60 * 24)

				print(f"Now: {now}, last MOTD check: {last_checked}")

				motd_check_required = delta_seconds >= int(NVRAMValues.MOTD_CHECK_INTERVAL)
			else:
				motd_check_required = True

			if motd_check_required:
				print(f"MOTD check interval exceeded")
				try:
					self.render_splash("Checking messages...")
					motd = ConsumeMOTDAPIRequest().get_motd()

					if motd is not None:
						self.clear_and_show_battery()
						Modal(
							devices = self.devices,
							message = motd,
							before_wait_loop = lambda: Piezo.tone("motd")
						).render_and_wait()
						self.clear_and_show_battery()

					self.offline_state.last_motd_check = now
					self.offline_state.to_sdcard()
				except Exception as e:
					import traceback
					traceback.print_exception(e)
					print(f"Getting MOTD failed: {e}")

	def device_startup(self) -> None:
		self.devices.lcd.clear()
		self.auto_connect()
		self.init_rtc()
		self.init_battery()
		self.devices.lcd.clear()

	def init_child_id(self) -> None:
		child_id = NVRAMValues.CHILD_ID.get()
		if not child_id:
			self.render_splash("Getting children...")
			try:
				child_id = GetFirstChildIDAPIRequest().get_first_child_id()
			except Exception as e:
				self.on_error(e)
				print("Child discovery failed so just guessing ID 1")
				child_id = 1
			NVRAMValues.CHILD_ID.write(child_id)
			self.devices.lcd.clear()
		self.child_id = child_id
		print(f"Using child ID {child_id}")

	def loop(self) -> None:
		while True:
			try:
				self.main_menu()
				if not self.is_shutting_down:
					self.clear_and_show_battery()
			except Exception as e:
				self.on_error(e)
				if not self.is_shutting_down:
					self.clear_and_show_battery()

	def jump_to_running_timer(self) -> None:
		timer = None
		if not NVRAMValues.OFFLINE:
			print("Checking for active timers to skip main menu...")
			timer = self.check_for_running_timer()
		if timer is not None:
			try:
				if timer.name == TimerAPIRequest.get_timer_name("feeding"):
					self.feeding(timer)
				elif timer.name == TimerAPIRequest.get_timer_name("sleep"):
					self.sleep(timer)
				elif timer.name == TimerAPIRequest.get_timer_name("tummy_time"):
					self.tummy_time(timer)
				elif timer.name == TimerAPIRequest.get_timer_name("pumping"):
					self.pumping(timer)
				self.clear_and_show_battery()
			except Exception as e:
				self.on_error(e)
				self.clear_and_show_battery()

	def check_for_running_timer(self) -> Optional[Timer]:
		timer = None
		try:
			self.render_splash("Checking timers...")
			timers = list(GetAllTimersAPIRequest(limit = 1).get_active_timers())
			if timers:
				timer = timers[0]
			self.clear_and_show_battery()
		except Exception as e:
			print(f"Failed getting active timers; continuing to main menu: {e}")
			self.clear_and_show_battery()
		return timer

	def on_error(self, e: Exception) -> None:
		traceback.print_exception(e)
		message = f"Got {type(e).__name__}!"
		if isinstance(e, APIRequestFailedException):
			request = e.request

			if isinstance(request, GetAPIRequest):
				message = "GET"
			elif isinstance(request, PostAPIRequest):
				message = "POST"
			elif isinstance(request, DeleteAPIRequest):
				message = "DELETE"
			else:
				message = "Request"

			message += " failed"
			if e.http_status_code != 0:
				message += f" ({e.http_status_code})"
		elif "ETIMEDOUT" in str(e):
				message = "Request timeout!"

		self.devices.lcd.backlight.set_color(BacklightColors.ERROR)
		self.devices.piezo.tone("error")
		self.clear_and_show_battery()
		self.suppress_dim_timeout = True
		Modal(devices = self.devices, message = message).render_and_wait()
		self.devices.lcd.backlight.set_color(BacklightColors.DEFAULT)
		self.suppress_dim_timeout = False

	def render_header_text(self, text: str) -> None:
		self.devices.lcd.write(text, (0, 0))

	@staticmethod
	def format_battery_percent(percent: int) -> str:
		return f"{percent}%"

	def render_battery_percent(self, only_if_changed: bool = False) -> None:
		if self.devices.battery_monitor is None:
			return

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
		self.devices.lcd.backlight.set_color(BacklightColors.SUCCESS)
		self.devices.piezo.tone("success")
		time.sleep(hold_seconds)
		self.devices.lcd.backlight.set_color(BacklightColors.DEFAULT)

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
		if self.use_offline_feeding_stats or NVRAMValues.OFFLINE:
			last_feeding = self.offline_state.last_feeding
			method = self.offline_state.last_feeding_method

			# reapply the value which could have been changed by feeding saved just now
			self.use_offline_feeding_stats = bool(NVRAMValues.OFFLINE)
		else:
			self.render_splash("Getting feeding...")
			last_feeding, method = GetLastFeedingAPIRequest(self.child_id).get_last_feeding()
			if self.offline_state is not None and \
					(self.offline_state.last_feeding != last_feeding or
					self.offline_state.last_feeding_method != method):
				self.offline_state.last_feeding = last_feeding
				self.offline_state.last_feeding_method = method
				self.offline_state.to_sdcard()

		if last_feeding is not None:
			last_feeding_str = "Feed " + Flow.datetime_to_time_str(last_feeding)

			if method == "right breast":
				last_feeding_str += " R"
			elif method == "left breast":
				last_feeding_str += " L"
			elif method == "both breasts":
				last_feeding_str += " RL"
			elif method == "bottle":
				last_feeding_str += " B"
		else:
			last_feeding_str = "Feeding"

		self.clear_and_show_battery()

		selected_index = VerticalMenu(options = [
			last_feeding_str,
			"Diaper change",
			"Sleep",
			"Pumping",
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
			self.sleep()
		elif selected_index == 3:
			self.pumping()

		self.clear_and_show_battery()

	def settings(self) -> None:
		options = [
			"Sounds"
		]

		initial_states = [
			NVRAMValues.PIEZO.get()
		]

		has_offline_hardware = self.devices.rtc and self.devices.sdcard
		if has_offline_hardware:
			options.append("Offline")
			initial_states.append(NVRAMValues.OFFLINE.get())

		responses = VerticalCheckboxes(
			options = options,
			initial_states = initial_states, devices = self.devices, anchor = VerticalMenu.ANCHOR_TOP
		).render_and_wait()

		if responses is not None:
			NVRAMValues.PIEZO.write(responses[0])

			if has_offline_hardware:
				if NVRAMValues.OFFLINE and not responses[1]: # was offline, now back online
					self.back_online()
				elif not NVRAMValues.OFFLINE and responses[1]: # was online, now offline
					self.offline()

	def offline(self):
		self.render_splash("Going offline")
		self.devices.piezo.tone("info")
		time.sleep(1)
		ConnectionManager.disconnect()
		NVRAMValues.OFFLINE.write(True)

	def back_online(self) -> None:
		NVRAMValues.OFFLINE.write(False)
		self.auto_connect()
		files = self.offline_queue.get_json_files()
		if len(files) > 0:
			print(f"Replaying offline-serialized {len(files)} requests")

			self.devices.lcd.clear()

			progress_bar = ProgressBar(devices = self.devices, count = len(files), message = "Syncing changes...")
			progress_bar.render_and_wait()

			index = 0
			for filename in files:
				progress_bar.set_index(index)
				try:
					self.offline_queue.replay(filename)
				except Exception as e:
					NVRAMValues.OFFLINE.write(True)
					raise e
				index += 1

			self.render_success_splash("Change synced!" if len(files) == 1 else f"{len(files)} changes synced!")

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

			request = PostChangeAPIRequest(
				child_id = self.child_id,
				is_wet = is_wet,
				is_solid = is_solid
			)
			if NVRAMValues.OFFLINE:
				self.offline_queue.add(request)
			else:
				self.render_splash("Saving...")
				request.invoke()
			self.render_success_splash()

	def pumping(self, existing_timer: Optional[Timer] = None) -> None:
		saved = False
		while not saved:
			timer = self.start_or_resume_timer(
				existing_timer = existing_timer,
				header_text = "Pumping",
				timer_name = "pumping",
				periodic_chime = ConsistentIntervalPeriodicChime(
					devices = self.devices,
					chime_at_seconds = 5 * 60
				)
			)

			if timer is not None:
				self.clear_and_show_battery()
				self.render_header_text("How much?")

				amount = NumericSelector(
					devices = self.devices,
					minimum = 0,
					step = 0.5,
					format_str = "%.1f fl oz"
				).render_and_wait()

				if amount is not None:
					request = PostPumpingAPIRequest(
						child_id = self.child_id,
						timer = timer,
						amount = amount
					)
					if NVRAMValues.OFFLINE:
						self.offline_queue.add(request)
					else:
						self.render_splash("Saving...")
						request.invoke()
					self.render_success_splash()
					saved = True
			else:
				return

	def start_or_resume_timer(self,
		header_text: str,
		timer_name: str,
		periodic_chime: PeriodicChime = None,
		subtext: str = None,
		existing_timer: Optional[Timer] = None,
	) -> Optional[Timer]:
		if existing_timer is not None:
			timer = existing_timer
		elif NVRAMValues.OFFLINE:
			timer = Timer(
				name = timer_name,
				offline = True,
				rtc = self.devices.rtc,
				battery = self.devices.battery_monitor
			)
			timer.started_at = self.devices.rtc.now()
			timer.start_or_resume()
		else:
			self.render_splash("Checking status...")
			timer = Timer(
				name = timer_name,
				offline = False,
				battery = self.devices.battery_monitor
			)
			timer.start_or_resume()

		self.clear_and_show_battery()
		self.render_header_text(header_text)

		if subtext is not None:
			self.devices.lcd.write(message = subtext, coords = (0, 2))

		self.suppress_idle_warning = True
		response = ActiveTimer(
			devices = self.devices,
			periodic_chime = periodic_chime,
			start_at = timer.resume_from_duration
		).render_and_wait()
		self.suppress_idle_warning = False

		if response is None:
			if not NVRAMValues.OFFLINE:
				self.render_splash("Canceling...")
			timer.cancel()
			return None # canceled

		return timer

	def feeding(self, existing_timer: Optional[Timer] = None) -> None:
		saved = False
		while not saved:
			timer = self.start_or_resume_timer(
				existing_timer = existing_timer,
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

		request = PostFeedingAPIRequest(
			child_id = self.child_id,
			timer = timer,
			food_type = food_type,
			method = method
		)
		if NVRAMValues.OFFLINE:
			self.offline_queue.add(request)
		else:
			self.render_splash("Saving...")
			request.invoke()

		if self.offline_state is not None:
			self.offline_state.last_feeding = timer.started_at
			self.offline_state.last_feeding_method = method
			self.offline_state.to_sdcard()
			self.use_offline_feeding_stats = True

		self.render_success_splash()

		return True

	def sleep(self, existing_timer: Optional[Timer] = None) -> None:
		timer = self.start_or_resume_timer(
			existing_timer = existing_timer,
			header_text = "Sleep",
			timer_name = "sleep"
		)

		if timer is not None:
			request = PostSleepAPIRequest(child_id = self.child_id, timer = timer)
			if NVRAMValues.OFFLINE:
				self.offline_queue.add(request)
			else:
				self.render_splash("Saving...")
				request.invoke()

			self.render_success_splash()

	def tummy_time(self, existing_timer: Optional[Timer] = None) -> None:
		timer = self.start_or_resume_timer(
			existing_timer = existing_timer,
			header_text = "Tummy time",
			timer_name = "tummy_time",
			periodic_chime = ConsistentIntervalPeriodicChime(
				devices = self.devices,
				chime_at_seconds = 60
			)
		)

		if timer is not None:
			request = PostTummyTimeAPIRequest(child_id = self.child_id, timer = timer)
			if NVRAMValues.OFFLINE:
				self.offline_queue.add(request)
			else:
				self.render_splash("Saving...")
				request.invoke()
			self.render_success_splash()
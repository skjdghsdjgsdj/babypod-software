import time

import adafruit_datetime
import adafruit_requests
import microcontroller
import wifi
import os
from adafruit_datetime import datetime
import binascii
import adafruit_connection_manager
import re

from battery_monitor import BatteryMonitor
from external_rtc import ExternalRTC
from util import Util

# noinspection PyBroadException
try:
	from typing import Optional, List, Any, Generator, Callable, Dict
except:
	pass
	# ignore, just for IDE's sake, not supported on board

class ConnectionManager:
	requests: adafruit_requests.Session = None
	timeout: int

	@staticmethod
	def connect() -> adafruit_requests.Session:
		if ConnectionManager.requests is None:
			ssid = os.getenv("CIRCUITPY_WIFI_SSID_DEFER")
			password = os.getenv("CIRCUITPY_WIFI_PASSWORD_DEFER")

			channel = os.getenv("CIRCUITPY_WIFI_INITIAL_CHANNEL")
			channel = int(channel) if channel else 0

			ConnectionManager.mac_id = binascii.hexlify(wifi.radio.mac_address).decode("ascii")
			wifi.radio.hostname = f"babypod-{ConnectionManager.mac_id}"

			try:
				print(f"Connecting to {ssid}...")
				wifi.radio.connect(ssid = ssid, password = password, channel = channel, timeout = ConnectionManager.timeout)
				print("Getting SSL context...")
				ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
				print("Getting socket pool...")
				pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
				print("Getting session...")
				ConnectionManager.requests = adafruit_requests.Session(pool, ssl_context)
				print(f"Connected: RSSI {wifi.radio.ap_info.rssi} on channel {wifi.radio.ap_info.channel}, tx power {wifi.radio.tx_power} dBm")
			except ConnectionError as e:
				print(f"Connection attempt failed: {e}")
				raise e

		return ConnectionManager.requests

	@staticmethod
	def disconnect() -> None:
		wifi.radio.enabled = False
		ConnectionManager.requests = None

timeout = os.getenv("CIRCUITPY_WIFI_TIMEOUT")
ConnectionManager.timeout = 10 if (timeout is None or not timeout) else int(timeout)

class APIRequest:
	API_KEY = os.getenv("BABYBUDDY_AUTH_TOKEN")
	BASE_URL = os.getenv("BABYBUDDY_BASE_URL")

	def __init__(self, uri: str, uri_args = None, payload = None):
		self.uri = uri
		self.uri_args = uri_args
		self.payload = payload

	def serialize_to_json(self) -> object:
		raise RuntimeError(f"{str(type(self))} is not supported offline")

	@classmethod
	def deserialize_from_json(cls, json_object):
		raise RuntimeError(f"{str(cls)} is not supported offline")

	def merge_serialized_notes(self, json_object):
		if "notes" in json_object and json_object["notes"] is not None:
			self.payload["notes"] = json_object["notes"]

		return self

	@staticmethod
	def escape_uri_value(value: str) -> str:
		safe_chars = re.compile(r"[A-Za-z0-9]")
		escaped = ""
		for char in str(value):
			escaped += f"%{ord(char):x}" if safe_chars.match(char) is None else char

		return escaped

	def build_full_url(self) -> str:
		full_url = APIRequest.BASE_URL + self.uri + "/"
		if self.uri_args:
			is_first = True
			for key, value in self.uri_args.items():
				value = APIRequest.escape_uri_value(value)
				full_url += ("?" if is_first else "&") + f"{key}={value}"
				is_first = False

		return full_url

	def validate_response(self, response: adafruit_requests.Response) -> None:
		if response.status_code < 200 or response.status_code >= 300:
			raise APIRequestFailedException(self, response.status_code)

	@staticmethod
	def merge(payload, timer = None, extra_notes: List[str] = None):
		if timer is not None:
			payload.update(timer.as_payload())

		notes = os.getenv("DEVICE_NAME") or "BabyPod"

		if extra_notes is None:
			extra_notes = []

		if timer is not None:
			battery_notes = APIRequest.battery_delta_as_notes(timer)
			if battery_notes is not None:
				extra_notes.append(battery_notes)

		if len(extra_notes) > 0:
			notes += "\n" + "\n".join(extra_notes)

		payload.update({"notes": notes})

		return payload

	@staticmethod
	def battery_delta_as_notes(timer):
		ending_battery_percent = None
		if timer is not None and timer.starting_battery_percent is not None:
			try:
				ending_battery_percent = timer.battery.get_percent()
			except Exception as e:
				print(f"Got {e} while getting battery percent; not tracking for this timer")

		if timer is not None and timer.starting_battery_percent is not None and ending_battery_percent is not None:
			consumed = ending_battery_percent - timer.starting_battery_percent
			return f"🔋 {timer.starting_battery_percent}% → {ending_battery_percent}%, Δ{-consumed}%"

		return None

	def get_verb(self) -> str:
		raise NotImplementedError()

	def get_connection_method(self) -> Callable:
		raise NotImplementedError()

	def invoke(self):
		full_url = self.build_full_url()
		print(f"HTTP {self.get_verb()}: {full_url}")
		if self.payload is not None:
			print(f"Payload: {self.payload}")

		microcontroller.watchdog.feed()

		start = time.monotonic()
		response = self.get_connection_method()(
			url = full_url,
			json = self.payload,
			headers = {
				"Authorization": f"Token {APIRequest.API_KEY}"
			},
			timeout = ConnectionManager.timeout
		)
		end = time.monotonic()
		self.validate_response(response)
		print(f"Got HTTP {response.status_code}, took {end - start} sec")

		microcontroller.watchdog.feed()

		# HTTP 204 is No Content so there shouldn't be a response payload
		response_json = None if response.status_code is 204 else response.json()
		response.close()

		return response_json

class APIRequestFailedException(Exception):
	def __init__(self, request: APIRequest, http_status_code: int = 0):
		self.request = request
		self.http_status_code = http_status_code

class GetAPIRequest(APIRequest):
	def get_verb(self) -> str:
		return "GET"

	def get_connection_method(self) -> Callable:
		return ConnectionManager.connect().get

class PostAPIRequest(APIRequest):
	def get_verb(self) -> str:
		return "POST"

	def get_connection_method(self) -> Callable:
		return ConnectionManager.connect().post

class DeleteAPIRequest(APIRequest):
	def get_verb(self) -> str:
		return "DELETE"

	def get_connection_method(self) -> Callable:
		return ConnectionManager.connect().delete

class TaggableLimitableGetAPIRequest(GetAPIRequest):
	def __init__(self, uri: str, tag_name: Optional[str] = None, limit: Optional[int] = None, uri_args = None, payload = None):
		self.tag_name = tag_name
		self.limit = limit
		self.uri_args = uri_args or {}

		self.merge_limit()
		self.merge_tag()

		super().__init__(uri, self.uri_args, payload)

	def merge_limit(self) -> None:
		if self.limit is not None:
			if self.limit <= 0:
				raise ValueError(f"Limit must be >= 1, not {self.limit}")
			self.uri_args["limit"] = self.limit

	def merge_tag(self) -> None:
		if self.tag_name is not None:
			self.uri_args["tags"] = self.tag_name

class GetNotesAPIRequest(TaggableLimitableGetAPIRequest):
	def __init__(self, tag_name: Optional[str] = None, limit: Optional[int] = None):
		super().__init__(uri = "notes", tag_name = tag_name, limit = limit)

class ConsumeMOTDAPIRequest:
	TAG_NAME = "BabyPod MOTD"

	def __init__(self, tag_name: str = TAG_NAME):
		self.tag_name = tag_name

	def get_motd(self) -> Optional[str]:
		response = GetNotesAPIRequest(tag_name = self.tag_name, limit = 1).invoke()
		if len(response["results"]) <= 0:
			return None

		note_id = response["results"][0]["id"]
		motd = response["results"][0]["note"]

		DeleteNotesAPIRequest(note_id = note_id).invoke()

		return motd

class DeleteNotesAPIRequest(DeleteAPIRequest):
	def __init__(self, note_id: int):
		super().__init__(uri = f"notes/{note_id}")

class Timer:
	def __init__(self, name: str, offline: bool, rtc: ExternalRTC = None, battery: BatteryMonitor = None):
		self.offline = offline
		self.started_at: Optional[datetime] = None
		self.ended_at: Optional[datetime] = None
		self.timer_id: Optional[int] = None
		self.name = name
		self.rtc = rtc
		self.battery = battery
		self.starting_battery_percent = None
		self.resume_from_duration = None

	@staticmethod
	def duration_to_seconds(duration: str) -> int:
		duration_parts = duration.split(":")

		hours = int(duration_parts[0])
		minutes = int(duration_parts[1])
		seconds = int(float(duration_parts[2]))

		return (hours * 60 * 60) + (minutes * 60) + seconds

	def start_or_resume(self) -> None:
		elapsed = 0

		self.starting_battery_percent = None
		if self.battery is not None:
			try:
				self.starting_battery_percent = self.battery.get_percent()
			except Exception as e:
				print(f"Got {e} while checking starting battery percent; not tracking battery usage for this timer")

		if not self.offline:
			timers = GetNamedTimerAPIRequest(self.name).invoke()
			max_id = None
			timer = None

			for timer_result in timers["results"]:
				if max_id is None or timer_result["id"] > max_id:
					max_id = timer_result["id"]
					timer = timer_result

			if timer is not None:
				self.timer_id = timer["id"]
				elapsed = Timer.duration_to_seconds(timer["duration"])

				if elapsed > 0:
					self.starting_battery_percent = None
			else:
				timer = CreateTimerAPIRequest(self.name).invoke()
				self.timer_id = timer["id"]

			self.started_at = Util.to_datetime(timer["start"])

		self.resume_from_duration = elapsed

	def cancel(self) -> None:
		if not self.offline:
			DeleteTimerAPIRequest(self.timer_id).invoke()

	def as_payload(self) -> dict[str, Any]:
		if self.timer_id is None:
			if self.started_at is None:
				raise ValueError("Timer was never started or resumed")

			if self.ended_at is None and self.rtc is not None:
				self.ended_at = self.rtc.now()

			return {
				"start": self.started_at.isoformat(),
				"end": self.ended_at.isoformat()
			}
		else:
			return {
				"timer": self.timer_id
			}

	@staticmethod
	def from_payload(name: str, payload: dict[str, Any]):
		if "timer" in payload:
			timer = Timer(name = name, offline = False)
			timer.timer_id = payload["timer"]
		elif "start" in payload and "end" in payload:
			timer = Timer(name = name, offline = True)
			timer.started_at = Util.to_datetime(payload["start"])
			timer.ended_at = Util.to_datetime(payload["end"])
		else:
			raise ValueError("Don't know how to create a timer from this payload")

		return timer

	def __str__(self) -> str:
		value = "Timer"
		if self.name:
			value += f" \"{self.name}\""

		if self.timer_id:
			value += f" ID {self.timer_id}"

		if self.started_at:
			value += f"{self.started_at} ->"

		if self.ended_at:
			value += f" {self.ended_at}"
		else:
			value += " ongoing"

		return value

class PostChangeAPIRequest(PostAPIRequest):
	def __init__(self, child_id: int, is_wet: bool, is_solid: bool):
		super().__init__(uri = "changes", payload = APIRequest.merge({
			"child": child_id,
			"wet": is_wet,
			"solid": is_solid
		}))

	def serialize_to_json(self) -> object:
		return {
			"child_id": self.payload["child"],
			"is_wet": self.payload["wet"],
			"is_solid": self.payload["solid"],
			"notes": self.payload["notes"]
		}

	@classmethod
	def deserialize_from_json(cls, json_object):
		request = PostChangeAPIRequest(
			child_id = json_object["child_id"],
			is_wet = json_object["is_wet"],
			is_solid = json_object["is_solid"]
		)

		return request.merge_serialized_notes(json_object)

class PostPumpingAPIRequest(PostAPIRequest):
	def __init__(self, child_id: int, timer: Timer, amount: float):
		super().__init__(uri = "pumping", payload = APIRequest.merge({
			"child": child_id,
			"amount": amount
		}, timer))

		self.timer = timer

	def serialize_to_json(self) -> object:
		return APIRequest.merge({
			"child_id": self.payload["child"],
			"amount": self.payload["amount"]
		}, self.timer)

	@classmethod
	def deserialize_from_json(cls, json_object):
		timer = Timer.from_payload(name = "pumping", payload = json_object)
		request = PostPumpingAPIRequest(
			child_id = json_object["child_id"],
			timer = timer,
			amount = json_object["amount"]
		)

		return request.merge_serialized_notes(json_object)


class PostSleepAPIRequest(PostAPIRequest):
	def __init__(self, child_id: int, timer: Timer, nap: Optional[bool] = None):
		super().__init__(uri = "sleep", payload = APIRequest.merge({
			"child": child_id,
			"nap": nap
		}, timer))

		self.timer = timer

	def serialize_to_json(self) -> object:
		return APIRequest.merge({
			"child_id": self.payload["child"],
			"nap": self.payload["nap"]
		}, self.timer)

	@classmethod
	def deserialize_from_json(cls, json_object):
		timer = Timer.from_payload(name = "sleep", payload = json_object)
		request = PostSleepAPIRequest(
			child_id = json_object["child_id"],
			timer = timer,
			nap = json_object["nap"]
		)

		return request.merge_serialized_notes(json_object)

class PostTummyTimeAPIRequest(PostAPIRequest):
	def __init__(self, child_id: int, timer: Timer):
		super().__init__(uri = "tummy-times", payload = APIRequest.merge({
			"child": child_id
		}, timer))

		self.timer = timer

	def serialize_to_json(self) -> object:
		return APIRequest.merge({
			"child_id": self.payload["child"]
		}, self.timer)

	@classmethod
	def deserialize_from_json(cls, json_object):
		timer = Timer.from_payload(name = "tummy-time", payload = json_object)
		request = PostTummyTimeAPIRequest(
			child_id = json_object["child_id"],
			timer = timer
		)

		return request.merge_serialized_notes(json_object)

class PostFeedingAPIRequest(PostAPIRequest):
	def __init__(self, child_id: int, food_type: str, method: str, timer: Timer):
		super().__init__(uri = "feedings", payload = APIRequest.merge({
			"child": child_id,
			"type": food_type,
			"method": method
		}, timer))

		self.timer = timer

	def serialize_to_json(self) -> object:
		return APIRequest.merge(payload = {
			"child_id": self.payload["child"],
			"food_type": self.payload["type"],
			"method": self.payload["method"]
		}, timer = self.timer)

	@classmethod
	def deserialize_from_json(cls, json_object):
		timer = Timer.from_payload(name = "feeding", payload = json_object)
		request = PostFeedingAPIRequest(
			child_id = json_object["child_id"],
			food_type = json_object["food_type"],
			method = json_object["method"],
			timer = timer
		)

		return request.merge_serialized_notes(json_object)

class GetLastFeedingAPIRequest(GetAPIRequest):
	def __init__(self, child_id: int):
		super().__init__(uri = "feedings", uri_args = {
			"limit": 1,
			"child_id": child_id
		})

	def get_last_feeding(self) -> Optional[tuple[adafruit_datetime.datetime, str]]:
		response = self.invoke()

		if response["count"] <= 0:
			return None

		return Util.to_datetime(response["results"][0]["start"]), response["results"][0]["method"]

class GetFirstChildIDAPIRequest(GetAPIRequest):
	def __init__(self):
		super().__init__("children")

	def get_first_child_id(self) -> int:
		response = self.invoke()
		if response["count"] <= 0:
			raise ValueError("No children defined in Baby Buddy")
		else:
			if response["count"] > 1:
				print("More than one child defined in Baby Buddy; using first one")

			return response["results"][0]["id"]

class TimerAPIRequest:
	@staticmethod
	def get_timer_basename() -> str:
		return "babypod-"

	@staticmethod
	def get_timer_name(name: str):
		return TimerAPIRequest.get_timer_basename() + name

class CreateTimerAPIRequest(PostAPIRequest, TimerAPIRequest):
	def __init__(self, name: str):
		super().__init__(uri = "timers", payload = {
			"name": self.get_timer_name(name)
		})

class GetNamedTimerAPIRequest(GetAPIRequest, TimerAPIRequest):
	def __init__(self, name: str):
		super().__init__(uri = "timers", uri_args = {
			"name": self.get_timer_name(name)
		})

class GetAllTimersAPIRequest(TaggableLimitableGetAPIRequest, TimerAPIRequest):
	def __init__(self, tag_name: Optional[str] = None, limit: Optional[int] = None):
		super().__init__(uri = "timers", tag_name = tag_name, limit = limit)

	def get_active_timers(self) -> Generator[Timer]:
		response = self.invoke()
		prefix = TimerAPIRequest.get_timer_basename()
		for result in response["results"]:
			name: str = result["name"]
			if name is not None and name.startswith(prefix):
				timer = Timer(
					name = name,
					offline = False
				)
				timer.started_at = Util.to_datetime(result["start"])
				timer.timer_id = result["id"]
				timer.resume_from_duration = Timer.duration_to_seconds(result["duration"])

				yield timer

class DeleteTimerAPIRequest(DeleteAPIRequest):
	def __init__(self, timer_id: int):
		super().__init__(uri = f"timers/{timer_id}")
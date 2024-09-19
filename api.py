import adafruit_datetime
import adafruit_requests
import wifi
import os
from adafruit_datetime import datetime
import binascii
import adafruit_connection_manager

from battery_monitor import BatteryMonitor
from external_rtc import ExternalRTC

# noinspection PyBroadException
try:
	from typing import Optional, List, Any
except:
	pass
	# ignore, just for IDE's sake, not supported on board

class APIRequest:
	API_KEY = os.getenv("BABYBUDDY_AUTH_TOKEN")
	BASE_URL = os.getenv("BABYBUDDY_BASE_URL")

	requests = None
	mac_id = None

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

	def build_full_url(self) -> str:
		full_url = APIRequest.BASE_URL + self.uri
		if self.uri_args is not None:
			is_first = True
			for key, value in self.uri_args.items():
				# not escaped! urllib not available for this board
				full_url += ("?" if is_first else "&") + f"{key}={value}"
				is_first = False

		return full_url

	@staticmethod
	def validate_response(response: adafruit_requests.Response) -> None:
		if response.status_code < 200 or response.status_code >= 300:
			raise Exception(f"Got HTTP {response.status_code} for request: {response.text}")

	@staticmethod
	def connect() -> adafruit_requests.Session:
		if APIRequest.requests is None:
			ssid = os.getenv("CIRCUITPY_WIFI_SSID_DEFER")
			password = os.getenv("CIRCUITPY_WIFI_PASSWORD_DEFER")
			timeout = os.getenv("CIRCUITPY_WIFI_TIMEOUT")
			timeout = int(timeout) if timeout else 10

			channel = os.getenv("CIRCUITPY_WIFI_INITIAL_CHANNEL")
			channel = int(channel) if channel else 0

			APIRequest.mac_id = binascii.hexlify(wifi.radio.mac_address).decode("ascii")
			wifi.radio.hostname = f"babypod-{APIRequest.mac_id}"

			print(f"Connecting to {ssid}...")
			wifi.radio.connect(ssid = ssid, password = password, channel = channel, timeout = timeout)
			print("Getting SSL context...")
			ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
			print("Getting socket pool...")
			pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
			print("Getting session...")
			APIRequest.requests = adafruit_requests.Session(pool, ssl_context)
			print(f"Connected: RSSI {wifi.radio.ap_info.rssi} on channel {wifi.radio.ap_info.channel}, tx power {wifi.radio.tx_power} dBm")

		return APIRequest.requests

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

	def invoke(self):
		raise NotImplementedError()

class PostAPIRequest(APIRequest):
	def __init__(self, uri: str, uri_args = None, payload = None):
		super().__init__(uri = uri, uri_args = uri_args, payload = payload)

	def invoke(self):
		full_url = self.build_full_url()
		print(f"HTTP POST: {full_url} with data: {self.payload}")
		response = APIRequest.connect().post(
			url = full_url,
			json = self.payload,
			headers = {
				"Authorization": f"Token {APIRequest.API_KEY}"
			}
		)
		APIRequest.validate_response(response)
		response_json = response.json()
		response.close()

		return response_json

class GetAPIRequest(APIRequest):
	def __init__(self, uri: str, uri_args = None, payload = None):
		super().__init__(uri = uri, uri_args = uri_args, payload = payload)

	def invoke(self):
		full_url = self.build_full_url()
		print(f"HTTP GET: {full_url}")
		response = APIRequest.connect().get(
			url = full_url,
			headers = {
				"Authorization": f"Token {APIRequest.API_KEY}"
			}
		)

		APIRequest.validate_response(response)
		json_response = response.json()
		response.close()

		return json_response

class DeleteAPIRequest(APIRequest):
	def __init__(self, uri: str, uri_args = None, payload = None):
		super().__init__(uri = uri, uri_args = uri_args, payload = payload)

	def invoke(self):
		full_url = self.build_full_url()
		print(f"HTTP DELETE: {full_url}")
		response = APIRequest.connect().delete(
			url = full_url,
			headers = {
				"Authorization": f"Token {APIRequest.API_KEY}"
			}
		)

		APIRequest.validate_response(response)

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

	def start_or_resume(self) -> int:
		elapsed = 0

		self.starting_battery_percent = None
		if self.battery is not None:
			try:
				self.starting_battery_percent = self.battery.get_percent()
			except Exception as e:
				print(f"Got {e} while checking starting battery percent; not tracking battery usage for this timer")

		if not self.offline:
			timers = GetTimerAPIRequest(self.name).invoke()
			max_id = None
			timer = None

			for timer_result in timers["results"]:
				if max_id is None or timer_result["id"] > max_id:
					max_id = timer_result["id"]
					timer = timer_result

			if timer is not None:
				self.timer_id = timer["id"]

				duration_parts = timer["duration"].split(":")

				hours = int(duration_parts[0])
				minutes = int(duration_parts[1])
				seconds = int(float(duration_parts[2]))

				elapsed = (hours * 60 * 60) + (minutes * 60) + seconds

				if elapsed > 0:
					self.starting_battery_percent = None
			else:
				timer = CreateTimerAPIRequest(self.name).invoke()
				self.timer_id = timer["id"]

			self.started_at = datetime.fromisoformat(timer["start"])

		return elapsed

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
			timer.started_at = datetime.fromisoformat(payload["start"])
			timer.ended_at = datetime.fromisoformat(payload["end"])
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
	def __init__(self, child_id: int, amount: float):
		super().__init__(uri = "pumping", payload = {
			"child": child_id,
			"amount": amount
		})

	def serialize_to_json(self) -> object:
		return {
			"child_id": self.payload["child"],
			"amount": self.payload["amount"]
		}

	@classmethod
	def deserialize_from_json(cls, json_object):
		request = PostPumpingAPIRequest(
			child_id = json_object["child_id"],
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

		return datetime.fromisoformat(response["results"][0]["start"]), response["results"][0]["method"]

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
	def get_timer_name(name: str):
		return f"babypod-{name}"

class CreateTimerAPIRequest(PostAPIRequest, TimerAPIRequest):
	def __init__(self, name: str):
		super().__init__(uri = "timers", payload = {
			"name": self.get_timer_name(name)
		})

class GetTimerAPIRequest(GetAPIRequest, TimerAPIRequest):
	def __init__(self, name: str):
		super().__init__(uri = "timers", uri_args = {
			"name": self.get_timer_name(name)
		})

class DeleteTimerAPIRequest(DeleteAPIRequest):
	def __init__(self, timer_id: int):
		super().__init__(uri = f"timers/{timer_id}")
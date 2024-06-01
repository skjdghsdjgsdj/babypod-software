import json
import adafruit_datetime
import adafruit_requests
import wifi
import socketpool
import ssl
import os
from adafruit_datetime import datetime
import binascii

# noinspection PyBroadException
try:
	from typing import Optional, List
except:
	pass
	# ignore, just for IDE's sake, not supported on board

class Duration:
	def __init__(self, seconds: float):
		assert(seconds >= 0)
		self.seconds = seconds

	@staticmethod
	def from_api(duration: str):
		hours_str, minutes_str, seconds_str = duration.split(":")

		hours = int(hours_str)
		minutes = int(minutes_str)
		seconds = float(seconds_str)

		return Duration((hours * 60 * 60) + (minutes * 60) + seconds)

	def to_hms(self):
		return self.seconds // 3600, self.seconds // 60 % 60, self.seconds % 60

	def to_short_format(self):
		hours, minutes, seconds = self.to_hms()

		parts = []
		if hours > 0:
			parts.append(f"{hours}h")
		if minutes > 0:
			parts.append(f"{minutes}m")
		if seconds > 0:
			parts.append("%ds" % seconds)

		return "0s" if len(parts) == 0 else " ".join(parts)

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
			raise Exception(f"Got HTTP {response.status_code} for request")

	@staticmethod
	def connect() -> adafruit_requests.Session:
		if APIRequest.requests is None:
			ssid = os.getenv("CIRCUITPY_WIFI_SSID_DEFER")
			password = os.getenv("CIRCUITPY_WIFI_PASSWORD_DEFER")
			channel = int(os.getenv("CIRCUITPY_WIFI_INITIAL_CHANNEL"))

			APIRequest.mac_id = binascii.hexlify(wifi.radio.mac_address).decode("ascii")
			wifi.radio.hostname = f"babypod-{APIRequest.mac_id}"

			print(f"Connecting to {ssid}...")
			wifi.radio.connect(ssid = ssid, password = password, channel = channel)
			pool = socketpool.SocketPool(wifi.radio)
			# noinspection PyTypeChecker
			APIRequest.requests = adafruit_requests.Session(pool, ssl.create_default_context())
			print("Connected!")

		return APIRequest.requests

	def invoke(self):
		raise NotImplementedError()

class OfflineEventQueue:
	JSON_PATH = "/sd/queue/"
	INDEX = "index.json"

	def __init__(self):
		self.queue: List[APIRequest] = []

		index_json_path = f"{OfflineEventQueue.JSON_PATH}/{OfflineEventQueue.INDEX}"
		create_new_index = not os.path.exists(index_json_path)

		self.index_fp = open(index_json_path, mode = "rw")
		if create_new_index:
			self.reset_index()

	def __del__(self):
		self.index_fp.close()

	def reset_index(self):
		self.index_fp.seek(0)
		self.index_fp.write(json.dumps([]))

	def load_index(self):
		self.index_fp.seek(0)
		return json.load(self.index_fp)

	def append_to_index(self, payload):
		index = self.load_index()
		print(f"Appending {type(payload)} to index (now {len(index)} items)")
		index.append(payload)
		json.dump(index, self.index_fp)

	def add(self, request: APIRequest):
		payload = {
			"type": type(request),
			"payload": request.serialize_to_json()
		}
		self.append_to_index(payload)

	def replay_all(self, empty_on_success = True):
		index = self.load_index()
		print(f"Replaying index ({len(index)} items)")
		for item in index:
			klass = locals().get(item["type"])
			method = getattr(klass, "deserialize_from_json")
			request: APIRequest = method(item["payload"])

			print(f"Replaying {request}")

			request.invoke()

		if empty_on_success:
			self.reset_index()

class PostAPIRequest(APIRequest):
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
	def invoke(self):
		full_url = self.build_full_url()
		print(f"HTTP GET: {full_url}")
		response = APIRequest.connect().delete(
			url = full_url,
			headers = {
				"Authorization": f"Token {APIRequest.API_KEY}"
			}
		)

		APIRequest.validate_response(response)

class Timer:
	def __init__(self, name: str, offline: bool):
		self.offline = offline
		self.started_at: Optional[datetime] = None
		self.ended_at: Optional[datetime] = None
		self.timer_id: Optional[int] = None
		self.name = name

	def start_or_resume(self):
		if self.started_at is None:
			self.started_at = datetime.now()

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
				self.started_at = datetime.fromisoformat(timer["start"])
			else:
				response = CreateTimerAPIRequest(self.name).invoke()
				self.timer_id = response["id"]

	def cancel(self):
		if not self.offline:
			DeleteTimerAPIRequest(self.timer_id).invoke()

	def as_payload(self):
		if self.timer_id is None:
			if self.started_at is None:
				raise ValueError("Timer was never started or resumed")

			if self.ended_at is None:
				self.ended_at = datetime.now()

			return {
				"start": self.started_at.isoformat(),
				"end": self.ended_at.isoformat()
			}
		else:
			return {
				"timer": self.timer_id
			}

	@staticmethod
	def from_payload(name: str, payload):
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

class PostChangeAPIRequest(PostAPIRequest):
	def __init__(self, child_id: int, is_wet: bool, is_solid: bool):
		super().__init__(uri = "changes", payload = {
			"child": child_id,
			"wet": is_wet,
			"solid": is_solid
		})

	def serialize_to_json(self) -> object:
		return {
			"child_id": self.payload["child"],
			"is_wet": self.payload["wet"],
			"is_solid": self.payload["solid"]
		}

	@classmethod
	def deserialize_from_json(cls, json_object):
		return PostChangeAPIRequest(
			child_id = json_object["child_id"],
			is_wet = json_object["is_wet"],
			is_solid = json_object["is_dry"]
		)

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
		return PostPumpingAPIRequest(
			child_id = json_object["child_id"],
			amount = json_object["amount"]
		)

class PostTummyTimeAPIRequest(PostAPIRequest):
	def __init__(self, child_id: int, timer: Timer):
		super().__init__(uri = "tummy-times", payload = {
			"child": child_id
		}.update(timer.as_payload()))

		self.timer = timer

	def serialize_to_json(self) -> object:
		return {
			"child_id": self.payload["child"]
		}.update(self.timer.as_payload())

	@classmethod
	def deserialize_from_json(cls, json_object):
		timer = Timer.from_payload(name = "tummy-time", payload = json_object)
		return PostTummyTimeAPIRequest(
			child_id = json_object["child_id"],
			timer = timer
		)

class PostFeedingAPIRequest(PostAPIRequest):
	def __init__(self, child_id: int, food_type: str, method: str, timer: Timer):
		super().__init__(uri = "feedings", payload = {
			"child": child_id,
			"type": food_type,
			"method": method
		}.update(timer.as_payload()))

		self.timer = timer

	def serialize_to_json(self) -> object:
		return {
			"child_id": self.payload["child"],
			"food_type": self.payload["type"],
			"method": self.payload["timer"]
		}.update(self.timer.as_payload())

	@classmethod
	def deserialize_from_json(cls, json_object):
		timer = Timer.from_payload(name = "feeding", payload = json_object)
		return PostFeedingAPIRequest(
			child_id = json_object["child_id"],
			food_type = json_object["food_type"],
			method = json_object["method"],
			timer = timer
		)

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
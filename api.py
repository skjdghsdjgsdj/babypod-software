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
	from typing import Optional
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

class API:
	def __init__(self):
		self.requests = None
		self.child_id = None
		self.mac_id = None
	
		self.api_key = os.getenv("BABYBUDDY_AUTH_TOKEN")
		self.base_url = os.getenv("BABYBUDDY_BASE_URL")

	def connect(self) -> None:
		if self.requests is None:
			ssid = os.getenv("CIRCUITPY_WIFI_SSID_DEFER")
			password = os.getenv("CIRCUITPY_WIFI_PASSWORD_DEFER")
			channel = int(os.getenv("CIRCUITPY_WIFI_INITIAL_CHANNEL"))

			self.mac_id = binascii.hexlify(wifi.radio.mac_address).decode("ascii")
			print(f"This device's MAC ID is {self.mac_id}")

			wifi.radio.hostname = f"babypod-{self.mac_id}"
			print(f"This device's hostname is {wifi.radio.hostname}")

			print(f"Connecting to {ssid}...")
			wifi.radio.connect(ssid = ssid, password = password, channel = channel)
			print("Creating socket pool")
			pool = socketpool.SocketPool(wifi.radio)
			print("Creating requests instance")
			# noinspection PyTypeChecker
			self.requests = adafruit_requests.Session(pool, ssl.create_default_context())
			print("Connected!")
		
	def get_requests(self) -> adafruit_requests.Session:
		self.connect()
		return self.requests

	def post_change(self, is_wet: bool, is_solid: bool):
		payload = {
			"child": self.child_id,
			"wet": is_wet,
			"solid": is_solid
		}

		return self.post("changes", payload)

	def post_pumping(self, amount: float):
		payload = {
			"child": self.child_id,
			"amount": amount
		}

		return self.post("pumping", payload)

	def post_tummy_time(self, timer_id: int):
		return self.post("tummy-times", {
			"child": self.child_id,
			"timer": timer_id
		})

	def get_last_feeding(self) -> tuple[Optional[adafruit_datetime.datetime], Optional[str]]:
		feeding = self.get("feedings", {
			"child_id": self.child_id,
			"limit": 1
		})

		if feeding["count"] <= 0:
			return None, None

		return datetime.fromisoformat(feeding["results"][0]["start"]), feeding["results"][0]["method"]

	def get_timer(self, name: str) -> tuple[Optional[int], Optional[Duration]]:
		timers = self.get("timers", {
			"child_id": self.child_id,
			"name": self.build_timer_name(name)
		})

		max_id = None
		timer = None

		for timer_result in timers["results"]:
			if max_id is None or timer_result["id"] > max_id:
				max_id = timer_result["id"]
				timer = timer_result

		if timer is not None:
			return timer["id"], Duration.from_api(timer["duration"])
		else:
			return None, None

	def post_feeding(self, food_type: str, method :str, timer_id = None):
		if timer_id is None:
			timer_id = self.start_timer("feeding")

		return self.post("feedings", {
			"child": self.child_id,
			"type": food_type,
			"method": method,
			"timer": timer_id
		})

	def build_timer_name(self, base_name: str) -> str:
		return f"babypod-{self.mac_id}-{base_name}"

	def start_timer(self, name: str) -> int:
		response = self.post("timers", {
			"child_id": self.child_id,
			"name": self.build_timer_name(name)
		})
		return response["id"]

	def get_child_id(self) -> int:
		response = self.get("children")
		if response["count"] <= 0:
			raise ValueError("No children defined in Baby Buddy")
		else:
			if response["count"] > 1:
				print("More than one child defined in Baby Buddy; using first one")

			return response["results"][0]["id"]

	def stop_timer(self, timer_id: int) -> None:
		self.delete("timers", timer_id)

	@staticmethod
	def validate_response(response: adafruit_requests.Response) -> None:
		if response.status_code < 200 or response.status_code >= 300:
			raise Exception(f"Got HTTP {response.status_code} for request")

	def post(self, endpoint: str, payload_data):
		url = self.base_url + endpoint
		print(f"HTTP POST: {url}")
		print(f"Data: {payload_data}")
		response = self.get_requests().post(
			url,
			json = payload_data,
			headers = self.build_auth_headers()
		)
		self.validate_response(response)
		response_json = response.json()
		response.close()

		return response_json

	def delete(self, endpoint: str, endpoint_item_id: int) -> None:
		url = endpoint + "/" + str(endpoint_item_id) + "/"
		full_url = self.base_url + url

		print(f"HTTP DELETE: {full_url}")
		response = self.get_requests().delete(
			full_url,
			headers = self.build_auth_headers()
		)
		self.validate_response(response)
		response.close()

	# not escaped! urllib not available for this board
	@staticmethod
	def build_url_args(args) -> str:
		args_str = ""

		is_first = True
		for key, value in args.items():
			args_str += "?" if is_first else "&"
			is_first = False

			args_str += f"{key}={value}"

		return args_str

	def get(self, endpoint: str, args = None):
		url = endpoint
		if args is not None:
			url += self.build_url_args(args)

		full_url = self.base_url + url
		print(f"HTTP GET: {full_url}")
		response = self.get_requests().get(
			full_url,
			headers = self.build_auth_headers()
		)

		self.validate_response(response)

		json_response = response.json()
		response.close()
		return json_response

	def build_auth_headers(self):
		return {
			"Authorization": f"Token {self.api_key}"
		}

	@staticmethod
	def datetime_to_time_str(datetime_obj: adafruit_datetime.datetime) -> str:
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
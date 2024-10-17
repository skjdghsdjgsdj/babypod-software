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
	"""
	Connects to and disconnects from Wi-Fi. If CIRCUITPY_WIFI_TIMEOUT is defined in settings.toml, then Wi-Fi actions
	such as connecting and making requests have a timeout of that many seconds, or if not defined, 10 seconds. If the
	timeout is 0, then there is no timeout...which is bad, don't do that.
	"""

	requests: adafruit_requests.Session = None
	timeout: float

	@staticmethod
	def connect() -> adafruit_requests.Session:
		"""
		Connects to Wi-Fi using the information from settings.toml.

		:return: A session object for making requests, or an existing one if already connected.
		"""

		if ConnectionManager.requests is None:
			ConnectionManager.set_timeout()

			ssid = os.getenv("CIRCUITPY_WIFI_SSID_DEFER")
			password = os.getenv("CIRCUITPY_WIFI_PASSWORD_DEFER")

			channel = os.getenv("CIRCUITPY_WIFI_INITIAL_CHANNEL")
			channel = int(channel) if channel else 0

			ConnectionManager.mac_id = binascii.hexlify(wifi.radio.mac_address).decode("ascii")
			wifi.radio.enabled = True
			wifi.radio.hostname = f"babypod-{ConnectionManager.mac_id}"

			try:
				print(f"Connecting to {ssid}, timeout {ConnectionManager.timeout}...", end = "")
				wifi.radio.connect(ssid = ssid, password = password, channel = channel, timeout = ConnectionManager.timeout)
				ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
				pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
				ConnectionManager.requests = adafruit_requests.Session(pool, ssl_context)
				print(f"done, RSSI {wifi.radio.ap_info.rssi}, channel {wifi.radio.ap_info.channel}, tx power {wifi.radio.tx_power} dBm")
			except ConnectionError as e:
				print()
				raise e

		return ConnectionManager.requests

	@staticmethod
	def disconnect() -> None:
		"""
		Disables the Wi-Fi radio and disconnects.
		"""
		wifi.radio.enabled = False
		ConnectionManager.requests = None

	@staticmethod
	def set_timeout(timeout: Optional[int] = None) -> None:
		"""
		Sets the timeout for Wi-Fi connections and requests.

		:param timeout: timeout in seconds; None for default of 10 seconds or 0 for no timeout
		"""

		if timeout is None:
			timeout = os.getenv("CIRCUITPY_WIFI_TIMEOUT")

		ConnectionManager.timeout = 10 if (timeout is None or not timeout) else int(timeout)

class APIRequest:
	"""
	Base class for all API requests to Baby Buddy.
	"""

	API_KEY = os.getenv("BABYBUDDY_AUTH_TOKEN")
	BASE_URL = os.getenv("BABYBUDDY_BASE_URL")

	def __init__(self, uri: str, uri_args = None, payload = None):
		"""
		Creates a new API request to the given endpoint.

		:param uri: Baby Buddy API endpoint (URI after the trailing slash for .../api/)
		:param uri_args: Arguments to pass along with the URL as key/value pairs; will be escaped
		:param payload: payload for HTTP verbs that accept one, like POST
		"""

		self.uri = uri
		self.uri_args = uri_args
		self.payload = payload

	def serialize_to_json(self) -> object:
		"""
		Create a JSON object of this request to store offline to subsequently be deserialized for online playback.
		The base version of this method raises a RuntimeError and assumes this request can't be serialized for offline
		storage.

		:return: This APIRequest expressed as JSON for later deserialization
		"""

		raise RuntimeError(f"{str(type(self))} is not supported offline")

	@classmethod
	def deserialize_from_json(cls, json_object):
		"""
		Create a concrete APIRequest of the given offline serialized version of a request.
		The base version of this method raises a RuntimeError and assumes this request can't be serialized for offline
		storage.

		:return: A concrete APIRequest instance deserialized from the given JSON object
		"""

		raise RuntimeError(f"{str(cls)} is not supported offline")

	def merge_serialized_notes(self, json_object):
		"""
		If the given serialized request contains a "notes" attribute, merge it into the payload that goes to Baby
		Buddy.

		:param json_object:
		:return: self
		"""

		if "notes" in json_object and json_object["notes"] is not None:
			self.payload["notes"] = json_object["notes"]

		return self

	@staticmethod
	def escape_uri_value(value: str) -> str:
		"""
		Escapes a value so it's "safe" to use as a URL argument. Probably overly aggressive but CircuitPython doesn't
		seem to have native support for this.

		:param value: Value to escape
		:return: Escaped value
		"""
		safe_chars = re.compile(r"[A-Za-z0-9]")
		escaped = ""
		for char in str(value):
			escaped += f"%{ord(char):x}" if safe_chars.match(char) is None else char

		return escaped

	def build_full_url(self) -> str:
		"""
		Given the attributes of this APIRequest, creates a fully qualified URL that can be requested, including the
		Baby Buddy API base URL, endpoint URI, and all URI arguments.

		:return: Full URL to invoke on Baby Buddy API
		"""
		full_url = APIRequest.BASE_URL + self.uri + "/"
		if self.uri_args:
			is_first = True
			for key, value in self.uri_args.items():
				value = APIRequest.escape_uri_value(value)
				full_url += ("?" if is_first else "&") + f"{key}={value}"
				is_first = False

		return full_url

	def validate_response(self, response: adafruit_requests.Response) -> None:
		"""
		Raise an exception if the given response that isn't 2xx.

		:param response: Response to check
		"""

		if response.status_code < 200 or response.status_code >= 300:
			raise APIRequestFailedException(self, response.status_code)

	@staticmethod
	def merge(payload, timer = None, extra_notes: List[str] = None):
		"""
		Merges timer and any extra notes into the given payload that will end up getting set to Baby Buddy. Also merges
		in autogenerated notes about this device and, if available, the battery delta that happened as this timer ran.

		:param payload: JSON payload
		:param timer: Timer, if one is running and should be used as context for this payload
		:param extra_notes: User-specified extra notes to merge in
		:return: Payload with a "notes" attribute with relevant information
		"""

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
	def battery_delta_as_notes(timer: Optional) -> Optional[str]:
		"""
		Creates a string representation of how much battery was consumed during this timer, if available.

		:param timer: Timer that was running
		:return: String showing battery delta or None if data isn't available
		"""

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
		"""
		What verb this HTTP request is, like "GET." Base implementation raises NotImplementedError().

		:return: HTTP verb as a string
		"""

		raise NotImplementedError()

	def get_connection_method(self) -> Callable[..., adafruit_requests.Response]:
		"""
		Gets a method that can invoke this request on an adafruit_requests.Session object, like
		adafruit_requests.Session.get. Base implementation raises NotImplementedError().

		:return: Method that actually sends the request and gets a response back. 
		"""

		raise NotImplementedError()

	def invoke(self):
		"""
		Sends this request to Baby Buddy and returns its JSON response. Also feeds the microcontroller watchdog before
		sending the request and after getting and validating the response in case it happens to take a long time and
		the watchdog would time out while waiting.

		Raises an APIRequestFailedException if the response's status code is not 2xx. The underlying implementation of
		sending the request defined through get_connection_method() could raise other exceptions too.

		:return: JSON response from Baby Buddy, or None if the status code is 204 and no content is expected
		"""

		full_url = self.build_full_url()
		print(f"HTTP {self.get_verb()}: {full_url}, timeout {ConnectionManager.timeout}", end = "")
		if self.payload is not None:
			print(f"; payload: {self.payload}", end = "")
		print("...", end = "")

		microcontroller.watchdog.feed()

		start = time.monotonic()
		try:
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
		except Exception as e:
			print("failed!")
			raise e
		print(f"{response.status_code}, {end - start} sec")

		microcontroller.watchdog.feed()

		# HTTP 204 is No Content so there shouldn't be a response payload
		response_json = None if response.status_code is 204 else response.json()
		response.close()

		return response_json

class APIRequestFailedException(Exception):
	"""
	Raised when a request returns a response other than 2xx.
	"""

	def __init__(self, request: APIRequest, http_status_code: int = 0):
		"""
		:param request: Request that failed
		:param http_status_code: Response code that came back, or 0 if unknown
		"""
		self.request = request
		self.http_status_code = http_status_code

class GetAPIRequest(APIRequest):
	"""
	An HTTP GET request.
	"""

	def get_verb(self) -> str:
		"""
		Returns "GET"

		:return: "GET"
		"""
		return "GET"

	def get_connection_method(self) -> Callable[..., adafruit_requests.Response]:
		"""
		Returns a reference to adafruit_requests.Session.get.

		:return: a reference to adafruit_requests.Session.get
		"""
		return ConnectionManager.connect().get

class PostAPIRequest(APIRequest):
	"""
	An HTTP POST request.
	"""

	def get_verb(self) -> str:
		"""
		Returns "POST"

		:return: "POST"
		"""
		return "POST"

	def get_connection_method(self) -> Callable[..., adafruit_requests.Response]:
		"""
		Returns a reference to adafruit_requests.Session.post.

		:return: a reference to adafruit_requests.Session.post
		"""
		return ConnectionManager.connect().post

class DeleteAPIRequest(APIRequest):
	"""
	An HTTP DELETE request.
	"""

	def get_verb(self) -> str:
		"""
		Returns "DELETE"

		:return: "DELETE"
		"""
		return "DELETE"

	def get_connection_method(self) -> Callable[..., adafruit_requests.Response]:
		"""
		Returns a reference to adafruit_requests.Session.delete.

		:return: a reference to adafruit_requests.Session.delete
		"""
		return ConnectionManager.connect().delete

class TaggableLimitableGetAPIRequest(GetAPIRequest):
	"""
	A GET request that accepts filters based on optional tag names and response count limits.
	"""

	def __init__(self, uri: str, tag_name: Optional[str] = None, limit: Optional[int] = None, uri_args = None, payload = None):
		"""
		:param uri: Request URI as defined in APIRequest
		:param tag_name: Tag to filter by, or None to not
		:param limit: Result count limit, or None for no limit; must be >= 1 if specified
		:param uri_args: Request URI arguments as defined in APIRequest
		:param payload: Request payload as defined in APIRequest
		"""
		self.tag_name = tag_name
		self.limit = limit
		self.uri_args = uri_args or {}

		self.merge_limit()
		self.merge_tag()

		super().__init__(uri, self.uri_args, payload)

	def merge_limit(self) -> None:
		"""
		Merges the result count limit into uri_args.
		"""
		if self.limit is not None:
			if self.limit <= 0:
				raise ValueError(f"Limit must be >= 1, not {self.limit}")
			self.uri_args["limit"] = self.limit

	def merge_tag(self) -> None:
		"""
		Merges the filter tag into uri_args.
		"""
		if self.tag_name is not None:
			self.uri_args["tags"] = self.tag_name

class GetNotesAPIRequest(TaggableLimitableGetAPIRequest):
	"""
	Gets notes from Baby Buddy.
	"""
	def __init__(self, tag_name: Optional[str] = None, limit: Optional[int] = None):
		"""
		:param tag_name: Tag for the notes, or None for no tag filter
		:param limit: Number of notes to return or None for no limit; must be >= 1 if specified
		"""
		super().__init__(uri = "notes", tag_name = tag_name, limit = limit)

class ConsumeMOTDAPIRequest:
	"""
	Gets and then deletes, if one exists, the BabyPod message-of-the-day (MOTD) note.
	"""

	TAG_NAME = "BabyPod MOTD"

	def __init__(self, tag_name: str = TAG_NAME):
		"""
		:param tag_name: Tag name to filter by; defaults to ConsumeMOTDAPIRequest.TAG_NAME
		"""
		self.tag_name = tag_name

	def get_motd(self) -> Optional[str]:
		"""
		Gets and then deletes, if one exists, the BabyPod message-of-the-day (MOTD) note. If there are multiple matching
		notes, only acts on the first one found in an undefined order.

		:return: Contents of the MOTD note or None if there isn't one
		"""
		response = GetNotesAPIRequest(tag_name = self.tag_name, limit = 1).invoke()
		if len(response["results"]) <= 0:
			return None

		note_id = response["results"][0]["id"]
		motd = response["results"][0]["note"]

		DeleteNotesAPIRequest(note_id = note_id).invoke()

		return motd

class DeleteNotesAPIRequest(DeleteAPIRequest):
	"""
	Deletes a note from Baby Buddy.
	"""

	def __init__(self, note_id: int):
		"""
		:param note_id: ID of the note to delete
		"""
		super().__init__(uri = f"notes/{note_id}")

class Timer:
	"""
	A timer in Baby Buddy, either stored there or kept locally. A timer represents a discrete chunk of time with a
	start and end date/time.
	"""

	def __init__(self, name: str, offline: bool, rtc: ExternalRTC = None, battery: BatteryMonitor = None):
		"""
		:param name: Name of the timer. It may be modified once actually sent to Baby Buddy.
		:param offline: True if this timer is to be used offline, False if online.
		:param rtc: RTC instance to use for offline timers to track start/end dates/times, or None if no RTC is
		available
		:param battery: Battery monitor to track starting and ending battery consumption, or None if one isn't
		available
		"""

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
		"""
		Takes a duration in the form h:mm:ss and converts to a total number of seconds. If there are milliseconds, they
		are truncated.

		:param duration: Duration as a string
		:return: Duration as total number of seconds
		"""

		duration_parts = duration.split(":")

		hours = int(duration_parts[0])
		minutes = int(duration_parts[1])
		seconds = int(float(duration_parts[2]))

		return (hours * 60 * 60) + (minutes * 60) + seconds

	def start_or_resume(self) -> None:
		"""
		Starts this timer, or if one already exists with this one's name, resumes it.
		"""

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
		"""
		"Stops" this timer by deleting it from Baby Buddy. No effect for offline timers.
		"""

		if not self.offline:
			DeleteTimerAPIRequest(self.timer_id).invoke()

	def as_payload(self) -> dict[str, Any]:
		"""
		Expresses this timer as a partial JSON payload to be merged into API requests that expect a timer. For online
		requests, just the timer ID is provided. For offline timers where this payload will later be merged with a
		deserialized request and no timer was created in Baby Buddy itself, just start and end dates/times are provided.

		:return: A partial JSON payload that can be merged into API requests
		"""

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
		"""
		Creates a new Timer instance with the given information.

		:param name: Timer's name
		:param payload: Partial JSON payload of either the timer ID or the timer's start/end dates/times.

		:return: A timer instance from the given payload
		"""

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
		"""
		Expresses this timer as a string for debugging's sake. Don't use this value for parsing.

		:return: This timer as a string for debugging's sake
		"""

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
	"""
	Records a diaper change in Baby Buddy.
	"""

	def __init__(self, child_id: int, is_wet: bool, is_solid: bool):
		"""
		:param child_id: Child ID for the change
		:param is_wet: Peed?
		:param is_solid: Pooped?
		"""

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
	"""
	Records a breast pumping session.
	"""

	def __init__(self, child_id: int, timer: Timer, amount: float):
		"""
		:param child_id: Child ID to which to associate this pumping session
		:param timer: Timer for this session
		:param amount: Amount pumped; Baby Buddy is unitless, so this is too
		"""

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
	"""
	Records a sleep session, either a nap or overnight sleep. Baby Buddy is authoritative on which one it is; refer to
	its settings, but it can be overridden.
	"""

	def __init__(self, child_id: int, timer: Timer, nap: Optional[bool] = None):
		"""
		:param child_id: Child ID who slept
		:param timer: Sleep timer
		:param nap: True if this was a nap, False if it was overnight sleep, or None to let Baby Buddy be authoritative
		"""

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
	"""
	Saves tummy time to Baby Buddy.
	"""

	def __init__(self, child_id: int, timer: Timer):
		"""
		:param child_id: Child ID who did tummy time
		:param timer: Tummy time session
		"""

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

class FeedingAPIRequest(APIRequest):
	"""
	Base class for all feeding requests.

	* FOOD_TYPES: a list of valid food types: their names to show to the user (name), what the API expects and emits
	(type), methods to which the food type applies (methods), and a bitmask as a reference for toggling specific food
	types to show up in the feeding menu.
	* FEEDING_METHODS: a list of valid feeding methods: their names to show to the user (name) and what the API expects
	and emits (method)
	"""

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
			"name": "L. breast",
			"method": "left breast"
		},
		{
			"name": "R. breast",
			"method": "right breast"
		},
		{
			"name": "Bottle",
			"method": "bottle",
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

class PostFeedingAPIRequest(PostAPIRequest, FeedingAPIRequest):
	"""
	Saves a feeding to Baby Buddy.
	"""

	def __init__(self, child_id: int, food_type: str, method: str, timer: Timer):
		"""
		:param child_id: Child ID who fed
		:param food_type: One of: "breast milk", "formula", "fortified breast milk", "solid food"
		:param method: One of: "bottle", "left breast", "right breast", "both breasts", "parent fed", "self fed"
		:param timer: Feeding session timer
		"""

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

class GetLastFeedingAPIRequest(GetAPIRequest, FeedingAPIRequest):
	"""
	Gets the most recent feeding from Baby Buddy.
	"""

	def __init__(self, child_id: int):
		"""
		:param child_id: Get the feeding for this child ID
		"""

		super().__init__(uri = "feedings", uri_args = {
			"limit": 1,
			"child_id": child_id
		})

	def get_last_feeding(self) -> Optional[tuple[adafruit_datetime.datetime, str]]:
		"""
		Gets the most recent feeding, or None if there isn't one.

		:return: Most recent feeding (when and what method) or None if there isn't one
		"""

		response = self.invoke()

		if response["count"] <= 0:
			return None

		return Util.to_datetime(response["results"][0]["start"]), response["results"][0]["method"]

class GetFirstChildIDAPIRequest(GetAPIRequest):
	"""
	Gets the first child ID from Baby Buddy, although what is "first" is undefined. This exists just to be sure you're
	sending valid child IDs to Baby Buddy instead of just guessing "1."
	"""

	def __init__(self):
		super().__init__("children")

	def get_first_child_id(self) -> int:
		"""
		Gets the first child ID from Baby Buddy, although what is "first" is undefined. If no children are defined,
		raises a ValueError.

		:return: The first child ID from Baby Buddy, although what is "first" is undefined.
		"""

		response = self.invoke()
		if response["count"] <= 0:
			raise ValueError("No children defined in Baby Buddy")
		else:
			if response["count"] > 1:
				print("More than one child defined in Baby Buddy; using first one")

			return response["results"][0]["id"]

class TimerAPIRequest:
	"""
	Abstract base class for Baby Buddy timer-related requests.
	"""

	@staticmethod
	def get_timer_basename() -> str:
		"""
		Gets the prefix that gets added to all timer names for Baby Buddy so BabyPod timers don't step on others.

		:return: "babypod-" by default, but don't rely on that. Call this method instead.
		"""
		return "babypod-"

	@staticmethod
	def get_timer_name(name: str):
		"""
		Given a timer name, "normalizes" it to include any applicable prefix. The net result is a timer name that
		actually applies to API requests.

		:param name: Timer name without any prefix
		:return: Timer name with prefix suitable for API requests
		"""
		return TimerAPIRequest.get_timer_basename() + name

class CreateTimerAPIRequest(PostAPIRequest, TimerAPIRequest):
	"""
	Creates a new timer in Baby Buddy.
	"""

	def __init__(self, name: str):
		"""
		:param name: Timer name, like "feeding"
		"""
		super().__init__(uri = "timers", payload = {
			"name": self.get_timer_name(name)
		})

class GetNamedTimerAPIRequest(GetAPIRequest, TimerAPIRequest):
	"""
	Gets timers (data, not Timer instances) that match a given name.
	"""

	def __init__(self, name: str):
		"""
		:param name: Timer name, like "feeding"
		"""

		super().__init__(uri = "timers", uri_args = {
			"name": self.get_timer_name(name)
		})

class GetAllTimersAPIRequest(TaggableLimitableGetAPIRequest, TimerAPIRequest):
	"""
	Gets concrete timer instances from Baby Buddy that match given information.
	"""

	def __init__(self, tag_name: Optional[str] = None, limit: Optional[int] = None):
		"""
		:param tag_name: tag_name like in TaggableLimitableGetAPIRequest
		:param limit: limit like in TaggableLimitableGetAPIRequest
		"""

		super().__init__(uri = "timers", tag_name = tag_name, limit = limit)

	def get_active_timers(self) -> Generator[Timer]:
		"""
		Yields Timer instances that match the given request.

		:return: Timer instances that match the given request
		"""

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
	"""
	Deletes a running timer from Baby Buddy, which effectively stops it without creating any new data like feedings,
	etc.
	"""

	def __init__(self, timer_id: int):
		"""
		:param timer_id: ID of the timer to stop
		"""

		super().__init__(uri = f"timers/{timer_id}")
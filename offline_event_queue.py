import json
import os

from external_rtc import ExternalRTC

# noinspection PyBroadException
try:
	from typing import List
except:
	pass

from api import APIRequest
from sdcard import SDCard

class OfflineEventQueue:
	"""
	A queue of events that were generated while the BabyPod was offline and will be replayed once back online.

	The queue is stored as individual JSON files for each event named after the date/time they occurred. As the queue
	replays, each successful replay of an event deletes that event from the queue.
	"""

	@staticmethod
	def from_sdcard(sdcard: SDCard, rtc: ExternalRTC):
		"""
		Gets an instance of the event queue given an SD card that stores it and an RTC used for timing data.

		:param sdcard: SD card for storing this queue
		:param rtc: RTC for timing data
		:return: OfflineEventQueue instance
		"""

		return OfflineEventQueue(sdcard.get_absolute_path("queue"), rtc)

	def __init__(self, json_path: str, rtc: ExternalRTC):
		"""
		Starts a new queue or resumes an existing one at the given directory containing JSON files.

		Use get_instance() to respect the use of the SD card vs. guessing at paths.

		:param json_path: Directory that contains, or will contain, the JSON queue
		:param rtc: RTC for timing data
		"""
		self.json_path = json_path
		self.rtc = rtc

		try:
			os.stat(self.json_path)
		except OSError:
			print(f"Creating new offline event queue at {self.json_path}")
			os.mkdir(self.json_path)

	def get_json_files(self) -> List[str]:
		"""
		Gets a list of all JSON files in this queue sorted by their origination date in ascending order. Use this along
		with replay() on each file returned to replay the queue in order.

		:return: All JSON filenames in the queue (which could be an empty list)
		"""

		files = os.listdir(self.json_path)
		files.sort()
		return list(map(lambda filename: f"{self.json_path}/{filename}", files))

	def build_json_filename(self) -> str:
		"""
		Creates a filename for storing a JSON file based on the current date/time. In the unlikely event of a conflict,
		then an increasing number is added to the end of the file. In the ridiculously unlikely event of a conflict
		after many attempts to avoid one, raises a ValueError. Something would have gone horribly wrong for that to
		happen.

		:return: JSON filename for an event, like /sd/queue/20241015224103-0001.json
		"""

		now = self.rtc.now()
		formatted_now = f"{now.year:04}{now.month:02}{now.day:02}{now.hour:02}{now.minute:02}{now.second:02}"

		i = 0
		while i < 1000:
			filename = self.json_path + f"/{formatted_now}-{i:04}.json"
			try:
				os.stat(filename)
				# if stat() passes, then the file already exists; try again with next index
				i += 1
			except OSError: # stat() failed, which means file doesn't exist (hopefully) and is a good candidate
				return filename

		raise ValueError("No candidate files available, somehow")

	def add(self, request: APIRequest) -> None:
		"""
		Adds an event to the queue.

		:param request: Request to serialize to replay layer
		"""

		payload = {
			"type": type(request).__name__,
			"payload": request.serialize_to_json()
		}

		filename = self.build_json_filename()
		print(f"Serializing {type(request)} to {filename}")

		with open(filename, "w") as file:
			json.dump(payload, file)
			file.flush()

	# TODO making this dynamic with reflection would be nice but I don't think CircuitPython can
	def init_api_request(self, class_name: str, payload) -> APIRequest:
		"""
		Creates a concrete APIRequest instance given the JSON payload of an event in the queue
		:param class_name: Class name of the APIRequest concrete type, like "PostFeedingAPIRequest"
		:param payload: JSON payload of an event in the queue
		:return: Concrete APIRequest instance that can be invoke()d
		"""

		if class_name == "PostFeedingAPIRequest":
			from api import PostFeedingAPIRequest
			return PostFeedingAPIRequest.deserialize_from_json(payload)
		elif class_name == "PostChangeAPIRequest":
			from api import PostChangeAPIRequest
			return PostChangeAPIRequest.deserialize_from_json(payload)
		elif class_name == "PostPumpingAPIRequest":
			from api import PostPumpingAPIRequest
			return PostPumpingAPIRequest.deserialize_from_json(payload)
		elif class_name == "PostTummyTimeAPIRequest":
			from api import PostTummyTimeAPIRequest
			return PostTummyTimeAPIRequest.deserialize_from_json(payload)
		elif class_name == "PostSleepAPIRequest":
			from api import PostSleepAPIRequest
			return PostSleepAPIRequest.deserialize_from_json(payload)
		else:
			raise NotImplementedError(f"Don't know how to deserialize a {class_name}")

	def replay(self, full_json_path: str, delete_on_success: bool = True) -> None:
		"""
		Replays a single event from the queue by deserializing it back to a concrete APIRequest and calling invoke()
		on it. If invoke() succeeds, even if it takes a few attempts, and if delete_on_success is True, then the JSON
		file is deleted to avoid duplicate playback.

		:param full_json_path: Path to the JSON file containing the serialized APIRequest to replay
		:param delete_on_success: True to delete the file if it is successfully replayed, False to keep it
		"""

		with open(full_json_path, "r") as file:
			item = json.load(file)

		request = self.init_api_request(item["type"], item["payload"])
		print(f"Replaying {request}: {full_json_path}")

		retry_count = 0
		while retry_count <= 5:
			try:
				retry_count += 1
				request.invoke()
				print(f"Replay of {request} successful")
				if delete_on_success:
					print(f"Deleting {full_json_path}")
					os.unlink(full_json_path)
				return
			except Exception as e:
				print(f"{e} while trying to replay {request}; retrying (count = {retry_count})")
				if retry_count > 5:
					raise e
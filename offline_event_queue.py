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
	@staticmethod
	def from_sdcard(sdcard: SDCard, rtc: ExternalRTC):
		return OfflineEventQueue(sdcard.get_absolute_path("queue"), rtc)

	def __init__(self, json_path: str, rtc: ExternalRTC):
		self.json_path = json_path
		self.rtc = rtc

		try:
			os.stat(self.json_path)
			print(f"Resuming offline event queue at {self.json_path}")
		except OSError:
			print(f"No offline event queue exists yet at {self.json_path}, creating one")
			os.mkdir(self.json_path)

	def get_json_files(self) -> List[str]:
		files = os.listdir(self.json_path)
		files.sort()
		return files

	def build_json_filename(self) -> str:
		now = self.rtc.now()
		formatted_now = f"{now.year:04}{now.month:02}{now.day:02}{now.hour:02}{now.second:02}"

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
		else:
			raise NotImplementedError(f"Don't know how to deserialize a {class_name}")

	def replay(self, full_json_path: str) -> None:
		with open(full_json_path, "r") as file:
			item = json.load(file)

		request = self.init_api_request(item["type"], item["payload"])
		print(f"Replaying {request}: {full_json_path}")
		retry_count = 0
		try:
			retry_count += 1
			request.invoke()
		except Exception as e:
			if retry_count > 5:
				print(f"{e} while trying to replay {request}, hard failing (retry count exceeded)")
				raise e

			print(f"{e} while trying to replay {request}; retrying (count = {retry_count})")

	def replay_all(self, delete_on_success = True) -> None:
		files = self.get_json_files()

		print(f"Replaying offline-serialized {len(files)} requests")
		for filename in files:
			full_json_path = f"{self.json_path}/{filename}"
			self.replay(full_json_path)

			if delete_on_success:
				os.unlink(full_json_path)
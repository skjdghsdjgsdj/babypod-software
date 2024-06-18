import json
import os

# noinspection PyBroadException
try:
	from typing import List
except:
	pass

from api import APIRequest
from sdcard import SDCard

class OfflineEventQueue:
	@staticmethod
	def from_sdcard(sdcard: SDCard):
		return OfflineEventQueue(sdcard.get_absolute_path("offline_queue.json"))

	def __init__(self, json_path: str):
		self.json_path = json_path
		#print(f"Loading offline event queue from {self.json_path}")

		self.queue: List[APIRequest] = []

		try:
			os.stat(self.json_path)
			print(f"Resuming offline event queue at {self.json_path}")
			create_new_index = False
		except OSError:
			print(f"No offline event queue exists yet at {self.json_path}")
			create_new_index = True

		self.index_fp = open(self.json_path, mode = "a+")

		if create_new_index:
			print("Creating new offline event index")
			self.reset_index()
		else:
			try:
				self.load_index()
			except ValueError as e:
				print(f"{e} when loading index; resetting")
				self.reset_index()

	def __del__(self):
		self.index_fp.close()

	def reset_index(self):
		print("Resetting offline event index")
		self.index_fp.seek(0)
		self.index_fp.write(json.dumps([]))
		self.index_fp.flush()

	def load_index(self):
		self.index_fp.seek(0)
		try:
			index = json.load(self.index_fp)
		except ValueError as e:
			print(f"Failed parsing {self.json_path}:")
			self.index_fp.seek(0)
			json_str = self.index_fp.read()
			if len(json_str) == 0:
				print("JSON is empty string")
			else:
				print(json_str)
			raise e

		print(f"Loaded offline event index with {len(index)} items")
		return index

	def append_to_index(self, payload):
		index = self.load_index()
		index.append(payload)
		print(f"Offline event queue now has {len(index)} items")
		serialized = json.dumps(index)
		print(serialized)

		self.index_fp.seek(0)
		self.index_fp.write(serialized)
		self.index_fp.flush()

	def add(self, request: APIRequest):
		print(f"Appending {type(request)} to index")
		payload = {
			"type": type(request).__name__,
			"payload": request.serialize_to_json()
		}
		self.append_to_index(payload)

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

	def replay_all(self, empty_on_success = True):
		index = self.load_index()
		print(f"Replaying index ({len(index)} items)")
		for item in index:
			request = self.init_api_request(item["type"], item["payload"])
			print(f"Replaying {request}")
			retry_count = 0
			try:
				retry_count += 1
				request.invoke()
			except Exception as e:
				if retry_count > 5:
					print(f"{e} while trying to replay {request}, hard failing (retry count exceeded)")
					raise e

				print(f"{e} while trying to replay {request}; retrying (count = {retry_count})")

		if empty_on_success:
			self.reset_index()

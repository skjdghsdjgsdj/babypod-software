"""
Stores values that are too big or complex for NVRAM that persist across reboots and power cycles. Not to be confused
with the offline event queue which is a list of individual events to replay later.
"""

import json
import os
from adafruit_datetime import datetime

from api import Timer
from sdcard import SDCard

# noinspection PyBroadException
try:
    from typing import Optional
except:
    pass

class OfflineState:
    """
    Stores some state information in a JSON file for offline use. This is separate from the OfflineEventQueue which
    stores a list of serialized APIRequest instances to be replayed in sequence once back online.

    Use get_instance() to get a fully initialized instance, not the constructor.
    """

    from_datetime = lambda value: datetime.fromisoformat(value)
    to_datetime = lambda value: value.isoformat()
    passthrough = lambda value: value

    state_definition = {
        "last_feeding": (from_datetime, to_datetime),
        "last_feeding_method": (passthrough, passthrough),
        "last_rtc_set": (from_datetime, to_datetime),
        "rtc_utc_offset": (lambda value: float(value), passthrough),
        "last_motd_check": (from_datetime, to_datetime),
        "active_timer_name": (passthrough, passthrough),
        "active_timer": (
            lambda payload: Timer.from_payload(name = None, payload = payload),
            lambda timer: timer.as_payload()
        )
    }

    def __init__(self, sdcard: SDCard):
        """
        :param sdcard: Where to save the state
        """
        self.sdcard = sdcard

        self.last_feeding: Optional[datetime] = None
        self.last_feeding_method: Optional[str] = None
        self.last_rtc_set: Optional[datetime] = None
        self.rtc_utc_offset: Optional[float] = None
        self.last_motd_check: Optional[datetime] = None
        self.active_timer_name: Optional[str] = None
        self.active_timer: Optional[Timer] = None

    @staticmethod
    def load_state():
        pass

    @staticmethod
    def from_sdcard(sdcard: SDCard):
        """
        Gets offline state as stored on the SD card. If one doesn't exist on the SD card, it is created.

        :param sdcard: Where to save the state
        :return: Fully initialized instance of OfflineState
        """

        state = OfflineState(sdcard)
        path = sdcard.get_absolute_path("state.json")
        exists = False
        try:
            os.stat(path)
            exists = True
        except OSError:
            pass

        if exists:
            with open(path, "r") as file:
                print(f"Loading offline state from {path}...", end = "")
                serialized = json.load(file)
                print(serialized)

            for key, metadata in OfflineState.state_definition.items():
                if key in serialized and serialized[key] is not None:
                    deserializer, _ = metadata
                    value = serialized[key]
                    setattr(state, key, deserializer(value))

            if state.active_timer is not None:
                state.active_timer.name = state.active_timer_name
        else:
            print("No existing serialized state")
            state.to_sdcard()

        return state

    def to_sdcard(self) -> None:
        """
        Stores offline state back to the SD card.
        """

        serialized = {}
        for key, metadata in self.state_definition.items():
            _, serializer = metadata
            value = getattr(self, key)
            serialized[key] = None if value is None else serializer(getattr(self, key))

        print(f"Saving offline state: {serialized}")

        with open(self.sdcard.get_absolute_path("state.json"), "w") as file:
            # noinspection PyTypeChecker
            json.dump(serialized, file)
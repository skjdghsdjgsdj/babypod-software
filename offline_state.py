import json
import os
from adafruit_datetime import datetime

from sdcard import SDCard
from util import Util

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

    def __init__(self, sdcard: SDCard):
        """
        :param sdcard: Where to save the state
        """
        self.last_feeding: Optional[datetime] = None
        self.last_feeding_method: Optional[str] = None
        self.last_rtc_set: Optional[datetime] = None
        self.rtc_utc_offset: Optional[float] = None
        self.last_motd_check: Optional[datetime] = None
        self.sdcard = sdcard

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
            print("Reloading serialized state")
            with open(path, "r") as file:
                print(f"Loading offline state from {path}:")
                serialized = json.load(file)
                print(serialized)

            if "last_feeding" in serialized and serialized["last_feeding"] is not None:
                state.last_feeding = Util.to_datetime(serialized["last_feeding"])

            if "last_feeding_method" in serialized:
                state.last_feeding_method = serialized["last_feeding_method"]

            if "last_rtc_set" in serialized and serialized["last_rtc_set"] is not None:
                state.last_rtc_set = Util.to_datetime(serialized["last_rtc_set"])

            if "last_motd_check" in serialized and serialized["last_motd_check"] is not None:
                state.last_motd_check = Util.to_datetime(serialized["last_motd_check"])

            if "rtc_utc_offset" in serialized and serialized["rtc_utc_offset"] is not None:
                state.rtc_utc_offset = float(serialized["rtc_utc_offset"])
        else:
            print("No existing serialized state")
            state.to_sdcard()

        return state

    def to_sdcard(self) -> None:
        """
        Stores offline state back to the SD card.
        """

        serialized = {
            "last_feeding": self.last_feeding.isoformat() if self.last_feeding else None,
            "last_feeding_method": self.last_feeding_method,
            "last_rtc_set": self.last_rtc_set.isoformat() if self.last_rtc_set else None,
            "last_motd_check": self.last_motd_check.isoformat() if self.last_motd_check else None,
            "rtc_utc_offset": self.rtc_utc_offset,
        }

        print("Persisting serialized state to SD card:")
        print(serialized)

        with open(self.sdcard.get_absolute_path("state.json"), "w") as file:
            json.dump(serialized, file)
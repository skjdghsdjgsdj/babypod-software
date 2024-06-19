import json
import os
from adafruit_datetime import datetime
from sdcard import SDCard

# noinspection PyBroadException
try:
    from typing import Optional
except:
    pass

class OfflineState:
    def __init__(self, sdcard: SDCard):
        self.last_feeding: Optional[datetime] = None
        self.last_feeding_method: Optional[str] = None
        self.last_rtc_set: Optional[datetime] = None
        self.rtc_utc_offset: Optional[float] = None
        self.sdcard = sdcard

    @staticmethod
    def from_sdcard(sdcard: SDCard):
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

            if "last_feeding" in serialized and serialized["last_feeding"]:
                state.last_feeding = datetime.fromisoformat(serialized["last_feeding"])

            if "last_feeding_method" in serialized:
                state.last_feeding_method = serialized["last_feeding_method"]

            if "last_rtc_set" in serialized and serialized["last_rtc_set"]:
                state.last_rtc_set = datetime.fromisoformat(serialized["last_rtc_set"])

            if "rtc_utc_offset" in serialized and serialized["rtc_utc_offset"]:
                state.rtc_utc_offset = float(serialized["rtc_utc_offset"])
        else:
            print("No existing serialized state")
            state.to_sdcard()

        return state

    def to_sdcard(self) -> None:
        serialized = {
            "last_feeding": self.last_feeding.isoformat() if self.last_feeding else None,
            "last_feeding_method": self.last_feeding_method,
            "last_rtc_set": self.last_rtc_set.isoformat() if self.last_rtc_set else None,
            "rtc_utc_offset": self.rtc_utc_offset,
        }

        print("Persisting serialized state to SD card:")
        print(serialized)

        with open(self.sdcard.get_absolute_path("state.json"), "w") as file:
            json.dump(serialized, file)
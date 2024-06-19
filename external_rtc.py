from time import struct_time

import adafruit_datetime
import adafruit_requests
import os
import adafruit_pcf8523.pcf8523
from adafruit_datetime import datetime
from busio import I2C

from offline_state import OfflineState

# noinspection PyBroadException
try:
    from typing import Optional
except:
    pass

class ExternalRTC:
    def __init__(self, i2c: I2C):
        self.device = adafruit_pcf8523.pcf8523.PCF8523(i2c)
        self.offline_state: Optional[OfflineState] = None

    def sync(self, requests: adafruit_requests.Session):
        if not self.offline_state:
            raise RuntimeError("Must set offline_state before syncing")

        print("Updating RTC from Adafruit IO")

        username = os.getenv("ADAFRUIT_AIO_USERNAME")
        api_key = os.getenv("ADAFRUIT_AIO_KEY")

        if not username or not api_key:
            raise ValueError("adafruit.io username or key not defined in settings.toml")

        response = requests.get(f"https://io.adafruit.com/api/v2/{username}/integrations/time/clock?x-aio-key={api_key}")
        now = datetime.fromisoformat(response.text)
        self.offline_state.rtc_utc_offset = (now.utcoffset().seconds / 60 / 60) - 24

        print(f"Setting RTC to {now}")
        self.device.datetime = struct_time((
            now.year,
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second,
            now.weekday(),
            -1,
            -1
        ))

        self.offline_state.last_rtc_set = now
        self.offline_state.to_sdcard()

        print(f"RTC now set to: {self.device.datetime} UTC offset {self.offline_state.rtc_utc_offset}")

    def now(self) -> Optional[datetime]:
        if not self.offline_state:
            raise RuntimeError("Must set offline_state before getting time")

        now = self.device.datetime
        if now.tm_year < 2024 or now.tm_year > 2050:
            return None

        if self.offline_state.rtc_utc_offset is None:
            return None

        # noinspection PyUnresolvedReferences
        tz = adafruit_datetime.timezone.utc
        tz._offset = adafruit_datetime.timedelta(seconds = int(self.offline_state.rtc_utc_offset * 60 * 60))

        return datetime(
            year = now.tm_year,
            month = now.tm_mon,
            day = now.tm_mday,
            hour = now.tm_hour,
            minute = now.tm_min,
            second = now.tm_sec
        ).replace(tzinfo = tz)

    @staticmethod
    def exists(i2c: I2C) -> bool:
        while not i2c.try_lock():
            pass
        i2c_address_list = i2c.scan()
        i2c.unlock()

        return 0x68 in i2c_address_list
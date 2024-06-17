from backlight import Backlight
from battery_monitor import BatteryMonitor
from external_rtc import ExternalRTC
from lcd import LCD
from piezo import Piezo
from sdcard import SDCard
from user_input import UserInput

class Devices:
    def __init__(self,
                 user_input: UserInput,
                 piezo: Piezo,
                 lcd: LCD,
                 backlight: Backlight,
                 battery_monitor: BatteryMonitor,
                 sdcard: SDCard,
                 rtc: ExternalRTC):
        self.user_input = user_input
        self.piezo = piezo
        self.lcd = lcd
        self.backlight = backlight
        self.battery_monitor = battery_monitor
        self.sdcard = sdcard
        self.rtc = rtc
from battery_monitor import BatteryMonitor
from external_rtc import ExternalRTC
from lcd import LCD
from piezo import Piezo
from power_control import PowerControl
from sdcard import SDCard
from user_input import RotaryEncoder

# noinspection PyBroadException
try:
    from typing import Optional
except:
    pass
    # ignore, just for IDE's sake, not supported on board

class Devices:
    def __init__(self,
                 rotary_encoder: RotaryEncoder,
                 piezo: Piezo,
                 lcd: LCD,
                 battery_monitor: BatteryMonitor,
                 sdcard: Optional[SDCard],
                 rtc: Optional[ExternalRTC],
                 power_control: PowerControl):
        self.rotary_encoder = rotary_encoder
        self.piezo = piezo
        self.lcd = lcd
        self.battery_monitor = battery_monitor
        self.sdcard = sdcard
        self.rtc = rtc
        self.power_control = power_control
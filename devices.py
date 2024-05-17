from backlight import Backlight
from battery_monitor import BatteryMonitor
from lcd import LCD
from piezo import Piezo
from rotary_encoder import RotaryEncoder

class Devices:
    def __init__(self,
        rotary_encoder: RotaryEncoder,
        piezo: Piezo,
        lcd: LCD,
        backlight: Backlight,
        battery_monitor: BatteryMonitor
    ):
        self.rotary_encoder = rotary_encoder
        self.piezo = piezo
        self.lcd = lcd
        self.backlight = backlight
        self.battery_monitor = battery_monitor
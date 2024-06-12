from backlight import Backlight
from battery_monitor import BatteryMonitor
from lcd import LCD
from piezo import Piezo
from user_input import UserInput

class Devices:
    def __init__(self,
                 user_input: UserInput,
                 piezo: Piezo,
                 lcd: LCD,
                 backlight: Backlight,
                 battery_monitor: BatteryMonitor
                 ):
        self.user_input = user_input
        self.piezo = piezo
        self.lcd = lcd
        self.backlight = backlight
        self.battery_monitor = battery_monitor
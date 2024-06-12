import board
import supervisor

supervisor.runtime.autoreload = False

from busio import I2C
from lcd import LCD

# noinspection PyUnresolvedReferences
i2c = I2C(sda = board.SDA, scl = board.SCL, frequency = 400000)

lcd = LCD.get_instance(i2c)
lcd.write("Starting up...", (0, 0))

try:
	from version import *
except ImportError:
	# don't care
	pass

if "BABYPOD_VERSION" in globals():
	# noinspection PyUnresolvedReferences
	lcd.write_bottom_right_aligned(BABYPOD_VERSION)

from piezo import Piezo
piezo = Piezo()
piezo.tone("startup")

from backlight import Backlight
backlight = Backlight.get_instance()

from digitalio import DigitalInOut, Direction
from battery_monitor import BatteryMonitor
from user_input import UserInput
from flow import Flow

# turn off Neopixel
# noinspection PyUnresolvedReferences
neopixel = DigitalInOut(board.NEOPIXEL)
neopixel.direction = Direction.OUTPUT
neopixel.value = False

battery_monitor = BatteryMonitor.get_instance(i2c)
user_input = UserInput.get_instance(i2c)

from devices import Devices
devices = Devices(
	user_input = user_input,
	piezo = piezo,
	lcd = lcd,
	backlight = backlight,
	battery_monitor = battery_monitor
)

Flow(devices = devices).start()

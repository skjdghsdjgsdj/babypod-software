import supervisor
import board

try:
	from version import *
except ImportError:
	# don't care
	pass

supervisor.runtime.autoreload = False

from busio import I2C
from lcd import LCD

# noinspection PyUnresolvedReferences
i2c = I2C(sda = board.SDA, scl = board.SCL, frequency = 400000)

lcd = LCD(i2c)
lcd.write("Starting up...")

if "BABYPOD_VERSION" in globals():
	lcd.write_bottom_right_aligned(BABYPOD_VERSION)

from nvram import NVRAMValues

from piezo import Piezo
piezo = Piezo()
piezo.tone("startup")

from backlight import Backlight
backlight = Backlight()

from digitalio import DigitalInOut, Direction
from battery_monitor import BatteryMonitor
from rotary_encoder import RotaryEncoder
from flow import Flow

# turn off Neopixel
# noinspection PyUnresolvedReferences
neopixel = DigitalInOut(board.NEOPIXEL)
neopixel.direction = Direction.OUTPUT
neopixel.value = False

battery_monitor = BatteryMonitor.get_instance(i2c)
rotary_encoder = RotaryEncoder(i2c)

from devices import Devices
devices = Devices(
	rotary_encoder = rotary_encoder,
	piezo = piezo,
	lcd = lcd,
	backlight = backlight,
	battery_monitor = battery_monitor
)

Flow(
	child_id = NVRAMValues.CHILD_ID.get(),
	devices = devices
).start()

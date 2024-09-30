import supervisor
supervisor.runtime.autoreload = False

from busio import I2C
import board
i2c = I2C(sda = board.SDA, scl = board.SCL, frequency = 400000)

from piezo import Piezo
piezo = Piezo()
piezo.tone("startup")

from lcd import LCD, BacklightColors
lcd = LCD.get_instance(i2c)
lcd.backlight.set_color(BacklightColors.DEFAULT)
lcd.write("Starting up...", (0, 0))

from digitalio import DigitalInOut, Direction

# turn off Neopixel
neopixel = DigitalInOut(board.NEOPIXEL)
neopixel.direction = Direction.OUTPUT
neopixel.value = False

from user_input import RotaryEncoder
rotary_encoder = RotaryEncoder(i2c)

from power_control import PowerControl
power_control = PowerControl(piezo, lcd, rotary_encoder)

from battery_monitor import BatteryMonitor
battery_monitor = BatteryMonitor.get_instance(i2c)

sdcard = None
rtc = None
from external_rtc import ExternalRTC
if ExternalRTC.exists(i2c):
	from sdcard import SDCard
	try:
		sdcard = SDCard()
	except Exception as e:
		print(f"Error while trying to mount SD card, assuming hardware is missing: {e}")
		from nvram import NVRAMValues
		NVRAMValues.OFFLINE.write(False)

	rtc = ExternalRTC(i2c)

from devices import Devices
devices = Devices(
	rotary_encoder = rotary_encoder,
	piezo = piezo,
	lcd = lcd,
	battery_monitor = battery_monitor,
	sdcard = sdcard,
	rtc = rtc,
	power_control = power_control
)

from flow import Flow
Flow(devices = devices).start()

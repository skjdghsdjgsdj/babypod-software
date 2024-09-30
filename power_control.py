import time

import alarm
import board
import microcontroller
from adafruit_seesaw import seesaw

from lcd import LCD
from piezo import Piezo
from user_input import RotaryEncoder
import wifi

class PowerControl:
	def __init__(self, piezo: Piezo, lcd: LCD, encoder: RotaryEncoder, interrupt_pin: microcontroller.Pin = board.D11, seesaw_pin: int = 1):
		self.encoder = encoder
		self.lcd = lcd
		self.interrupt_pin = interrupt_pin
		self.seesaw_pin = seesaw_pin
		self.spi = board.SPI()
		self.piezo = piezo

	def init_center_button_interrupt(self) -> None:
		mask = 1 << self.seesaw_pin

		self.encoder.seesaw.pin_mode(self.seesaw_pin, seesaw.Seesaw.INPUT_PULLUP)
		self.encoder.seesaw.set_GPIO_interrupts(mask, True)

		print("Enabled interrupt for center button")

	def lcd_shutdown(self) -> None:
		self.lcd.backlight.off()
		self.lcd.clear()
		self.lcd.write("Press center button", (0, 1))
		self.lcd.write("to turn on BabyPod.", (0, 2))

	def sd_shutdown(self) -> None:
		self.spi.deinit()
		print("SPI bus disabled")

	def enter_deep_sleep(self) -> None:
		from alarm.pin import PinAlarm
		pin_alarm = PinAlarm(self.interrupt_pin, value = False, pull = False)

		self.encoder.seesaw.digital_read_bulk(1 << self.seesaw_pin)
		print("Entering deep sleep")
		alarm.exit_and_deep_sleep_until_alarms(pin_alarm)

		raise RuntimeError("Deep sleep failed")

	def shutdown(self) -> None:
		self.piezo.tone("shutdown")
		self.sd_shutdown()
		self.lcd_shutdown()
		self.init_center_button_interrupt()

		time.sleep(3) # give the user time to let go of the button, or it'll just wake immediately
		self.enter_deep_sleep()
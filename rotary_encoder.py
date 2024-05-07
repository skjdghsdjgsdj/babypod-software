from time import monotonic, sleep
#from adafruit_seesaw import seesaw, rotaryio, digitalio as seesaw_digitalio
from adafruit_seesaw import rotaryio, seesaw
from adafruit_seesaw.seesaw import Seesaw
import digitalio
from adafruit_seesaw.digitalio import DigitalIO

class RotaryEncoder:
	def __init__(self, i2c):
		# it's physically rotated 90 CW so adjust accordingly
		self.last_position = None
		self.buttons = {}
		self.last_button_down = None
		self.encoder = None
		self.i2c = i2c

	def init_rotary_encoder(self):
		seesaw_controller = seesaw.Seesaw(self.i2c, addr = 0x49)

		product_id = (seesaw_controller.get_version() >> 16) & 0xFFFF
		assert(product_id == 5740)

		buttons = [
			RotaryEncoder.SELECT,
			RotaryEncoder.UP,
			RotaryEncoder.LEFT,
			RotaryEncoder.DOWN,
			RotaryEncoder.RIGHT
		]

		for index in range(0, len(buttons)):
			value = buttons[index]
			#seesaw_controller.pin_mode(value, seesaw_controller.INPUT_PULLUP)
			#self.buttons[value] = seesaw_digitalio.DigitalIO(seesaw_controller, value)

			success = False
			while not success:
				try:
					self.buttons[value] = DigitalIO(seesaw_controller, value)
					self.buttons[value].direction = digitalio.Direction.INPUT
					self.buttons[value].pull = digitalio.Pull.UP

					success = True
				except OSError as e:
					print(f"Failed to set up rotary encoder button, try again: {e}")
					sleep(0.2)

		self.encoder = rotaryio.IncrementalEncoder(seesaw_controller)
		self.last_position = self.encoder.position

	def wait(self, listen_for_buttons = True, listen_for_rotation = True, on_wait_tick = None, wait_tick = 5):
		assert(listen_for_buttons or listen_for_rotation)
		assert(on_wait_tick is None or callable(on_wait_tick))

		if self.encoder is None:
			self.init_rotary_encoder()

		response = None

		start = monotonic()
		last_tick = start
		while response is None:
			if listen_for_buttons:
				for key, button in self.buttons.items():
					if not button.value:
						self.last_button_down = key
					elif key == self.last_button_down:
						self.last_button_down = None
						response = key

			if listen_for_rotation:
				current_position = self.encoder.position
				last_position = self.last_position

				self.last_position = current_position

				if current_position > last_position:
					response = RotaryEncoder.CLOCKWISE
				elif current_position < last_position:
					response = RotaryEncoder.COUNTERCLOCKWISE

			if on_wait_tick is not None:
				now = monotonic()
				if now - last_tick > wait_tick:
					elapsed = now - start
					on_wait_tick(elapsed)
					last_tick = now

		return response

RotaryEncoder.SELECT = 1
RotaryEncoder.UP = 3
RotaryEncoder.LEFT = 4
RotaryEncoder.DOWN = 5
RotaryEncoder.RIGHT = 2
RotaryEncoder.CLOCKWISE = 10
RotaryEncoder.COUNTERCLOCKWISE = 11

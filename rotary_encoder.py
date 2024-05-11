from time import monotonic, sleep
from adafruit_seesaw import rotaryio, seesaw
import digitalio
from adafruit_seesaw.digitalio import DigitalIO

class RotaryEncoder:
	SELECT = 1
	UP = 3
	LEFT = 4
	DOWN = 5
	RIGHT = 2
	CLOCKWISE = 10
	COUNTERCLOCKWISE = 11

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
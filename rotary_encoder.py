import time
from adafruit_seesaw import rotaryio, seesaw
import digitalio
from adafruit_seesaw.digitalio import DigitalIO
from busio import I2C

class WaitTickListener:
	def __init__(self, seconds: int, on_tick, recurring = False):
		self.seconds = seconds
		self.on_tick = on_tick
		self.last_triggered = None
		self.recurring = recurring

	def trigger(self, elapsed: float) -> None:
		self.last_triggered = elapsed
		self.on_tick(elapsed)

class ActivityListener:
	def __init__(self, on_activity):
		self.on_activity = on_activity

	def trigger(self) -> None:
		self.on_activity()

class RotaryEncoder:
	SELECT = 1
	# it's physically rotated 90 CW so adjust accordingly
	UP = 3
	LEFT = 4
	DOWN = 5
	RIGHT = 2
	CLOCKWISE = 10
	COUNTERCLOCKWISE = 11

	def __init__(self, i2c: I2C):
		self.last_position = None
		self.buttons = {}
		self.last_button_down = None
		self.encoder = None
		self.i2c = i2c
		self.on_activity_listeners = []
		self.on_wait_tick_listeners = []

	def init_rotary_encoder(self) -> None:
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
					print(f"Failed to set up rotary encoder button, trying again: {e}")
					time.sleep(0.2)

		self.encoder = rotaryio.IncrementalEncoder(seesaw_controller)
		self.last_position = self.encoder.position

	def wait(self,
		listen_for_buttons: bool = True,
		listen_for_rotation: bool = True,
		extra_wait_tick_listeners: list[WaitTickListener] = None
	) -> int:
		assert(listen_for_buttons or listen_for_rotation)

		if self.encoder is None:
			self.init_rotary_encoder()

		response = None

		if extra_wait_tick_listeners is None:
			extra_wait_tick_listeners = []

		wait_tick_listeners = self.on_wait_tick_listeners + extra_wait_tick_listeners

		start = time.monotonic()
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

			now = time.monotonic()
			elapsed = now - start

			for listener in wait_tick_listeners:
				if elapsed > listener.seconds and listener.last_triggered is None:
					listener.trigger(elapsed)
					listener.last_triggered = now
				elif listener.recurring and listener.last_triggered is not None:
					last_relative_triggered = now - listener.last_triggered
					if last_relative_triggered >= listener.seconds:
						listener.trigger(elapsed)
						listener.last_triggered = now

		for activity_listener in self.on_activity_listeners:
			activity_listener.trigger()

			for wait_tick_listener in wait_tick_listeners:
				wait_tick_listener.last_triggered = None # reset for next call of wait()

		return response
import time

from busio import I2C

# noinspection PyBroadException
try:
	from typing import List, Optional, Callable, Any
except:
	# don't care
	pass

from adafruit_seesaw import seesaw, rotaryio
import digitalio
from adafruit_seesaw.digitalio import DigitalIO

class WaitTickListener:
	def __init__(self, seconds: int, on_tick: Callable[[float], None], recurring = False):
		self.seconds = seconds
		self.on_tick = on_tick
		self.last_triggered = None
		self.recurring = recurring

	def trigger(self, elapsed: float) -> None:
		self.last_triggered = elapsed
		self.on_tick(elapsed)

class ShutdownRequestListener:
	def __init__(self, on_shutdown_requested: Callable[[], None]):
		self.on_shutdown_requested = on_shutdown_requested

	def trigger(self) -> None:
		self.on_shutdown_requested()

class ActivityListener:
	def __init__(self, on_activity):
		self.on_activity = on_activity

	def trigger(self) -> None:
		self.on_activity()

class Button(DigitalIO):
	def __init__(self, seesaw: seesaw.Seesaw, pin: int):
		self.pin = pin
		success = False
		while not success:
			try:
				super().__init__(seesaw, pin)
				self.direction = digitalio.Direction.INPUT
				self.pull = digitalio.Pull.UP

				success = True
			except OSError as e:
				print(f"Failed to set up rotary encoder button, trying again: {e}")
				time.sleep(0.2)

		self.press_start: float = 0
		self.is_pressed = False

	# a click (down then up), not just down
	def was_pressed(self) -> tuple[bool, float]:
		if not self.value:
			if not self.is_pressed:
				self.press_start = time.monotonic()
			self.is_pressed = True

			return False, time.monotonic() - self.press_start

		if self.value and self.is_pressed:
			self.is_pressed = False
			return True, time.monotonic() - self.press_start

		return False, 0

class RotaryEncoder:
	SELECT = 1
	UP = 3
	LEFT = 4
	DOWN = 5
	RIGHT = 2
	CLOCKWISE = 10
	COUNTERCLOCKWISE = 11

	HOLD_FOR_SHUTDOWN_SECONDS = 3

	def __init__(self, i2c: I2C):
		self.i2c = i2c

		self.on_activity_listeners: List[ActivityListener] = []
		self.on_wait_tick_listeners: List[WaitTickListener] = []
		self.on_shutdown_requested_listeners: List[ShutdownRequestListener] = []

		self.last_position = None
		self.buttons = {}
		self.last_button_down = None
		self.last_button_down_times = {}

		self.seesaw = self.init_seesaw()
		self.encoder = self.init_rotary_encoder()

	def init_seesaw(self) -> seesaw.Seesaw:
		seesaw_controller = seesaw.Seesaw(self.i2c, addr = 0x49)
		product_id = (seesaw_controller.get_version() >> 16) & 0xFFFF
		assert product_id == 5740
		return seesaw_controller

	def init_rotary_encoder(self) -> rotaryio.IncrementalEncoder:
		# it's physically rotated 90 CW so adjust accordingly
		buttons = [
			RotaryEncoder.SELECT,
			RotaryEncoder.UP,
			RotaryEncoder.LEFT,
			RotaryEncoder.DOWN,
			RotaryEncoder.RIGHT
		]

		for pin in buttons:
			self.buttons[pin] = Button(self.seesaw, pin)

		encoder = rotaryio.IncrementalEncoder(self.seesaw)
		self.last_position = encoder.position
		return encoder

	def wait(self,
		listen_for_buttons: bool = True,
		listen_for_rotation: bool = True,
		extra_wait_tick_listeners: list[WaitTickListener] = None
	) -> int:
		assert(listen_for_buttons or listen_for_rotation)

		response = None

		if extra_wait_tick_listeners is None:
			extra_wait_tick_listeners = []

		start = time.monotonic()
		while response is None:
			response = self.poll_for_input()
			self.trigger_applicable_listeners(extra_wait_tick_listeners, start)

		for activity_listener in self.on_activity_listeners:
			activity_listener.trigger()

			for wait_tick_listener in self.on_wait_tick_listeners + extra_wait_tick_listeners:
				wait_tick_listener.last_triggered = None # reset for next call of wait()

		return response

	def trigger_applicable_listeners(self, extra_wait_tick_listeners: List[WaitTickListener], start: float) -> None:
		now = time.monotonic()
		elapsed = now - start

		for listener in self.on_wait_tick_listeners + extra_wait_tick_listeners:
			if elapsed > listener.seconds and listener.last_triggered is None:
				listener.trigger(elapsed)
				listener.last_triggered = now
			elif listener.recurring and listener.last_triggered is not None:
				last_relative_triggered = now - listener.last_triggered
				if last_relative_triggered >= listener.seconds:
					listener.trigger(elapsed)
					listener.last_triggered = now

	def poll_for_input(self, listen_for_buttons: bool = True, listen_for_rotation: bool = True) -> int:
		response = None

		for key, button in self.buttons.items():
			was_pressed, hold_time = button.was_pressed()
			if button.pin == RotaryEncoder.SELECT and hold_time >= RotaryEncoder.HOLD_FOR_SHUTDOWN_SECONDS:
				print("Informing listeners of shutdown request")
				for listener in self.on_shutdown_requested_listeners:
					listener.on_shutdown_requested()
				raise RuntimeError("No listeners initiated shutdown!")
			if was_pressed and listen_for_buttons:
				response = key
				break

		if listen_for_rotation:
			current_position = self.encoder.position
			last_position = self.last_position

			self.last_position = current_position

			if current_position > last_position:
				response = RotaryEncoder.CLOCKWISE
			elif current_position < last_position:
				response = RotaryEncoder.COUNTERCLOCKWISE

		return response
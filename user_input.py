import time

import microcontroller
from busio import I2C

from util import Util

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
	"""
	Something that happens periodically while waiting for user input.
	"""

	def __init__(self,
				 seconds: int,
				 on_tick: Callable[[float], None],
				 only_invoke_if: Optional[Callable[[], bool]] = None,
				 recurring = False,
				 name: Optional[str] = None):
		"""
		:param seconds: How frequently to do the thing
		:param on_tick: What the thing is to do; gets passed elapsed time
		:param only_invoke_if: Only do the thing if this returns True, or if None, always do the thing
		:param recurring: Do the thing just once (False) or at a regular interval (True)
		:param name: Name for debugging's sake
		"""

		self.seconds = seconds
		self.on_tick = on_tick
		self.only_invoke_if = only_invoke_if
		self.last_triggered = None
		self.recurring = recurring
		self.name = name

	def trigger(self, elapsed: float) -> None:
		"""
		Do the thing if only_invoke_if returns True or is None.

		:param elapsed: How many seconds have passed
		"""

		self.last_triggered = elapsed
		if self.only_invoke_if is None or self.only_invoke_if():
			self.on_tick(elapsed)

	def __str__(self):
		"""
		Gets this listener as a string for debugging's sake; don't parse it.

		:return: self.name if provided, otherwise the base implementation of __str__()
		"""

		return super().__str__() if self.name is None else self.name

class Button(DigitalIO):
	"""
	A physical button that's associated to a digital IO pin.
	"""

	def __init__(self, seesaw_controller: seesaw.Seesaw, pin: int):
		"""
		:param seesaw_controller: Seesaw controller with virtual pins
		:param pin: Virtual pin number on the seesaw controller
		"""
		super().__init__(seesaw_controller, pin)

		self.pin = pin
		self.seesaw_controller = seesaw_controller
		Util.try_repeatedly(
			method = self.init_rotary_encoder,
			max_attempts = 20
		)
		self.press_start: float = 0
		self.is_pressed = False

	def init_rotary_encoder(self) -> None:
		"""
		Sets up the digital IO as an input with pull-up.
		"""

		super().__init__(self.seesaw_controller, self.pin)
		self.direction = digitalio.Direction.INPUT
		self.pull = digitalio.Pull.UP

	def was_pressed(self) -> tuple[bool, float]:
		"""
		Checks if a button was pressed and then released, and if so, for how long.

		:return: A tuple: first item is True if the button has been pressed and released and False if not, and the
		second item is for how long the button was held in seconds or 0 if it wasn't.
		"""

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
	"""
	Abstraction of the rotary encoder that's connected to an I2C seesaw controller:
	https://www.adafruit.com/product/5740

	Careful! Because this assumes you built a BabyPod using the instructions at
	https://github.com/skjdghsdjgsdj/babypod-hardware, it also assumes the rotary encoder is rotated 90°! Therefore,
	UP isn't necessarily UP as it appears on the board, but rather how the board is mounted in the enclosure.
	That is, "UP" is at the top of the rotary encoder as it's mounted in the enclosure, not necessarily how it would
	be if the board is oriented to align with the text printed on it.
	"""

	SELECT = 1
	UP = 3
	LEFT = 4
	DOWN = 5
	RIGHT = 2
	CLOCKWISE = 10
	COUNTERCLOCKWISE = 11

	HOLD_FOR_SHUTDOWN_SECONDS = 2

	def __init__(self, i2c: I2C):
		"""
		:param i2c: I2C bus with the rotary encoder
		"""
		self.i2c = i2c

		self.on_activity_listeners: List[Callable[[], None]] = []
		self.on_wait_tick_listeners: List[WaitTickListener] = []
		self.on_shutdown_requested_listeners: List[Callable[[], None]] = []
		self.on_reset_requested_listeners: List[Callable[[], None]] = []

		self.last_position = None
		self.buttons = {}
		self.last_button_down = None
		self.last_button_down_times = {}

		self.seesaw = self.init_seesaw()
		self.encoder = self.init_rotary_encoder()

	def init_seesaw(self) -> seesaw.Seesaw:
		"""
		Connects to the Seesaw controller on the I2C bus at address 0x49 and verifies that it's using the product ID
		5740.

		:return: Seesaw controller
		"""
		seesaw_controller = seesaw.Seesaw(self.i2c, addr = 0x49)
		product_id = (seesaw_controller.get_version() >> 16) & 0xFFFF
		assert product_id == 5740
		return seesaw_controller

	def init_rotary_encoder(self) -> rotaryio.IncrementalEncoder:
		"""
		Sets up digital IO wrappers for all of the rotary encoder's buttons and stores its initial rotational
		position.

		:return: Rotary encoder
		"""

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
		"""
		Waits for the user to make any user input: either for a button press and/or for rotation. While waiting,
		various listeners may be triggered. At least one of the listen arguments must be True.

		:param listen_for_buttons: Listen for any button press
		:param listen_for_rotation: Listen for a rotation in any direction
		:param extra_wait_tick_listeners: Do these things while waiting for input
		:return: The button that was pressed or direction of rotation; refer to the class-level fields for constants
		"""

		assert(listen_for_buttons or listen_for_rotation)

		response = None

		if extra_wait_tick_listeners is None:
			extra_wait_tick_listeners = []

		start = time.monotonic()
		while response is None:
			response = self.poll_for_input()
			self.trigger_applicable_listeners(extra_wait_tick_listeners, start)

		for activity_listener in self.on_activity_listeners:
			activity_listener()

			for wait_tick_listener in self.on_wait_tick_listeners + extra_wait_tick_listeners:
				wait_tick_listener.last_triggered = None # reset for next call of wait()

		return response

	def trigger_applicable_listeners(self, extra_wait_tick_listeners: List[WaitTickListener], start: float) -> None:
		"""
		Triggers any wait tick listeners that are due to be invoked by now.

		:param extra_wait_tick_listeners: Also trigger these additional listeners if necessary
		:param start: Monotonic time for when input listening started
		"""

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
		"""
		Blocks waiting for the user to make any kind of input.

		:param listen_for_buttons: Return once a button is pressed
		:param listen_for_rotation: Return once rotation is made
		:return: The button that was pressed or direction of rotation; refer to the class-level fields for constants
		"""

		response = None

		for key, button in self.buttons.items():
			was_pressed, hold_time = button.was_pressed()
			if hold_time >= RotaryEncoder.HOLD_FOR_SHUTDOWN_SECONDS:
				if button.pin == RotaryEncoder.SELECT and len(self.on_shutdown_requested_listeners) > 0:
					for listener in self.on_shutdown_requested_listeners:
						listener()
					raise RuntimeError("No listeners initiated shutdown!")
				elif button.pin == RotaryEncoder.DOWN and len(self.on_reset_requested_listeners) > 0:
					try:
						for listener in self.on_reset_requested_listeners:
							listener()
					finally:
						microcontroller.reset()
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

		microcontroller.watchdog.feed()

		return response
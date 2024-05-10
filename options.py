import microcontroller

class Options:
	def __init__(self):
		# defaults
		self.values = {
			Options.PIEZO: True,
			Options.BACKLIGHT: True
		}

		self.NVM_INDEX = 0
		self.NVM_TRUE = 0xFF
		self.NVM_FALSE = 0xF0

	def __getitem__(self, item):
		return self.values[item]

	def load(self):
		for index, value in self.values.items():
			value = microcontroller.nvm[index]

			if value == self.NVM_TRUE:
				self.values[index] = True
			elif value == self.NVM_FALSE:
				self.values[index] = False
			elif value != 0:
				print(f"Option at index {index} in NVM is not true, false, or 0x0 but instead is: " + hex(value))

		return self

	def save(self, option, value):
		self.values[option] = value
		microcontroller.nvm[option] = self.NVM_TRUE if value else self.NVM_FALSE

Options.PIEZO = 0
Options.BACKLIGHT = 1

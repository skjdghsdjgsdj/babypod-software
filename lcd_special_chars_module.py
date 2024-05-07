# https://www.quinapalus.com/hd44780udg.html
class LCDSpecialChars:
	def __init__(self, lcd):
		self.lcd = lcd
		self.is_inited = False

	def apply(self):
		if not self.is_inited:
			for i in range(0, len(LCDSpecialChars.CHARS)):
				self.lcd.create_char(i, LCDSpecialChars.CHARS[i])
			self.is_inited = True

	def __getitem__(self, index):
		if index < 0 or index >= len(LCDSpecialChars.CHARS):
			raise Exception("Illegal index")

		self.apply()

		return chr(index)

LCDSpecialChars.UP_DOWN = 0
LCDSpecialChars.CHECKED = 1
LCDSpecialChars.UNCHECKED = 2
LCDSpecialChars.CHARGING = 3
LCDSpecialChars.RIGHT = 4
LCDSpecialChars.LEFT = 5

LCDSpecialChars.CHARS = {
	LCDSpecialChars.UP_DOWN: [0x4, 0xe, 0x1f, 0x0, 0x0, 0x1f, 0xe, 0x4],
	LCDSpecialChars.UNCHECKED: [0x0, 0x1f, 0x11, 0x11, 0x11, 0x1f, 0x0, 0x0],  
	LCDSpecialChars.CHECKED: [0x0, 0x1, 0x3, 0x16, 0x1c, 0x8, 0x0, 0x0],
	LCDSpecialChars.CHARGING: [0x4, 0xe, 0x1b, 0x0, 0xe, 0xa, 0xe, 0xe],
	LCDSpecialChars.RIGHT: [0x10, 0x18, 0x1c, 0x1e, 0x1c, 0x18, 0x10, 0x0],
	LCDSpecialChars.LEFT: [0x2, 0x6, 0xe, 0x1e, 0xe, 0x6, 0x2, 0x0]
}

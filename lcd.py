import time

# noinspection PyBroadException
try:
    from typing import List
except:
    pass

from busio import I2C

class LCD:
    UP_DOWN = 0
    CHECKED = 1
    UNCHECKED = 2
    CHARGING = 3
    RIGHT = 4
    LEFT = 5
    
    COLUMNS = 20
    LINES = 4
    
    def __init__(self, i2c: I2C):
        self.i2c = i2c
        for key, value in LCD.CHARS.items():
            self.create_special_char(key, value)

    def write(self, message: str, coords: tuple[int, int]) -> None:
        LCD.validate_coords(coords)
        self.write_impl(message, coords)

    def write_impl(self, message: str, coords: tuple[int, int]) -> None:
        raise NotImplementedError()

    def write_centered(self, text: str, erase_if_shorter_than: int = None, y_delta: int = 0) -> None:
        if erase_if_shorter_than is not None and len(text) < erase_if_shorter_than:
            self.write_centered(" " * erase_if_shorter_than, y_delta = y_delta)

        coords = (max(int(LCD.COLUMNS / 2 - len(text) / 2), 0), max(int(LCD.LINES / 2) - 1 + y_delta, 0))
        self.write(text, coords)

    def write_right_aligned(self, text: str, y: int = 0) -> None:
        if len(text) >= LCD.COLUMNS:
            raise ValueError(f"Text exceeds {LCD.COLUMNS} chars: {text}")

        self.write(text, (LCD.COLUMNS - len(text), y))

    def write_bottom_right_aligned(self, text: str, y_delta: int = 0) -> None:
        self.write_right_aligned(text, LCD.LINES - 1 - y_delta)

    def write_bottom_left_aligned(self, text: str, y_delta: int = 0) -> None:
        self.write(text, (0, y_delta))

    def clear(self) -> None:
        raise NotImplementedError()

    def __getitem__(self, special_char: int) -> str:
        return chr(special_char)

    def create_special_char(self, special_char: int, data: List[int]) -> None:
        raise NotImplementedError()

    @staticmethod
    def validate_coords(coords: tuple[int, int]) -> None:
        x, y = coords
        if x < 0 or x >= LCD.COLUMNS:
            raise ValueError(f"x ({x}) must be >= 0 and < {LCD.COLUMNS}")

        if y < 0 or y >= LCD.LINES:
            raise ValueError(f"y ({y}) must be >= 0 and < {LCD.LINES}")

    @staticmethod
    def get_instance(i2c: I2C):
        attempts = 0
        i2c_address_list = None
        while attempts <= 20:
            while not i2c.try_lock():
                pass
            i2c_address_list = i2c.scan()
            i2c.unlock()

            attempts += 1

            if 0x20 in i2c_address_list:
                return AdafruitCharacterLCDBackpack(i2c)
            elif 0x72 in i2c_address_list:
                return SparkfunSerLCD(i2c)

            print("Couldn't find LCD on I2C, retrying")
            time.sleep(0.2)

        found_count = len(i2c_address_list)
        found_addresses = ", ".join([hex(device_address) for device_address in i2c_address_list])
        raise RuntimeError(f"Couldn't find LCD on I2C at 0x20 (Adafruit LCD backpack) or 0x72 (Sparkfun SerLCD): " +
                           f"only found {found_count} I2C devices at addresses: {found_addresses}")

# https://www.quinapalus.com/hd44780udg.html
LCD.CHARS = {
    LCD.UP_DOWN: [0x4, 0xe, 0x1f, 0x0, 0x0, 0x1f, 0xe, 0x4],
    LCD.UNCHECKED: [0x0, 0x1f, 0x11, 0x11, 0x11, 0x1f, 0x0, 0x0],
    LCD.CHECKED: [0x0, 0x1, 0x3, 0x16, 0x1c, 0x8, 0x0, 0x0],
    LCD.CHARGING: [0x4, 0xe, 0x1b, 0x0, 0xe, 0xa, 0xe, 0xe],
    LCD.RIGHT: [0x10, 0x18, 0x1c, 0x1e, 0x1c, 0x18, 0x10, 0x0],
    LCD.LEFT: [0x2, 0x6, 0xe, 0x1e, 0xe, 0x6, 0x2, 0x0]
}

class SparkfunSerLCD(LCD):
    def __init__(self, i2c: I2C):
        from sparkfun_serlcd import Sparkfun_SerLCD_I2C
        self.device = Sparkfun_SerLCD_I2C(i2c)
        super().__init__(i2c)
        self.device.command(0x2F) # turn off command messages
        self.device.command(0x31) # disable splash screen

    def write_impl(self, message: str, coords: tuple[int, int]) -> None:
        x, y = coords
        self.device.set_cursor(x, y)
        self.device.write(message)

    def clear(self) -> None:
        self.device.clear()

    def create_special_char(self, special_char: int, data: List[int]) -> None:
        self.device.create_character(special_char, data)

class AdafruitCharacterLCDBackpack(LCD):
    def __init__(self, i2c: I2C):
        from adafruit_character_lcd.character_lcd_i2c import Character_LCD_I2C
        super().__init__(i2c)
        self.device = Character_LCD_I2C(i2c, LCD.COLUMNS, LCD.LINES)

    def create_special_char(self, special_char: int, data: List[int]) -> None:
        self.device.create_char(special_char, data)

    def write_impl(self, message: str, coords: tuple[int, int]):
        x, y = coords
        self.device.cursor_position(x, y)
        self.device.message = message

    def clear(self) -> None:
        self.device.clear()
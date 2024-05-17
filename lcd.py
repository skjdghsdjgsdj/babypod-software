from adafruit_character_lcd.character_lcd_i2c import Character_LCD_I2C
from busio import I2C

class LCD:
    COLUMNS = 20
    LINES = 4

    UP_DOWN = 0
    CHECKED = 1
    UNCHECKED = 2
    CHARGING = 3
    RIGHT = 4
    LEFT = 5

    CHARS = {
        UP_DOWN: [0x4, 0xe, 0x1f, 0x0, 0x0, 0x1f, 0xe, 0x4],
        UNCHECKED: [0x0, 0x1f, 0x11, 0x11, 0x11, 0x1f, 0x0, 0x0],
        CHECKED: [0x0, 0x1, 0x3, 0x16, 0x1c, 0x8, 0x0, 0x0],
        CHARGING: [0x4, 0xe, 0x1b, 0x0, 0xe, 0xa, 0xe, 0xe],
        RIGHT: [0x10, 0x18, 0x1c, 0x1e, 0x1c, 0x18, 0x10, 0x0],
        LEFT: [0x2, 0x6, 0xe, 0x1e, 0xe, 0x6, 0x2, 0x0]
    }

    def __init__(self, i2c: I2C):
        self.device = Character_LCD_I2C(i2c, LCD.COLUMNS, LCD.LINES)
        self.inited_chars = []

    def write(self, message: str, coords: tuple[int, int] = None):
        if coords is not None:
            x, y = coords
            if x < 0 or x >= LCD.COLUMNS:
                raise ValueError(f"x ({x}) must be >= 0 and < {LCD.COLUMNS}")

            if y < 0 or y >= LCD.LINES:
                raise ValueError(f"y ({y}) must be >= 0 and < {LCD.LINES}")

            self.device.cursor_position(x, y)

        self.device.message = message

    def write_centered(self, text: str, erase_if_shorter_than: int = None, y_delta: int = 0) -> None:
        if erase_if_shorter_than is not None and len(text) < erase_if_shorter_than:
            self.write_centered(" " * erase_if_shorter_than, y_delta = y_delta)

        coords = (max(int(LCD.COLUMNS / 2 - len(text) / 2), 0), max(int(LCD.LINES / 2) - 1 + y_delta, 0))
        self.write(text, coords)

    def write_right_aligned(self, text: str, y: int = 0) -> None:
        if len(str) >= LCD.COLUMNS:
            raise ValueError(f"Text exceeds {LCD.COLUMNS} chars: {text}")

        self.write(text, (LCD.COLUMNS - len(str), y))

    def write_bottom_right_aligned(self, text: str, y_delta: int = 0) -> None:
        self.write_right_aligned(text, LCD.LINES - 1 - y_delta)

    def write_bottom_left_aligned(self, text: str, y_delta: int = 0) -> None:
        self.write(text, (0, y_delta))

    def clear(self) -> None:
        self.device.clear()

    def __getitem__(self, special_char: int) -> str:
        if special_char not in self.inited_chars:
            self.device.create_char(special_char, LCD.CHARS[special_char])
            self.inited_chars.append(special_char)

        return chr(special_char)
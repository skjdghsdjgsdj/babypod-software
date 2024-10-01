import microcontroller

class NVRAMValue:
    def __init__(self, index: int, default = None, name: str = None):
        self.index = index
        self.default = default
        self.value = default
        self.has_read = False
        self.name = name

    def nvram_to_native(self, nvram_value: int):
        raise NotImplementedError()

    def native_to_nvram(self, native_value) -> int:
        raise NotImplementedError()

    def get(self):
        value = self.value
        if not self.has_read:
            value = self.read()

        return value

    def read(self):
        nvram_value = microcontroller.nvm[self.index]
        self.value = self.default
        if nvram_value != 0x0:
            self.value = self.nvram_to_native(nvram_value)
            #print(f"Read {self.value} from NVRAM at index {self.index}, stored as {nvram_value}")
        else:
            #print(f"NVRAM at index {self.index} is 0x0, using default value {self.default}")
            pass

        self.has_read = True

        return self.value

    def write(self, native_value: int, only_if_changed: bool = True) -> None:
        if not only_if_changed or native_value != self.value:
            self.value = native_value
            nvram_value = self.native_to_nvram(self.value)
            microcontroller.nvm[self.index] = nvram_value

            print(f"Wrote {self}")

    def reset_to_default(self):
        self.write(self.default)

    def __str__(self):
        if self.name is not None:
            value = f"NVRAM {self.name}"
        else:
            value = f"NVRAM #{self.index}"

        value += " -> " + str(self.value)

        return value

class NVRAMBooleanValue(NVRAMValue):
    def __init__(self, index: int, default: bool = None, name: str = None):
        super().__init__(index, default, name)

    def nvram_to_native(self, nvram_value: int) -> bool:
        if nvram_value == 0xFF:
            return True
        elif nvram_value == 0xF0:
            return False
        else:
            print(f"NVRAM value at index {self.index} isn't known true or false value; using default")
            return self.default

    def native_to_nvram(self, native_value: bool) -> int:
        return 0xFF if native_value else 0xF0

    def write(self, native_value: bool, only_if_changed: bool = True) -> None:
        super().write(native_value, only_if_changed)

    def get(self) -> bool:
        return super().get()

    def __bool__(self):
        return self.get()

class NVRAMIntegerValue(NVRAMValue):
    def __init__(self, index: int, default: int = None, name: str = None):
        super().__init__(index, default, name)

    def nvram_to_native(self, nvram_value: int) -> int:
        if nvram_value == 0x0:
            print(f"NVRAM value is 0x0 which is ambiguous: could be int(0), could be unset, assuming the former")
        return int(nvram_value)

    def native_to_nvram(self, native_value: int) -> int:
        if native_value == 0x0:
            print("Using int(0) as an NVRAM value is ambiguous: could be int(0), could be unset, assuming the former")
        return native_value
    
    def get(self) -> int:
        return super().get()

    def __int__(self):
        return self.get()

    def __float__(self):
        return float(int(self))

class NVRAMValues:
    # True to play piezo sounds, False to not
    PIEZO = NVRAMBooleanValue(0, True, "PIEZO")
    # Baby Buddy child ID; 0 to autodiscover
    CHILD_ID = NVRAMIntegerValue(2, 0, "CHILD_ID")
    # How many seconds until backlight dims from user inactivity on most screens
    BACKLIGHT_DIM_TIMEOUT = NVRAMIntegerValue(3, 30, "BACKLIGHT_DIM_TIMEOUT")
    # If battery is not charging, how many seconds until the piezo makes a warning tone
    IDLE_WARNING = NVRAMIntegerValue(4, 60 * 2, "IDLE_WARNING")
    # Bitmask of food types to enable in the feeding menu for flow.py; default is all
    ENABLED_FOOD_TYPES_MASK = NVRAMIntegerValue(5, 0x1 + 0x2 + 0x4 + 0x8, "ENABLED_FOOD_TYPES_MASK")
    # True to work offline; requires an RTC and SD card hardware
    OFFLINE = NVRAMBooleanValue(6, False, "OFFLINE")
    # True to force the RTC to update at next boot; use only for debugging
    FORCE_RTC_UPDATE = NVRAMBooleanValue(7, False, "FORCE_RTC_UPDATE")
    # For soft power control, wake up every N seconds to refresh the battery display, then go back to sleep. This is only applicable when running on battery; when
    # charging, the refresh is much more often.
    SOFT_SHUTDOWN_BATTERY_REFRESH_INTERVAL = NVRAMIntegerValue(8, 60 * 10, "SOFT_SHUTDOWN_BATTERY_REFRESH_INTERVAL")
    # False (default) means this BabyPod doesn't use the Sparkfun LCD or hasn't configured some of its flags yet, or
    # True if flags are configured and don't need to be reconfigured. No effect for the Adafruit LCD.
    HAS_CONFIGURED_SPARKFUN_LCD = NVRAMBooleanValue(9, False, "HAS_CONFIGURED_SPARKFUN_LCD")
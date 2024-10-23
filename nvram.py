# noinspection PyBroadException
try:
    from abc import abstractmethod, ABC
except:
    class ABC:
        pass

    # noinspection PyUnusedLocal
    def abstractmethod(*args, **kwargs):
        pass

import microcontroller

class NVRAMValue(ABC):
    """
    Wraps a native Python type with a value that can be stored in NVRAM. Abstract class; construct a child class to use
    this.
    """

    def __init__(self, index: int, default = None, name: str = None):
        """
        :param index: Index in NVRAM that will hold the data. Must be unique across NVRAMValue instances.
        :param default: Default value if one isn't defined in NVRAM
        :param name: Name of this value; only used for debug output
        """

        self.index = index
        self.default = default
        self.value = default
        self.has_read = False
        self.name = name

    @abstractmethod
    def nvram_to_native(self, nvram_value: int):
        """
        Gets a native Python value of what's stored in NVRAM as the given NVRAM byte. Abstract method; must be
        overridden by child classes.

        :param nvram_value: NVRAM byte
        :return: Native Python value of what's stored as this NVRAM byte
        """

        raise NotImplementedError()

    @abstractmethod
    def native_to_nvram(self, native_value) -> int:
        """
        Gets an NVRAM byte used to store the given native Python value. Abstract method; must be overridden by child
        classes.

        Avoid using 0x0 for native values as that's treated effectively as "nothing was set".

        :param native_value: Python native value to store in NVRAM
        :return: NVRAM byte version of native_value
        """

        raise NotImplementedError()

    def get(self):
        """
        Gets the current value from NVRAM. If this object was previously read successfully and not written since last
        read by this same object, returns a memoized value instead of querying NVRAM directly again.

        :return: Native Python value of what's stored in NVRAM
        """

        value = self.value
        if not self.has_read:
            value = self.read()

        return value

    def read(self):
        """
        Reads the current value from NVRAM and returns it as a native Python value. Unlike get(), this will ALWAYS
        read NVRAM; you probably want to use get() instead.

        :return: Native Python value of what's in NVRAM.
        """

        nvram_value = microcontroller.nvm[self.index]
        self.value = self.default
        if nvram_value != 0x0:
            self.value = self.nvram_to_native(nvram_value)

        self.has_read = True

        return self.value

    def write(self, native_value: int, only_if_changed: bool = True) -> None:
        """
        Stores a value in NVRAM.

        :param native_value: Python native value to store
        :param only_if_changed: True to only write to NVRAM if the value passed differs from the last value read, or
        False to write regardless.
        """

        if not only_if_changed or native_value != self.value:
            self.value = native_value
            nvram_value = self.native_to_nvram(self.value)
            microcontroller.nvm[self.index] = nvram_value

            print(f"Wrote {self}")

    def reset_to_default(self) -> None:
        """
        Resets the value stored in NVRAM to the default value.
        """

        self.write(self.default)

    def __str__(self) -> str:
        """
        Convenience method for debug printing NVRAMValues.

        :return: Like "NVRAM SOME_NAME -> 3"
        """

        if self.name is not None:
            value = f"NVRAM {self.name}"
        else:
            value = f"NVRAM #{self.index}"

        value += " -> " + str(self.value)

        return value

class NVRAMBooleanValue(NVRAMValue):
    """
    NVRAMValue that wraps a Python boolean. The NVRAM byte is 0xFF for True, 0xF0 for false. 0x0 is avoided because
    that's meant to be "nothing was set." In instances where the value in NVRAM is not 0xFF nor 0xF0, then the default
    is used.
    """

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

    def __bool__(self) -> bool:
        """
        Typecasts this NVRAMValue as a native Python boolean.

        :return: self.get(), literally
        """
        return self.get()

class NVRAMIntegerValue(NVRAMValue):
    """
    NVRAMValue that wraps a Python int. For native values, avoid using 0 as that would get stored as 0x0 and that's
    ambiguous between "store a 0" vs. "nothing was set." Because the underlying data is only a single byte, the value
    must be 0..255 and, I presume, unsigned.
    """
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

    def __int__(self) -> int:
        """
        :return: self.get(), literally
        """
        return self.get()

    def __float__(self) -> float:
        """
        :return: self.get() cast to a float
        """
        return float(int(self))

class NVRAMValues:
    """
    Enum-like class of NVRAMValue instances. If modifying this list, be very careful not to reuse indices.
    """

    # True to play piezo sounds, False to not
    PIEZO = NVRAMBooleanValue(0, True, "PIEZO")
    # Baby Buddy child ID; 0 to autodiscover
    CHILD_ID = NVRAMIntegerValue(2, 0, "CHILD_ID")
    # How many seconds until backlight dims from user inactivity on most screens
    BACKLIGHT_DIM_TIMEOUT = NVRAMIntegerValue(3, 30, "BACKLIGHT_DIM_TIMEOUT")
    # How many seconds until the piezo makes a warning tone (repeating)
    IDLE_WARNING = NVRAMIntegerValue(4, 60, "IDLE_WARNING")
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
    # How frequently in seconds to check for a MOTD
    MOTD_CHECK_INTERVAL = NVRAMIntegerValue(10, 60 * 60 * 6, "MOTD_CHECK_INTERVAL")
    # Soft shutdown after this many seconds of being idle and not in a timer; only has an effect if soft shutdown
    # is enabled
    IDLE_SHUTDOWN = NVRAMIntegerValue(11, 60 * 3 - 5, "IDLE_SHUTDOWN") # -5 seconds to avoid the warning triggering right at shutdown
    # For soft power control, auto shutdown after saving a timer. Also shut down soon after starting a sleep timer.
    TIMERS_AUTO_OFF = NVRAMBooleanValue(12, False, "AUTO_OFF_AFTER_TIMER_SAVED")
    # What options to show on the main menu (bitmask); defaults to Feeding, Diaper change, Pumping, and Sleep. If you
    # omit feeding, then the main menu loads faster because it doesn't need to check when the last feeding was.
    # Remember to only enable up to four items because menus only show up to four items.
    ENABLED_MAIN_MENU_ITEMS = NVRAMIntegerValue(13, 0x1 + 0x2 + 0x4 + 0x8, "ENABLED_MAIN_MENU_ITEMS")
import microcontroller

class NVRAMValue:
    def __init__(self, index, default = None):
        self.index = index
        self.default = default
        self.value = default
        self.has_read = False

    def nvram_to_native(self, nvram_value):
        raise NotImplementedError()

    def native_to_nvram(self, native_value):
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
            print(f"Read {self.value} from NVRAM at index {self.index}, stored as {nvram_value}")
        else:
            print(f"NVRAM at index {self.index} is 0x0, using default value {self.default}")

        self.has_read = True

        return self.value

    def write(self, native_value, only_if_changed: bool = True):
        if not only_if_changed or native_value != self.value:
            self.value = native_value
            nvram_value = self.native_to_nvram(self.value)
            microcontroller.nvm[self.index] = nvram_value

            print(f"Persisted {native_value} as NVRAM value {nvram_value} to NVRAM index {self.index}")

    def reset_to_default(self):
        self.write(self.default)

class NVRAMBooleanValue(NVRAMValue):
    def __init__(self, index, default: bool = None):
        super().__init__(index, default)

    def nvram_to_native(self, nvram_value):
        if nvram_value == 0xFF:
            return True
        elif nvram_value == 0xF0:
            return False
        else:
            print(f"NVRAM value at index {self.index} isn't known true or false value; using default")
            return self.default

    def native_to_nvram(self, native_value: bool):
        return 0xFF if native_value else 0xF0

class NVRAMIntegerValue(NVRAMValue):
    def __init__(self, index, default: int = None):
        super().__init__(index, default)

    def nvram_to_native(self, nvram_value):
        if nvram_value == 0x0:
            print(f"NVRAM value is 0x0 which is ambiguous: could be int(0), could be unset, assuming the former")
        return int(nvram_value)

    def native_to_nvram(self, native_value: int):
        if native_value == 0x0:
            print("Using int(0) as an NVRAM value is ambiguous: could be int(0), could be unset, assuming the former")
        return native_value

class NVRAMValues:
    OPTION_PIEZO = NVRAMBooleanValue(0, True)
    OPTION_BACKLIGHT = NVRAMBooleanValue(1, True)
    CHILD_ID = NVRAMIntegerValue(2, 1)
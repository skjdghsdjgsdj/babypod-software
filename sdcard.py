import board
import sdcardio
import storage

class SDCard:
    def __init__(self, cs_pin = board.D10):
        spi = board.SPI()

        self.mount_point = "/sd"

        self.device = sdcardio.SDCard(spi, cs_pin)
        # noinspection PyTypeChecker
        self.vfs = storage.VfsFat(self.device)
        storage.mount(self.vfs, self.mount_point)

        #print(f"Mounted SD card to {self.mount_point}")

    def get_absolute_path(self, filename: str) -> str:
        return self.mount_point + "/" + filename
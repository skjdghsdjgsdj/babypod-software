import board
import sdcardio
import storage

class SDCard:
    def __init__(self):
        spi = board.SPI()
        cs = board.D10

        self.mount_point = "/sd"

        self.device = sdcardio.SDCard(spi, cs)
        # noinspection PyTypeChecker
        self.vfs = storage.VfsFat(self.device)
        storage.mount(self.vfs, self.mount_point)

        #print(f"Mounted SD card to {self.mount_point}")

    def get_absolute_path(self, filename: str) -> str:
        return self.mount_point + "/" + filename
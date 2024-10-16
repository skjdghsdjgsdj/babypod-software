import board
import sdcardio
import storage

class SDCard:
    """
    Abstraction of an SD card reader. It could be an actual SD card or an embedded one, like
    https://www.adafruit.com/product/4899, but either way, it's connected to the SPI bus.
    """

    def __init__(self, cs_pin = board.D10):
        """
        :param cs_pin: Chip select (CS) pin to which the SD card is wired
        """

        spi = board.SPI()

        self.mount_point = "/sd"

        self.device = sdcardio.SDCard(spi, cs_pin)
        # noinspection PyTypeChecker
        self.vfs = storage.VfsFat(self.device)
        storage.mount(self.vfs, self.mount_point)

        #print(f"Mounted SD card to {self.mount_point}")

    def get_absolute_path(self, filename: str) -> str:
        """
        Given a filename or relative path, gets the full path of a file.

        :param filename: Relative path, like queue/test.json
        :return: Full path, like /sd/queue/test.json
        """
        return self.mount_point + "/" + filename
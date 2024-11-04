#!/bin/bash
circup --path lib --board-id adafruit_feather_esp32s3_4mbflash_2mbpsram --cpy-version $(pip show circuitpython-stubs | grep Version: | cut -d' ' -f2) update --all
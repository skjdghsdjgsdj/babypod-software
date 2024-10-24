#!/usr/bin/env python3

"""
Bundles the app for use on an actual hardware CircuitPython device.
"""

import argparse
import glob
import subprocess
import sys
import zipfile
from typing import Final
import shutil
import os
import pathlib
import tempfile

CIRCUITPY_PATH: Final = "/Volumes/CIRCUITPY"

parser = argparse.ArgumentParser(description = "Build and deploy CircuitPython files to a hardware device")
parser.add_argument(
    "--no-compile",
    action = "store_true",
    help = "Copy .py files instead of building .mpy files"
)

parser.add_argument(
    "--no-reboot",
    action = "store_true",
    help = "Do not attempt to reboot the board automatically"
)

parser.add_argument(
    "--modules",
    nargs = "+",
    default = [],
    help = "Only build/deploy the given modules; omit for all"
)

parser.add_argument(
    "--clean",
    action = "store_true",
    help = "Recreate the board's lib/ directory with just the Adafruit modules"
)

parser.add_argument(
    "--output",
    action = "store",
    default = None,
    help = f"Output to this directory instead of {CIRCUITPY_PATH}"
)

parser.add_argument(
    "--build-release-zip",
    action = "store",
    default = None,
    help = "Builds a zip suitable for deployment to GitHub to this zip filename; overrides other arguments"
)

def get_base_path() -> str:
    """
    Gets the base path of this script
    :return: Base path of this script
    """

    return os.path.abspath(os.path.dirname(__file__))

def reboot() -> None:
    """
    Attempts to connect to the first device found in /dev/ beginning with "cu.usbmodem" and sends Ctrl-C then Ctrl-D to
    it, which interrupts the current code and then sends EOF to signal a reboot.
    """

    devices = glob.glob("/dev/cu.usbmodem*")
    if not devices:
        raise ValueError("Couldn't find any device named /dev/cu.usbmodem*")

    if len(devices) > 1:
        raise ValueError("Multiple devices named /dev/cu.usbmodem* found")

    device = devices[0]

    subprocess.Popen(f"expect -c \"send \003;\" > {device}", shell = True).communicate()
    subprocess.Popen(f"expect -c \"send \004;\" > {device}", shell = True).communicate()

def clean(clean_path: str) -> None:
    """
    Deletes everything from /lib/ on the device and repopulates it with what's in /lib/ locally.
    :param clean_path: Device base path, like /Volumes/CIRCUITPY, without trailing slash
    """

    lib = f"{clean_path}/lib"
    print(f"Purging everything from {lib}...", end = "", flush = True)
    shutil.rmtree(lib, ignore_errors = True)
    print("done")

    print(f"Repopulating {lib}...", end = "", flush = True)
    local_lib = get_base_path() + "/lib"
    shutil.copytree(local_lib, lib)
    print("done")

def build_and_deploy(source_module: str, module_output_path: str, compile_to_mpy: bool = True) -> str:
    """
    For a given module, optionally compiles the module and then copies either the compiled output or the original
    source code to the hardware device.
    :param source_module: Source module to deploy; use "code" for code.py or the filename of the module sans extension
    like "nvram" for nvram.py
    :param module_output_path: Base path to the device, like /Volumes/CIRCUITPY, without trailing slash
    :param compile_to_mpy: True to run mpy-cross on the module first then copy the resulting .mpy to the device or False
    to just copy the original .py source code.
    :return: Path to the file that ended up on the hardware device
    """
    if source_module == "code":
        print("Copying code.py...", end = "", flush = True)
        dst = f"{module_output_path}/code.py"
        shutil.copyfile(get_base_path() + "/code.py", dst)
        print("done")
    else:
        full_src = get_base_path() + "/" + source_module + ".py"
        if not os.path.isfile(full_src):
            raise ValueError(f"File doesn't exist: {full_src}")

        if compile_to_mpy:
            temp_mpy = tempfile.NamedTemporaryFile(suffix = ".mpy", delete = False, delete_on_close = False)
            print(f"Compiling {source_module}.py...", end = "", flush = True)
            result = subprocess.run(["mpy-cross", full_src, "-O9", "-o", temp_mpy.name])
            if result.returncode != 0:
                raise ValueError(f"mpy-cross failed with status {result.returncode}")

            if not os.path.isfile(temp_mpy.name):
                raise ValueError(f"mpy-cross didn't actually output a file to {temp_mpy.name}")

            dst = f"{module_output_path}/lib/{source_module}.mpy"

            output_directory = pathlib.Path(dst).parent
            output_directory.mkdir(parents = True, exist_ok = True)

            print("deploying...", end = "", flush = True)
            shutil.copy(temp_mpy.name, dst)
            os.remove(temp_mpy.name)
            print("done")
        else:
            dst = f"{module_output_path}/lib/{source_module}.py"
            print(f"Copying {source_module}.py (not compiling)...", end = "", flush = True)
            shutil.copyfile(full_src, dst)
            print("done")

    return dst

args = parser.parse_args()

if args.build_release_zip:
    if args.output:
        print("Warning: --output has no effect when specifying --build-release-zip; a temp path will be used", file = sys.stderr)
    if args.modules:
        print("Warning: --modules has no effect when specifying --build-release-zip; all modules will be built", file = sys.stderr)
    if args.no_reboot:
        print("Warning: --no-reboot has no effect when specifying --build-release-zip; deployment won't go to device", file = sys.stderr)
    if args.clean:
        print("Warning: --clean has no effect when specifying --build-release-zip; deployment won't go to device", file = sys.stderr)
    if args.no_compile:
        print("Warning: --no-compile has no effect when specifying --build-release-zip; releases are always compiled", file = sys.stderr)

    args.output = tempfile.gettempdir()
    args.modules = None
    args.no_reboot = True
    args.clean = False
    args.no_compile = False

output_path = args.output or CIRCUITPY_PATH

if args.clean:
    clean(output_path)

zip_file = None
if args.build_release_zip:
    zip_file = zipfile.ZipFile(file = args.build_release_zip, mode = "w")

if args.modules:
    for module in args.modules:
        build_and_deploy(module, output_path, compile_to_mpy = not args.no_compile)
else:
    py_files = glob.glob("*.py", root_dir = get_base_path())
    for py_file in py_files:
        py_file = pathlib.Path(py_file).with_suffix("").name
        if py_file != "build-and-deploy" and not py_file.startswith("._"):
            output = build_and_deploy(py_file, output_path, compile_to_mpy = not args.no_compile)
            if zip_file is not None:
                zip_file.write(filename = output, arcname = os.path.relpath(output, output_path))

if zip_file is not None:
    zip_file.write("settings.toml.example", "settings.toml.example")
    zip_file.close()

if not args.no_reboot:
    print("Rebooting")
    reboot()

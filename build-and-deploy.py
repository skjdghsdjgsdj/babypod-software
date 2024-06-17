import argparse
import glob
import subprocess
from typing import Final
import shutil
import os
import pathlib
import tempfile

CIRCUITPY_PATH: Final = "/Volumes/CIRCUITPY"

parser = argparse.ArgumentParser(description = "Build and deploy CircuitPython files to ESP32")
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

def get_base_path():
    return os.path.abspath(os.path.dirname(__file__))

def reboot():
    ttys = glob.glob("/dev/tty.usbmodem*")
    if not ttys:
        raise ValueError("Couldn't find any device named /dev/tty.usbmodem*")

    if len(ttys) > 1:
        raise ValueError("Multiple devices named /dev/tty.usbmodem* found")

    tty = ttys[0]

    subprocess.Popen(f"expect -c \"send \003;\" > {tty}", shell = True).communicate()
    subprocess.Popen(f"expect -c \"send \004;\" > {tty}", shell = True).communicate()

def clean():
    lib = f"{CIRCUITPY_PATH}/lib"
    print(f"Purging everything from {lib}...", end = "", flush = True)
    shutil.rmtree(lib, ignore_errors = True)
    print("done")

    print(f"Re-initing {lib}...", end = "", flush = True)
    local_lib = get_base_path() + "/lib"
    shutil.copytree(local_lib, lib)
    print("done")

def build_and_deploy(source_module: str, compile_to_mpy: bool = True) -> str:
    if source_module == "code":
        print("Copying code.py...", end = "", flush = True)
        dst = f"{CIRCUITPY_PATH}/code.py"
        shutil.copyfile(get_base_path() + "/code.py", dst)
        print("done")
    else:
        full_src = get_base_path() + "/" + source_module + ".py"
        if not os.path.isfile(full_src):
            raise ValueError(f"File doesn't exist: {full_src}")

        if compile_to_mpy:
            temp_mpy = tempfile.NamedTemporaryFile(suffix = ".mpy")
            print(f"Compiling {source_module}.py...", end = "", flush = True)
            result = subprocess.run(["mpy-cross", full_src, "-O9", "-o", temp_mpy.name])
            if result.returncode != 0:
                raise ValueError(f"mpy-cross failed with status {result.returncode}")

            dst = f"{CIRCUITPY_PATH}/lib/{source_module}.mpy"

            print("deploying...", end = "", flush = True)
            shutil.move(temp_mpy.name, dst)
            print("done")
        else:
            dst = f"{CIRCUITPY_PATH}/lib/{source_module}.py"
            print(f"Copying {source_module}.py (not compiling)...", end = "", flush = True)
            shutil.copyfile(full_src, dst)
            print("done")

    return dst

args = parser.parse_args()

if args.clean:
    clean()

if args.modules:
    for module in args.modules:
        build_and_deploy(module, compile_to_mpy = not args.no_compile)
else:
    py_files = glob.glob("*.py", root_dir = get_base_path())
    for py_file in py_files:
        py_file = pathlib.Path(py_file).with_suffix("").name
        if py_file != "build-and-deploy" and not py_file.startswith("._"):
            build_and_deploy(py_file, compile_to_mpy = not args.no_compile)

if not args.no_reboot:
    print("Rebooting")
    reboot()
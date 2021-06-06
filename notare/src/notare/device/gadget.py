# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import contextlib
import io
import os
import pathlib
import subprocess

GADGET_CONFIG = pathlib.Path("/sys/kernel/config/usb_gadget")
GADGET_PATH = GADGET_CONFIG / "tabula"

UDC = pathlib.Path("/sys/class/udc")
FUNCTION_NAME = "ecm.usb0"

# These are reserved values belonging to OpenMoko for use in documentation.
# Replace with the real value when we get it.
VENDOR_ID = str(0x1D50)
PRODUCT_ID = str(0x5200)

# Locally-administered MAC addresses; randomly generated.
HOST_MAC_ADDR = "02:00:00:c1:c5:ab"
DEV_MAC_ADDR = "02:00:00:fb:a1:9b"

# Kobo serial number can be gotten from dd if=/dev/mmcblk0 bs=1 skip=515 count=13
# haven't seen this documented but it seems to always be 13 chars in that spot, on all tested kobos
def read_serial_number_from_device():
    with io.FileIO("/dev/mmcblk0", "r") as blk:
        blk.seek(515)
        return blk.read(13)


def read_serial_number():
    # Startup script may populate it
    if "SERIAL_NUMBER" in os.environ:
        return os.environ["SERIAL_NUMBER"].encode("ascii")
    return read_serial_number_from_device()


def code_version(*, major: int, minor: int, subminor: int):
    return "0x{:04X}".format(
        (major & 0xFF) << 8 | (minor & 0x0F) << 4 | subminor & 0x0F
    )


class Gadget(contextlib.AbstractContextManager):
    def __enter__(self):
        setup_gadget()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        teardown_gadget()


def setup_gadget():
    GADGET_PATH.mkdir()

    (GADGET_PATH / "idVendor").write_text(VENDOR_ID, encoding="ascii")
    (GADGET_PATH / "idProduct").write_text(PRODUCT_ID, encoding="ascii")
    # TODO: base this off the notare version number
    (GADGET_PATH / "bcdDevice").write_text(
        code_version(major=0, minor=1, subminor=0), encoding="ascii"
    )
    # USB version number
    (GADGET_PATH / "bcdUSB").write_text(
        code_version(major=2, minor=0, subminor=0), encoding="ascii"
    )

    strings_path = GADGET_PATH / "strings" / "0x409"
    strings_path.mkdir()
    (strings_path / "serialnumber").write_bytes(read_serial_number())
    (strings_path / "manufacturer").write_text("Straylight Labs", encoding="ascii")
    (strings_path / "product").write_text("Tabula", encoding="ascii")

    config_path = GADGET_PATH / "configs" / "c.1"
    config_path.mkdir()
    config_strings_path = config_path / "strings" / "0x409"
    config_strings_path.mkdir()
    (config_strings_path / "configuration").write_text(
        "Config 1: Tabula display", encoding="ascii"
    )

    # Only bus powered
    (config_path / "bmAttributes").write_bytes(str(0x80).encode("ascii"))
    (config_path / "MaxPower").write_bytes(str(250).encode("ascii"))

    function_path = GADGET_PATH / "functions" / FUNCTION_NAME
    function_path.mkdir()

    # https://www.kernel.org/doc/html/v5.4/usb/gadget-testing.html#ecm-function
    (function_path / "host_addr").write_bytes(HOST_MAC_ADDR.encode("ascii"))
    (function_path / "dev_addr").write_bytes(DEV_MAC_ADDR.encode("ascii"))

    (config_path / FUNCTION_NAME).symlink_to(function_path)

    # Enable gadget
    # ls /sys/class/udc > UDC
    udc_name = os.listdir(UDC)[0]
    (GADGET_PATH / "UDC").write_bytes(udc_name.encode("ascii"))

    # read ifname
    ifname = (function_path / "ifname").read_bytes().decode("ascii")
    # bring interface up
    # ifconfig $ifname 10.52.0.1 netmask 255.255.255.0
    subprocess.run(
        ["ifconfig", ifname, "10.52.0.1", "netmask", "255.255.255.0"], check=True
    )


def teardown_gadget():
    # take interface down
    (GADGET_PATH / "UDC").write_bytes(b"")

    config_path = GADGET_PATH / "configs" / "c.1"
    (config_path / FUNCTION_NAME).unlink()

    config_strings_path = config_path / "strings" / "0x409"
    config_strings_path.rmdir()
    config_path.rmdir()
    function_path = GADGET_PATH / "functions" / FUNCTION_NAME
    function_path.rmdir()
    strings_path = GADGET_PATH / "strings" / "0x409"
    strings_path.rmdir()
    GADGET_PATH.rmdir()

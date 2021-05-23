# SPDX-License-Identifier: GPL-3.0-or-later
import io
import pathlib

from .descriptors import descriptors, strings
from .mount import mount_ffs, umount_ffs

GADGET_CONFIG = pathlib.Path("/sys/kernel/config/usb_gadget")
GADGET_PATH = GADGET_CONFIG / "tabula"

UDC = pathlib.Path("/sys/class/udc")
MOUNTPOINT = pathlib.Path("/dev/tabula")

# These are reserved values belonging to OpenMoko for use in documentation.
# Replace with the real value when we get it.
VENDOR_ID = 0x1D50
PRODUCT_ID = 0x5200

# Kobo serial number from dd if=/dev/mmcblk0 bs=1 skip=515 count=13
# or /usr/local/Kobo/udev/usb gets it passed in as $SN. not sure how nickel gets it.
# but it seems to always be 13 chars in that spot, on all tested kobos
SERIALNUMBER = "N249111041699"
MANUFACTURER = "Straylight Labs"
PRODUCT = "Tabula"


def setup_gadget():
    GADGET_PATH.mkdir()

    (GADGET_PATH / "idVendor").write_bytes(str(VENDOR_ID).encode("ascii"))
    (GADGET_PATH / "idProduct").write_bytes(str(PRODUCT_ID).encode("ascii"))
    # binary-coded decimal, represents version 1.0.0
    (GADGET_PATH / "bcdDevice").write_bytes(str(0x0100).encode("ascii"))
    # USB2
    (GADGET_PATH / "bcdUSB").write_bytes(str(0x0200).encode("ascii"))

    strings_path = GADGET_PATH / "strings" / "0x409"
    strings_path.mkdir()
    (strings_path / "serialnumber").write_text(SERIALNUMBER, encoding="ascii")
    (strings_path / "manufacturer").write_text(MANUFACTURER, encoding="ascii")
    (strings_path / "product").write_text(PRODUCT, encoding="ascii")

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

    function_path = GADGET_PATH / "functions" / "ffs.usb0"
    function_path.mkdir()
    (config_path / "ffs.usb0").symlink_to(function_path)

    MOUNTPOINT.mkdir()

    # This name needs to match the second half of the function name.
    mount_ffs("usb0", MOUNTPOINT)

    ep0 = MOUNTPOINT / "ep0"

    ep0file = io.FileIO(bytes(ep0), "r+")
    ep0file.write(descriptors())
    ep0file.write(strings())
    return ep0file

    # # Enable gadget
    # ls /sys/class/udc > UDC


def teardown_gadget():
    # cd /sys/kernel/config/usb_gadget/tabula/
    # echo "" > UDC

    umount_ffs(MOUNTPOINT)
    MOUNTPOINT.rmdir()

    config_path = GADGET_PATH / "configs" / "c.1"
    (config_path / "ffs.usb0").unlink()

    config_strings_path = config_path / "strings" / "0x409"
    config_strings_path.rmdir()
    config_path.rmdir()
    function_path = GADGET_PATH / "functions" / "ffs.usb0"
    function_path.rmdir()
    strings_path = GADGET_PATH / "strings" / "0x409"
    strings_path.rmdir()
    GADGET_PATH.rmdir()

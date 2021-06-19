# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
from .ink import Ink, DeviceInfo


class DummyInk(Ink):
    def clear(self):
        print("clear")

    def get_device_info(self) -> DeviceInfo:
        return DeviceInfo(
            width=1, height=1, dpi=0, device_name="Dummy", code_name="Dummy"
        )

    def display_png(self, path: str, x: int, y: int):
        print("display_png: {} ({}, {})".format(path, x, y))

    def display_pixels(
        self, imagebytes: bytes, x: int, y: int, width: int, height: int
    ):
        print(
            "display_pixels: {} bytes, ({}, {}) {}x{}".format(
                len(imagebytes), x, y, width, height
            )
        )

    def save_screen(self) -> None:
        print("Saved")

    def restore_screen(self) -> None:
        print("Restored")

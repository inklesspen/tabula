# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib

from .ink import Ink


class DummyInk(contextlib.AbstractContextManager, Ink):
    def clear(self):
        print("clear")

    def display_pixels(
        self, imagebytes: bytes, x: int, y: int, width: int, height: int
    ):
        print(
            "display_pixels: {} bytes, ({}, {}) {}x{}".format(
                len(imagebytes), x, y, width, height
            )
        )

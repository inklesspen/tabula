# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import io
import contextlib

from ._fbink import ffi, lib
from .ink import Ink


class FbInk(contextlib.AbstractContextManager, Ink):
    def __init__(self):
        self.fbink_cfg = ffi.new("FBInkConfig *")

    def __enter__(self):
        self.fbfd = lib.fbink_open()
        lib.fbink_init(self.fbfd, self.fbink_cfg)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        lib.fbink_close(self.fbfd)
        self.fbfb = None

    def clear(self):
        lib.fbink_cls(self.fbfd, self.fbink_cfg, ffi.NULL)

    def display_pixels(
        self, imagebytes: bytes, x: int, y: int, width: int, height: int
    ):
        lib.fbink_print_raw_data(
            self.fbfd, imagebytes, width, height, len(imagebytes), x, y, self.fbink_cfg
        )

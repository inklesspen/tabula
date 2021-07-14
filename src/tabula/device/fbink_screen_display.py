# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib

from ._fbink import ffi, lib
from .types import ScreenInfo, ScreenRect


class FbInk(contextlib.AbstractContextManager):
    def __init__(self):
        self.fbink_cfg = ffi.new("FBInkConfig *")
        self.fbink_cfg.is_quiet = True
        self.screendump = None

    def __enter__(self):
        self.fbfd = lib.fbink_open()
        lib.fbink_init(self.fbfd, self.fbink_cfg)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        lib.fbink_close(self.fbfd)
        self.fbfb = None

    def get_screen_info(self) -> ScreenInfo:
        with ffi.new("FBInkState *") as state:
            lib.fbink_get_state(self.fbink_cfg, state)
            return ScreenInfo(
                width=state.view_width,
                height=state.view_height,
                dpi=state.screen_dpi,
            )

    def clear(self):
        lib.fbink_cls(self.fbfd, self.fbink_cfg, ffi.NULL)

    def display_pixels(self, imagebytes: bytes, rect: ScreenRect):
        lib.fbink_print_raw_data(
            self.fbfd,
            imagebytes,
            rect.width,
            rect.height,
            len(imagebytes),
            rect.x,
            rect.y,
            self.fbink_cfg,
        )

    def save_screen(self) -> None:
        self.screendump = ffi.new("FBInkDump *")
        lib.fbink_dump(self.fbfd, self.screendump)

    def restore_screen(self) -> None:
        if self.screendump is None:
            raise ValueError("Cannot restore screen; nothing saved.")
        with self.screendump:
            lib.fbink_restore(self.fbfd, self.fbink_cfg, self.screendump)
            lib.fbink_free_dump_data(self.screendump)
        self.screendump = None

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import enum

from ._fbink import ffi, lib as clib  # type: ignore
from ..commontypes import Size, Rect, ScreenInfo, TouchCoordinateTransform, ScreenRotation
from ..util import check_c_enum


# https://www.waveshare.net/w/upload/c/c4/E-paper-mode-declaration.pdf
@check_c_enum(ffi, "WFM_MODE_INDEX_E")
class WaveformMode(enum.IntEnum):
    AUTO = 0
    # direct update; b&w only, very fast
    DU = 1
    # The grayscale clearing (GC16) mode is used to update the full display and
    # provide a high image quality
    GC16 = 2
    GC4 = 3
    # The A2 mode is a fast, non-flash update mode designed for fast paging turning.
    A2 = 4
    # The GL16 waveform is primarily used to update sparse content on a white
    # background,  such as a page of anti-aliased text, with reduced flash. The
    # GL16 waveform has 16 unique gray levels.
    GL16 = 5
    # aka GLR16
    # The GLR16 mode is used in conjunction with an image preprocessing algorithm to
    # update sparse content on a white background with reduced flash and reduced
    # image artifacts.
    REAGL = 6
    # aka GLD16
    # The GLD16 mode is used in conjunction with an image preprocessing algorithm to
    # update sparse content on a white background with reduced flash and reduced
    # image artifacts.
    REAGLD = 7
    GC16_FAST = 8
    GL16_FAST = 9
    # The DU4 is a fast update time (similar to DU), non-flashy waveform. This mode
    # supports transitions from any gray tone to gray tones 1,6,11,16 represented by
    # pixel states [0 10 20 30]. The combination of fast update time and four gray tones
    # make it useful for anti-aliased text in menus.
    DU4 = 10
    GL4 = 11
    GL16_INV = 12
    GCK16 = 13
    GLKW16 = 14
    INIT = 15
    UNKNOWN = 16
    INIT2 = 17
    A2IN = 18
    A2OUT = 19
    GC16HQ = 20
    GS16 = 21
    GU16 = 22
    GLK16 = 23
    CLEAR = 24
    GC4L = 25
    GCC16 = 26
    GC16_PARTIAL = 27
    GCK16_PARTIAL = 28
    DUNM = 29
    P2SW = 30
    MAX = 255


TOUCH_COORDINATE_TRANSFORMS = (
    TouchCoordinateTransform.IDENTITY,
    TouchCoordinateTransform.SWAP_AND_MIRROR_Y,
    TouchCoordinateTransform.MIRROR_X_AND_MIRROR_Y,
    TouchCoordinateTransform.SWAP_AND_MIRROR_X,
)


class FbInk(contextlib.AbstractContextManager):
    def __init__(self):
        self.fbink_cfg = ffi.new("FBInkConfig *")
        self.fbink_cfg.is_quiet = True
        self.screendump = None

    def __enter__(self):
        self.fbfd = clib.fbink_open()
        clib.fbink_init(self.fbfd, self.fbink_cfg)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        clib.fbink_close(self.fbfd)
        self.fbfb = None

    @property
    def active(self):
        return self.fbfd is not None

    def get_screen_info(self) -> ScreenInfo:
        with ffi.new("FBInkState *") as state:
            clib.fbink_get_state(self.fbink_cfg, state)
            touch_coordinate_transform = TOUCH_COORDINATE_TRANSFORMS[state.current_rota]
            return ScreenInfo(
                size=Size(width=state.view_width, height=state.view_height),
                dpi=state.screen_dpi,
                rotation=ScreenRotation.PORTRAIT,
                touch_coordinate_transform=touch_coordinate_transform,
            )

    def clear(self):
        clib.fbink_cls(self.fbfd, self.fbink_cfg, ffi.NULL, False)

    def display_pixels(self, imagebytes: bytes, rect: Rect):
        clib.fbink_print_raw_data(
            self.fbfd,
            imagebytes,
            rect.spread.width,
            rect.spread.height,
            len(imagebytes),
            rect.origin.x,
            rect.origin.y,
            self.fbink_cfg,
        )

    def save_screen(self) -> None:
        self.screendump = ffi.new("FBInkDump *")
        clib.fbink_dump(self.fbfd, self.screendump)

    def restore_screen(self) -> None:
        if self.screendump is None:
            raise ValueError("Cannot restore screen; nothing saved.")
        with self.screendump:
            clib.fbink_restore(self.fbfd, self.fbink_cfg, self.screendump)
            clib.fbink_free_dump_data(self.screendump)
        self.screendump = None

    def set_waveform_mode(self, wfm_mode: str):
        self.fbink_cfg.wfm_mode = WaveformMode[wfm_mode]

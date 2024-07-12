# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import enum
import errno
import logging

from ._fbink import ffi, lib as clib  # type: ignore
from ..commontypes import Size, Rect, ScreenInfo, TouchCoordinateTransform, ScreenRotation
from ..util import check_c_enum

logger = logging.getLogger(__name__)


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


class KoboRota(enum.IntEnum):
    PORTRAIT_UPRIGHT = clib.FORCE_ROTA_UR  # native_rota: 3, canonical_rota: 0
    LANDSCAPE_CCW = clib.FORCE_ROTA_CCW  # native_rota: 0, canonical_rota: 3
    PORTRAIT_UPSIDE_DOWN = clib.FORCE_ROTA_UD  # native_rota: 1, canonical_rota: 2
    LANDSCAPE_CW = clib.FORCE_ROTA_CW  # native_rota: 2, canonical_rota: 1

    @classmethod
    def from_screen_rotation(cls, sr: ScreenRotation):
        match sr:
            case ScreenRotation.PORTRAIT:
                return cls.PORTRAIT_UPRIGHT
            case ScreenRotation.INVERTED_PORTRAIT:
                return cls.PORTRAIT_UPSIDE_DOWN
            case ScreenRotation.LANDSCAPE_PORT_LEFT:
                return cls.LANDSCAPE_CW
            case ScreenRotation.LANDSCAPE_PORT_RIGHT:
                return cls.LANDSCAPE_CCW

    def to_screen_rotation(self):
        match self:
            case KoboRota.PORTRAIT_UPRIGHT:
                return ScreenRotation.PORTRAIT
            case KoboRota.LANDSCAPE_CCW:
                return ScreenRotation.LANDSCAPE_PORT_RIGHT
            case KoboRota.PORTRAIT_UPSIDE_DOWN:
                return ScreenRotation.INVERTED_PORTRAIT
            case KoboRota.LANDSCAPE_CW:
                return ScreenRotation.LANDSCAPE_PORT_LEFT

    def touch_coordinate_transform(self):
        match self:
            case KoboRota.PORTRAIT_UPRIGHT:
                return TouchCoordinateTransform.SWAP_AND_MIRROR_X
            case KoboRota.LANDSCAPE_CCW:
                return TouchCoordinateTransform.IDENTITY
            case KoboRota.PORTRAIT_UPSIDE_DOWN:
                return TouchCoordinateTransform.SWAP_AND_MIRROR_Y
            case KoboRota.LANDSCAPE_CW:
                return TouchCoordinateTransform.MIRROR_X_AND_MIRROR_Y


TOUCH_COORDINATE_TRANSFORMS = (
    TouchCoordinateTransform.IDENTITY,  # native_rota 0
    TouchCoordinateTransform.SWAP_AND_MIRROR_Y,  # native_rota 1
    TouchCoordinateTransform.MIRROR_X_AND_MIRROR_Y,  # native_rota 2
    TouchCoordinateTransform.SWAP_AND_MIRROR_X,  # native_rota 3
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
            canonical_rota = KoboRota(clib.fbink_rota_native_to_canonical(state.current_rota))
            # https://github.com/NiLuJe/FBInk/blob/master/utils/finger_trace.c#L502-L534
            touch_coordinate_transform = TOUCH_COORDINATE_TRANSFORMS[state.current_rota]
            if touch_coordinate_transform != canonical_rota.touch_coordinate_transform():
                raise Exception("something's gone wrong with tcts")

            logger.debug("Screen rotation: %r", canonical_rota)
            logger.debug("Touch Coordinate Transform: %r", touch_coordinate_transform)

            # These are in FBInk master branch but not in release 1.25.0
            # swap_axes = state.touch_swap_axes
            # mirror_x = state.touch_mirror_x
            # mirror_y = state.touch_mirror_y
            # logger.debug("before adjustment: touch_swap_axes: %r", swap_axes)
            # logger.debug("before adjustment: touch_mirror_x: %r", mirror_x)
            # logger.debug("before adjustment: touch_mirror_y: %r", mirror_y)
            # match canonical_rota:
            #     case KoboRota.LANDSCAPE_CW:
            #         swap_axes = not swap_axes
            #         mirror_y = not mirror_y
            #     case KoboRota.PORTRAIT_UPSIDE_DOWN:
            #         mirror_x = not mirror_x
            #         mirror_y = not mirror_y
            #     case KoboRota.LANDSCAPE_CCW:
            #         swap_axes = not swap_axes
            #         mirror_x = not mirror_x

            # logger.debug("after adjustment: touch_swap_axes: %r", swap_axes)
            # logger.debug("after adjustment: touch_mirror_x: %r", mirror_x)
            # logger.debug("after adjustment: touch_mirror_y: %r", mirror_y)

            return ScreenInfo(
                size=Size(width=state.view_width, height=state.view_height),
                dpi=state.screen_dpi,
                rotation=canonical_rota.to_screen_rotation(),
                touch_coordinate_transform=touch_coordinate_transform,
            )

    def set_rotation(self, sr: ScreenRotation):
        native_rota = clib.fbink_rota_canonical_to_native(KoboRota.from_screen_rotation(sr))
        code = clib.fbink_set_fb_info(self.fbfd, native_rota, clib.KEEP_CURRENT_BITDEPTH, clib.KEEP_CURRENT_GRAYSCALE, self.fbink_cfg)
        if code == errno.ENODEV:
            raise Exception("device not initialized; this should never happen")
        if code == errno.EINVAL:
            raise ValueError("invalid argument")
        if code == errno.ECANCELED:
            raise Exception("ioctl failure; re-init recommended")

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

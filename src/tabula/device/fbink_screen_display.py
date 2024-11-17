# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import contextlib
import enum
import errno
import logging
import typing

from ..commontypes import NotInContextError, Rect, ScreenInfo, ScreenRotation, Size, TouchCoordinateTransform
from ..util import check_c_enum
from ._fbink import ffi, lib  # type: ignore
from .hwtypes import DisplayUpdateMode, HardwareError

logger = logging.getLogger(__name__)


class FBInkError(HardwareError):
    pass


# https://www.waveshare.net/w/upload/c/c4/E-paper-mode-declaration.pdf
# also see notes at https://github.com/NiLuJe/FBInk/blob/master/fbink.h#L354
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
    PORTRAIT_UPRIGHT = lib.FORCE_ROTA_UR  # native_rota: 3, canonical_rota: 0
    LANDSCAPE_CCW = lib.FORCE_ROTA_CCW  # native_rota: 0, canonical_rota: 3
    PORTRAIT_UPSIDE_DOWN = lib.FORCE_ROTA_UD  # native_rota: 1, canonical_rota: 2
    LANDSCAPE_CW = lib.FORCE_ROTA_CW  # native_rota: 2, canonical_rota: 1

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

DISPLAY_UPDATE_MODES = {  # This may need to be kobo-model dependent
    DisplayUpdateMode.AUTO: WaveformMode.AUTO,
    DisplayUpdateMode.RAPID: WaveformMode.GC4,
    DisplayUpdateMode.FIDELITY: WaveformMode.REAGL,  # TODO: try using GC16 for FIDELITY
}


BitDepth = typing.Optional[typing.Literal[4, 8, 16, 32]]  # None for KEEP_CURRENT_BITDEPTH


class FbInk(contextlib.AbstractContextManager):
    def __init__(self):
        self.display_update_mode = DisplayUpdateMode.AUTO
        self.fbink_cfg = ffi.new("FBInkConfig *")
        self.fbink_cfg.is_quiet = True
        self.fbink_cfg.ignore_alpha = True
        self.fbink_cfg.wfm_mode = DISPLAY_UPDATE_MODES[self.display_update_mode]
        self.fbfd = None

    def __enter__(self):
        self.fbfd = lib.fbink_open()
        lib.fbink_init(self.fbfd, self.fbink_cfg)
        self.set_bitdepth(8)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        lib.fbink_close(self.fbfd)
        self.fbfb = None

    @property
    def active(self):
        return self.fbfd is not None

    def set_bitdepth(self, depth: BitDepth, set_grayscale=True):
        if not self.active:
            raise NotInContextError()
        if depth is None:
            depth = lib.KEEP_CURRENT_BITDEPTH
        # #define GRAYSCALE_8BIT          0x1
        grayscale = 1 if set_grayscale else lib.KEEP_CURRENT_GRAYSCALE
        code = lib.fbink_set_fb_info(self.fbfd, lib.KEEP_CURRENT_ROTATE, depth, grayscale, self.fbink_cfg)
        if code == errno.ENODEV:
            raise FBInkError("device not initialized; this should never happen")
        if code == errno.EINVAL:
            raise ValueError("invalid argument")
        if code == errno.ECANCELED:
            raise FBInkError("ioctl failure; re-init recommended")

    def get_screen_info(self) -> ScreenInfo:
        with ffi.new("FBInkState *") as state:
            lib.fbink_get_state(self.fbink_cfg, state)
            canonical_rota = KoboRota(lib.fbink_rota_native_to_canonical(state.current_rota))
            # https://github.com/NiLuJe/FBInk/blob/master/utils/finger_trace.c#L502-L534
            touch_coordinate_transform = TOUCH_COORDINATE_TRANSFORMS[state.current_rota]
            if touch_coordinate_transform != canonical_rota.touch_coordinate_transform():
                raise FBInkError("something's gone wrong with tcts")

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
        if not self.active:
            raise NotInContextError()
        native_rota = lib.fbink_rota_canonical_to_native(KoboRota.from_screen_rotation(sr))
        code = lib.fbink_set_fb_info(self.fbfd, native_rota, lib.KEEP_CURRENT_BITDEPTH, lib.KEEP_CURRENT_GRAYSCALE, self.fbink_cfg)
        if code == errno.ENODEV:
            raise FBInkError("device not initialized; this should never happen")
        if code == errno.EINVAL:
            raise ValueError("invalid argument")
        if code == errno.ECANCELED:
            raise FBInkError("ioctl failure; re-init recommended")

    def clear(self):
        lib.fbink_cls(self.fbfd, self.fbink_cfg, ffi.NULL, False)

    def display_pixels(self, imagebytes: bytes, rect: Rect):
        lib.fbink_print_raw_data(
            self.fbfd,
            imagebytes,
            int_coord(rect.spread.width),
            int_coord(rect.spread.height),
            len(imagebytes),
            int_coord(rect.origin.x),
            int_coord(rect.origin.y),
            self.fbink_cfg,
        )

    def set_display_update_mode(self, mode: DisplayUpdateMode):
        self.display_update_mode = mode
        self.fbink_cfg.wfm_mode = DISPLAY_UPDATE_MODES.get(mode, WaveformMode.AUTO)

    @contextlib.contextmanager
    def display_update_mode(self, mode: DisplayUpdateMode):
        initial_mode = self.display_update_mode
        self.set_display_update_mode(mode)
        yield
        self.set_display_update_mode(initial_mode)

    def set_waveform_mode(self, wfm_mode: str):
        self.fbink_cfg.wfm_mode = WaveformMode[wfm_mode]

    def emergency_print(self, message: str):
        # only use this if we're about to shut down; it makes no attempt to clean up after itself.
        cmanager = contextlib.nullcontext(self) if self.active else self
        with cmanager:
            self.fbink_cfg.is_cleared = True
            self.fbink_cfg.is_centered = True
            self.fbink_cfg.is_halfway = True
            lib.fbink_print(self.fbfd, message.encode("utf-8"), self.fbink_cfg)


def int_coord(maybeint):
    actuallyint = round(maybeint)
    if actuallyint != maybeint:
        logger.warning("Got a non-integer rendering coordinate %r", maybeint, stack_info=True)
    return actuallyint

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import enum

import msgspec

from ..commontypes import Rect
from ..util import check_c_enum
from ._cairopango import ffi, lib  # type: ignore


@check_c_enum(ffi, "cairo_hint_style_t", AUTO=lib.CAIRO_HINT_STYLE_SLIGHT)
class HintMode(enum.IntEnum):
    DEFAULT = 0
    NONE = 1
    SLIGHT = 2
    MEDIUM = 3
    FULL = 4
    AUTO = SLIGHT


@check_c_enum(ffi, "cairo_subpixel_order_t")
class SubpixelOrder(enum.IntEnum):
    DEFAULT = 0
    RGB = 1
    BGR = 2
    VRGB = 3
    VBGR = 4


@check_c_enum(ffi, "cairo_antialias_t")
class Antialias(enum.IntEnum):
    DEFAULT = 0
    NONE = 1
    GRAY = 2
    SUBPIXEL = 3
    FAST = 4
    GOOD = 5
    BEST = 6


@check_c_enum(ffi, "cairo_hint_metrics_t")
class HintMetrics(enum.IntEnum):
    DEFAULT = 0
    OFF = 1
    ON = 2


@check_c_enum(ffi, "PangoWrapMode")
class WrapMode(enum.IntEnum):
    WORD = 0
    CHAR = 1
    WORD_CHAR = 2


@check_c_enum(ffi, "PangoAlignment")
class Alignment(enum.IntEnum):
    LEFT = 0
    CENTER = 1
    RIGHT = 2


@check_c_enum(ffi, "cairo_status_t")
class CairoStatus(enum.IntEnum):
    SUCCESS = 0
    NO_MEMORY = 1
    INVALID_RESTORE = 2
    INVALID_POP_GROUP = 3
    NO_CURRENT_POINT = 4
    INVALID_MATRIX = 5
    INVALID_STATUS = 6
    NULL_POINTER = 7
    INVALID_STRING = 8
    INVALID_PATH_DATA = 9
    READ_ERROR = 10
    WRITE_ERROR = 11
    SURFACE_FINISHED = 12
    SURFACE_TYPE_MISMATCH = 13
    PATTERN_TYPE_MISMATCH = 14
    INVALID_CONTENT = 15
    INVALID_FORMAT = 16
    INVALID_VISUAL = 17
    FILE_NOT_FOUND = 18
    INVALID_DASH = 19
    INVALID_DSC_COMMENT = 20
    INVALID_INDEX = 21
    CLIP_NOT_REPRESENTABLE = 22
    TEMP_FILE_ERROR = 23
    INVALID_STRIDE = 24
    FONT_TYPE_MISMATCH = 25
    USER_FONT_IMMUTABLE = 26
    USER_FONT_ERROR = 27
    NEGATIVE_COUNT = 28
    INVALID_CLUSTERS = 29
    INVALID_SLANT = 30
    INVALID_WEIGHT = 31
    INVALID_SIZE = 32
    USER_FONT_NOT_IMPLEMENTED = 33
    DEVICE_TYPE_MISMATCH = 34
    DEVICE_ERROR = 35
    INVALID_MESH_CONSTRUCTION = 36
    DEVICE_FINISHED = 37
    JBIG2_GLOBAL_MISSING = 38
    PNG_ERROR = 39
    FREETYPE_ERROR = 40
    WIN32_GDI_ERROR = 41
    TAG_ERROR = 42
    LAST_STATUS = 45


class AffineTransform(msgspec.Struct, frozen=True):
    # Both Cairo and Pango represent affine transforms as 6-tuples
    # https://www.cairographics.org/manual/cairo-cairo-matrix-t.html
    # https://docs.gtk.org/Pango/struct.Matrix.html
    xx: float
    xy: float
    yx: float
    yy: float
    x0: float
    y0: float

    @classmethod
    def identity(cls):
        return cls(xx=1, xy=0, yx=0, yy=1, x0=0, y0=0)

    @classmethod
    def translation(cls, tx: float, ty: float):
        return cls(xx=1, xy=0, yx=0, yy=1, x0=tx, y0=ty)


class Rendered(msgspec.Struct, frozen=True):
    image: bytes
    extent: Rect


class Margins(msgspec.Struct, frozen=True):
    top: int
    bottom: int
    left: int
    right: int


class CairoOp(enum.Enum):
    STROKE = enum.auto()
    FILL = enum.auto()


class CairoColor(enum.IntEnum):
    WHITE = 1
    BLACK = 0


class CairoPathOp(msgspec.Struct, frozen=True):
    op: CairoOp
    color: CairoColor


class LayoutRects(msgspec.Struct, frozen=True):
    ink: Rect
    logical: Rect

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import enum
from os.path import commonprefix
import typing

import msgspec

from ._cairopango import ffi, lib as clib
from tabula.rebuild.commontypes import Point, Size, Rect, ScreenInfo


def _c_enum(enum_t: str, python_name: str, **extras: int) -> typing.Type[enum.IntEnum]:
    ctype = ffi.typeof(enum_t)
    prefix = commonprefix(tuple(ctype.relements.keys()))
    values: dict[str, int] = {
        k.removeprefix(prefix): v for v, k in sorted(ctype.elements.items())
    }
    values.update(extras)
    return enum.IntEnum(python_name, values)


HintMode = _c_enum("cairo_hint_style_t", "HintMode", AUTO=clib.CAIRO_HINT_STYLE_SLIGHT)

SubpixelOrder = _c_enum("cairo_subpixel_order_t", "SubpixelOrder")

Antialias = _c_enum("cairo_antialias_t", "Antialias")

HintMetrics = _c_enum("cairo_hint_metrics_t", "HintMetrics")

WrapMode = _c_enum("PangoWrapMode", "WrapMode")

Alignment = _c_enum("PangoAlignment", "Alignment")


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


class Opts(msgspec.Struct):
    dpi: float = 96.0
    hinting: HintMode = HintMode.DEFAULT
    hint_metrics: HintMetrics = HintMetrics.DEFAULT
    subpixel_order: SubpixelOrder = SubpixelOrder.DEFAULT
    antialias: Antialias = Antialias.DEFAULT
    screen_size: Size = Size(width=0, height=0)


class RenderOpts(msgspec.Struct):
    font: str = ""
    text: str = ""
    markup: bool = False
    draw_border: bool = False
    justify: bool = False
    alignment: Alignment = Alignment.LEFT
    single_par: bool = False
    wrap: WrapMode = WrapMode.WORD_CHAR
    margin_t: int = 10
    margin_r: int = 10
    margin_b: int = 10
    margin_l: int = 10
    clear_before_render: bool = True

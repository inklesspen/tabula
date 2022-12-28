# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import attr
import enum
import os.path
import typing

from ._cairopango import ffi, lib as clib


def _c_enum(enum_t: str, python_name: str, **extras: int) -> typing.Type[enum.IntEnum]:
    ctype = ffi.typeof(enum_t)
    prefix = os.path.commonprefix(tuple(ctype.relements.keys()))
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


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Point:
    x: int
    y: int


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Size:
    width: int
    height: int

    def total(self):
        return self.width * self.height

    def as_tuple(self):
        return (self.width, self.height)

    def as_numpy_shape(self):
        return (self.height, self.width)

    @classmethod
    def from_tuple(cls, tup):
        return cls(width=tup[0], height=tup[1])

    @classmethod
    def from_numpy_shape(cls, shape):
        return cls(height=shape[0], width=shape[1])


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Rect:
    origin: Point
    spread: Size

    def as_pillow_box(self):
        return (
            self.origin.x,
            self.origin.y,
            self.origin.x + self.spread.width,
            self.origin.y + self.spread.height,
        )


@attr.s(auto_attribs=True)
class Opts:
    dpi: float = 96.0
    hinting: HintMode = HintMode.DEFAULT
    hint_metrics: HintMetrics = HintMetrics.DEFAULT
    subpixel_order: SubpixelOrder = SubpixelOrder.DEFAULT
    antialias: Antialias = Antialias.DEFAULT
    screen_size: Size = Size(width=0, height=0)


@attr.s(auto_attribs=True)
class RenderOpts:
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

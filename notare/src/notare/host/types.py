# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import enum

import attr

import stilus.types

from ..protocol import (
    Rect,
)


class UpdateKind(enum.Enum):
    NEW = enum.auto()
    CHANGE = enum.auto()


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class ParagraphUpdate:
    paragraph: int
    kind: UpdateKind


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Renderable:
    paragraph: int
    has_cursor: bool


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class ArrayRect:
    top: int
    bottom: int
    left: int
    right: int

    def to_protocol_rect(self, y_adjust: int = 0) -> Rect:
        return Rect(
            x=self.left,
            y=self.top + y_adjust,
            width=self.right - self.left,
            height=self.bottom - self.top,
        )

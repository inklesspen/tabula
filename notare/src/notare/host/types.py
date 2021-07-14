# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import enum
import typing

import attr
import timeflake

from stilus.types import Size
from stilus.markdown import make_markup

from ..protocol import Rect, DeviceInfo


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Session:
    id: timeflake.Timeflake
    started_on: datetime.date
    updated_at: datetime.datetime
    exported_at: typing.Optional[datetime.datetime] = attr.ib(default=None)
    wordcount: int = attr.ib(default=0)

    @property
    def needs_export(self):
        return self.exported_at is None or self.exported_at < self.updated_at


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Paragraph:
    id: timeflake.Timeflake
    session_id: timeflake.Timeflake
    index: int
    sprint_id: typing.Optional[timeflake.Timeflake] = attr.ib(default=None)
    markdown: str = attr.ib(repr=False, cmp=False)
    markup: str = attr.ib(repr=False, cmp=False, init=False)

    @markup.default
    def _init_markup(self):
        return make_markup(self.markdown)

    def evolve(self, markdown: str):
        return attr.evolve(self, markdown=markdown)

    def to_db_dict(self):
        return attr.asdict(
            self, filter=attr.filters.exclude(attr.fields(Paragraph).markup)
        )

    # def enter_sprint(self, sprint_id: timeflake.Timeflake):
    #     if len(self.markdown) > 0:
    #         raise ValueError("Cannot enter sprint mid-paragraph")
    #     return attr.evolve(self, sprint_id=sprint_id)

    # def leave_sprint(self):
    #     if len(self.markdown) > 0:
    #         raise ValueError("Cannot leave sprint mid-paragraph")
    #     return attr.evolve(self, sprint_id=None)


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Renderable:
    index: int
    markup: str
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


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class ScreenInfo:
    screen_size: Size
    dpi: int

    @classmethod
    def from_device_info(cls, device_info: DeviceInfo):
        return ScreenInfo(
            screen_size=Size(width=device_info.width, height=device_info.height),
            dpi=device_info.dpi,
        )


class EditorMode(enum.Enum):
    DRAFT = enum.auto()
    COMMAND = enum.auto()
    DISPLAY = enum.auto()

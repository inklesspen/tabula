# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import enum
import typing

import attr
import timeflake

from ..device.keyboard_consts import Key, KeyPress
from ..rendering.markdown import make_markup


# stage 1: track modifier keydown/up and annotate keystream with current modifiers
@attr.frozen(kw_only=True)
class ModifierAnnotation:
    alt: bool = attr.field(default=False)
    ctrl: bool = attr.field(default=False)
    meta: bool = attr.field(default=False)
    shift: bool = attr.field(default=False)
    capslock: bool = attr.field(default=False)


@attr.frozen(kw_only=True)
class AnnotatedKeyEvent:
    key: Key
    press: KeyPress
    annotation: ModifierAnnotation
    character: typing.Optional[str] = attr.field(default=None)
    is_modifier: bool = attr.field(default=False)


@attr.frozen(kw_only=True)
class Session:
    id: timeflake.Timeflake
    started_on: datetime.date
    updated_at: datetime.datetime
    exported_at: typing.Optional[datetime.datetime] = attr.field(default=None)
    wordcount: int = attr.field(default=0)

    @property
    def needs_export(self):
        return self.exported_at is None or self.exported_at < self.updated_at


@attr.frozen(kw_only=True)
class Paragraph:
    id: timeflake.Timeflake
    session_id: timeflake.Timeflake
    index: int
    sprint_id: typing.Optional[timeflake.Timeflake] = attr.field(default=None)
    markdown: str = attr.field(repr=False, eq=False, order=False)
    markup: str = attr.field(repr=False, eq=False, order=False, init=False)

    @markup.default
    def _init_markup(self):
        return make_markup(self.markdown)

    def evolve(self, markdown: str):
        return attr.evolve(self, markdown=markdown)

    def to_db_dict(self):
        return attr.asdict(
            self, filter=attr.filters.exclude(attr.fields(Paragraph).markup)
        )

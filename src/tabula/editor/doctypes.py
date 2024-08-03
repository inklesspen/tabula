import datetime
import typing

import attrs
import msgspec
import timeflake
from attrs import define, field

from ..rendering.markup import make_markup
from ..util import now


class Session(msgspec.Struct, kw_only=True, frozen=True):
    id: timeflake.Timeflake
    started_on: datetime.date
    updated_at: datetime.datetime
    exported_at: typing.Optional[datetime.datetime] = None
    wordcount: int = 0

    @property
    def needs_export(self):
        return self.exported_at is None or self.exported_at < self.updated_at


class Sprint(msgspec.Struct, kw_only=True, frozen=True):
    id: timeflake.Timeflake
    session_id: timeflake.Timeflake
    started_at: datetime.datetime
    intended_duration: datetime.timedelta
    ended_at: typing.Optional[datetime.datetime] = None
    wordcount: int = 0

    @property
    def elapsed(self):
        return now() - self.started_at

    @property
    def remaining(self):
        return self.intended_duration - self.elapsed

    @property
    def actual_duration(self):
        if self.ended_at is None:
            return self.elapsed
        return self.ended_at - self.started_at

    @property
    def completed(self):
        return self.elapsed >= self.intended_duration


@define(kw_only=True, frozen=True)
class Paragraph:
    id: timeflake.Timeflake
    session_id: timeflake.Timeflake
    index: int
    sprint_id: typing.Optional[timeflake.Timeflake] = field(default=None)
    markdown: str = field(repr=False, eq=False, order=False)
    markup: str = field(repr=False, eq=False, order=False, init=False)

    @markup.default
    def _init_markup(self):
        return make_markup(self.markdown)

    def evolve(self, markdown: str):
        return attrs.evolve(self, markdown=markdown)

    def to_db_dict(self):
        return attrs.asdict(self, filter=attrs.filters.exclude(attrs.fields(Paragraph).markup))

import datetime
import typing

from attrs import define, field
import attrs
import timeflake

from ..rendering.markdown import make_markup
from ..util import now


@define(kw_only=True, frozen=True)
class Session:
    id: timeflake.Timeflake
    started_on: datetime.date
    updated_at: datetime.datetime
    exported_at: typing.Optional[datetime.datetime] = field(default=None)
    wordcount: int = field(default=0)

    @property
    def needs_export(self):
        return self.exported_at is None or self.exported_at < self.updated_at


@define(kw_only=True, frozen=True)
class Sprint:
    id: timeflake.Timeflake
    session_id: timeflake.Timeflake
    started_at: datetime.datetime
    intended_duration: datetime.timedelta
    ended_at: typing.Optional[datetime.datetime] = field(default=None)
    wordcount: int = field(default=0)

    @property
    def elapsed(self):
        return now() - self.started_at

    @property
    def remaining(self):
        return self.intended_duration - self.elapsed


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

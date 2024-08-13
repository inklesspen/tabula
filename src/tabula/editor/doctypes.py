import datetime
import typing

import msgspec
import timeflake

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


class Paragraph(msgspec.Struct, kw_only=True):
    id: timeflake.Timeflake
    session_id: timeflake.Timeflake
    index: int
    sprint_id: typing.Optional[timeflake.Timeflake] = None
    markdown: str

    def __setattr__(self, name: str, value: typing.Any) -> None:
        if name != "markdown":
            raise AttributeError(f"The field {name!r} cannot be modified.")
        return super().__setattr__(name, value)

    def is_comment(self):
        # a paragraph is comment material (and therefore doesn't contribute to wordcount) if the first character is a #
        return bool(self.markdown and self.markdown[0] == "#")

    def to_db_dict(self):
        return msgspec.structs.asdict(self)

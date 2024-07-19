# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import datetime
import pathlib

import timeflake
from dateutil.tz import tzlocal
from sqlalchemy import (
    Column,
    ForeignKey,
    MetaData,
    Table,
    UniqueConstraint,
    event,
    null,
    or_,
    select,
)
from sqlalchemy.dialects.sqlite import CHAR, DATE, DATETIME, insert
from sqlalchemy.engine import URL as EngineURL
from sqlalchemy.engine import Connectable, Engine, create_engine
from sqlalchemy.sql import column, text
from sqlalchemy.types import Integer, String, TypeDecorator, UnicodeText

from .durations import format_duration, parse_duration
from .editor.doctypes import Paragraph, Session, Sprint
from .util import now


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA locking_mode=EXCLUSIVE")
    cursor.close()


class Timeflake(TypeDecorator):
    """
    A 128-bit, roughly-ordered, URL-safe UUID.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CHAR(22))

    def process_bind_param(self, value, dialect):
        if isinstance(value, timeflake.Timeflake):
            return value.base62
        return value

    def process_result_value(self, value, dialect):
        if isinstance(value, str):
            return timeflake.parse(from_base62=value)
        return value

    def __repr__(self):
        return "Timeflake()"

    @classmethod
    def generate(cls):
        return timeflake.random()


class AwareDateTime(TypeDecorator):
    """
    A DateTime type which can only store tz-aware DateTimes
    """

    impl = DATETIME

    def process_bind_param(self, value, dialect):
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                raise ValueError("{!r} must be TZ-aware".format(value))
            else:
                value = value.astimezone(datetime.timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if isinstance(value, datetime.datetime):
            value = value.replace(tzinfo=datetime.timezone.utc).astimezone(tzlocal())
        return value

    def __repr__(self):
        return "AwareDateTime()"


class Duration(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return format_duration(value)

    def process_result_value(self, value, dialect):
        return parse_duration(value)

    def __repr__(self):
        return "Duration()"


metadata = MetaData()

session_table = Table(
    "sessions",
    metadata,
    Column("id", Timeflake, primary_key=True),
    Column("started_on", DATE, nullable=False, index=True),
    Column("updated_at", AwareDateTime, nullable=False, index=True),
    Column("exported_at", AwareDateTime, nullable=True, index=True),
    Column("wordcount", Integer, nullable=True),
)

sprint_table = Table(
    "sprints",
    metadata,
    Column("id", Timeflake, primary_key=True),
    Column("session_id", ForeignKey("sessions.id"), nullable=False, index=True),
    Column("duration", Duration, nullable=False),
    Column("wordcount", Integer, nullable=True),
    Column("started_at", AwareDateTime, nullable=False),
    Column("ended_at", AwareDateTime, nullable=True),
)

paragraph_table = Table(
    "paragraphs",
    metadata,
    Column("id", Timeflake, primary_key=True),
    Column("session_id", ForeignKey("sessions.id"), nullable=False, index=True),
    Column("index", Integer, nullable=False, index=True),
    UniqueConstraint("session_id", "index"),
    Column("sprint_id", ForeignKey("sprints.id"), nullable=True),
    Column("markdown", UnicodeText, nullable=False),
)

DB_VERSION = 1


class DbVersionError(Exception):
    pass


def check_version(conn: Connectable, path: pathlib.Path, expected_version: int):
    found_version = conn.scalar(text("PRAGMA user_version").columns(column("version", Integer)))
    if found_version != expected_version:
        raise DbVersionError(f"Expected DB version {expected_version} in {path}, but found {found_version}.")


def set_version(conn: Connectable, version: int):
    # looks like pragma does not support bindparams, hence the f-string
    conn.execute(text(f"PRAGMA user_version = {version}"))


def make_db(sqlite_path: pathlib.Path):
    exists = sqlite_path.is_file()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    engine_url = EngineURL.create(drivername="sqlite", database=sqlite_path.__fspath__())
    engine = create_engine(engine_url, future=True)
    with engine.begin() as conn:
        if exists:
            check_version(conn, sqlite_path, DB_VERSION)
        else:
            metadata.create_all(conn)
            set_version(conn, DB_VERSION)
    return TabulaDb(engine)


class TabulaDb:
    def __init__(self, engine: Engine):
        self.engine = engine

    def new_session(self) -> timeflake.Timeflake:
        session_id = Timeflake.generate()
        timestamp = now()

        with self.engine.begin() as conn:
            conn.execute(
                session_table.insert().values(
                    id=session_id,
                    started_on=timestamp.date(),
                    updated_at=timestamp,
                    exported_at=None,
                    wordcount=0,
                )
            )
            conn.execute(paragraph_table.insert().values(id=Timeflake.generate(), session_id=session_id, index=0, markdown=""))

        return session_id

    def list_sessions(self, limit=None, only_exportable=False):
        s = select(session_table).order_by(session_table.c.id.desc())
        if limit is not None:
            s = s.limit(limit)
        if only_exportable:
            s = s.where(
                or_(
                    session_table.c.exported_at == null(),
                    session_table.c.exported_at < session_table.c.updated_at,
                )
            )
        with self.engine.begin() as conn:
            result = conn.execute(s)
            return [Session(**row._mapping) for row in result]

    def load_session_paragraphs(self, session_id):
        with self.engine.begin() as conn:
            result = conn.execute(
                select(paragraph_table).where(paragraph_table.c.session_id == session_id).order_by(paragraph_table.c.index.asc())
            )
            return [Paragraph(**row._mapping) for row in result]

    def save_session(self, session_id, wordcount, paragraphs):
        timestamp = now()
        with self.engine.begin() as conn:
            conn.execute(session_table.update().where(session_table.c.id == session_id).values(updated_at=timestamp, wordcount=wordcount))
            pstmt = insert(paragraph_table)
            p_on_update = pstmt.on_conflict_do_update(
                # the unique constraint apparently fires before the id constraint
                # and sqlite < 3.35.0 only allows a single conflict target.
                index_elements=["session_id", "index"],
                set_=dict(sprint_id=pstmt.excluded.sprint_id, markdown=pstmt.excluded.markdown),
            )
            conn.execute(p_on_update, [para.to_db_dict() for para in paragraphs])

    def set_exported_time(self, session_id, timestamp):
        with self.engine.begin() as conn:
            conn.execute(session_table.update().where(session_table.c.id == session_id).values(exported_at=timestamp))

    def delete_session(self, session_id):
        with self.engine.begin() as conn:
            conn.execute(paragraph_table.delete().where(paragraph_table.c.session_id == session_id))
            conn.execute(sprint_table.delete().where(sprint_table.c.session_id == session_id))
            conn.execute(session_table.delete().where(session_table.c.id == session_id))

    def new_sprint(self, session_id: timeflake.Timeflake, duration: datetime.timedelta):
        sprint_id = Timeflake.generate()

        timestamp = now()

        with self.engine.begin() as conn:
            conn.execute(
                sprint_table.insert().values(
                    id=sprint_id,
                    session_id=session_id,
                    duration=duration,
                    wordcount=0,
                    started_at=timestamp,
                )
            )

        return sprint_id

    def load_sprint_info(self, sprint_id: timeflake.Timeflake):
        s = select(sprint_table).where(sprint_table.c.id == sprint_id)
        with self.engine.begin() as conn:
            row = conn.execute(s).one()
            return Sprint(
                id=row.id,
                session_id=row.session_id,
                started_at=row.started_at,
                intended_duration=row.duration,
                ended_at=row.ended_at,
                wordcount=row.wordcount,
            )

    def update_sprint(self, sprint_id: timeflake.Timeflake, wordcount: int, ended: bool = False):
        timestamp = now()
        update = {"wordcount": wordcount}
        if ended:
            update["ended_at"] = timestamp
        with self.engine.begin() as conn:
            conn.execute(sprint_table.update().where(sprint_table.c.id == sprint_id).values(**update))

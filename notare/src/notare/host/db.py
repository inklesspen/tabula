# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import datetime
import pathlib

from dateutil.tz import tzlocal
from sqlalchemy import (
    event,
    MetaData,
    Table,
    Column,
    ForeignKey,
    UniqueConstraint,
    select,
    or_,
    null,
)
from sqlalchemy.types import Integer, UnicodeText, TypeDecorator
from sqlalchemy.dialects.sqlite import CHAR, DATE, DATETIME
from sqlalchemy.engine import Engine, Connectable, URL as EngineURL, create_engine
from sqlalchemy.sql import column, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection, AsyncEngine
import timeflake
import trio
import xdg

from .types import Paragraph, Session


async def _checkpoint():
    await trio.sleep(0)


def now():
    return datetime.datetime.now(tzlocal())


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


metadata = MetaData()

session_table = Table(
    "sessions",
    metadata,
    Column("id", Timeflake, primary_key=True),
    Column("started_on", DATE, nullable=False, index=True),
    Column("updated_at", DATETIME, nullable=False, index=True),
    Column("exported_at", DATETIME, nullable=True, index=True),
    Column("wordcount", Integer, nullable=True),
)

sprint_table = Table(
    "sprints",
    metadata,
    Column("id", Timeflake, primary_key=True),
    Column("session_id", ForeignKey("sessions.id"), nullable=False, index=True),
    Column("wordcount", Integer, nullable=True),
    Column("started_at", DATETIME, nullable=False),
    Column("ended_at", DATETIME, nullable=True),
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
    found_version = conn.scalar(
        text("PRAGMA user_version").columns(column("version", Integer))
    )
    if found_version != expected_version:
        raise DbVersionError(
            f"Expected DB version {expected_version} in {path}, but found {found_version}."
        )


def set_version(conn: Connectable, version: int):
    # looks like pragma does not support bindparams, hence the f-string
    conn.execute(text(f"PRAGMA user_version = {version}"))


async def real_make_db():
    sqlite_path = xdg.xdg_state_home() / "tabula" / "tabula.db"
    exists = sqlite_path.is_file()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    engine_url = EngineURL.create(
        drivername="sqlite+aiosqlite", database=sqlite_path.__fspath__()
    )
    engine = create_async_engine(engine_url)
    conn: AsyncConnection
    async with engine.begin() as conn:
        if exists:
            await conn.run_sync(check_version, sqlite_path, DB_VERSION)
        else:
            await conn.run_sync(metadata.create_all)
            await conn.run_sync(set_version, DB_VERSION)
    return AsyncDb(engine)


class real_AsyncDb:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def new_session(self) -> timeflake.Timeflake:
        await _checkpoint()
        session_id = Timeflake.generate()
        timestamp = now()

        conn: AsyncConnection
        async with self.engine.begin() as conn:
            await conn.execute(
                session_table.insert().values(
                    id=session_id,
                    started_on=timestamp.date(),
                    updated_at=timestamp,
                    exported_at=None,
                    wordcount=0,
                )
            )
            await conn.execute(
                paragraph_table.insert().values(
                    id=Timeflake.generate(), session_id=session_id, index=0, markdown=""
                )
            )

        return session_id

    async def list_sessions(self, limit, only_exportable=False):
        await _checkpoint()
        s = select(session_table).order_by(session_table.id.desc()).limit(limit)
        if only_exportable:
            s = s.where(
                or_(
                    session_table.c.exported_at == null(),
                    session_table.c.exported_at < session_table.c.updated_at,
                )
            )
        async with self.engine.begin() as conn:
            result = await conn.execute(s)
            return [Session(**row._mapping) for row in result]

    async def load_session_paragraphs(self, session_id):
        await _checkpoint()
        async with self.engine.begin() as conn:
            result = await conn.execute(
                select(paragraph_table)
                .where(paragraph_table.c.session_id == session_id)
                .order_by(paragraph_table.c.index.asc())
            )
            return [Paragraph(**row._mapping) for row in result]


def make_db():
    sqlite_path = xdg.xdg_state_home() / "tabula" / "tabula.db"
    exists = sqlite_path.is_file()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    engine_url = EngineURL.create(
        drivername="sqlite", database=sqlite_path.__fspath__()
    )
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
            conn.execute(
                paragraph_table.insert().values(
                    id=Timeflake.generate(), session_id=session_id, index=0, markdown=""
                )
            )

        return session_id

    def list_sessions(self, limit, only_exportable=False):
        s = select(session_table).order_by(session_table.id.desc()).limit(limit)
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
                select(paragraph_table)
                .where(paragraph_table.c.session_id == session_id)
                .order_by(paragraph_table.c.index.asc())
            )
            return [Paragraph(**row._mapping) for row in result]

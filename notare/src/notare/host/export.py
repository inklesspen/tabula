# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import pathlib

from sqlalchemy import select
import trio
import typer

from .config import Settings
from .types import Timeflake
from .db import make_engine, session_table, sprint_table, paragraph_table


# async def export_all(destpath: pathlib.Path):
#     engine = await make_engine()
#     async with engine.begin() as conn:
#         result = await conn.execute(
#             select(session_table).order_by(session_table.c.id.asc())
#         )
#         for row in result:
#             pass


# def sync_export_all(destpath: pathlib.Path):
#     trio.run(export_all, destpath)


# def run_sync_export_all():
#     typer.run(sync_export_all)

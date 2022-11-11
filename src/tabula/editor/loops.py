# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import abc
import datetime
import typing
import unicodedata

import timeflake
import trio

from stilus.types import Size

from ..settings import Settings
from .db import TabulaDb, now
from .document import DocumentModel
from .help import HELP, COMPOSES_TEMPLATE
from .types import DeviceInfo, Renderable
from .rendering import Screen, ModalDialog


async def _checkpoint():
    await trio.sleep(0)


class Loop(abc.ABC):
    def __init__(self):
        self.setup()

    @classmethod
    def loops(cls):
        return cls.__subclasses__()

    def setup(self):
        raise NotImplementedError()

    async def activate(self):
        raise NotImplementedError()

    async def deactivate(self):
        raise NotImplementedError()

    async def handle_keystroke(self, keystroke: str):
        raise NotImplementedError()

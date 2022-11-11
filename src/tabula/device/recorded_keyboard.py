# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections
import collections.abc
import json
import pathlib

import attr
import trio

from .types import Keyboard, KeyEvent


class Recorder:
    def __init__(self, wrapped: Keyboard):
        self.wrapped = wrapped
        self.presence = wrapped.presence
        self.zero_time = None
        self.events = []

    def save_events(self, path: pathlib.Path):
        with path.open("w") as outfile:
            json.dump(self.events, outfile)

    async def keystream(self) -> collections.abc.AsyncIterable[KeyEvent]:
        event: KeyEvent
        async for event in self.wrapped.keystream():
            now = trio.current_time()
            if self.zero_time is None:
                self.zero_time = now
            self.events.append((now - self.zero_time, attr.asdict(event)))
            yield event


class Replayer:
    def __init__(self):
        self.events = []

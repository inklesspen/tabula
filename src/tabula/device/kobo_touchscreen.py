# SPDX-FileCopyrightText: 2022 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import collections
import collections.abc
import logging
import typing

import msgspec
import trio

from .eventsource import AbsCode, Event, EventSource, EventType, KeyCode, SynCode
from .hwtypes import TouchEvent, TouchReport

# https://www.kernel.org/doc/Documentation/input/multi-touch-protocol.txt
# Kobo Clara HD uses what koreader calls a "snow protocol"; ABS_MT_TRACKING_ID is used
# to convey a slot-type value (instead of using ABS_MT_SLOT properly)
# Lifting the touch is conveyed with EV_KEY:BTN_TOUCH:0.

# clara 2e uses slots! this is all wrong for clara 2e, oh no
# https://github.com/NiLuJe/koreader/blob/master/frontend/device/kobo/device.lua
logger = logging.getLogger(__name__)


class Touches(msgspec.Struct):
    first: typing.Optional[TouchEvent] = None
    second: typing.Optional[TouchEvent] = None

    def __getitem__(self, key: int):
        match key:
            case 0:
                return self.first
            case 1:
                return self.second
            case _:
                raise IndexError("Only two touches are tracked")

    def __setitem__(self, key: int, value: typing.Optional[TouchEvent]):
        match key:
            case 0:
                self.first = value
            case 1:
                self.second = value
            case _:
                raise IndexError("Only two touches are tracked")

    @property
    def values(self):
        return [v for v in [self.first, self.second] if v is not None]

    def clear(self):
        self.first = None
        self.second = None


class WipTouchEvent(msgspec.Struct):
    mt_tracking_id: typing.Optional[int] = None
    x: typing.Optional[int] = None
    y: typing.Optional[int] = None
    pressure: typing.Optional[int] = None

    def finalize(self):
        return TouchEvent(
            x=self.x,
            y=self.y,
            pressure=self.pressure,
            slot=self.mt_tracking_id,
        )

    def clear(self):
        self.mt_tracking_id = None
        self.x = None
        self.y = None
        self.pressure = None


class Touchscreen:
    def __init__(self, channel: trio.abc.SendChannel, event_source: typing.Optional[EventSource] = None):
        self.active_touches = Touches()
        self.wip = WipTouchEvent()
        self.eventqueue = collections.deque(maxlen=50)
        self.channel = channel
        if event_source is None:
            # Prevent importing libevdev unless necessary
            from .deviceutil import EventDevice

            event_source = EventDevice("/dev/input/event1")
        self.event_source = event_source

    async def handle_events(self, *, task_status=trio.TASK_STATUS_IGNORED):
        with self.event_source:
            task_status.started()
            disregard = False
            while True:
                for e in self.event_source.events():
                    await trio.lowlevel.checkpoint()
                    match e:
                        case Event(type=EventType.EV_SYN, code=SynCode.SYN_REPORT):
                            if disregard:
                                disregard = False
                            else:
                                self.eventqueue.append(TouchReport(touches=self.active_touches.values, timestamp=e.timestamp))
                            self.active_touches.clear()
                            self.wip.clear()
                        case Event(type=EventType.EV_SYN, code=SynCode.SYN_MT_REPORT):
                            self.active_touches[self.wip.mt_tracking_id] = self.wip.finalize()
                            self.wip.clear()
                        case Event(type=EventType.EV_SYN, code=SynCode.SYN_DROPPED):
                            disregard = True
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_TRACKING_ID) if not disregard:
                            self.wip.mt_tracking_id = e.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_POSITION_X) if not disregard:
                            self.wip.x = e.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_POSITION_Y) if not disregard:
                            self.wip.y = e.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_PRESSURE) if not disregard:
                            self.wip.pressure = e.value
                        case Event(type=EventType.EV_KEY, code=KeyCode.BTN_TOUCH, value=0):
                            self.wip.clear()
                            self.active_touches.clear()
                await trio.sleep(1 / 60)

    async def eventstream(self):
        while True:
            try:
                yield self.eventqueue.popleft()
                await trio.lowlevel.checkpoint()
            except IndexError:
                # No key events, sleep a bit longer.
                await trio.sleep(1 / 60)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        async with trio.open_nursery() as nursery:
            task_status.started()
            nursery.start_soon(self.handle_events)
            async for event in self.eventstream():
                await self.channel.send(event)

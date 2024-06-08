# SPDX-FileCopyrightText: 2022 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections
import collections.abc
import typing

import msgspec
import libevdev
import trio

from .rpctypes import TouchReport, TouchEvent
from .deviceutil import open_device

# Kobo Clara HD uses what koreader calls a "snow protocol"; ABS_MT_TRACKING_ID is used
# to convey a slot-type value (instead of using ABS_MT_SLOT properly)
# Lifting the touch is conveyed with EV_KEY:BTN_TOUCH:0.


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
    def __init__(self, channel: trio.abc.SendChannel):
        self.active_touches = Touches()
        self.wip = WipTouchEvent()
        self.eventqueue = collections.deque(maxlen=50)
        self.channel = channel

    async def handle_events(self, *, task_status=trio.TASK_STATUS_IGNORED):
        with open_device("/dev/input/event1") as d:
            task_status.started()
            disregard = False
            while True:
                for e in d.events():
                    await trio.sleep(0)
                    match e.type:
                        case libevdev.EV_SYN:
                            match e.code:
                                case libevdev.EV_SYN.SYN_REPORT:
                                    if disregard:
                                        disregard = False
                                    else:
                                        self.eventqueue.append(
                                            TouchReport(
                                                touches=self.active_touches.values,
                                                sec=e.sec,
                                                usec=e.usec,
                                            )
                                        )
                                    self.active_touches.clear()
                                    self.wip.clear()
                                case libevdev.EV_SYN.SYN_MT_REPORT:
                                    self.active_touches[self.wip.mt_tracking_id] = self.wip.finalize()
                                    self.wip.clear()
                                case libevdev.EV_SYN.SYN_DROPPED:
                                    disregard = True
                        case libevdev.EV_ABS:
                            if disregard:
                                continue
                            match e.code:
                                case libevdev.EV_ABS.ABS_MT_TRACKING_ID:
                                    self.wip.mt_tracking_id = e.value
                                case libevdev.EV_ABS.ABS_MT_POSITION_X:
                                    self.wip.x = e.value
                                case libevdev.EV_ABS.ABS_MT_POSITION_Y:
                                    self.wip.y = e.value
                                case libevdev.EV_ABS.ABS_MT_PRESSURE:
                                    self.wip.pressure = e.value
                        case libevdev.EV_KEY:
                            if e.matches(libevdev.EV_KEY.BTN_TOUCH, 0):
                                self.wip.clear()
                                self.active_touches.clear()
                await trio.sleep(1 / 60)

    async def eventstream(self):
        while True:
            try:
                yield self.eventqueue.popleft()
                await trio.sleep(0)
            except IndexError:
                # No key events, sleep a bit longer.
                await trio.sleep(1 / 60)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        async with trio.open_nursery() as nursery:
            task_status.started()
            nursery.start_soon(self.handle_events)
            async for event in self.eventstream():
                await self.channel.send(event)

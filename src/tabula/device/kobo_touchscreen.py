# SPDX-FileCopyrightText: 2022 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import collections
import logging
import typing

import msgspec
import trio

from .eventsource import AbsCode, Event, EventSource, EventType, KeyCode, SynCode
from .hwtypes import MultitouchVariant, TouchEvent, TouchReport

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


class WipTouchEvent(msgspec.Struct, kw_only=True):
    slot: typing.Optional[int] = None
    x: typing.Optional[int] = None
    y: typing.Optional[int] = None
    pressure: typing.Optional[int] = None
    tracking_id: typing.Optional[int] = None

    def finalize(self):
        return TouchEvent(
            x=self.x,
            y=self.y,
            pressure=self.pressure,
            slot=self.slot,
        )

    def clear(self):
        self.slot = None
        self.x = None
        self.y = None
        self.pressure = None
        self.tracking_id = None


class Touchscreen:
    # https://www.kernel.org/doc/Documentation/input/multi-touch-protocol.txt
    def __init__(self, variant: MultitouchVariant, channel: trio.abc.SendChannel, event_source: typing.Optional[EventSource] = None):
        self.variant = variant
        self.active_touches = Touches()
        self.wip = WipTouchEvent()
        self.wip_touches: dict[int, WipTouchEvent] = collections.defaultdict(WipTouchEvent)
        self.channel = channel
        if event_source is None:
            # Prevent importing libevdev unless necessary
            from .deviceutil import EventDevice

            allow_auto_sync = self.variant is not MultitouchVariant.SNOW_PROTOCOL
            event_source = EventDevice("/dev/input/event1", allow_auto_sync=allow_auto_sync)
        self.event_source = event_source

    async def handle_events_snow_protocol(self, *, task_status=trio.TASK_STATUS_IGNORED):
        # Kobo Clara HD uses what koreader calls a "snow protocol"; ABS_MT_TRACKING_ID is used
        # to convey a slot-type value (instead of using ABS_MT_SLOT properly)
        # Lifting the touch is conveyed with EV_KEY:BTN_TOUCH:0.
        with self.event_source:
            task_status.started()
            while True:
                for evt in self.event_source.events():
                    await trio.lowlevel.checkpoint()
                    match evt:
                        case Event(type=EventType.EV_SYN, code=SynCode.SYN_REPORT):
                            await self.channel.send(TouchReport(touches=self.active_touches.values, timestamp=evt.timestamp))
                            self.active_touches.clear()
                            self.wip.clear()
                        case Event(type=EventType.EV_SYN, code=SynCode.SYN_MT_REPORT):
                            self.active_touches[self.wip.slot] = self.wip.finalize()
                            self.wip.clear()
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_TRACKING_ID):
                            self.wip.slot = evt.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_POSITION_X):
                            self.wip.x = evt.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_POSITION_Y):
                            self.wip.y = evt.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_PRESSURE):
                            self.wip.pressure = evt.value
                        case Event(type=EventType.EV_KEY, code=KeyCode.BTN_TOUCH, value=0):
                            self.wip.clear()
                            self.active_touches.clear()
                        case Event(type=EventType.EV_SYN, code=SynCode.SYN_CONFIG, value=42):
                            self.channel.close()
                            return
                await trio.sleep(1 / 60)

    async def handle_events_type_b(self, *, task_status=trio.TASK_STATUS_IGNORED):
        with self.event_source:
            task_status.started()
            current_slot = None
            while True:
                for evt in self.event_source.events():
                    await trio.lowlevel.checkpoint()
                    match evt:
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_SLOT):
                            current_slot = evt.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_TRACKING_ID):
                            # the ABS_MT_SLOT event might get skipped if only the 0th slot has been used so far
                            if current_slot is None:
                                current_slot = 0
                            if evt.value == -1:
                                # touch lifted; this is the only time we clear out a wip touch.
                                del self.wip_touches[current_slot]
                            else:
                                # touch; if it matches the current wip in that slot, do nothing. otherwise start a new wip in that slot.
                                # honestly it's probably a protocol error if there IS a current wip in that slot. but who cares.
                                if self.wip_touches[current_slot].tracking_id != evt.value:
                                    self.wip_touches[current_slot].clear()
                                    self.wip_touches[current_slot].slot = current_slot
                                    self.wip_touches[current_slot].tracking_id = evt.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_POSITION_X):
                            if current_slot is None:
                                logger.warning("Got ABS_MT_POSITION_X but current_slot is None")
                                continue
                            self.wip_touches[current_slot].x = evt.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_POSITION_Y):
                            if current_slot is None:
                                logger.warning("Got ABS_MT_POSITION_Y but current_slot is None")
                                continue
                            self.wip_touches[current_slot].y = evt.value
                        case Event(type=EventType.EV_ABS, code=AbsCode.ABS_MT_PRESSURE):
                            if current_slot is None:
                                logger.warning("Got ABS_MT_PRESSURE but current_slot is None")
                                continue
                            self.wip_touches[current_slot].pressure = evt.value
                        case Event(type=EventType.EV_SYN, code=SynCode.SYN_REPORT):
                            for wip in self.wip_touches.values():
                                if wip.slot > 1:
                                    logger.warning("Unable to handle touch in slot %d", wip.slot)
                                    continue
                                self.active_touches[wip.slot] = wip.finalize()
                            await self.channel.send(TouchReport(touches=self.active_touches.values, timestamp=evt.timestamp))
                        case Event(type=EventType.EV_SYN, code=SynCode.SYN_CONFIG, value=42):
                            self.channel.close()
                            return
                await trio.sleep(1 / 60)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        async with trio.open_nursery() as nursery:
            match self.variant:
                case MultitouchVariant.SNOW_PROTOCOL:
                    nursery.start_soon(self.handle_events_snow_protocol)
                case MultitouchVariant.TYPE_B:
                    nursery.start_soon(self.handle_events_type_b)
                case _:
                    raise NotImplementedError(f"Variant {self.variant} is not yet implemented")
            task_status.started()

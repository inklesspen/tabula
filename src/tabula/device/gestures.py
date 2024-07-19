# noot noot
# inspired by https://github.com/mikaelho/pythonista-gestures/blob/master/pygestures.py (public domain)
import collections.abc
import datetime
import enum
from contextlib import aclosing, asynccontextmanager
from typing import cast

import trio

from ..commontypes import Point
from .hwtypes import (
    PersistentTouch,
    PersistentTouchReport,
    TapEvent,
    TapPhase,
    TouchEvent,
    TouchPhase,
    TouchReport,
)
from .keystreams import Section, pump_all


class RecognitionState(enum.Enum):
    POSSIBLE = enum.auto()
    FAILED = enum.auto()
    RECOGNIZED = enum.auto()
    INITIATED = enum.auto()
    CANCELED = enum.auto()
    CHANGED = enum.auto()


class MakePersistent(Section):
    move_threshold = 10  # Could make this DPI-independent, I suppose

    def __init__(self):
        self.id_counter = 0
        self.slots = [None, None]

    async def pump(self, source: trio.MemoryReceiveChannel[TouchReport], sink: trio.MemorySendChannel[PersistentTouchReport]):
        async with aclosing(source), aclosing(sink):
            async for report in source:
                by_slot = [None, None]
                report_data = {
                    "began": [],
                    "moved": [],
                    "ended": [],
                    "timestamp": report.timestamp,
                }
                for t in report.touches:
                    by_slot[t.slot] = t
                for i in (0, 1):
                    if self.slots[i] is None and by_slot[i] is not None:
                        # new touch
                        self.id_counter += 1
                        t: TouchEvent = by_slot[i]
                        pt = PersistentTouch(
                            touch_id=self.id_counter,
                            location=Point(t.x, t.y),
                            max_pressure=t.pressure,
                            phase=TouchPhase.BEGAN,
                        )
                        report_data["began"].append(pt)
                        self.slots[i] = pt
                        continue
                    if self.slots[i] is not None and by_slot[i] is None:
                        # touch ended
                        pt: PersistentTouch = self.slots[i]
                        pt.phase = TouchPhase.ENDED
                        report_data["ended"].append(pt)
                        self.slots[i] = None
                        continue
                    if self.slots[i] is not None and by_slot[i] is not None:
                        t: TouchEvent = by_slot[i]
                        pt: PersistentTouch = self.slots[i]
                        pt.phase = TouchPhase.STATIONARY
                        pt.max_pressure = max(pt.max_pressure, t.pressure)
                        new_location = Point(t.x, t.y)
                        if abs(new_location - pt.location) > self.move_threshold:
                            pt.phase = TouchPhase.MOVED
                            report_data["moved"].append(pt)
                        pt.location = new_location
                        continue
                ptr = PersistentTouchReport(**report_data)
                if ptr.began or ptr.moved or ptr.ended:
                    await sink.send(ptr)


class TapRecognizer(Section):
    max_duration = datetime.timedelta(microseconds=300000)
    required_pressure = 26

    def reset(self):
        self.touch = None
        self.current_touch_ids = set()
        self.start_timestamp = None
        self.state = RecognitionState.POSSIBLE

    async def pump(self, source: trio.MemoryReceiveChannel[PersistentTouchReport], sink: trio.MemorySendChannel[TapEvent]):
        self.reset()
        async with aclosing(source), aclosing(sink):
            async for report in source:
                await self._handle_report(report, sink.send)
                if len(self.current_touch_ids) == 0:
                    self.reset()

    async def _handle_report(self, report: PersistentTouchReport, output):
        self.current_touch_ids.difference_update([touch.touch_id for touch in report.ended])
        self.current_touch_ids.update([touch.touch_id for touch in report.began])
        for touch in report.began:
            if self.touch is not None:
                if self.state is RecognitionState.INITIATED:
                    await output(TapEvent(location=self.touch.location, phase=TapPhase.CANCELED))
                self.state = RecognitionState.FAILED
                return
            self.touch = touch
            self.start_timestamp = report.timestamp
            self.state = RecognitionState.POSSIBLE
            if touch.max_pressure >= self.required_pressure:
                self.state = RecognitionState.INITIATED
                await output(TapEvent(location=touch.location, phase=TapPhase.INITIATED))
        for touch in report.moved:
            if touch is self.touch and touch.phase is TouchPhase.MOVED:
                if self.state is RecognitionState.INITIATED:
                    await output(TapEvent(location=touch.location, phase=TapPhase.CANCELED))
                self.state = RecognitionState.FAILED
                return
            if touch.max_pressure >= self.required_pressure:
                self.state = RecognitionState.INITIATED
                await output(TapEvent(location=touch.location, phase=TapPhase.INITIATED))
        for touch in report.ended:
            if touch is self.touch and touch.phase is TouchPhase.ENDED:
                if touch.max_pressure < self.required_pressure:
                    self.state = RecognitionState.FAILED
                    return
                duration = report.timestamp - self.start_timestamp
                if duration > self.max_duration:
                    self.state = RecognitionState.FAILED
                    if self.state is RecognitionState.INITIATED:
                        await output(TapEvent(location=touch.location, phase=TapPhase.CANCELED))
                    return
                if self.state in (
                    RecognitionState.POSSIBLE,
                    RecognitionState.INITIATED,
                ):
                    self.state = RecognitionState.RECOGNIZED
                    await output(TapEvent(location=touch.location, phase=TapPhase.COMPLETED))


@asynccontextmanager
async def make_tapstream(touch_report_source: collections.abc.AsyncIterable):
    async with pump_all(
        touch_report_source,
        MakePersistent(),
        TapRecognizer(),
    ) as tapstream:
        yield cast(trio.MemoryReceiveChannel[TapEvent], tapstream)

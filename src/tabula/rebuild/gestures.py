# noot noot
# inspired by https://github.com/mikaelho/pythonista-gestures/blob/master/pygestures.py (public domain)
import collections.abc
from contextlib import asynccontextmanager, aclosing
import datetime
import enum

from slurry import Pipeline
from slurry.environments import TrioSection
import trio

from .commontypes import Point
from .hwtypes import (
    TouchEvent,
    TouchReport,
    PersistentTouch,
    TouchPhase,
    PersistentTouchReport,
    TapEvent,
)


class RecognitionState(enum.Enum):
    POSSIBLE = enum.auto()
    FAILED = enum.auto()
    RECOGNIZED = enum.auto()
    BEGAN = enum.auto()
    CANCELED = enum.auto()
    CHANGED = enum.auto()


class MakePersistent(TrioSection):
    move_threshold = 10  # Could make this DPI-independent, I suppose

    def __init__(self):
        self.id_counter = 0
        self.slots = [None, None]

    async def refine(self, input, output):
        async with aclosing(input) as source:
            report: TouchReport
            async for report in source:
                by_slot = [None, None]
                report_data = {"began": [], "moved": [], "ended": []}
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
                            timestamp=t.timestamp,
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
                        pt.timestamp = t.timestamp
                        pt.max_pressure = max(pt.max_pressure, t.pressure)
                        new_location = Point(t.x, t.y)
                        if abs(new_location - pt.location) > self.move_threshold:
                            pt.phase = TouchPhase.MOVED
                            report_data["moved"].append(pt)
                        pt.location = new_location
                        continue
                ptr = PersistentTouchReport(**report_data)
                if ptr.began or ptr.moved or ptr.ended:
                    await output(ptr)


class TapRecognizer(TrioSection):
    max_duration = datetime.timedelta(microseconds=300000)
    required_pressure = 26

    def reset(self):
        self.touch = None
        self.current_touch_ids = set()
        self.start_timestamp = None
        self.state = RecognitionState.POSSIBLE

    async def refine(self, input, output):
        self.reset()
        async with aclosing(input) as source:
            async for report in source:
                await self._handle_report(report, output)
                if len(self.current_touch_ids) == 0:
                    self.reset()

    async def _handle_report(self, report: PersistentTouchReport, output):
        self.current_touch_ids.difference_update(
            [touch.touch_id for touch in report.ended]
        )
        self.current_touch_ids.update([touch.touch_id for touch in report.began])
        for touch in report.began:
            if self.touch is not None:
                self.state = RecognitionState.FAILED
                return
            self.touch = touch
            self.start_timestamp = touch.timestamp
            self.state = RecognitionState.POSSIBLE
        for touch in report.moved:
            if touch is self.touch and touch.phase is TouchPhase.MOVED:
                self.state = RecognitionState.FAILED
                return
        for touch in report.ended:
            if touch is self.touch and touch.phase is TouchPhase.ENDED:
                if touch.max_pressure < self.required_pressure:
                    self.state = RecognitionState.FAILED
                    return
                duration = touch.timestamp - self.start_timestamp
                if duration > self.max_duration:
                    self.state = RecognitionState.FAILED
                    return
                if self.state is RecognitionState.POSSIBLE:
                    self.state = RecognitionState.RECOGNIZED
                    await output(TapEvent(location=touch.location))


@asynccontextmanager
async def make_tapstream(touch_report_source: collections.abc.AsyncIterable):
    tapstream: trio.MemoryReceiveChannel[TapEvent]
    async with Pipeline.create(
        touch_report_source,
        MakePersistent(),
        TapRecognizer(),
    ) as pipeline, pipeline.tap() as tapstream:
        yield tapstream

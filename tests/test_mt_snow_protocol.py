import contextlib
import datetime

import trio
from tabula.device.eventsource import Event
from tabula.device.hwtypes import TouchEvent, TouchReport
from tabula.device.kobo_touchscreen import Touchscreen


class SimpleEventSource(contextlib.AbstractContextManager):
    def __init__(self, events: list[Event]):
        self._events = events

    def events(self):
        while self._events:
            evt = self._events.pop(0)
            yield evt

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return None


async def test_simple_tap(nursery):
    raw_events = [
        Event.from_log("EV_KEY", "BTN_TOOL_FINGER", value=1, seconds=3110, microseconds=243391),
        Event.from_log("EV_KEY", "BTN_TOUCH", value=1, seconds=3110, microseconds=243391),
        Event.from_log("EV_ABS", "ABS_MT_TRACKING_ID", value=0, seconds=3110, microseconds=243391),
        Event.from_log("EV_ABS", "ABS_MT_DISTANCE", value=0, seconds=3110, microseconds=243391),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_X", value=601, seconds=3110, microseconds=243391),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_Y", value=618, seconds=3110, microseconds=243391),
        Event.from_log("EV_ABS", "ABS_MT_PRESSURE", value=38, seconds=3110, microseconds=243391),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MAJOR", value=0, seconds=3110, microseconds=243391),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MINOR", value=0, seconds=3110, microseconds=243391),
        Event.from_log("EV_ABS", "ABS_MT_ORIENTATION", value=0, seconds=3110, microseconds=243391),
        Event.from_log("EV_SYN", "SYN_MT_REPORT", value=0, seconds=3110, microseconds=243391),
        Event.from_log("EV_SYN", "SYN_REPORT", value=0, seconds=3110, microseconds=243391),
        Event.from_log("EV_ABS", "ABS_MT_TRACKING_ID", value=0, seconds=3110, microseconds=254292),
        Event.from_log("EV_ABS", "ABS_MT_DISTANCE", value=0, seconds=3110, microseconds=254292),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_X", value=601, seconds=3110, microseconds=254292),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_Y", value=618, seconds=3110, microseconds=254292),
        Event.from_log("EV_ABS", "ABS_MT_PRESSURE", value=38, seconds=3110, microseconds=254292),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MAJOR", value=0, seconds=3110, microseconds=254292),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MINOR", value=0, seconds=3110, microseconds=254292),
        Event.from_log("EV_ABS", "ABS_MT_ORIENTATION", value=0, seconds=3110, microseconds=254292),
        Event.from_log("EV_SYN", "SYN_MT_REPORT", value=0, seconds=3110, microseconds=254292),
        Event.from_log("EV_SYN", "SYN_REPORT", value=0, seconds=3110, microseconds=254292),
        Event.from_log("EV_ABS", "ABS_MT_TRACKING_ID", value=0, seconds=3110, microseconds=264990),
        Event.from_log("EV_ABS", "ABS_MT_DISTANCE", value=0, seconds=3110, microseconds=264990),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_X", value=601, seconds=3110, microseconds=264990),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_Y", value=618, seconds=3110, microseconds=264990),
        Event.from_log("EV_ABS", "ABS_MT_PRESSURE", value=38, seconds=3110, microseconds=264990),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MAJOR", value=0, seconds=3110, microseconds=264990),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MINOR", value=0, seconds=3110, microseconds=264990),
        Event.from_log("EV_ABS", "ABS_MT_ORIENTATION", value=0, seconds=3110, microseconds=264990),
        Event.from_log("EV_SYN", "SYN_MT_REPORT", value=0, seconds=3110, microseconds=264990),
        Event.from_log("EV_SYN", "SYN_REPORT", value=0, seconds=3110, microseconds=264990),
        Event.from_log("EV_ABS", "ABS_MT_TRACKING_ID", value=0, seconds=3110, microseconds=281031),
        Event.from_log("EV_ABS", "ABS_MT_DISTANCE", value=0, seconds=3110, microseconds=281031),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_X", value=601, seconds=3110, microseconds=281031),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_Y", value=618, seconds=3110, microseconds=281031),
        Event.from_log("EV_ABS", "ABS_MT_PRESSURE", value=38, seconds=3110, microseconds=281031),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MAJOR", value=0, seconds=3110, microseconds=281031),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MINOR", value=0, seconds=3110, microseconds=281031),
        Event.from_log("EV_ABS", "ABS_MT_ORIENTATION", value=0, seconds=3110, microseconds=281031),
        Event.from_log("EV_SYN", "SYN_MT_REPORT", value=0, seconds=3110, microseconds=281031),
        Event.from_log("EV_SYN", "SYN_REPORT", value=0, seconds=3110, microseconds=281031),
        Event.from_log("EV_ABS", "ABS_MT_TRACKING_ID", value=0, seconds=3110, microseconds=296867),
        Event.from_log("EV_ABS", "ABS_MT_DISTANCE", value=0, seconds=3110, microseconds=296867),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_X", value=601, seconds=3110, microseconds=296867),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_Y", value=618, seconds=3110, microseconds=296867),
        Event.from_log("EV_ABS", "ABS_MT_PRESSURE", value=38, seconds=3110, microseconds=296867),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MAJOR", value=0, seconds=3110, microseconds=296867),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MINOR", value=0, seconds=3110, microseconds=296867),
        Event.from_log("EV_ABS", "ABS_MT_ORIENTATION", value=0, seconds=3110, microseconds=296867),
        Event.from_log("EV_SYN", "SYN_MT_REPORT", value=0, seconds=3110, microseconds=296867),
        Event.from_log("EV_SYN", "SYN_REPORT", value=0, seconds=3110, microseconds=296867),
        Event.from_log("EV_ABS", "ABS_MT_TRACKING_ID", value=0, seconds=3110, microseconds=312807),
        Event.from_log("EV_ABS", "ABS_MT_DISTANCE", value=0, seconds=3110, microseconds=312807),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_X", value=601, seconds=3110, microseconds=312807),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_Y", value=617, seconds=3110, microseconds=312807),
        Event.from_log("EV_ABS", "ABS_MT_PRESSURE", value=38, seconds=3110, microseconds=312807),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MAJOR", value=0, seconds=3110, microseconds=312807),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MINOR", value=0, seconds=3110, microseconds=312807),
        Event.from_log("EV_ABS", "ABS_MT_ORIENTATION", value=0, seconds=3110, microseconds=312807),
        Event.from_log("EV_SYN", "SYN_MT_REPORT", value=0, seconds=3110, microseconds=312807),
        Event.from_log("EV_SYN", "SYN_REPORT", value=0, seconds=3110, microseconds=312807),
        Event.from_log("EV_ABS", "ABS_MT_TRACKING_ID", value=0, seconds=3110, microseconds=328752),
        Event.from_log("EV_ABS", "ABS_MT_DISTANCE", value=0, seconds=3110, microseconds=328752),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_X", value=601, seconds=3110, microseconds=328752),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_Y", value=615, seconds=3110, microseconds=328752),
        Event.from_log("EV_ABS", "ABS_MT_PRESSURE", value=35, seconds=3110, microseconds=328752),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MAJOR", value=0, seconds=3110, microseconds=328752),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MINOR", value=0, seconds=3110, microseconds=328752),
        Event.from_log("EV_ABS", "ABS_MT_ORIENTATION", value=0, seconds=3110, microseconds=328752),
        Event.from_log("EV_SYN", "SYN_MT_REPORT", value=0, seconds=3110, microseconds=328752),
        Event.from_log("EV_SYN", "SYN_REPORT", value=0, seconds=3110, microseconds=328752),
        Event.from_log("EV_ABS", "ABS_MT_TRACKING_ID", value=0, seconds=3110, microseconds=344374),
        Event.from_log("EV_ABS", "ABS_MT_DISTANCE", value=0, seconds=3110, microseconds=344374),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_X", value=600, seconds=3110, microseconds=344374),
        Event.from_log("EV_ABS", "ABS_MT_POSITION_Y", value=613, seconds=3110, microseconds=344374),
        Event.from_log("EV_ABS", "ABS_MT_PRESSURE", value=34, seconds=3110, microseconds=344374),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MAJOR", value=0, seconds=3110, microseconds=344374),
        Event.from_log("EV_ABS", "ABS_MT_TOUCH_MINOR", value=0, seconds=3110, microseconds=344374),
        Event.from_log("EV_ABS", "ABS_MT_ORIENTATION", value=0, seconds=3110, microseconds=344374),
        Event.from_log("EV_SYN", "SYN_MT_REPORT", value=0, seconds=3110, microseconds=344374),
        Event.from_log("EV_SYN", "SYN_REPORT", value=0, seconds=3110, microseconds=344374),
        Event.from_log("EV_KEY", "BTN_TOUCH", value=0, seconds=3110, microseconds=375037),
        Event.from_log("EV_KEY", "BTN_TOOL_FINGER", value=0, seconds=3110, microseconds=375037),
    ]

    expected = [
        TouchReport(
            touches=[TouchEvent(x=601, y=618, pressure=38, slot=0)], timestamp=datetime.timedelta(seconds=3110, microseconds=243391)
        ),
        TouchReport(
            touches=[TouchEvent(x=601, y=618, pressure=38, slot=0)], timestamp=datetime.timedelta(seconds=3110, microseconds=254292)
        ),
        TouchReport(
            touches=[TouchEvent(x=601, y=618, pressure=38, slot=0)], timestamp=datetime.timedelta(seconds=3110, microseconds=264990)
        ),
        TouchReport(
            touches=[TouchEvent(x=601, y=618, pressure=38, slot=0)], timestamp=datetime.timedelta(seconds=3110, microseconds=281031)
        ),
        TouchReport(
            touches=[TouchEvent(x=601, y=618, pressure=38, slot=0)], timestamp=datetime.timedelta(seconds=3110, microseconds=296867)
        ),
        TouchReport(
            touches=[TouchEvent(x=601, y=617, pressure=38, slot=0)], timestamp=datetime.timedelta(seconds=3110, microseconds=312807)
        ),
        TouchReport(
            touches=[TouchEvent(x=601, y=615, pressure=35, slot=0)], timestamp=datetime.timedelta(seconds=3110, microseconds=328752)
        ),
        TouchReport(
            touches=[TouchEvent(x=600, y=613, pressure=34, slot=0)], timestamp=datetime.timedelta(seconds=3110, microseconds=344374)
        ),
    ]
    touch_send, touch_receive = trio.open_memory_channel[TouchReport](0)
    touchscreen = Touchscreen(touch_send, SimpleEventSource(raw_events))
    await nursery.start(touchscreen.run)
    received = []
    async with touch_receive:
        while len(received) < len(expected):
            event = await touch_receive.receive()
            received.append(event)
    assert received == expected

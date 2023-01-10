# noot noot
# inspired by https://github.com/mikaelho/pythonista-gestures/blob/master/pygestures.py (public domain)
import datetime
import enum

from .hwtypes import TouchEvent, TouchReport


class RecognitionState(enum.Enum):
    POSSIBLE = enum.auto()
    FAILED = enum.auto()
    RECOGNIZED = enum.auto()
    BEGAN = enum.auto()
    CANCELED = enum.auto()
    CHANGED = enum.auto()


class TapRecognizer:
    tap_threshold = datetime.timedelta(microseconds=300000)
    pressure_threshold = 26
    move_threshold = 15  # Could make this DPI-independent, I suppose

    def __init__(self):
        self.reset()

    def handle_report(self, report: TouchReport):
        if len(report.touches) > 1:
            self.state = RecognitionState.FAILED
            return
        if len(report.touches) == 1:
            touch = report.touches[0]
            if self.touch_slot is None:
                self._touch_began(touch)
            elif self.touch_slot == touch.slot:
                self._touch_moved(touch)
            else:
                self.state = RecognitionState.FAILED
        else:
            self._touch_ended()

    def _touch_began(self, touch: TouchEvent):
        self.touch_slot = touch.slot
        self.location = touch.point
        self.start_location = touch.point
        self.max_pressure = touch.pressure
        self.timestamp = touch.timestamp
        self.start_timestamp = touch.timestamp
        self.state = RecognitionState.POSSIBLE

    def _touch_moved(self, touch: TouchEvent):
        self.max_pressure = max(self.max_pressure, touch.pressure)
        self.timestamp = touch.timestamp
        duration = self.timestamp - self.start_timestamp
        if duration > self.tap_threshold:
            self.state = RecognitionState.FAILED
        self.location = touch.point
        distance = abs(self.location - self.start_location)
        if distance > self.move_threshold:
            self.state = RecognitionState.FAILED

    def _touch_ended(self):
        self.touch_slot = None
        if self.max_pressure < self.pressure_threshold:
            self.state = RecognitionState.FAILED
            return
        if self.state is RecognitionState.POSSIBLE:
            self.state = RecognitionState.RECOGNIZED

    def reset(self):
        self.touch_slot = None
        self.location = None
        self.start_location = None
        self.max_pressure = None
        self.timestamp = None
        self.start_timestamp = None
        self.state = RecognitionState.POSSIBLE

import collections.abc
import datetime
import enum
import typing

import msgspec

from tabula.device.keyboard_consts import Key, KeyPress, Led
from .commontypes import Point, Size, Rect


class ScreenRect(msgspec.Struct, frozen=True):
    # TODO: unify with Rect
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_rect(cls, rect: Rect):
        return cls(
            x=rect.origin.x,
            y=rect.origin.y,
            width=rect.spread.width,
            height=rect.spread.height,
        )


class KeyboardDisconnect(msgspec.Struct, frozen=True):
    pass


class KeyEvent(msgspec.Struct, frozen=True):
    key: Key
    press: KeyPress

    @classmethod
    def pressed(cls, key: Key):
        return cls(key=key, press=KeyPress.PRESSED)

    @classmethod
    def released(cls, key: Key):
        return cls(key=key, press=KeyPress.RELEASED)


class ModifierAnnotation(msgspec.Struct, frozen=True):
    alt: bool = False
    ctrl: bool = False
    meta: bool = False
    shift: bool = False
    capslock: bool = False
    compose: bool = False


class AnnotatedKeyEvent(msgspec.Struct, frozen=True):
    key: Key
    press: KeyPress
    annotation: ModifierAnnotation
    character: typing.Optional[str] = None
    is_modifier: bool = False
    is_led_able: bool = False


class TouchEvent(msgspec.Struct, frozen=True):
    x: int
    y: int
    pressure: int
    sec: int
    usec: int
    slot: int

    @property
    def point(self):
        return Point(x=self.x, y=self.y)

    @property
    def timestamp(self):
        return datetime.timedelta(seconds=self.sec, microseconds=self.usec)


class TouchReport(msgspec.Struct, frozen=True):
    touches: typing.List[TouchEvent]


class EventType(enum.Enum):
    KeyEvent = enum.auto()
    AnnotatedKeyEvent = enum.auto()


class ChargingState(enum.IntEnum):
    DISCHARGING = enum.auto()
    CHARGING = enum.auto()
    NOT_CHARGING = enum.auto()


class BatteryState(msgspec.Struct, frozen=True):
    state: ChargingState
    current_charge: int


class SetLed(msgspec.Struct, frozen=True):
    led: Led
    state: bool


class TouchCoordinateTransform(enum.IntEnum):
    IDENTITY = 0
    SWAP_AND_MIRROR_Y = 1
    MIRROR_X_AND_MIRROR_Y = 2
    SWAP_AND_MIRROR_X = 3

    def apply(self, event: TouchEvent, screen_size: Size):
        match self:
            case TouchCoordinateTransform.IDENTITY:
                return event
            case TouchCoordinateTransform.SWAP_AND_MIRROR_Y:
                return TouchEvent(
                    x=event.y,
                    y=screen_size.height - event.x,
                    pressure=event.pressure,
                    sec=event.sec,
                    usec=event.usec,
                    slot=event.slot,
                )
            case TouchCoordinateTransform.MIRROR_X_AND_MIRROR_Y:
                return TouchEvent(
                    x=screen_size.width - event.x,
                    y=screen_size.height - event.y,
                    pressure=event.pressure,
                    sec=event.sec,
                    usec=event.usec,
                    slot=event.slot,
                )
            case TouchCoordinateTransform.SWAP_AND_MIRROR_X:
                return TouchEvent(
                    x=screen_size.width - event.y,
                    y=event.x,
                    pressure=event.pressure,
                    sec=event.sec,
                    usec=event.usec,
                    slot=event.slot,
                )


class TouchPhase(enum.Enum):
    BEGAN = enum.auto()
    MOVED = enum.auto()
    STATIONARY = enum.auto()
    ENDED = enum.auto()
    CANCELLED = enum.auto()


class PersistentTouch(msgspec.Struct):
    touch_id: int
    location: Point
    max_pressure: int
    timestamp: datetime.timedelta
    phase: TouchPhase


class PersistentTouchReport(msgspec.Struct, frozen=True):
    began: collections.abc.Sequence[PersistentTouch]
    moved: collections.abc.Sequence[PersistentTouch]
    ended: collections.abc.Sequence[PersistentTouch]


class TapEvent(msgspec.Struct, frozen=True):
    location: Point

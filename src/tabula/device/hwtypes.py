from __future__ import annotations

import datetime
import enum
import typing

import msgspec

from tabula.device.keyboard_consts import KeyPress

from ..commontypes import Point

if typing.TYPE_CHECKING:
    import collections.abc

    from ..commontypes import Size, TouchCoordinateTransform
    from .keyboard_consts import Key, Led


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
    slot: int

    @property
    def point(self):
        return Point(x=self.x, y=self.y)

    def apply_transform(self, transform: TouchCoordinateTransform, screen_size: Size):
        match transform:
            case TouchCoordinateTransform.IDENTITY:
                return self
            case TouchCoordinateTransform.SWAP_AND_MIRROR_Y:
                return TouchEvent(
                    x=self.y,
                    y=screen_size.height - self.x,
                    pressure=self.pressure,
                    slot=self.slot,
                )
            case TouchCoordinateTransform.MIRROR_X_AND_MIRROR_Y:
                return TouchEvent(
                    x=screen_size.width - self.x,
                    y=screen_size.height - self.y,
                    pressure=self.pressure,
                    slot=self.slot,
                )
            case TouchCoordinateTransform.SWAP_AND_MIRROR_X:
                return TouchEvent(
                    x=screen_size.width - self.y,
                    y=self.x,
                    pressure=self.pressure,
                    slot=self.slot,
                )


class TouchReport(msgspec.Struct, frozen=True):
    touches: typing.List[TouchEvent]
    sec: int
    usec: int

    @property
    def timestamp(self):
        return datetime.timedelta(seconds=self.sec, microseconds=self.usec)


class EventType(enum.Enum):
    KeyEvent = enum.auto()
    AnnotatedKeyEvent = enum.auto()


class SetLed(msgspec.Struct, frozen=True):
    led: Led
    state: bool


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
    phase: TouchPhase


class PersistentTouchReport(msgspec.Struct, frozen=True):
    began: collections.abc.Sequence[PersistentTouch]
    moved: collections.abc.Sequence[PersistentTouch]
    ended: collections.abc.Sequence[PersistentTouch]
    timestamp: datetime.timedelta


class TapPhase(enum.Enum):
    INITIATED = enum.auto()
    COMPLETED = enum.auto()
    CANCELED = enum.auto()


class TapEvent(msgspec.Struct, frozen=True):
    location: Point
    phase: TapPhase


TabulaEvent = AnnotatedKeyEvent | TapEvent | KeyboardDisconnect

from __future__ import annotations

import enum
import typing

import msgspec

from ..commontypes import Point, Size, TabulaError, TouchCoordinateTransform

if typing.TYPE_CHECKING:
    import collections.abc
    import datetime

    from .eventsource import KeyCode, LedCode


class HardwareError(TabulaError):
    pass


class BluetoothInitError(HardwareError):
    pass


class KeyboardDisconnect(msgspec.Struct, frozen=True):
    pass


class KeyPress(enum.IntEnum):
    RELEASED = 0
    PRESSED = 1
    REPEATED = 2


class KeyEvent(msgspec.Struct, frozen=True):
    key: KeyCode
    press: KeyPress

    @classmethod
    def pressed(cls, key: KeyCode):
        return cls(key=key, press=KeyPress.PRESSED)

    @classmethod
    def released(cls, key: KeyCode):
        return cls(key=key, press=KeyPress.RELEASED)


class ModifierAnnotation(msgspec.Struct, frozen=True):
    alt: bool = False
    ctrl: bool = False
    meta: bool = False
    shift: bool = False
    capslock: bool = False
    compose: bool = False


class AnnotatedKeyEvent(msgspec.Struct, frozen=True):
    key: KeyCode
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
    timestamp: datetime.timedelta


class EventType(enum.Enum):
    KeyEvent = enum.auto()
    AnnotatedKeyEvent = enum.auto()


class SetLed(msgspec.Struct, frozen=True):
    led: LedCode
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

    def apply_transform(self, transform: TouchCoordinateTransform, screen_size: Size):
        match transform:
            case TouchCoordinateTransform.IDENTITY:
                return self
            case TouchCoordinateTransform.SWAP_AND_MIRROR_Y:
                return TapEvent(location=Point(x=self.location.y, y=screen_size.height - self.location.x), phase=self.phase)
            case TouchCoordinateTransform.MIRROR_X_AND_MIRROR_Y:
                return TapEvent(
                    location=Point(x=screen_size.width - self.location.x, y=screen_size.height - self.location.y), phase=self.phase
                )
            case TouchCoordinateTransform.SWAP_AND_MIRROR_X:
                return TapEvent(location=Point(x=screen_size.width - self.location.y, y=self.location.x), phase=self.phase)


TabulaEvent = AnnotatedKeyEvent | TapEvent | KeyboardDisconnect


@enum.unique
class BluetoothVariant(enum.Enum):
    NONE = "none"
    CLARA2E = "clara2e"


@enum.unique
class MultitouchVariant(enum.Enum):
    TYPE_A = "type_a"
    TYPE_B = "type_b"
    SNOW_PROTOCOL = "snow_protocol"


@enum.unique
class DisplayUpdateMode(enum.Enum):
    AUTO = "auto"
    RAPID = "rapid"
    FIDELITY = "fidelity"


@enum.unique
class DeviceBus(enum.Enum):
    USB = "usb"
    BLUETOOTH = "bluetooth"


class InputDeviceDetails(typing.Protocol):
    name: str
    bus: DeviceBus

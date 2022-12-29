import enum
import typing

import msgspec

from tabula.device.keyboard_consts import Key, KeyPress, LED


class ScreenRect(msgspec.Struct, frozen=True):
    x: int
    y: int
    width: int
    height: int

    @property
    def pillow_size(self):
        return (self.width, self.height)

    @property
    def pillow_origin(self):
        return (self.x, self.y)


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


class ScreenInfo(msgspec.Struct, frozen=True):
    width: int
    height: int
    dpi: int


class LedState(msgspec.Struct, frozen=True):
    led: LED
    state: bool

import typing

import msgspec

from tabula.device.keyboard_consts import Key, KeyPress, Led
from .hwtypes import ScreenRect, TouchEvent, ChargingState


### Request Types

### Laptop to Kobo


class GetBatteryState(msgspec.Struct, tag=True):
    pass


class GetScreenInfo(msgspec.Struct, tag=True):
    pass


class DisplayPixels(msgspec.Struct, tag=True):
    imagebytes: bytes
    rect: ScreenRect


class ClearScreen(msgspec.Struct, tag=True):
    pass


class SetLed(msgspec.Struct, tag=True):
    led: Led
    state: bool


HostRequests = GetBatteryState | GetScreenInfo | DisplayPixels | ClearScreen | SetLed

### Kobo to Laptop


class BatteryState(msgspec.Struct, tag=True):
    state: ChargingState
    current_charge: int


class ScreenInfo(msgspec.Struct, tag=True):
    width: int
    height: int
    dpi: int


class KeyEvent(msgspec.Struct, tag=True):
    key: Key
    press: KeyPress


class TouchReport(msgspec.Struct, tag=True):
    touches: typing.List[TouchEvent]


class KeyboardDisconnect(msgspec.Struct, tag=True):
    pass


KoboRequests = BatteryState | ScreenInfo | KeyEvent | TouchReport | KeyboardDisconnect

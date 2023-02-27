import typing

import msgspec

from tabula.device.keyboard_consts import Key, KeyPress, Led
from .hwtypes import ScreenRect, TouchEvent, TouchCoordinateTransform


### Request Types

### Laptop to Kobo


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


class SetWaveformMode(msgspec.Struct, tag=True):
    wfm_mode: str


HostRequests = GetScreenInfo | DisplayPixels | ClearScreen | SetLed | SetWaveformMode

### Kobo to Laptop


class ScreenInfo(msgspec.Struct, tag=True):
    width: int
    height: int
    dpi: int
    touch_coordinate_transform: TouchCoordinateTransform


class KeyEvent(msgspec.Struct, tag=True):
    key: Key
    press: KeyPress


class TouchReport(msgspec.Struct, tag=True):
    touches: typing.List[TouchEvent]
    sec: int
    usec: int


class KeyboardDisconnect(msgspec.Struct, tag=True):
    pass


KoboRequests = ScreenInfo | KeyEvent | TouchReport | KeyboardDisconnect

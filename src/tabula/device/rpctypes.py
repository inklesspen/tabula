import typing

import msgspec

from tabula.device.keyboard_consts import Key, KeyPress, Led
from .hwtypes import ScreenRect, TouchEvent, ChargingState, TouchCoordinateTransform


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


class SetWaveformMode(msgspec.Struct, tag=True):
    wfm_mode: str


HostRequests = (
    GetBatteryState
    | GetScreenInfo
    | DisplayPixels
    | ClearScreen
    | SetLed
    | SetWaveformMode
)

### Kobo to Laptop


class BatteryState(msgspec.Struct, tag=True):
    state: ChargingState
    current_charge: int


class ScreenInfo(msgspec.Struct, tag=True):
    width: int
    height: int
    dpi: int
    touch_coordinate_transform: TouchCoordinateTransform


class KeyEvent(msgspec.Struct, tag=True):
    key: Key
    press: KeyPress


class TouchReport(msgspec.Struct, tag=True):
    # TODO: make the timestamp part of the report, and not the touch
    # So that a report with no touches still has a timestamp
    touches: typing.List[TouchEvent]


class KeyboardDisconnect(msgspec.Struct, tag=True):
    pass


KoboRequests = BatteryState | ScreenInfo | KeyEvent | TouchReport | KeyboardDisconnect

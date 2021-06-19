# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import abc
import base64
import datetime
import enum
import gzip
import ipaddress
from typing import List

import pydantic

TABULA_IP: ipaddress.IPv4Address = ipaddress.ip_address("10.52.0.1")
TABULA_PORT = 48148


class Rect(pydantic.BaseModel):
    x: int
    y: int
    width: int
    height: int


class Framelet(pydantic.BaseModel):
    rect: Rect
    image: bytes

    @staticmethod
    def encode_bytes(some_bytes: bytes) -> bytes:
        return base64.b85encode(gzip.compress(some_bytes, compresslevel=1))

    @staticmethod
    def decode_bytes(some_bytes: bytes) -> bytes:
        return gzip.decompress(base64.b85decode(some_bytes))


class ChargingState(str, enum.Enum):
    DISCHARGING = "Discharging"
    CHARGING = "Charging"
    NOT_CHARGING = "Not charging"


class BatteryState(pydantic.BaseModel):
    state: ChargingState
    current_charge: int


class KoboTime(pydantic.BaseModel):
    now: datetime.datetime


class DeviceInfo(pydantic.BaseModel):
    width: int
    height: int
    dpi: int
    device_name: str
    code_name: str


class Protocol(abc.ABC):
    @abc.abstractmethod
    def update_screen(self, framelets: List[Framelet]) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def clear_screen(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def save_screen(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def restore_screen(self) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_device_info(self) -> DeviceInfo:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_battery_state(self) -> BatteryState:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_current_time(self) -> KoboTime:
        raise NotImplementedError()

    @abc.abstractmethod
    def shutdown(self) -> None:
        raise NotImplementedError()

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import abc
import base64
import datetime
import enum
import gzip
import ipaddress
import json

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

    class Config:
        @staticmethod
        def json_dumps(val, **kw):
            compressed = gzip.compress(val['image'], compresslevel=1)
            val["image"] = base64.b85encode(compressed)
            return json.dumps(val, **kw)

        @staticmethod
        def json_loads(val):
            loaded = json.loads(val)
            loaded["image"] = gzip.decompress(base64.b85decode(loaded["image"]))
            return loaded


class ChargingState(str, enum.Enum):
    DISCHARGING = "Not charging"
    CHARGING = "Charging"
    NOT_CHARGING = "Not charging"


class BatteryState(pydantic.BaseModel):
    state: ChargingState
    current_charge: int


class KoboTime(pydantic.BaseModel):
    now: datetime.datetime


class Protocol(abc.ABC):
    @abc.abstractmethod
    def update_display(self, framelet: Framelet):
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

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import typing

from trio_jsonrpc import JsonRpcConnection

from ..protocol import (
    Framelet,
    BatteryState,
    KoboTime,
    DeviceInfo,
    Protocol,
)


class Stub(Protocol):
    def __init__(self, client: JsonRpcConnection):
        self.client = client

    async def update_screen(self, framelets: typing.List[Framelet]) -> None:
        args = {"framelets": [json.loads(framelet.json()) for framelet in framelets]}
        await self.client.request("update_screen", args)

    async def clear_screen(self) -> None:
        await self.client.request("clear_screen", {})

    async def save_screen(self) -> None:
        await self.client.request("save_screen", {})

    async def restore_screen(self) -> None:
        await self.client.request("restore_screen", {})

    async def get_device_info(self) -> DeviceInfo:
        response = await self.client.request("get_device_info", {})
        return DeviceInfo.parse_raw(json.dumps(response))

    async def get_battery_state(self) -> BatteryState:
        response = await self.client.request("get_battery_state", {})
        return BatteryState.parse_raw(json.dumps(response))

    async def get_current_time(self) -> KoboTime:
        response = await self.client.request("get_current_time", {})
        return KoboTime.parse_raw(json.dumps(response))

    async def shutdown(self) -> None:
        print("shutting down")
        await self.client.request("shutdown", {})

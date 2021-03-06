# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import collections.abc
import datetime
import inspect
import json
import os
import typing

import attr
from dateutil.tz import tzlocal
import pkg_resources
from sansio_jsonrpc import (
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcApplicationError,
    JsonRpcError,
    JsonRpcException,
    JsonRpcInvalidParamsError,
    JsonRpcInvalidRequestError,
    JsonRpcInternalError,
    JsonRpcMethodNotFoundError,
    JsonRpcReservedError,
    JsonRpcParseError,
)
import trio
from trio_jsonrpc import JsonRpcConnection, JsonRpcConnectionType
from trio_jsonrpc.transport.ws import WebSocketTransport
import trio_websocket

import imprimare

from .battery import Battery
from .button import buttonwatch
from .gadget import Gadget
from ..protocol import (
    Framelet,
    BatteryState,
    KoboTime,
    DeviceInfo,
    Protocol,
    TABULA_PORT,
)


class Servicer(Protocol):
    def __init__(self, ink: imprimare.Ink, battery: Battery):
        self.ink = ink
        self.battery = battery

    def update_screen(self, framelets: typing.List[Framelet]) -> None:
        # TODO: allow a sequence of framelets and only refresh at the end
        for framelet in framelets:
            rect = framelet.rect
            image = Framelet.decode_bytes(framelet.image)
            self.ink.display_pixels(image, rect.x, rect.y, rect.width, rect.height)

    def clear_screen(self) -> None:
        self.ink.clear()

    def save_screen(self) -> None:
        self.ink.save_screen()

    def restore_screen(self) -> None:
        self.ink.restore_screen()

    def get_device_info(self) -> DeviceInfo:
        return DeviceInfo(**attr.asdict(self.ink.get_device_info()))

    def get_battery_state(self) -> BatteryState:
        return self.battery.get()

    def get_current_time(self) -> KoboTime:
        return KoboTime(now=datetime.datetime.now(tzlocal()))

    def shutdown(self) -> None:
        # This is currently handled by the connection_handler directly.
        return None


def dispatch_request(servicer, request):
    if hasattr(servicer, request.method):
        # dynamically convert params into pydantic types
        smethod = getattr(servicer, request.method)
        sig = inspect.signature(smethod)
        try:
            bound = (
                sig.bind(**request.params)
                if isinstance(request.params, collections.abc.Mapping)
                else sig.bind(*request.params)
            )
        except TypeError:
            raise JsonRpcInvalidParamsError()
        for k, v in bound.arguments.items():
            vclass = sig.parameters[k].annotation
            # We support generic lists
            if typing.get_origin(vclass) is list:
                vclass = typing.get_args(vclass)[0]
                bound.arguments[k] = [vclass.parse_raw(json.dumps(x)) for x in v]
            else:
                bound.arguments[k] = vclass.parse_raw(json.dumps(v))
        result = smethod(*bound.args, **bound.kwargs)
        if sig.return_annotation is None:
            # Actually returning None causes problems :(
            return "ok"
        return json.loads(result.json())
    else:
        raise JsonRpcMethodNotFoundError()


async def run_server(host, port):
    loading_png_path = pkg_resources.resource_filename(
        "notare", "device/preload/waiting.png"
    )
    with imprimare.get_ink() as ink:
        ink.clear()
        ink.display_png(loading_png_path, 0, 0)
        async with Battery() as battery:
            server_cancel_scope = trio.CancelScope()
            servicer = Servicer(ink, battery)

            async def connection_handler(ws_request):
                ws = await ws_request.accept()
                transport = WebSocketTransport(ws)
                rpc_conn = JsonRpcConnection(transport, JsonRpcConnectionType.SERVER)
                ink.clear()
                async with trio.open_nursery() as nursery:
                    nursery.start_soon(rpc_conn._background_task)
                    async for request in rpc_conn.iter_requests():
                        try:
                            result = dispatch_request(servicer, request)
                            await rpc_conn.respond_with_result(request, result)
                        except JsonRpcException as e:
                            err = e.get_error()
                            await rpc_conn.respond_with_error(request, err)
                        if request.method == "shutdown":
                            if os.environ.get("KEEP_GOING"):
                                break
                            else:
                                server_cancel_scope.cancel()
                    nursery.cancel_scope.cancel()

            with server_cancel_scope:
                trio.lowlevel.spawn_system_task(buttonwatch, server_cancel_scope.cancel)
                await trio_websocket.serve_websocket(
                    connection_handler, host, port, None
                )
        ink.clear()


def main():
    if os.environ.get("SKIP_GADGET"):
        trio.run(run_server, None, TABULA_PORT)
    else:
        with Gadget():
            trio.run(run_server, None, TABULA_PORT)


if __name__ == "__main__":
    main()

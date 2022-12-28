import abc
import typing

import msgspec
import trio
import trio_util
import tricycle

from .hwtypes import (
    ScreenRect,
    BatteryState,
    ScreenInfo,
    KeyEvent,
    TouchReport,
)
from .rpctypes import (
    KoboRequests,
    HostRequests,
    BatteryState as RpcBatteryState,
    ScreenInfo as RpcScreenInfo,
    GetBatteryState as RpcGetBatteryState,
    GetScreenInfo as RpcGetScreenInfo,
    DisplayPixels as RpcDisplayPixels,
    ClearScreen as RpcClearScreen,
    KeyEvent as RpcKeyEvent,
    TouchReport as RpcTouchReport,
    KeyboardDisconnect as RpcKeyboardDisconnect,
)
from .keystreams import make_keystream
from .util import checkpoint, settings as app_settings


class LengthPrefixedMsgpackStreamChannel(trio.abc.Channel):
    def __init__(self, socket_stream: trio.SocketStream):
        self.decoder = msgspec.msgpack.Decoder(KoboRequests)
        self.encoder = msgspec.msgpack.Encoder()
        self.socket_stream = socket_stream
        self.buffered_stream = tricycle.BufferedReceiveStream(socket_stream)
        self._prefix_length = 4

    async def send(self, value: HostRequests):
        buffer = self.encoder.encode(value)
        prefix = len(buffer).to_bytes(self._prefix_length, "big")
        await self.socket_stream.send_all(prefix)
        await self.socket_stream.send_all(buffer)
        await self.socket_stream.wait_send_all_might_not_block()

    async def receive(self) -> KoboRequests:
        prefix = await self.buffered_stream.receive_exactly(self._prefix_length)
        n = int.from_bytes(prefix, "big")
        buffer = await self.buffered_stream.receive_exactly(n)
        return self.decoder.decode(buffer)

    async def aclose(self):
        await self.socket_stream.aclose()


# Hardware should be an ABC, with subclasses RpcHardware, KoboHardware, TestHardware


class Hardware(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_battery_state(self) -> BatteryState:
        ...

    @abc.abstractmethod
    async def get_screen_info(self) -> ScreenInfo:
        ...

    @abc.abstractmethod
    async def display_pixels(self, imagebytes: bytes, rect: ScreenRect):
        ...

    @abc.abstractmethod
    async def clear_screen(self):
        ...

    @abc.abstractmethod
    def reset_keystream(self, enable_composes: bool):
        ...


class RpcHardware(Hardware):
    battery_state_response: trio_util.AsyncValue[typing.Optional[BatteryState]]
    screen_info_response: trio_util.AsyncValue[typing.Optional[ScreenInfo]]

    def __init__(self, event_channel: trio.abc.SendChannel):
        self.host = "kobo.apollo"
        self.port = 1234
        self.event_channel = event_channel
        self.battery_state_response = trio_util.AsyncValue(None)
        self.screen_info_response = trio_util.AsyncValue(None)

        self.req_send_channel, self.req_receive_channel = trio.open_memory_channel(0)
        # Throwaways, so we never have to check if a channel is None
        (
            self.keystream_send_channel,
            self.keystream_receive_channel,
        ) = trio.open_memory_channel(0)

    async def get_battery_state(self) -> BatteryState:
        self.battery_state_response.value = None
        await self.req_send_channel.send(RpcGetBatteryState())
        resp = await self.battery_state_response.wait_value(lambda v: v is not None)
        return resp

    async def get_screen_info(self) -> ScreenInfo:
        self.screen_info_response.value = None
        await self.req_send_channel.send(RpcGetScreenInfo())
        resp = await self.screen_info_response.wait_value(lambda v: v is not None)
        return resp

    async def display_pixels(self, imagebytes: bytes, rect: ScreenRect):
        await self.req_send_channel.send(RpcDisplayPixels(imagebytes, rect))

    async def clear_screen(self):
        await self.req_send_channel.send(RpcClearScreen())

    async def _send_host_requests(
        self,
        network_channel: trio.abc.SendChannel,
        *,
        task_status=trio.TASK_STATUS_IGNORED
    ):
        task_status.started()
        while True:
            msg = await self.req_receive_channel.receive()
            await network_channel.send(msg)
            await checkpoint()

    async def _handle_kobo_requests(
        self,
        network_channel: trio.abc.ReceiveChannel,
        *,
        task_status=trio.TASK_STATUS_IGNORED
    ):
        task_status.started()
        while True:
            req: KoboRequests = await network_channel.receive()
            match req:
                case RpcBatteryState():
                    self.battery_state_response.value = BatteryState(
                        state=req.state, current_charge=req.current_charge
                    )
                case RpcScreenInfo():
                    self.screen_info_response.value = ScreenInfo(
                        width=req.width, height=req.height, dpi=req.dpi
                    )
                case RpcKeyEvent():
                    await self.keystream_send_channel.send(
                        KeyEvent(key=req.key, press=req.press)
                    )
                case RpcTouchReport():
                    await self.event_channel.send(TouchReport(touches=req.touches))
                case RpcKeyboardDisconnect():
                    raise Exception("implement this, dingus")
            await checkpoint()

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        async with tricycle.open_service_nursery() as nursery:
            client_stream = await trio.open_tcp_stream(self.host, self.port)
            async with client_stream:
                task_status.started()
                network_channel = LengthPrefixedMsgpackStreamChannel(client_stream)
                nursery.start_soon(self._handle_kobo_requests, network_channel)
                nursery.start_soon(self._send_host_requests, network_channel)
                nursery.start_soon(self._handle_keystream_results)

    # TODO: make_keystream returns a context manager, so this won't quite work
    # I think we need to use a cancel scope to stop one handler and start the next one
    async def _handle_keystream_results(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            try:
                event = self.keystream_receive_channel.receive_nowait()
                await self.event_channel.send(event)
            except trio.WouldBlock:
                pass
            await checkpoint()

    async def reset_keystream(self, enable_composes: bool):
        old_send_channel = self.keystream_send_channel
        old_receive_channel = self.keystream_receive_channel
        (
            new_keystream_send_channel,
            new_keystream_receive_channel,
        ) = trio.open_memory_channel(0)
        self.keystream_send_channel = new_keystream_send_channel
        self.keystream_receive_channel = await make_keystream(
            new_keystream_receive_channel, app_settings(), enable_composes
        )
        old_send_channel.close()
        old_receive_channel.close()

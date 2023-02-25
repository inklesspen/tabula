import abc
import typing

import msgspec
import trio
import trio_util
import tricycle

from .hwtypes import (
    ScreenRect,
    BatteryState,
    ChargingState,
    KeyEvent,
    AnnotatedKeyEvent,
    TouchReport,
    TouchEvent,
    SetLed,
    Led,
    TouchCoordinateTransform,
    KeyboardDisconnect,
)
from ..commontypes import Rect, Size, ScreenInfo
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
    SetLed as RpcSetLed,
)
from .keystreams import make_keystream
from .gestures import make_tapstream
from ..settings import Settings
from ..util import checkpoint

if typing.TYPE_CHECKING:
    from ..rendering.rendertypes import Rendered


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


class Hardware(metaclass=abc.ABCMeta):
    screen_size: Size
    touch_coordinate_transform: TouchCoordinateTransform
    capslock_led: bool
    compose_led: bool

    def __init__(
        self,
        event_channel: trio.abc.SendChannel,
        settings: Settings,
    ):
        self.event_channel = event_channel
        self.settings = settings
        self.capslock_led = False
        self.compose_led = False
        self.keystream_cancel_scope = trio.CancelScope()
        self.keystream = None
        self.keystream_send_channel = None
        self.reset_keystream(False)
        self.screen_size = Size(0, 0)
        self.touch_coordinate_transform = TouchCoordinateTransform.IDENTITY
        self.touchstream_cancel_scope = trio.CancelScope()
        self.touchstream = None
        self.touchstream_send_channel = None
        self.reset_touchstream()

    @abc.abstractmethod
    async def get_battery_state(self) -> BatteryState:
        ...

    @abc.abstractmethod
    async def get_screen_info(self) -> ScreenInfo:
        ...

    @abc.abstractmethod
    async def display_pixels(self, imagebytes: bytes, rect: Rect):
        ...

    async def display_rendered(self, rendered: "Rendered"):
        await self.display_pixels(rendered.image, rendered.extent)

    @abc.abstractmethod
    async def clear_screen(self):
        ...

    @abc.abstractmethod
    async def set_led_state(self, state: SetLed):
        ...

    async def _handle_keystream(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            if self.keystream is None:
                await checkpoint()
                continue
            with trio.CancelScope() as cancel_scope:
                self.keystream_cancel_scope = cancel_scope
                await self.set_led_state(SetLed(led=Led.LED_CAPSL, state=False))
                await self.set_led_state(SetLed(led=Led.LED_COMPOSE, state=False))
                async with self.keystream as keystream:
                    event: AnnotatedKeyEvent
                    async for event in keystream:
                        if event.is_led_able:
                            if event.annotation.capslock != self.capslock_led:
                                await self.set_led_state(
                                    SetLed(
                                        led=Led.LED_CAPSL,
                                        state=event.annotation.capslock,
                                    )
                                )
                                self.capslock_led = event.annotation.capslock
                            if event.annotation.compose != self.compose_led:
                                await self.set_led_state(
                                    SetLed(
                                        led=Led.LED_COMPOSE,
                                        state=event.annotation.compose,
                                    )
                                )
                                self.compose_led = event.annotation.compose
                        await self.event_channel.send(event)

    async def _handle_touchstream(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            if self.touchstream is None:
                await checkpoint()
                continue
            with trio.CancelScope() as cancel_scope:
                self.touchstream_cancel_scope = cancel_scope
                async with self.touchstream as touchstream:
                    async for event in touchstream:
                        await self.event_channel.send(event)

    def reset_keystream(self, enable_composes: bool):
        # when resetting the keystream, we want to cancel the current handler and start a new one.
        old_send_channel = self.keystream_send_channel
        (
            new_keystream_send_channel,
            new_keystream_receive_channel,
        ) = trio.open_memory_channel(0)
        self.keystream = make_keystream(
            new_keystream_receive_channel, self.settings, enable_composes
        )
        self.keystream_send_channel = new_keystream_send_channel
        if old_send_channel is not None:
            old_send_channel.close()
        self.keystream_cancel_scope.cancel()

    def reset_touchstream(self):
        # we would reset it when changing screens, for instance
        old_send_channel = self.touchstream_send_channel
        (
            new_touchstream_send_channel,
            new_touchstream_receive_channel,
        ) = trio.open_memory_channel(0)
        self.touchstream = make_tapstream(new_touchstream_receive_channel)
        self.touchstream_send_channel = new_touchstream_send_channel
        if old_send_channel is not None:
            old_send_channel.close()
        self.touchstream_cancel_scope.cancel()

    def _transform_touch_event(self, event: TouchEvent):
        return self.touch_coordinate_transform.apply(event, self.screen_size)


class RpcHardware(Hardware):
    battery_state_response: trio_util.AsyncValue[typing.Optional[BatteryState]]
    screen_info_response: trio_util.AsyncValue[typing.Optional[ScreenInfo]]

    def __init__(
        self,
        event_channel: trio.abc.SendChannel,
        settings: Settings,
    ):
        super().__init__(event_channel, settings)
        self.host = "kobo"
        self.port = 1234
        self.battery_state_response = trio_util.AsyncValue(None)
        self.screen_info_response = trio_util.AsyncValue(None)

        self.req_send_channel, self.req_receive_channel = trio.open_memory_channel(0)

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

    async def display_pixels(self, imagebytes: bytes, rect: Rect):
        if not isinstance(imagebytes, bytes):
            raise TypeError("can only display bytes")
        await self.req_send_channel.send(
            RpcDisplayPixels(imagebytes, ScreenRect.from_rect(rect))
        )

    async def clear_screen(self):
        await self.req_send_channel.send(RpcClearScreen())

    async def set_led_state(self, state: SetLed):
        await self.req_send_channel.send(RpcSetLed(led=state.led, state=state.state))

    async def _send_host_requests(
        self,
        network_channel: trio.abc.SendChannel,
        *,
        task_status=trio.TASK_STATUS_IGNORED,
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
        task_status=trio.TASK_STATUS_IGNORED,
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
                    screen_size = Size(width=req.width, height=req.height)
                    self.screen_size = screen_size
                    self.touch_coordinate_transform = req.touch_coordinate_transform
                    self.screen_info_response.value = ScreenInfo(
                        size=screen_size, dpi=req.dpi
                    )
                case RpcKeyEvent():
                    await self.keystream_send_channel.send(
                        KeyEvent(key=req.key, press=req.press)
                    )
                case RpcTouchReport():
                    # TODO: incorporate the transform into the touchscreen evdev procesing
                    await self.touchstream_send_channel.send(
                        TouchReport(
                            touches=[
                                self._transform_touch_event(evt) for evt in req.touches
                            ],
                            sec=req.sec,
                            usec=req.usec,
                        )
                    )
                case RpcKeyboardDisconnect():
                    await self.event_channel.send(KeyboardDisconnect())
            await checkpoint()

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        client_stream = await trio.open_tcp_stream(self.host, self.port)
        async with client_stream, tricycle.open_service_nursery() as nursery:
            task_status.started()
            network_channel = LengthPrefixedMsgpackStreamChannel(client_stream)
            nursery.start_soon(self._handle_kobo_requests, network_channel)
            nursery.start_soon(self._send_host_requests, network_channel)
            nursery.start_soon(self._handle_keystream)
            nursery.start_soon(self._handle_touchstream)


class EventTestHardware(Hardware):
    def __init__(
        self,
        event_channel: trio.abc.SendChannel,
        settings: Settings,
        incoming_event_channel: trio.abc.ReceiveChannel,
    ):
        super().__init__(event_channel, settings)
        self.incoming_event_channel = incoming_event_channel
        self.capslock_led = False
        self.compose_led = False

    async def get_battery_state(self) -> BatteryState:
        await checkpoint()
        return BatteryState(state=ChargingState.NOT_CHARGING, current_charge=100)

    async def get_screen_info(self) -> ScreenInfo:
        await checkpoint()
        return ScreenInfo(width=100, height=100, dpi=100)

    async def display_pixels(self, imagebytes: bytes, rect: Rect):
        await checkpoint()

    async def clear_screen(self):
        await checkpoint()

    async def set_led_state(self, state: SetLed):
        await checkpoint()
        match state.led:
            case Led.LED_CAPSL:
                self.capslock_led = state.state
            case Led.LED_COMPOSE:
                self.compose_led = state.state

    async def _handle_events(self, *, task_status=trio.TASK_STATUS_IGNORED):
        async with self.incoming_event_channel:
            task_status.started()
            async for event in self.incoming_event_channel:
                match event:
                    case KeyEvent():
                        if self.keystream_send_channel is not None:
                            await self.keystream_send_channel.send(event)
                    case TouchReport():
                        if self.touchstream_send_channel is not None:
                            await self.touchstream_send_channel.send(event)
                    case _:
                        raise NotImplementedError(
                            f"Don't know how to handle {type(event)}."
                        )

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        async with tricycle.open_service_nursery() as nursery:
            task_status.started()
            nursery.start_soon(self._handle_events)
            nursery.start_soon(self._handle_keystream)
            nursery.start_soon(self._handle_touchstream)

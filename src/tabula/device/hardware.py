from __future__ import annotations

import abc
import typing

import tricycle
import trio

from ..commontypes import Rect, ScreenInfo, ScreenRotation, Size, TouchCoordinateTransform
from ..settings import Settings
from .gestures import make_tapstream
from .hwtypes import (
    AnnotatedKeyEvent,
    KeyEvent,
    SetLed,
    TouchEvent,
    TouchReport,
)
from .keyboard_consts import Led
from .keystreams import make_keystream

if typing.TYPE_CHECKING:
    from ..rendering.rendertypes import Rendered


class Hardware(metaclass=abc.ABCMeta):
    screen_size: Size
    touch_coordinate_transform: TouchCoordinateTransform
    capslock_led: bool
    compose_led: bool
    event_channel: trio.abc.SendChannel
    event_receive_channel: trio.abc.ReceiveChannel

    def __init__(
        self,
        settings: Settings,
    ):
        self.event_channel, self.event_receive_channel = trio.open_memory_channel(0)
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
    def get_screen_info(self) -> ScreenInfo: ...

    @abc.abstractmethod
    def set_rotation(self, sr: ScreenRotation): ...

    @abc.abstractmethod
    def display_pixels(self, imagebytes: bytes, rect: Rect): ...

    def display_rendered(self, rendered: "Rendered"):
        self.display_pixels(rendered.image, rendered.extent)

    @abc.abstractmethod
    def clear_screen(self): ...

    @abc.abstractmethod
    def set_led_state(self, state: SetLed): ...

    async def _handle_keystream(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            if self.keystream is None:
                await trio.lowlevel.checkpoint()
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
                await trio.lowlevel.checkpoint()
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
        self.keystream = make_keystream(new_keystream_receive_channel, self.settings, enable_composes)
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
        return event.apply_transform(self.touch_coordinate_transform, self.screen_size)


class KoboHardware(Hardware):
    def __init__(
        self,
        settings: Settings,
    ):
        super().__init__(settings)
        from .fbink_screen_display import FbInk

        self.fbink = FbInk()
        self.keyboards = None

    def get_screen_info(self) -> ScreenInfo:
        info = self.fbink.get_screen_info()
        return info

    def set_rotation(self, sr: ScreenRotation):
        raise NotImplementedError()

    def display_pixels(self, imagebytes: bytes, rect: Rect):
        if self.fbink.active:
            self.fbink.display_pixels(imagebytes, rect)

    def clear_screen(self):
        if self.fbink.active:
            self.fbink.clear()

    def set_led_state(self, state: SetLed):
        if self.keyboards is not None:
            self.keyboards.set_led(state.led, state.state)

    def set_waveform_mode(self, wfm_mode: str):
        self.fbink.set_waveform_mode(wfm_mode)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        from .kobo_keyboard import AllKeyboards
        from .kobo_touchscreen import Touchscreen

        with self.fbink:
            async with trio.open_nursery() as nursery:
                task_status.started()
                self.keyboards = AllKeyboards(self.send_channel.clone())
                nursery.start_soon(self.keyboards.run)
                touchscreen = Touchscreen(self.send_channel.clone())
                nursery.start_soon(touchscreen.run)


class EventTestHardware(Hardware):
    def __init__(
        self,
        event_channel: trio.abc.SendChannel,
        settings: Settings,
        incoming_event_channel: trio.abc.ReceiveChannel,
    ):
        super().__init__(settings)
        self.event_channel = event_channel
        self.incoming_event_channel = incoming_event_channel
        self.capslock_led = False
        self.compose_led = False

    def get_screen_info(self) -> ScreenInfo:
        return ScreenInfo(width=100, height=100, dpi=100)

    def display_pixels(self, imagebytes: bytes, rect: Rect):
        pass

    def clear_screen(self):
        pass

    def set_led_state(self, state: SetLed):
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
                        raise NotImplementedError(f"Don't know how to handle {type(event)}.")

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        async with tricycle.open_service_nursery() as nursery:
            task_status.started()
            nursery.start_soon(self._handle_events)
            nursery.start_soon(self._handle_keystream)
            nursery.start_soon(self._handle_touchstream)

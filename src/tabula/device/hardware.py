from __future__ import annotations

import contextlib
import typing

import trio

from ..commontypes import Rect, ScreenInfo, ScreenRotation, Size, TouchCoordinateTransform
from .eventsource import LedCode
from .gestures import make_tapstream
from .hwtypes import (
    KEYBOARD_SEND_CHANNEL,
    TOUCHSCREEN_SEND_CHANNEL,
    BluetoothVariant,
    DisplayUpdateMode,
    KeyEvent,
    SetLed,
    TabulaEvent,
    TapEvent,
    TouchReport,
)
from .keystreams import make_keystream
from .kobo_models import detect_model

if typing.TYPE_CHECKING:
    from ..rendering.rendertypes import Rendered
    from ..settings import Settings


class Hardware:
    screen_size: Size
    touch_coordinate_transform: TouchCoordinateTransform
    capslock_led: bool
    compose_led: bool
    event_channel: trio.abc.SendChannel[TabulaEvent]
    event_receive_channel: trio.abc.ReceiveChannel[TabulaEvent]

    def __init__(
        self,
        settings: Settings,
    ):
        from .fbink_screen_display import FbInk  # can't import this if fbink library doesn't exist, so it has to be here

        self.model = detect_model()
        self.keyboard = None
        self.touchscreen = None
        self.event_channel, self.event_receive_channel = trio.open_memory_channel(0)
        self.settings = settings
        self.capslock_led = False
        self.compose_led = False
        self.keystream_cancel_scope = trio.CancelScope()
        self.keystream = None
        self.reset_keystream()
        self.screen_size = Size(0, 0)
        self.touch_coordinate_transform = TouchCoordinateTransform.IDENTITY
        self.touchstream_cancel_scope = trio.CancelScope()
        self.touchstream = None
        self.reset_touchstream()

        if self.settings.enable_bluetooth and self.model.bluetooth_variant is not BluetoothVariant.NONE:
            match self.model.bluetooth_variant:
                case BluetoothVariant.CLARA2E:
                    from .bluetooth.clara2e import bluetooth

                    self.bluetooth_cm = bluetooth
                case _:
                    raise NotImplementedError()
        else:
            self.bluetooth_cm = contextlib.nullcontext

        self.fbink = FbInk()

    def get_screen_info(self) -> ScreenInfo:
        info = self.fbink.get_screen_info()
        self.screen_size = info.size
        self.touch_coordinate_transform = info.touch_coordinate_transform
        return info

    def set_rotation(self, sr: ScreenRotation):
        self.fbink.set_rotation(sr)
        self.get_screen_info()  # refresh screen_size and touch_coordinate_transform

    def display_pixels(self, imagebytes: bytes, rect: Rect):
        if self.fbink.active:
            self.fbink.display_pixels(imagebytes, rect)

    def display_rendered(self, rendered: Rendered):
        self.display_pixels(rendered.image, rendered.extent)

    def set_display_update_mode(self, mode: DisplayUpdateMode):
        self.fbink.set_display_update_mode(mode)

    def display_update_mode(self, mode: DisplayUpdateMode):
        return self.fbink.display_update_mode(mode)

    def clear_screen(self):
        if self.fbink.active:
            self.fbink.clear()

    def set_led_state(self, state: SetLed):
        if self.keyboard is not None:
            self.keyboard.set_led_state(state)

    async def _handle_keystream(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            if self.keystream is None:
                await trio.lowlevel.checkpoint()
                continue
            with trio.CancelScope() as cancel_scope:
                self.keystream_cancel_scope = cancel_scope
                self.set_led_state(SetLed(led=LedCode.LED_CAPSL, state=False))
                self.set_led_state(SetLed(led=LedCode.LED_COMPOSE, state=False))
                async with self.keystream as keystream:
                    async for event in keystream:
                        if event.is_led_able:
                            if event.annotation.capslock != self.capslock_led:
                                self.set_led_state(SetLed(led=LedCode.LED_CAPSL, state=event.annotation.capslock))
                                self.capslock_led = event.annotation.capslock
                            if event.annotation.compose != self.compose_led:
                                self.set_led_state(SetLed(led=LedCode.LED_COMPOSE, state=event.annotation.compose))
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
                        await self.event_channel.send(self._transform_tap_event(event))

    def reset_keystream(self):
        # when resetting the keystream, we want to cancel the current handler and start a new one.
        old_send_channel = KEYBOARD_SEND_CHANNEL.get(None)
        (
            new_keystream_send_channel,
            new_keystream_receive_channel,
        ) = trio.open_memory_channel[KeyEvent](0)
        KEYBOARD_SEND_CHANNEL.set(new_keystream_send_channel)
        self.keystream = make_keystream(new_keystream_receive_channel, self.settings)
        if old_send_channel is not None:
            old_send_channel.close()
        self.keystream_cancel_scope.cancel()

    def reset_touchstream(self):
        # we would reset it when changing screens, for instance
        old_send_channel = TOUCHSCREEN_SEND_CHANNEL.get(None)
        (
            new_touchstream_send_channel,
            new_touchstream_receive_channel,
        ) = trio.open_memory_channel[TouchReport](0)
        TOUCHSCREEN_SEND_CHANNEL.set(new_touchstream_send_channel)
        self.touchstream = make_tapstream(new_touchstream_receive_channel)
        if old_send_channel is not None:
            old_send_channel.close()
        self.touchstream_cancel_scope.cancel()

    def _transform_tap_event(self, event: TapEvent):
        return event.apply_transform(self.touch_coordinate_transform, self.screen_size)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        from .kobo_keyboard import LibevdevKeyboard
        from .kobo_touchscreen import Touchscreen

        with self.fbink:
            async with self.bluetooth_cm(), trio.open_nursery() as nursery:
                task_status.started()
                self.keyboard = LibevdevKeyboard(self.event_channel.clone(), self.model.min_keyboard_input)
                nursery.start_soon(self._handle_keystream)
                nursery.start_soon(self.keyboard.run)
                touchscreen = Touchscreen(self.model.multitouch_variant)
                nursery.start_soon(self._handle_touchstream)
                nursery.start_soon(touchscreen.run)

    async def print_events(self):
        async with self.event_receive_channel:
            async for evt in self.event_receive_channel:
                print(evt)

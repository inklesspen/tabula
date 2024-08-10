# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import abc
import unicodedata
from contextlib import aclosing, asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterable, cast

import msgspec
import trio

from .eventsource import KeyCode
from .hwtypes import AnnotatedKeyEvent, KeyEvent, KeyPress, ModifierAnnotation

if TYPE_CHECKING:
    from ..settings import Settings


class Section(abc.ABC):
    @abc.abstractmethod
    async def pump(self, source: trio.MemoryReceiveChannel[Any], sink: trio.MemorySendChannel[Any]): ...


# stage 1: track modifier keydown/up and annotate keystream with current modifiers
class ModifierTracking(Section):
    def __init__(self):
        self.momentary_state = {
            KeyCode.KEY_LEFTALT: False,
            KeyCode.KEY_RIGHTALT: False,
            KeyCode.KEY_LEFTCTRL: False,
            KeyCode.KEY_RIGHTCTRL: False,
            KeyCode.KEY_LEFTMETA: False,
            KeyCode.KEY_RIGHTMETA: False,
            KeyCode.KEY_LEFTSHIFT: False,
            KeyCode.KEY_RIGHTSHIFT: False,
        }
        self.lock_state = {
            KeyCode.KEY_CAPSLOCK: False,
        }

    def _make_annotation(self):
        return ModifierAnnotation(
            alt=self.momentary_state[KeyCode.KEY_LEFTALT] or self.momentary_state[KeyCode.KEY_RIGHTALT],
            ctrl=self.momentary_state[KeyCode.KEY_LEFTCTRL] or self.momentary_state[KeyCode.KEY_RIGHTCTRL],
            meta=self.momentary_state[KeyCode.KEY_LEFTMETA] or self.momentary_state[KeyCode.KEY_RIGHTMETA],
            shift=self.momentary_state[KeyCode.KEY_LEFTSHIFT] or self.momentary_state[KeyCode.KEY_RIGHTSHIFT],
            capslock=self.lock_state[KeyCode.KEY_CAPSLOCK],
        )

    async def pump(self, source: trio.MemoryReceiveChannel[KeyEvent], sink: trio.MemorySendChannel[AnnotatedKeyEvent]):
        async with aclosing(source), aclosing(sink):
            async for event in source:
                is_modifier = False
                is_led_able = False
                if event.key in self.momentary_state:
                    is_modifier = True
                    self.momentary_state[event.key] = event.press is not KeyPress.RELEASED
                if event.key in self.lock_state:
                    is_modifier = True
                    is_led_able = True
                    if event.press is KeyPress.PRESSED:
                        self.lock_state[event.key] = not self.lock_state[event.key]
                await sink.send(
                    AnnotatedKeyEvent(
                        key=event.key,
                        press=event.press,
                        annotation=self._make_annotation(),
                        is_modifier=is_modifier,
                        is_led_able=is_led_able,
                    )
                )


# stage 1.5: drop KeyPress.RELEASED events
class OnlyPresses(Section):
    async def pump(self, source: trio.MemoryReceiveChannel[AnnotatedKeyEvent], sink: trio.MemorySendChannel[AnnotatedKeyEvent]):
        async with aclosing(source), aclosing(sink):
            async for event in source:
                if event.press == KeyPress.PRESSED:
                    await sink.send(event)


# stage 2: convert key event + modifier into character
class MakeCharacter(Section):
    def __init__(self, keymaps: dict[KeyCode, list[str]]):
        self.keymaps = keymaps

    async def pump(self, source: trio.MemoryReceiveChannel[AnnotatedKeyEvent], sink: trio.MemorySendChannel[AnnotatedKeyEvent]):
        async with aclosing(source), aclosing(sink):
            async for event in source:
                if event.key in self.keymaps:
                    keymap = self.keymaps[event.key]
                    is_shifted = event.annotation.shift
                    is_letter = unicodedata.category(keymap[0]).startswith("L")
                    if is_letter:
                        is_shifted ^= event.annotation.capslock
                    level = 1 if is_shifted else 0
                    await sink.send(msgspec.structs.replace(event, character=keymap[level]))
                else:
                    await sink.send(event)


# stage 2.25: convert compose key to KEY_COMPOSE (more convenient to keep separate from synthesis)
class ComposeKey(Section):
    def __init__(self, compose_key: KeyCode):
        self.compose_key = compose_key

    async def pump(self, source: trio.MemoryReceiveChannel[AnnotatedKeyEvent], sink: trio.MemorySendChannel[AnnotatedKeyEvent]):
        async with aclosing(source), aclosing(sink):
            async for event in source:
                if event.key == self.compose_key:
                    await sink.send(
                        AnnotatedKeyEvent(
                            key=KeyCode.KEY_COMPOSE,
                            press=KeyPress.PRESSED,
                            annotation=ModifierAnnotation(compose=True, capslock=event.annotation.capslock),
                            is_modifier=True,
                            is_led_able=True,
                        )
                    )
                else:
                    await sink.send(event)


@asynccontextmanager
async def pump_all(first_source: AsyncIterable[Any], *sections: Section):
    async with trio.open_nursery() as nursery:
        section_input = first_source
        for section in sections:
            section_send_channel, section_receive_channel = trio.open_memory_channel(0)
            nursery.start_soon(section.pump, section_input, section_send_channel)
            section_input = section_receive_channel
        yield section_input
        nursery.cancel_scope.cancel()


@asynccontextmanager
async def make_keystream(
    key_event_channel: trio.MemoryReceiveChannel[KeyEvent],
    settings: Settings,
):
    sections = [
        ModifierTracking(),
        OnlyPresses(),
        MakeCharacter(settings.keymaps),
        ComposeKey(settings.compose_key),
    ]

    async with pump_all(key_event_channel, *sections) as keystream:
        yield cast(trio.MemoryReceiveChannel[AnnotatedKeyEvent], keystream)

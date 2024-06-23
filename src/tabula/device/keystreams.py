# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import abc
from contextlib import asynccontextmanager, aclosing
import enum
import unicodedata
from typing import Any, AsyncIterable, cast

import msgspec
import pygtrie
import trio

from .hwtypes import KeyEvent, Key, KeyPress, ModifierAnnotation, AnnotatedKeyEvent
from ..settings import Settings


class Section(abc.ABC):
    @abc.abstractmethod
    async def pump(self, source: trio.MemoryReceiveChannel[Any], sink: trio.MemorySendChannel[Any]): ...


# stage 1: track modifier keydown/up and annotate keystream with current modifiers
class ModifierTracking(Section):
    def __init__(self):
        self.momentary_state = {
            Key.KEY_LEFTALT: False,
            Key.KEY_RIGHTALT: False,
            Key.KEY_LEFTCTRL: False,
            Key.KEY_RIGHTCTRL: False,
            Key.KEY_LEFTMETA: False,
            Key.KEY_RIGHTMETA: False,
            Key.KEY_LEFTSHIFT: False,
            Key.KEY_RIGHTSHIFT: False,
        }
        self.lock_state = {
            Key.KEY_CAPSLOCK: False,
        }

    def _make_annotation(self):
        return ModifierAnnotation(
            alt=self.momentary_state[Key.KEY_LEFTALT] or self.momentary_state[Key.KEY_RIGHTALT],
            ctrl=self.momentary_state[Key.KEY_LEFTCTRL] or self.momentary_state[Key.KEY_RIGHTCTRL],
            meta=self.momentary_state[Key.KEY_LEFTMETA] or self.momentary_state[Key.KEY_RIGHTMETA],
            shift=self.momentary_state[Key.KEY_LEFTSHIFT] or self.momentary_state[Key.KEY_RIGHTSHIFT],
            capslock=self.lock_state[Key.KEY_CAPSLOCK],
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
    def __init__(self, keymaps: dict[Key, list[str]]):
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
    def __init__(self, compose_key: Key):
        self.compose_key = compose_key

    async def pump(self, source: trio.MemoryReceiveChannel[AnnotatedKeyEvent], sink: trio.MemorySendChannel[AnnotatedKeyEvent]):
        async with aclosing(source), aclosing(sink):
            async for event in source:
                if event.key == self.compose_key:
                    await sink.send(
                        AnnotatedKeyEvent(
                            key=Key.KEY_COMPOSE,
                            press=KeyPress.PRESSED,
                            annotation=ModifierAnnotation(compose=True, capslock=event.annotation.capslock),
                            is_modifier=True,
                            is_led_able=True,
                        )
                    )
                else:
                    await sink.send(event)


# stage 2.5: synthesize based on key sequences
SYNTHETIC_SEQUENCES = pygtrie.Trie({(Key.KEY_COMPOSE, Key.KEY_COMPOSE): Key.SYNTHETIC_COMPOSE_DOUBLETAP})


class KeystreamState(enum.Enum):
    PASSTHROUGH = enum.auto()
    COLLECTING = enum.auto()


class SynthesizeKeys(Section):
    def __init__(self):
        self.sequences = SYNTHETIC_SEQUENCES
        self.state = KeystreamState.PASSTHROUGH
        self.collected = []

    async def pump(self, source: trio.MemoryReceiveChannel[AnnotatedKeyEvent], sink: trio.MemorySendChannel[AnnotatedKeyEvent]):
        async with aclosing(source), aclosing(sink):
            async for event in source:
                await sink.send(event)
                match self.state:
                    case KeystreamState.PASSTHROUGH:
                        if bool(self.sequences.has_node([event.key])):
                            self.state = KeystreamState.COLLECTING
                            self.collected.append(event)
                    case KeystreamState.COLLECTING:
                        self.collected.append(event)
                        collected_keys = [e.key for e in self.collected]
                        if self.sequences.has_key(collected_keys):
                            # success
                            synthesized_key = self.sequences[collected_keys]
                            await sink.send(
                                AnnotatedKeyEvent(
                                    key=synthesized_key,
                                    press=KeyPress.PRESSED,
                                    annotation=ModifierAnnotation(capslock=event.annotation.capslock),
                                )
                            )
                            self.collected = []
                            self.state = KeystreamState.PASSTHROUGH
                        elif bool(self.sequences.has_node(collected_keys)):
                            # still can match
                            continue
                        else:
                            # failure
                            self.collected = []
                            self.state = KeystreamState.PASSTHROUGH


# stage 3: compose sequences
class ComposeCharacters(Section):
    devoured: list[AnnotatedKeyEvent]
    devoured_characters: list[str]

    def __init__(self, sequences: pygtrie.Trie):
        self.sequences = sequences
        self.state = KeystreamState.PASSTHROUGH
        self.devoured = []
        self.devoured_characters = []

    async def pump(self, source: trio.MemoryReceiveChannel[AnnotatedKeyEvent], sink: trio.MemorySendChannel[AnnotatedKeyEvent]):
        async with aclosing(source), aclosing(sink):
            async for event in source:
                # TODO: figure out how to improve this state machine; the COLLECTING state is super complex
                match self.state:
                    case KeystreamState.PASSTHROUGH:
                        if event.key == Key.KEY_COMPOSE:
                            self.state = KeystreamState.COLLECTING
                            self.devoured = []
                            self.devoured_characters = []
                            # fallthrough and emit the KEY_COMPOSE event for visibility
                        await sink.send(event)
                    case KeystreamState.COLLECTING:
                        # TODO: if key is compose, restart the collecting
                        self.devoured.append(event)
                        if event.is_modifier and not event.is_led_able:
                            continue
                        still_matching = False
                        if event.character is not None:
                            self.devoured_characters.append(event.character)
                            still_matching = bool(self.sequences.has_node(self.devoured_characters))
                        if not (still_matching or event.is_modifier):
                            # not a match
                            self.state = KeystreamState.PASSTHROUGH
                            # synthesize a KEY_COMPOSE event for visibility, ending the compose annotation
                            await sink.send(
                                AnnotatedKeyEvent(
                                    key=Key.KEY_COMPOSE,
                                    press=KeyPress.PRESSED,
                                    annotation=msgspec.structs.replace(event.annotation, compose=False),
                                    is_modifier=True,
                                    is_led_able=True,
                                )
                            )
                            for devoured_event in self.devoured:
                                await sink.send(devoured_event)
                        else:
                            if self.sequences.has_key(self.devoured_characters):
                                # end of sequence
                                new_event = AnnotatedKeyEvent(
                                    key=Key.KEY_COMPOSE,
                                    press=KeyPress.PRESSED,
                                    annotation=ModifierAnnotation(capslock=event.annotation.capslock),
                                    character=self.sequences[self.devoured_characters],
                                    is_modifier=False,
                                    is_led_able=True,
                                )
                                self.state = KeystreamState.PASSTHROUGH
                                await sink.send(new_event)
                            if event.is_led_able:
                                # emit the event for visibility, but with compose annotated
                                visible_event = msgspec.structs.replace(
                                    event,
                                    annotation=msgspec.structs.replace(event.annotation, compose=True),
                                )
                                await sink.send(visible_event)


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
    enable_composes: bool,
):
    sections = [
        ModifierTracking(),
        OnlyPresses(),
        MakeCharacter(settings.keymaps),
        ComposeKey(settings.compose_key),
    ]
    if enable_composes:
        sections.append(SynthesizeKeys())
        sections.append(ComposeCharacters(settings.compose_sequences))

    async with pump_all(key_event_channel, *sections) as keystream:
        yield cast(trio.MemoryReceiveChannel[AnnotatedKeyEvent], keystream)

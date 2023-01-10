# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import asynccontextmanager, aclosing

from slurry import Pipeline
from slurry.environments import TrioSection
import pygtrie
import trio

from .hwtypes import KeyEvent, Key, KeyPress, ModifierAnnotation, AnnotatedKeyEvent
from .settings import Settings
from .util import evolve

# stage 1: track modifier keydown/up and annotate keystream with current modifiers
class ModifierTracking(TrioSection):
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
            alt=self.momentary_state[Key.KEY_LEFTALT]
            or self.momentary_state[Key.KEY_RIGHTALT],
            ctrl=self.momentary_state[Key.KEY_LEFTCTRL]
            or self.momentary_state[Key.KEY_RIGHTCTRL],
            meta=self.momentary_state[Key.KEY_LEFTMETA]
            or self.momentary_state[Key.KEY_RIGHTMETA],
            shift=self.momentary_state[Key.KEY_LEFTSHIFT]
            or self.momentary_state[Key.KEY_RIGHTSHIFT],
            capslock=self.lock_state[Key.KEY_CAPSLOCK],
        )

    async def refine(self, input, output):
        event: KeyEvent
        async with aclosing(input) as source:
            async for event in source:
                is_modifier = False
                is_led_able = False
                if event.key in self.momentary_state:
                    is_modifier = True
                    self.momentary_state[event.key] = (
                        event.press is not KeyPress.RELEASED
                    )
                if event.key in self.lock_state:
                    is_modifier = True
                    is_led_able = True
                    if event.press is KeyPress.PRESSED:
                        self.lock_state[event.key] = not self.lock_state[event.key]
                await output(
                    AnnotatedKeyEvent(
                        key=event.key,
                        press=event.press,
                        annotation=self._make_annotation(),
                        is_modifier=is_modifier,
                        is_led_able=is_led_able,
                    )
                )


# stage 1.5: drop KeyPress.RELEASED events
class OnlyPresses(TrioSection):
    async def refine(self, input, output):
        event: AnnotatedKeyEvent
        async with aclosing(input) as source:
            async for event in source:
                if event.press == KeyPress.PRESSED:
                    await output(event)


# stage 2: convert key event + modifier into character
class MakeCharacter(TrioSection):
    def __init__(self, keymaps: dict[Key, list[str]]):
        self.keymaps = keymaps

    async def refine(self, input, output):
        event: AnnotatedKeyEvent
        async with aclosing(input) as source:
            async for event in source:
                is_shifted = event.annotation.shift ^ event.annotation.capslock
                level = 1 if is_shifted else 0
                if event.key in self.keymaps:
                    await output(
                        evolve(event, character=self.keymaps[event.key][level])
                    )
                else:
                    await output(event)


# stage 3: compose sequences
class ComposeCharacters(TrioSection):
    devoured: list[AnnotatedKeyEvent]
    devoured_characters: list[str]

    def __init__(self, sequences: pygtrie.Trie, compose_key: Key):
        self.sequences = sequences
        self.compose_key = compose_key
        self.devouring = False
        self.devoured = []
        self.devoured_characters = []

    async def refine(self, input, output):
        event: AnnotatedKeyEvent
        async with aclosing(input) as source:
            async for event in source:
                if self.devouring:
                    self.devoured.append(event)
                    if event.is_modifier and not event.is_led_able:
                        continue
                    still_matching = False
                    if event.character is not None:
                        self.devoured_characters.append(event.character)
                        still_matching = bool(
                            self.sequences.has_node(self.devoured_characters)
                        )
                    if not (still_matching or event.is_modifier):
                        # not a match
                        self.devouring = False
                        # synthesize a KEY_COMPOSE event for visibility
                        await output(
                            AnnotatedKeyEvent(
                                key=Key.KEY_COMPOSE,
                                press=KeyPress.PRESSED,
                                annotation=ModifierAnnotation(),
                                is_modifier=True,
                                is_led_able=True,
                            )
                        )
                        for devoured_event in self.devoured:
                            await output(devoured_event)
                    else:
                        if self.sequences.has_key(self.devoured_characters):
                            # end of sequence
                            new_event = AnnotatedKeyEvent(
                                key=Key.KEY_COMPOSE,
                                press=KeyPress.PRESSED,
                                annotation=ModifierAnnotation(
                                    capslock=event.annotation.capslock
                                ),
                                character=self.sequences[self.devoured_characters],
                                is_modifier=False,
                                is_led_able=True,
                            )
                            self.devouring = False
                            await output(new_event)
                        if event.is_led_able:
                            # emit the event for visibility, but with compose turned on
                            visible_event = evolve(
                                event, annotation=evolve(event.annotation, compose=True)
                            )
                            await output(visible_event)

                else:
                    if event.key == self.compose_key:
                        self.devouring = True
                        self.devoured = [event]
                        self.devoured_characters = []
                        # synthesize a KEY_COMPOSE event for visibility
                        await output(
                            AnnotatedKeyEvent(
                                key=Key.KEY_COMPOSE,
                                press=KeyPress.PRESSED,
                                annotation=ModifierAnnotation(compose=True),
                                is_modifier=True,
                                is_led_able=True,
                            )
                        )
                    else:
                        await output(event)


@asynccontextmanager
async def make_keystream(
    key_event_channel: trio.MemoryReceiveChannel,
    settings: Settings,
    enable_composes: bool,
):
    sections = [
        key_event_channel,
        ModifierTracking(),
        OnlyPresses(),
        MakeCharacter(settings.keymaps),
    ]
    if enable_composes:
        sections.append(
            ComposeCharacters(settings.compose_sequences, settings.compose_key)
        )
    keystream: trio.MemoryReceiveChannel
    async with Pipeline.create(*sections) as pipeline, pipeline.tap() as keystream:
        yield keystream

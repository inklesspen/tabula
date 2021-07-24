# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections.abc
import typing

import attr

from ..device.keyboard_consts import Key, KeyPress
from ..device.types import KeyEvent, Keyboard
from ..settings import Settings
from .types import ModifierAnnotation, AnnotatedKeyEvent


# stage 1: track modifier keydown/up and annotate keystream with current modifiers
class ModifierTracking:
    def __init__(self, wrapped: Keyboard):
        self.wrapped = wrapped
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

    async def keystream(self) -> collections.abc.AsyncIterable[AnnotatedKeyEvent]:
        event: KeyEvent
        async for event in self.wrapped.keystream():
            is_modifier = False
            if event.key in self.momentary_state:
                is_modifier = True
                self.momentary_state[event.key] = event.press is not KeyPress.RELEASED
            if event.key in self.lock_state:
                is_modifier = True
                if event.press is KeyPress.PRESSED:
                    self.lock_state[event.key] = not self.lock_state[event.key]
            yield AnnotatedKeyEvent(
                key=event.key,
                press=event.press,
                annotation=self._make_annotation(),
                is_modifier=is_modifier,
            )


# stage 1.5: drop KeyPress.RELEASED events
class OnlyPresses:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    async def keystream(self) -> collections.abc.AsyncIterable[AnnotatedKeyEvent]:
        event: AnnotatedKeyEvent
        async for event in self.wrapped.keystream():
            if event.press == KeyPress.PRESSED:
                yield event


# stage 2: convert key event + modifier into character
class MakeCharacter:
    def __init__(self, wrapped, settings: Settings):
        self.wrapped = wrapped
        self.maps = settings.keymaps  # from settings

    async def keystream(self) -> collections.abc.AsyncIterable[AnnotatedKeyEvent]:
        event: AnnotatedKeyEvent
        async for event in self.wrapped.keystream():
            is_shifted = event.annotation.shift ^ event.annotation.capslock
            keymap = self.maps[1] if is_shifted else self.maps[0]
            if event.key in keymap:
                yield attr.evolve(event, character=keymap[event.key])
            else:
                yield event


# stage 3: compose sequences
class ComposeCharacters:
    devoured: list[AnnotatedKeyEvent]
    devoured_characters: list[str]

    def __init__(self, wrapped, settings: Settings):
        self.wrapped = wrapped
        self.sequences = settings.compose_sequences
        # TODO: make this come from the current keyboard config
        self.compose_key = Key.KEY_RIGHTMETA
        self.devouring = False
        self.devoured = []
        self.devoured_characters = []

    async def keystream(self) -> collections.abc.AsyncIterable[AnnotatedKeyEvent]:
        event: AnnotatedKeyEvent
        async for event in self.wrapped.keystream():
            if self.devouring:
                self.devoured.append(event)
                if event.is_modifier:
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
                    for devoured_event in self.devoured:
                        yield devoured_event
                else:
                    if self.sequences.has_key(self.devoured_characters):
                        # end of sequence
                        new_event = AnnotatedKeyEvent(
                            key=Key.KEY_COMPOSE,
                            press=KeyPress.PRESSED,
                            annotation=ModifierAnnotation(),
                            character=self.sequences[self.devoured_characters],
                            is_modifier=False,
                        )
                        self.devouring = False
                        yield new_event

            else:
                if event.key == self.compose_key:
                    self.devouring = True
                    self.devoured = [event]
                    self.devoured_characters = []
                else:
                    yield event

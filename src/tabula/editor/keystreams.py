# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections.abc
import typing

import attr

from ..device.keyboard_consts import Key, KeyPress
from ..device.types import KeyEvent, Keyboard
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
            if event.key in self.momentary_state:
                self.momentary_state[event.key] = event.press is not KeyPress.RELEASED
            if event.key in self.lock_state:
                self.lock_state[event.key] = not self.lock_state[event.key]
            yield AnnotatedKeyEvent(
                key=event.key, press=event.press, annotation=self._make_annotation()
            )


# stage 2: convert key event + modifier into character or special key code
# stage 3: compose sequences

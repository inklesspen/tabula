# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections.abc
import typing
from contextlib import aclosing

import pygtrie
import pytest
import trio
from tabula.device.eventsource import KeyCode
from tabula.device.hwtypes import AnnotatedKeyEvent, KeyEvent, KeyPress, ModifierAnnotation
from tabula.device.keystreams import ComposeKey, MakeCharacter, ModifierTracking, OnlyPresses, make_keystream, pump_all
from tabula.settings import Settings
from trio.lowlevel import checkpoint

T = typing.TypeVar("T")


async def make_async_source(
    items: collections.abc.Sequence[T],
):
    for item in items:
        await checkpoint()
        yield item


async def test_modifier_tracking_basics():
    async with (
        aclosing(
            make_async_source(
                [
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_H, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_H, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_O, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_O, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_W, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_W, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_O, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_O, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_R, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_R, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_D, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_D, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                ]
            )
        ) as keysource,
        pump_all(keysource, ModifierTracking()) as resultsource,
    ):
        results = [event async for event in resultsource]
        expected = [
            AnnotatedKeyEvent(
                key=KeyCode.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_H,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_H,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(shift=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_LEFTSHIFT,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(key=KeyCode.KEY_E, press=KeyPress.PRESSED, annotation=ModifierAnnotation()),
            AnnotatedKeyEvent(key=KeyCode.KEY_E, press=KeyPress.RELEASED, annotation=ModifierAnnotation()),
            AnnotatedKeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED, annotation=ModifierAnnotation()),
            AnnotatedKeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED, annotation=ModifierAnnotation()),
            AnnotatedKeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED, annotation=ModifierAnnotation()),
            AnnotatedKeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED, annotation=ModifierAnnotation()),
            AnnotatedKeyEvent(key=KeyCode.KEY_O, press=KeyPress.PRESSED, annotation=ModifierAnnotation()),
            AnnotatedKeyEvent(key=KeyCode.KEY_O, press=KeyPress.RELEASED, annotation=ModifierAnnotation()),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_SPACE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_SPACE,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_W,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_W,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_O,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_O,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_R,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_R,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_L,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_D,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_D,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
        ]
        assert results == expected


async def test_make_characters():
    keymaps = {
        KeyCode.KEY_H: ["h", "H"],
        KeyCode.KEY_E: ["e", "E"],
        KeyCode.KEY_L: ["l", "L"],
        KeyCode.KEY_O: ["o", "O"],
        KeyCode.KEY_W: ["w", "W"],
        KeyCode.KEY_R: ["r", "R"],
        KeyCode.KEY_D: ["d", "D"],
        KeyCode.KEY_1: ["1", "!"],
        KeyCode.KEY_2: ["2", "@"],
        KeyCode.KEY_3: ["3", "#"],
        KeyCode.KEY_4: ["4", "$"],
        KeyCode.KEY_5: ["5", "%"],
        KeyCode.KEY_6: ["6", "^"],
        KeyCode.KEY_7: ["7", "&"],
        KeyCode.KEY_8: ["8", "*"],
        KeyCode.KEY_9: ["9", "("],
        KeyCode.KEY_0: ["0", ")"],
        KeyCode.KEY_MINUS: ["-", "_"],
        KeyCode.KEY_EQUAL: ["=", "+"],
    }
    async with (
        aclosing(
            make_async_source(
                [
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_H, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_H, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_O, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_O, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_W, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_W, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_O, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_O, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_R, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_R, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_D, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_D, press=KeyPress.RELEASED),
                    # Numbers and punctuation should not be affected by capslock
                    KeyEvent(key=KeyCode.KEY_1, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_1, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_EQUAL, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_EQUAL, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                    # But they should be affected by shift
                    KeyEvent(key=KeyCode.KEY_RIGHTSHIFT, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_1, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_1, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTSHIFT, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_EQUAL, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_EQUAL, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                ]
            )
        ) as keysource,
        pump_all(keysource, ModifierTracking(), OnlyPresses(), MakeCharacter(keymaps)) as resultsource,
    ):
        results = [event async for event in resultsource]
        expected = [
            AnnotatedKeyEvent(
                key=KeyCode.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_H,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="H",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_E,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="e",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_O,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="o",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_SPACE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_W,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="W",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_O,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="O",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_R,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="R",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="L",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_D,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="D",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_1,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="1",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_EQUAL,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="=",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_RIGHTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_1,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="!",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_EQUAL,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="+",
            ),
        ]
        assert results == expected


async def test_compose_key():
    async with (
        aclosing(
            make_async_source(
                [
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTALT, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTALT, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTCTRL, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTCTRL, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                ]
            )
        ) as keysource,
        pump_all(keysource, ModifierTracking(), OnlyPresses(), ComposeKey(KeyCode.KEY_RIGHTMETA)) as resultsource,
    ):
        results = [event async for event in resultsource]
        expected = [
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_LEFTALT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(alt=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(alt=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_RIGHTCTRL,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(ctrl=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(ctrl=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True, capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
        ]
        assert results == expected


@pytest.mark.skip
async def test_synthesize_keys():
    async with (
        aclosing(
            make_async_source(
                [
                    # synthesizes
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    # interrupted
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    # three produces a synthesized and then a lone compose
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    # capslock is conserved
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                ]
            )
        ) as keysource,
        pump_all(
            keysource,
            ModifierTracking(),
            OnlyPresses(),
            ComposeKey(KeyCode.KEY_RIGHTMETA),
            SynthesizeKeys(),
        ) as resultsource,
    ):
        results = [event async for event in resultsource]
        expected = [
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.SYNTHETIC_COMPOSE_DOUBLETAP,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.SYNTHETIC_COMPOSE_DOUBLETAP,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True, capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True, capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.SYNTHETIC_COMPOSE_DOUBLETAP,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
        ]
        assert results == expected


@pytest.mark.skip
async def test_composes():
    raw_composes = {
        "A E": "Æ",
        "a e": "æ",
    }
    composes = pygtrie.Trie({tuple(k.split()): v for k, v in raw_composes.items()})
    keymaps = {
        KeyCode.KEY_A: ["a", "A"],
        KeyCode.KEY_E: ["e", "E"],
    }
    async with (
        aclosing(
            make_async_source(
                [
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_E, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                ]
            )
        ) as keysource,
        pump_all(
            keysource,
            ModifierTracking(),
            OnlyPresses(),
            MakeCharacter(keymaps),
            ComposeKey(KeyCode.KEY_RIGHTMETA),
            SynthesizeKeys(),
            ComposeCharacters(composes),
        ) as resultchannel,
    ):
        actual = [event async for event in resultchannel]
        expected = [
            AnnotatedKeyEvent(
                key=KeyCode.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="A",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_E,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="e",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="æ",
                is_modifier=False,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="Æ",
                is_modifier=False,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True, capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="Æ",
                is_modifier=False,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
        ]
        assert actual == expected


@pytest.mark.skip
async def test_composes_sequence_failure():
    raw_composes = {
        "A E": "Æ",
        "a e": "æ",
    }
    composes = pygtrie.Trie({tuple(k.split()): v for k, v in raw_composes.items()})
    keymaps = {
        KeyCode.KEY_A: ["a", "A"],
        KeyCode.KEY_E: ["e", "E"],
        KeyCode.KEY_B: ["b", "B"],
    }
    async with (
        aclosing(
            make_async_source(
                [
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
                    KeyEvent(key=KeyCode.KEY_B, press=KeyPress.PRESSED),
                    KeyEvent(key=KeyCode.KEY_B, press=KeyPress.RELEASED),
                ]
            )
        ) as keysource,
        pump_all(
            keysource,
            ModifierTracking(),
            OnlyPresses(),
            MakeCharacter(keymaps),
            ComposeKey(KeyCode.KEY_RIGHTMETA),
            SynthesizeKeys(),
            ComposeCharacters(composes),
        ) as resultchannel,
    ):
        actual = [event async for event in resultchannel]
        expected = [
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="a",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_B,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="b",
            ),
        ]
        assert actual == expected


@pytest.mark.skip
async def test_keystream_factory():
    send_channel, receive_channel = trio.open_memory_channel(60)
    settings = Settings.for_test()
    key_events = [
        KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_COMMA, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_COMMA, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_COMMA, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_COMMA, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_C, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_C, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_M, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_M, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_E, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_E, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_SPACE, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_I, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_I, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_S, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_S, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_H, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_H, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_M, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_M, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_A, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_A, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_E, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_E, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_L, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_L, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_DOT, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_DOT, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_DOT, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_DOT, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_RIGHTMETA, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_DOT, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_DOT, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_DOT, press=KeyPress.PRESSED),
        KeyEvent(key=KeyCode.KEY_DOT, press=KeyPress.RELEASED),
        KeyEvent(key=KeyCode.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
    ]
    async with aclosing(send_channel):
        for event in key_events:
            await send_channel.send(event)

    async with make_keystream(receive_channel, settings, True) as keystream:
        actual = [event async for event in keystream]

        expected = [
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="«",
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_C,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="C",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="a",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_SPACE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character=" ",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_M,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="m",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_E,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="e",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_SPACE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character=" ",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_I,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="I",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_S,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="s",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_H,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="h",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_M,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="m",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="a",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_E,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="e",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="…",
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=KeyCode.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="»",
                is_led_able=True,
            ),
        ]
        assert actual == expected

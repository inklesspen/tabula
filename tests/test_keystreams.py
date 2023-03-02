# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections.abc
from contextlib import aclosing
import typing

import pygtrie
import slurry
import trio

from tabula.device.keystreams import (
    ModifierTracking,
    OnlyPresses,
    MakeCharacter,
    ComposeKey,
    SynthesizeKeys,
    ComposeCharacters,
    make_keystream,
)
from tabula.device.hwtypes import (
    Key,
    KeyPress,
    KeyEvent,
    AnnotatedKeyEvent,
    ModifierAnnotation,
)
from tabula.settings import Settings
from tabula.util import checkpoint

T = typing.TypeVar("T")


async def make_async_source(
    items: collections.abc.Sequence[T],
):
    for item in items:
        await checkpoint()
        yield item


async def test_modifier_tracking_basics():
    async with aclosing(
        make_async_source(
            [
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_H, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_H, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_O, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_O, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_SPACE, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_SPACE, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_W, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_W, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_O, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_O, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_R, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_R, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_D, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_D, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
            ]
        )
    ) as keysource, slurry.Pipeline.create(
        keysource, ModifierTracking()
    ) as pipeline, pipeline.tap() as resultsource:
        results = [event async for event in resultsource]
        expected = [
            AnnotatedKeyEvent(
                key=Key.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_H,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_H,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(shift=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_LEFTSHIFT,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_E, press=KeyPress.PRESSED, annotation=ModifierAnnotation()
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_E, press=KeyPress.RELEASED, annotation=ModifierAnnotation()
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L, press=KeyPress.PRESSED, annotation=ModifierAnnotation()
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L, press=KeyPress.RELEASED, annotation=ModifierAnnotation()
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L, press=KeyPress.PRESSED, annotation=ModifierAnnotation()
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L, press=KeyPress.RELEASED, annotation=ModifierAnnotation()
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_O, press=KeyPress.PRESSED, annotation=ModifierAnnotation()
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_O, press=KeyPress.RELEASED, annotation=ModifierAnnotation()
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_SPACE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_SPACE,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_W,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_W,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_O,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_O,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_R,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_R,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_D,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_D,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.RELEASED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
        ]
        assert results == expected


async def test_make_characters():
    keymaps = {
        Key.KEY_H: ["h", "H"],
        Key.KEY_E: ["e", "E"],
        Key.KEY_L: ["l", "L"],
        Key.KEY_O: ["o", "O"],
        Key.KEY_W: ["w", "W"],
        Key.KEY_R: ["r", "R"],
        Key.KEY_D: ["d", "D"],
        Key.KEY_1: ["1", "!"],
        Key.KEY_2: ["2", "@"],
        Key.KEY_3: ["3", "#"],
        Key.KEY_4: ["4", "$"],
        Key.KEY_5: ["5", "%"],
        Key.KEY_6: ["6", "^"],
        Key.KEY_7: ["7", "&"],
        Key.KEY_8: ["8", "*"],
        Key.KEY_9: ["9", "("],
        Key.KEY_0: ["0", ")"],
        Key.KEY_MINUS: ["-", "_"],
        Key.KEY_EQUAL: ["=", "+"],
    }
    async with aclosing(
        make_async_source(
            [
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_H, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_H, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_O, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_O, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_SPACE, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_SPACE, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_W, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_W, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_O, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_O, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_R, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_R, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_L, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_D, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_D, press=KeyPress.RELEASED),
                # Numbers and punctuation should not be affected by capslock
                KeyEvent(key=Key.KEY_1, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_1, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_EQUAL, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_EQUAL, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                # But they should be affected by shift
                KeyEvent(key=Key.KEY_RIGHTSHIFT, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_1, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_1, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTSHIFT, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_EQUAL, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_EQUAL, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
            ]
        )
    ) as keysource, slurry.Pipeline.create(
        keysource, ModifierTracking(), OnlyPresses(), MakeCharacter(keymaps)
    ) as pipeline, pipeline.tap() as resultsource:
        results = [event async for event in resultsource]
        expected = [
            AnnotatedKeyEvent(
                key=Key.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_H,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="H",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_E,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="e",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_O,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="o",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_SPACE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_W,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="W",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_O,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="O",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_R,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="R",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="L",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_D,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="D",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_1,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="1",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_EQUAL,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="=",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_RIGHTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_1,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="!",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_EQUAL,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="+",
            ),
        ]
        assert results == expected


async def test_compose_key():
    async with aclosing(
        make_async_source(
            [
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTALT, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTALT, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTCTRL, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTCTRL, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
            ]
        )
    ) as keysource, slurry.Pipeline.create(
        keysource, ModifierTracking(), OnlyPresses(), ComposeKey(Key.KEY_RIGHTMETA)
    ) as pipeline, pipeline.tap() as resultsource:
        results = [event async for event in resultsource]
        expected = [
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_LEFTALT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(alt=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(alt=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_RIGHTCTRL,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(ctrl=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(ctrl=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True, capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
        ]
        assert results == expected


async def test_synthesize_keys():
    async with aclosing(
        make_async_source(
            [
                # synthesizes
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                # interrupted
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                # three produces a synthesized and then a lone compose
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                # capslock is conserved
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
            ]
        )
    ) as keysource, slurry.Pipeline.create(
        keysource,
        ModifierTracking(),
        OnlyPresses(),
        ComposeKey(Key.KEY_RIGHTMETA),
        SynthesizeKeys(),
    ) as pipeline, pipeline.tap() as resultsource:
        results = [event async for event in resultsource]
        expected = [
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.SYNTHETIC_COMPOSE_DOUBLETAP,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.SYNTHETIC_COMPOSE_DOUBLETAP,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True, capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True, capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.SYNTHETIC_COMPOSE_DOUBLETAP,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
        ]
        assert results == expected


async def test_composes():
    raw_composes = {
        "A E": "Æ",
        "a e": "æ",
    }
    composes = pygtrie.Trie({tuple(k.split()): v for k, v in raw_composes.items()})
    keymaps = {
        Key.KEY_A: ["a", "A"],
        Key.KEY_E: ["e", "E"],
    }
    async with aclosing(
        make_async_source(
            [
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_E, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
            ]
        )
    ) as keysource, slurry.Pipeline.create(
        keysource,
        ModifierTracking(),
        OnlyPresses(),
        MakeCharacter(keymaps),
        ComposeKey(Key.KEY_RIGHTMETA),
        SynthesizeKeys(),
        ComposeCharacters(composes),
    ) as pipeline, pipeline.tap() as resultchannel:
        actual = [event async for event in resultchannel]
        expected = [
            AnnotatedKeyEvent(
                key=Key.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="A",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_E,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="e",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="æ",
                is_modifier=False,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="Æ",
                is_modifier=False,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True, capslock=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(capslock=True),
                character="Æ",
                is_modifier=False,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_CAPSLOCK,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
        ]
        assert actual == expected


async def test_composes_sequence_failure():
    raw_composes = {
        "A E": "Æ",
        "a e": "æ",
    }
    composes = pygtrie.Trie({tuple(k.split()): v for k, v in raw_composes.items()})
    keymaps = {
        Key.KEY_A: ["a", "A"],
        Key.KEY_E: ["e", "E"],
        Key.KEY_B: ["b", "B"],
    }
    async with aclosing(
        make_async_source(
            [
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
                KeyEvent(key=Key.KEY_B, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_B, press=KeyPress.RELEASED),
            ]
        )
    ) as keysource, slurry.Pipeline.create(
        keysource,
        ModifierTracking(),
        OnlyPresses(),
        MakeCharacter(keymaps),
        ComposeKey(Key.KEY_RIGHTMETA),
        SynthesizeKeys(),
        ComposeCharacters(composes),
    ) as pipeline, pipeline.tap() as resultchannel:
        actual = [event async for event in resultchannel]
        expected = [
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="a",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_B,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="b",
            ),
        ]
        assert actual == expected


async def test_keystream_factory():
    send_channel, receive_channel = trio.open_memory_channel(60)
    settings = Settings.for_test()
    key_events = [
        KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_COMMA, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_COMMA, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_COMMA, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_COMMA, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_C, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_C, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_L, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_L, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_L, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_L, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_SPACE, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_SPACE, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_M, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_M, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_E, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_E, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_SPACE, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_SPACE, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_I, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_I, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_S, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_S, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_H, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_H, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_M, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_M, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_A, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_A, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_E, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_E, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_L, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_L, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_DOT, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_DOT, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_DOT, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_DOT, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_RIGHTMETA, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_DOT, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_DOT, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_DOT, press=KeyPress.PRESSED),
        KeyEvent(key=Key.KEY_DOT, press=KeyPress.RELEASED),
        KeyEvent(key=Key.KEY_LEFTSHIFT, press=KeyPress.RELEASED),
    ]
    async with aclosing(send_channel):
        for event in key_events:
            await send_channel.send(event)

    async with make_keystream(receive_channel, settings, True) as keystream:
        actual = [event async for event in keystream]

        expected = [
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="«",
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_C,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="C",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="a",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_SPACE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character=" ",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_M,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="m",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_E,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="e",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_SPACE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character=" ",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_LEFTSHIFT,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                is_modifier=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_I,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(shift=True),
                character="I",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_S,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="s",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_H,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="h",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_M,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="m",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_A,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="a",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_E,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="e",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_L,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="l",
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="…",
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(compose=True),
                is_modifier=True,
                is_led_able=True,
            ),
            AnnotatedKeyEvent(
                key=Key.KEY_COMPOSE,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(),
                character="»",
                is_led_able=True,
            ),
        ]
        assert actual == expected

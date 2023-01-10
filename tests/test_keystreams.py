# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections.abc
from contextlib import aclosing
import typing

import pygtrie
import slurry
import trio

from tabula.rebuild.keystreams import (
    ModifierTracking,
    OnlyPresses,
    MakeCharacter,
    ComposeCharacters,
    make_keystream,
)
from tabula.rebuild.hwtypes import (
    Key,
    KeyPress,
    KeyEvent,
    AnnotatedKeyEvent,
    ModifierAnnotation,
)
from tabula.rebuild.settings import Settings
from tabula.rebuild.util import checkpoint

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
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.PRESSED),
                KeyEvent(key=Key.KEY_CAPSLOCK, press=KeyPress.RELEASED),
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
        ComposeCharacters(composes, Key.KEY_RIGHTMETA),
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
        ComposeCharacters(composes, Key.KEY_RIGHTMETA),
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
                key=Key.KEY_RIGHTMETA,
                press=KeyPress.PRESSED,
                annotation=ModifierAnnotation(meta=True),
                is_modifier=True,
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
    from tabula.rebuild.settings import COMPOSE_SEQUENCES, KEYMAPS

    send_channel, receive_channel = trio.open_memory_channel(60)
    settings = Settings(
        drafting_fonts=[],
        compose_key=Key.KEY_RIGHTMETA,
        compose_sequences=pygtrie.Trie(
            {tuple(k.split()): v for k, v in COMPOSE_SEQUENCES.items()}
        ),
        keymaps={Key[k]: v for k, v in KEYMAPS.items()},
    )
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

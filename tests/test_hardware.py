# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import collections.abc

from async_generator import aclosing
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
from tabula.rebuild.hardware import EventTestHardware
from tabula.rebuild.settings import COMPOSE_SEQUENCES, KEYMAPS


async def receive_events(
    channel: trio.abc.ReceiveChannel,
    expected: collections.abc.Sequence[AnnotatedKeyEvent],
    deadline=30,
):
    with trio.fail_after(deadline):
        received = []
        while len(received) < len(expected):
            event: AnnotatedKeyEvent = await channel.receive()
            received.append(event)
        assert received == expected


async def receive_characters(
    channel: trio.abc.ReceiveChannel, expected: str, deadline=30
):
    with trio.fail_after(deadline):
        received = []
        while len(received) < len(expected):
            event: AnnotatedKeyEvent = await channel.receive()
            if event.character is not None:
                received.append(event.character)
        actual = "".join(received)
        assert actual == expected


async def send_events(
    events: list[KeyEvent],
    channel: trio.abc.SendChannel,
    *,
    task_status=trio.TASK_STATUS_IGNORED
):
    task_status.started()
    for event in events:
        await channel.send(event)


async def test_event_handling_basic():
    raw_send_channel, raw_receive_channel = trio.open_memory_channel(60)
    processed_send_channel, processed_receive_channel = trio.open_memory_channel(60)
    settings = Settings(
        drafting_fonts=[],
        compose_key=Key.KEY_RIGHTMETA,
        compose_sequences=pygtrie.Trie(
            {tuple(k.split()): v for k, v in COMPOSE_SEQUENCES.items()}
        ),
        keymaps={Key[k]: v for k, v in KEYMAPS.items()},
    )

    raw_events = [
        KeyEvent.pressed(Key.KEY_RIGHTSHIFT),
        KeyEvent.pressed(Key.KEY_T),
        KeyEvent.released(Key.KEY_T),
        KeyEvent.released(Key.KEY_RIGHTSHIFT),
        KeyEvent.pressed(Key.KEY_A),
        KeyEvent.released(Key.KEY_A),
        KeyEvent.pressed(Key.KEY_B),
        KeyEvent.released(Key.KEY_B),
        KeyEvent.pressed(Key.KEY_U),
        KeyEvent.released(Key.KEY_U),
        KeyEvent.pressed(Key.KEY_L),
        KeyEvent.released(Key.KEY_L),
        KeyEvent.pressed(Key.KEY_A),
        KeyEvent.released(Key.KEY_A),
    ]

    async with trio.open_nursery() as nursery:
        hardware = EventTestHardware(
            processed_send_channel, raw_receive_channel, settings
        )
        hardware.reset_keystream(False)
        await nursery.start(hardware.run)
        nursery.start_soon(send_events, raw_events, raw_send_channel)

        await receive_characters(processed_receive_channel, "Tabula")

        # Shut down
        nursery.cancel_scope.cancel()


async def test_event_handling_resets():
    raw_send_channel, raw_receive_channel = trio.open_memory_channel(60)
    processed_send_channel, processed_receive_channel = trio.open_memory_channel(60)
    settings = Settings(
        drafting_fonts=[],
        compose_key=Key.KEY_RIGHTMETA,
        compose_sequences=pygtrie.Trie(
            {tuple(k.split()): v for k, v in COMPOSE_SEQUENCES.items()}
        ),
        keymaps={Key[k]: v for k, v in KEYMAPS.items()},
    )

    async with trio.open_nursery() as nursery:
        hardware = EventTestHardware(
            processed_send_channel, raw_receive_channel, settings
        )
        hardware.reset_keystream(False)
        await nursery.start(hardware.run)

        await send_events(
            [
                KeyEvent.pressed(Key.KEY_RIGHTMETA),
                KeyEvent.released(Key.KEY_RIGHTMETA),
                KeyEvent.pressed(Key.KEY_DOT),
                KeyEvent.released(Key.KEY_DOT),
                KeyEvent.pressed(Key.KEY_DOT),
                KeyEvent.released(Key.KEY_DOT),
            ],
            raw_send_channel,
        )
        await receive_events(
            processed_receive_channel,
            [
                AnnotatedKeyEvent(
                    key=Key.KEY_RIGHTMETA,
                    press=KeyPress.PRESSED,
                    annotation=ModifierAnnotation(meta=True),
                    is_modifier=True,
                ),
                AnnotatedKeyEvent(
                    key=Key.KEY_DOT,
                    press=KeyPress.PRESSED,
                    character=".",
                    annotation=ModifierAnnotation(),
                ),
                AnnotatedKeyEvent(
                    key=Key.KEY_DOT,
                    press=KeyPress.PRESSED,
                    character=".",
                    annotation=ModifierAnnotation(),
                ),
            ],
        )
        assert not processed_receive_channel._closed

        hardware.reset_keystream(True)
        await send_events(
            [
                KeyEvent.pressed(Key.KEY_RIGHTMETA),
                KeyEvent.released(Key.KEY_RIGHTMETA),
                KeyEvent.pressed(Key.KEY_DOT),
                KeyEvent.released(Key.KEY_DOT),
                KeyEvent.pressed(Key.KEY_DOT),
                KeyEvent.released(Key.KEY_DOT),
            ],
            raw_send_channel,
        )
        await receive_events(
            processed_receive_channel,
            [
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
                    character="…",
                    annotation=ModifierAnnotation(),
                    is_led_able=True,
                ),
            ],
        )
        assert not processed_receive_channel._closed

        await send_events(
            [
                KeyEvent.pressed(Key.KEY_RIGHTMETA),
                KeyEvent.released(Key.KEY_RIGHTMETA),
                KeyEvent.pressed(Key.KEY_DOT),
                KeyEvent.released(Key.KEY_DOT),
            ],
            raw_send_channel,
        )
        await receive_events(
            processed_receive_channel,
            [
                AnnotatedKeyEvent(
                    key=Key.KEY_COMPOSE,
                    press=KeyPress.PRESSED,
                    annotation=ModifierAnnotation(compose=True),
                    is_modifier=True,
                    is_led_able=True,
                ),
            ],
        )
        assert hardware.compose_led
        assert not processed_receive_channel._closed
        hardware.reset_keystream(False)
        await send_events(
            [
                KeyEvent.pressed(Key.KEY_DOT),
                KeyEvent.released(Key.KEY_DOT),
            ],
            raw_send_channel,
        )
        await receive_characters(processed_receive_channel, ".")
        assert not hardware.compose_led

        # Shut down
        nursery.cancel_scope.cancel()

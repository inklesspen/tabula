# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import typing

import trio

from .device.types import Display, Touchable, Keyboard
from .editor.keystreams import (
    ModifierTracking,
    OnlyPresses,
    MakeCharacter,
    ComposeCharacters,
)
from .settings import SETTINGS, load_settings


class Tabula:
    def __init__(
        self,
        *,
        display_cls: typing.Type[Display],
        touchable_cls: typing.Type[Touchable],
        keyboard_cls: typing.Type[Keyboard]
    ):
        self.display_cls = display_cls
        self.touchable_cls = touchable_cls
        self.keyboard_cls = keyboard_cls


def kobo():
    from .device.kobo_keyboard import EventKeyboard

    keyboard_cls = EventKeyboard
    pass


def mac_tkinter():
    from .device.tkinter_screen import TkTouchScreen

    Tabula(
        display_cls=TkTouchScreen,
        touchable_cls=TkTouchScreen,
        keyboard_cls=TkTouchScreen,
    )


async def testit():
    load_settings()
    from .device.tkinter_screen import TkTouchScreen

    with TkTouchScreen() as screen:
        settings = SETTINGS.get()
        keyboard = ComposeCharacters(
            MakeCharacter(OnlyPresses(ModifierTracking(screen)), settings), settings
        )
        async with trio.open_nursery() as nursery:

            async def log_keys():
                async for event in keyboard.keystream():
                    print(event)
                    # if event.character is not None:
                    #     print(event.character)
                    # else:
                    #     print(event)

            async def log_touches():
                async for event in screen.touchstream():
                    print(event)

            nursery.start_soon(log_keys)
            nursery.start_soon(log_touches)
            await screen.run()


def stuff():
    trio.run(testit)

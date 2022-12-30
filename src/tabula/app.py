# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import trio

from .device.types import Display, Touchable, Keyboard
from .editor.keystreams import (
    ModifierTracking,
    OnlyPresses,
    MakeCharacter,
    ComposeCharacters,
)
from .editor.document import DocumentModel
from .rendering.pango_render import Renderer
from .rendering.rendertypes import Size
from .db import make_db
from .settings import SETTINGS, load_settings

# if known keyboard is not present, launch into keyboard select screen
# otherwise launch into new/resume session screen

# screens (do the same "loops" approach as in notare, but with a shared renderer from the Tabula class):
# drafting
# main menu
# font menu
# keyboard settings (select/forget/compose key)
# session list -> drafting
# session list -> export
# help (primary, compose sequences)
# sprint control

# wordcount on sprint/session/daily levels. daily wc reset time configurable in settings.


class Tabula:
    def __init__(self, *, display: Display, touchable: Touchable, keyboard: Keyboard):
        self.settings = load_settings()
        self.db = make_db()
        self.display = display
        self.touchable = touchable
        self.keyboard = keyboard
        screen_info = display.get_screen_info()
        self.renderer = Renderer(
            screen_size=Size(width=screen_info.width, height=screen_info.height),
            dpi=screen_info.dpi,
        )
        # TODO: pass dispatch channel
        self.document = DocumentModel(None)

    async def run(self, *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        while True:
            trio.sleep(1)


def kobo():
    from .device.kobo_keyboard import EventKeyboard

    keyboard_cls = EventKeyboard
    pass


def tkinter():
    from .device.tkinter_screen import TkTouchScreen

    screen = TkTouchScreen()
    app = Tabula(
        display=screen,
        touchable=screen,
        keyboard=screen,
    )


async def testit():
    settings = load_settings()
    from .device.tkinter_screen import TkTouchScreen

    screen = TkTouchScreen()
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

        # nursery.start_soon(log_keys)
        nursery.start_soon(log_touches)
        await screen.run()


def stuff():
    trio.run(testit)

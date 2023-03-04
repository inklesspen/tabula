import typing

import trio

from ..device.hwtypes import (
    AnnotatedKeyEvent,
    Key,
    KeyboardDisconnect,
)
from ..editor.document import DocumentModel
from ..util import TickCaller
from ..rendering.layout import LayoutManager, StatusLayout

from .base import (
    ChangeScreen,
    ScreenStackBehavior,
    RetVal,
    Screen,
    TargetScreen,
    DialogResult,
)

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..rendering.renderer import Renderer
    from ..db import TabulaDb


class Drafting(Screen):
    status_font = "Crimson Pro 12"

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
        db: "TabulaDb",
        document: "DocumentModel",
    ):
        self.settings = settings
        self.hardware = hardware
        self.db = db
        self.document = document
        self.layout_manager = LayoutManager(renderer, self.document)
        self.status_layout = StatusLayout(renderer, self.document)

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.hardware.reset_keystream(enable_composes=True)
        self.status_layout.set_leds(
            capslock=False,
            compose=False,
        )
        await self.hardware.clear_screen()
        await self.render_document()
        await self.render_status()

        async with TickCaller(15, self.tick):
            while True:
                event = await event_channel.receive()
                match event:
                    case AnnotatedKeyEvent():
                        if event.is_led_able:
                            self.status_layout.set_leds(
                                capslock=event.annotation.capslock,
                                compose=event.annotation.compose,
                            )
                        if self.document.graphical_char(event.character):
                            self.document.keystroke(event.character)
                            await self.render_document()
                        elif event.key is Key.KEY_ENTER:
                            self.document.new_para()
                            await self.render_document()
                            self.document.save_session(self.db)
                        elif event.key is Key.KEY_BACKSPACE:
                            self.document.backspace()
                            await self.render_document()
                        elif event.key is Key.KEY_F1:
                            self.document.save_session(self.db)
                            return ChangeScreen(
                                TargetScreen.Help,
                                screen_stack_behavior=ScreenStackBehavior.APPEND,
                            )
                        elif event.key is Key.SYNTHETIC_COMPOSE_DOUBLETAP:
                            self.document.save_session(self.db)
                            return ChangeScreen(
                                TargetScreen.ComposeHelp,
                                screen_stack_behavior=ScreenStackBehavior.APPEND,
                            )
                        elif event.key is Key.KEY_F12:
                            if self.document.wordcount == 0:
                                self.document.delete_session(self.db)
                            else:
                                self.document.save_session(self.db)
                            return ChangeScreen(TargetScreen.SystemMenu)
                        await self.render_status()
                    case KeyboardDisconnect():
                        self.document.save_session(self.db)
                        return ChangeScreen(
                            TargetScreen.KeyboardDetect,
                            screen_stack_behavior=ScreenStackBehavior.APPEND,
                        )

    async def tick(self):
        self.document.save_session(self.db)
        await self.render_status()

    async def render_status(self):
        await self.hardware.display_rendered(self.status_layout.render())

    async def render_document(self):
        current_font = self.settings.current_font
        font_size = self.settings.drafting_fonts[current_font][
            self.settings.current_font_size
        ]
        font_spec = f"{current_font} {font_size}"
        rendered = self.layout_manager.render_update(font_spec)
        await self.hardware.display_rendered(rendered)

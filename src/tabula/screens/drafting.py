import logging
import typing


from ..device.hwtypes import AnnotatedKeyEvent, Key
from ..util import TABULA
from ..rendering.layout import LayoutManager, StatusLayout

from .base import Screen, TargetScreen, TargetDialog

if typing.TYPE_CHECKING:
    from ..settings import Settings
    from ..rendering.renderer import Renderer
    from ..db import TabulaDb
    from ..editor.document import DocumentModel


logger = logging.getLogger(__name__)


class Drafting(Screen):
    status_font = "Crimson Pro 12"

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        db: "TabulaDb",
        document: "DocumentModel",
    ):
        self.settings = settings
        self.db = db
        self.document = document
        self.layout_manager = LayoutManager(renderer, self.document)
        self.status_layout = StatusLayout(renderer, self.document)

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream(enable_composes=True)
        # TODO: figure out how to make this work more better
        self.status_layout.set_leds(
            capslock=False,
            compose=False,
        )
        app.hardware.clear_screen()
        await self.render_document()
        await self.render_status()
        app.tick_receivers.append(self.tick)

    def resign_responder(self):
        app = TABULA.get()
        app.tick_receivers.remove(self.tick)
        self.document.save_session(self.db, "resign_responder")

    async def show_help(self):
        app = TABULA.get()
        future = await app.show_dialog(TargetDialog.Help)
        result = await future.wait()
        if result is TargetDialog.ComposeHelp:
            return await self.show_compose_help()

    async def show_compose_help(self):
        app = TABULA.get()
        future = await app.show_dialog(TargetDialog.ComposeHelp)
        result = await future.wait()
        if result is TargetDialog.Help:
            return await self.show_help()

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        if event.is_led_able:
            self.status_layout.capslock = event.annotation.capslock
            self.status_layout.compose = event.annotation.compose
        if self.document.graphical_char(event.character):
            if self.document.whitespace_char(event.character):
                pass  # TODO: check if we need to end a sprint
            self.document.keystroke(event.character)
            await self.render_document()
        elif event.key is Key.KEY_ENTER:
            # TODO: check if we need to end a sprint
            self.document.new_para()
            await self.render_document()
            self.document.save_session(self.db, "KEY_ENTER")
        elif event.key is Key.KEY_BACKSPACE:
            self.document.backspace()
            await self.render_document()
        elif event.key is Key.KEY_F1:
            self.document.save_session(self.db, "KEY_F1")
            await self.show_help()
        elif event.key is Key.KEY_F2 or event.key is Key.SYNTHETIC_COMPOSE_DOUBLETAP:
            self.document.save_session(self.db, "COMPOSE_HELP")
            await self.show_compose_help()
        elif event.key is Key.KEY_F8:
            self.document.save_session(self.db, "KEY_F8")
            # make this a dialog
            # return ChangeScreen(
            #     TargetScreen.SprintControl,
            #     screen_stack_behavior=ScreenStackBehavior.APPEND,
            # )

        elif event.key is Key.KEY_F12:
            app = TABULA.get()
            if self.document.wordcount == 0:
                self.document.delete_session(self.db)
            else:
                self.document.save_session(self.db, "KEY_F12")
            return await app.change_screen(TargetScreen.SystemMenu)
        await self.render_status()

    async def handle_keyboard_disconnect(self):
        self.document.save_session(self.db, "keyboard_disconnect")

    async def tick(self):
        self.document.save_session(self.db, "drafting tick")
        await self.render_status()  # This is mainly to update the clock.

    async def render_status(self):
        app = TABULA.get()
        app.hardware.display_rendered(self.status_layout.render())

    async def render_document(self):
        app = TABULA.get()
        current_font = self.settings.current_font
        font_size = self.settings.drafting_fonts[current_font][self.settings.current_font_size]
        font_spec = f"{current_font} {font_size}"
        rendered = self.layout_manager.render_update(font_spec)
        app.hardware.display_rendered(rendered)

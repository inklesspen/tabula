from __future__ import annotations

import logging
import typing

from ..commontypes import Size, Rect, Point
from ..device.hwtypes import AnnotatedKeyEvent, Key
from ..util import TABULA
from ..rendering.rendertypes import CairoColor
from ..rendering.layout import LayoutManager, StatusLayout
from ..rendering.cairo import Cairo

from .base import Screen, TargetScreen, TargetDialog

if typing.TYPE_CHECKING:
    from ..settings import Settings
    from ..commontypes import ScreenInfo
    from ..db import TabulaDb
    from ..editor.document import DocumentModel


logger = logging.getLogger(__name__)


class Drafting(Screen):
    def __init__(
        self,
        *,
        settings: Settings,
        screen_info: ScreenInfo,
        db: TabulaDb,
        document: DocumentModel,
    ):
        self.settings = settings
        self.db = db
        self.document = document
        self.screen_info = screen_info
        self.layout_manager = LayoutManager(self.screen_info, self.document)
        self.status_layout = StatusLayout(self.screen_info, self.document)

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream(enable_composes=True)
        if app.screen_info != self.screen_info:
            self.screen_info = app.screen_info
            self.layout_manager = LayoutManager(self.screen_info, self.document)
            self.status_layout = StatusLayout(self.screen_info, self.document)

        # TODO: figure out how to make this work more better
        self.status_layout.set_leds(
            capslock=False,
            compose=False,
        )
        app.hardware.clear_screen()
        self.render_document()
        self.render_status()
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
            if self.document.whitespace_char(event.character) and self.document.has_sprint and self.document.sprint.completed:
                self.document.end_sprint(self.db)
                self.clear_status_area()
            else:
                self.document.keystroke(event.character)
            self.render_document()
        elif event.key is Key.KEY_ENTER:
            if self.document.has_sprint and self.document.sprint.completed:
                self.document.end_sprint(self.db)
                self.clear_status_area()
            self.document.new_para()
            self.render_document()
            self.document.save_session(self.db, "KEY_ENTER")
        elif event.key is Key.KEY_BACKSPACE:
            self.document.backspace()
            self.render_document()
        elif event.key is Key.KEY_F1:
            self.document.save_session(self.db, "KEY_F1")
            await self.show_help()
        elif event.key is Key.KEY_F2 or event.key is Key.SYNTHETIC_COMPOSE_DOUBLETAP:
            self.document.save_session(self.db, "COMPOSE_HELP")
            await self.show_compose_help()
        elif event.key is Key.KEY_F8:
            self.document.save_session(self.db, "KEY_F8")
            app = TABULA.get()
            if self.document.has_sprint:
                future = await app.show_dialog(TargetDialog.YesNo, message="End sprint early?")
                result = await future.wait()
                if result:
                    self.document.end_sprint(self.db)
                    self.clear_status_area()
                    self.render_document()
                    self.document.save_session(self.db, "sprint ended")
            else:
                future = await app.show_dialog(TargetDialog.SprintControl)
                result = await future.wait()
                if result:
                    self.document.begin_sprint(self.db, duration=result)
                    self.render_document()
                    self.document.save_session(self.db, "new sprint")
                logger.debug("sprint control result: %r", result)

        elif event.key is Key.KEY_F12:
            app = TABULA.get()
            if self.document.has_sprint:
                self.document.end_sprint(self.db)
            if self.document.wordcount == 0:
                self.document.delete_session(self.db)
            else:
                self.document.save_session(self.db, "KEY_F12")
            return await app.change_screen(TargetScreen.SystemMenu)
        self.render_status()

    async def handle_keyboard_disconnect(self):
        self.document.save_session(self.db, "keyboard_disconnect")

    async def tick(self):
        self.document.save_session(self.db, "drafting tick")
        self.render_status()  # This is mainly to update the clock.

    def clear_status_area(self):
        app = TABULA.get()
        half_height = self.screen_info.size.height // 2
        status_area = Rect(origin=Point(x=0, y=half_height), spread=Size(width=self.screen_info.size.width, height=half_height))
        with Cairo(status_area.spread) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            rendered = cairo.get_rendered(status_area.origin)
        app.hardware.display_rendered(rendered)

    def render_status(self):
        app = TABULA.get()
        app.hardware.display_rendered(self.status_layout.render())

    def render_document(self):
        app = TABULA.get()
        current_font = self.settings.current_font
        font_size = self.settings.current_font_size
        font_spec = f"{current_font} {font_size}"
        rendered = self.layout_manager.render_update(font_spec)
        app.hardware.display_rendered(rendered)

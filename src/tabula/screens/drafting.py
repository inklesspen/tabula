from __future__ import annotations

import logging
import typing

from ..device.eventsource import KeyCode
from ..device.hwtypes import AnnotatedKeyEvent, DisplayUpdateMode
from ..editor.composes import ComposeFailed, ComposeOther, ComposeState, ComposeSucceeded
from ..rendering.layout import LayoutManager, StatusLayout
from ..util import TABULA
from .base import Screen, TargetDialog, TargetScreen

if typing.TYPE_CHECKING:
    from ..commontypes import ScreenInfo
    from ..db import TabulaDb
    from ..editor.document import DocumentModel
    from ..settings import Settings


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
        self.compose_state = ComposeState(self.settings.compose_sequences)

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream()
        if app.screen_info != self.screen_info:
            self.screen_info = app.screen_info
            self.layout_manager = LayoutManager(self.screen_info, self.document)
            self.status_layout = StatusLayout(self.screen_info, self.document)

        # TODO: figure out how to make this work more better
        self.status_layout.set_leds(
            capslock=False,
            compose=False,
        )
        app.hardware.set_display_update_mode(DisplayUpdateMode.FIDELITY)
        app.hardware.clear_screen()
        self.render_document()
        self.render_status()
        app.hardware.set_display_update_mode(DisplayUpdateMode.RAPID)
        app.tick_receivers.append(self.tick)

    def resign_responder(self):
        app = TABULA.get()
        app.tick_receivers.remove(self.tick)
        app.hardware.set_display_update_mode(DisplayUpdateMode.AUTO)
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

        compose_result = self.compose_state.handle_key_event(event)
        if isinstance(compose_result, ComposeOther):
            if compose_result.active_changed:
                self.status_layout.compose = self.compose_state.active
                self.render_status()
            if compose_result.show_help:
                self.document.save_session(self.db, "COMPOSE_HELP")
                return await self.show_compose_help()
            if not self.compose_state.active and not compose_result.absorb:
                return await self.handle_non_compose_key_event(event)
            self.render_document()
        elif isinstance(compose_result, ComposeFailed):
            self.status_layout.compose = False
            for key_event in compose_result.key_events:
                await self.handle_non_compose_key_event(key_event)
        elif isinstance(compose_result, ComposeSucceeded):
            self.status_layout.compose = False
            self.render_status()
            self.document.keystroke(compose_result.result)
            self.layout_manager.active_renderable.append_chars(compose_result.result)
            self.render_document()
        else:
            typing.assert_never()

    async def handle_non_compose_key_event(self, event: AnnotatedKeyEvent):
        if self.document.graphical_char(event.character):
            if self.document.whitespace_char(event.character) and self.document.has_sprint and self.document.sprint.completed:
                self.document.end_sprint(self.db)
                self.clear_status_area()
            else:
                self.document.keystroke(event.character)
                self.layout_manager.active_renderable.append_chars(event.character)
            self.render_document()
        elif event.key is KeyCode.KEY_ENTER:
            if self.document.has_sprint and self.document.sprint.completed:
                self.document.end_sprint(self.db)
                self.clear_status_area()
            self.document.new_para()
            self.render_document()
            self.document.save_session(self.db, "KEY_ENTER")
        elif event.key is KeyCode.KEY_BACKSPACE:
            self.document.backspace()
            self.layout_manager.active_renderable.backspace()
            self.render_document()
        elif event.key is KeyCode.KEY_F1:
            self.document.save_session(self.db, "KEY_F1")
            await self.show_help()
        elif event.key is KeyCode.KEY_F2:
            self.document.save_session(self.db, "COMPOSE_HELP")
            await self.show_compose_help()
        elif event.key is KeyCode.KEY_F8:
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

        elif event.key is KeyCode.KEY_F12:
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
        TABULA.get().hardware.display_rendered(self.status_layout.clear())

    def render_status(self):
        TABULA.get().hardware.display_rendered(self.status_layout.render())

    def render_document(self):
        TABULA.get().hardware.display_rendered(
            self.layout_manager.set_font(f"{self.settings.current_font} {self.settings.current_font_size}")
            .set_line_spacing(self.settings.current_line_spacing)
            .render_document(composing_chars=self.compose_state.composing_chars)
        )

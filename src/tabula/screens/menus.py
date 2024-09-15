from __future__ import annotations

import abc
import functools
import math
import typing
from collections.abc import Awaitable, Callable

import trio

from ..commontypes import Point, Rect, Size
from ..device.eventsource import KeyCode
from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, TapPhase
from ..editor.document import DocumentModel
from ..rendering.cairo import Cairo
from ..rendering.fonts import SERIF
from ..rendering.pango import Pango
from ..rendering.rendertypes import CairoColor
from ..util import TABULA, humanized_delta, now
from .base import Screen, TargetDialog, TargetScreen
from .numbers import B612_CIRCLED_DIGITS, NUMBER_KEYS
from .widgets import Button, ButtonSpec, ButtonState, Label, make_button_stack

if typing.TYPE_CHECKING:
    from ..commontypes import ScreenInfo
    from ..db import TabulaDb
    from ..editor.doctypes import Session
    from ..rendering.rendertypes import Rendered
    from ..settings import Settings

Handler = Callable[[], Awaitable[None]]


class ButtonMenu(Screen):
    # Buttons are 400 px wide, 100 px high
    # Spread them as equally as possible along the screen height.
    button_size = Size(width=600, height=100)

    def __init__(self, *, settings: Settings, screen_info: ScreenInfo):
        self.settings = settings
        self.screen_info = screen_info
        self.pango = Pango(dpi=screen_info.dpi)

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream()
        self.screen_info = app.screen_info
        self.render_screen()

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        app = TABULA.get()
        handler = None

        for menu_button in self.menu_buttons:
            if event.key == menu_button.hotkey:
                handler = typing.cast(Handler, menu_button.button_value)
                app.hardware.display_rendered(menu_button.render(override_state=ButtonState.PRESSED))

        if handler is not None:
            await handler()

    async def handle_tap_event(self, event: TapEvent):
        app = TABULA.get()
        handler = None
        if event.phase is TapPhase.COMPLETED:
            for menu_button in self.menu_buttons:
                if event.location in menu_button:
                    handler = typing.cast(Handler, menu_button.button_value)
                    app.hardware.display_rendered(menu_button.render(override_state=ButtonState.PRESSED))
        if handler is not None:
            await handler()

    def render_screen(self):
        app = TABULA.get()
        self.make_buttons()
        screen = self.render()
        app.hardware.display_rendered(screen)

    @abc.abstractmethod
    def make_buttons(self): ...

    @abc.abstractmethod
    def render(self) -> Rendered: ...


class SystemMenu(ButtonMenu):
    def __init__(self, *, settings: Settings, screen_info: ScreenInfo, db: TabulaDb, document: DocumentModel):
        super().__init__(
            settings=settings,
            screen_info=screen_info,
        )
        self.db = db
        self.document = document

    def make_buttons(self):
        specs = [
            ButtonSpec(button_text=f"{B612_CIRCLED_DIGITS[1]} — New Session", button_value=self.new_session, hotkey=NUMBER_KEYS[1]),
            ButtonSpec(
                button_text=f"{B612_CIRCLED_DIGITS[2]} — Previous Session", button_value=self.previous_session, hotkey=NUMBER_KEYS[2]
            ),
        ]
        next_number = 3
        if self.document.has_session:
            specs.append(
                ButtonSpec(
                    button_text=f"{B612_CIRCLED_DIGITS[next_number]} — Export Current Session",
                    button_value=self.export_current_session,
                    hotkey=NUMBER_KEYS[next_number],
                )
            )
            next_number += 1
        specs.append(
            ButtonSpec(
                button_text=f"{B612_CIRCLED_DIGITS[next_number]} — Fonts", button_value=self.set_font, hotkey=NUMBER_KEYS[next_number]
            )
        )
        next_number += 1
        if self.document.has_session:
            specs.append(
                ButtonSpec(
                    button_text=f"{B612_CIRCLED_DIGITS[9]} — Resume Drafting", button_value=self.resume_drafting, hotkey=NUMBER_KEYS[9]
                )
            )
        specs.append(ButtonSpec(button_text=f"{B612_CIRCLED_DIGITS[0]} — Shutdown", button_value=self.shutdown, hotkey=NUMBER_KEYS[0]))

        self.menu_buttons = make_button_stack(
            *specs,
            button_size=self.button_size,
            corner_radius=50,
            screen_area=Rect(origin=Point.zeroes(), spread=self.screen_info.size),
            pango=self.pango,
            default_font="B612 8",
        )

    def render(self):
        with Cairo(self.screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            for menu_button in self.menu_buttons:
                menu_button.paste_onto_cairo(cairo)
            rendered = cairo.get_rendered(origin=Point.zeroes())
        return rendered

    async def new_session(self):
        app = TABULA.get()
        session_id = self.db.new_session()
        self.document.load_session(session_id, self.db)
        await trio.lowlevel.checkpoint()
        return await app.change_screen(TargetScreen.Drafting)

    async def previous_session(self):
        app = TABULA.get()
        await trio.lowlevel.checkpoint()
        return await app.change_screen(TargetScreen.SessionList)

    async def export_current_session(self):
        app = TABULA.get()
        self.document.export_session(self.db, self.settings.export_path)
        await app.show_dialog(TargetDialog.Ok, message="Export complete!")

    async def set_font(self):
        app = TABULA.get()
        await trio.lowlevel.checkpoint()
        await app.change_screen(TargetScreen.Fonts)

    async def resume_drafting(self):
        app = TABULA.get()
        await trio.lowlevel.checkpoint()
        return await app.change_screen(TargetScreen.Drafting)

    async def shutdown(self):
        await trio.lowlevel.checkpoint()
        app = TABULA.get()
        await app.shutdown()


class SessionList(ButtonMenu):
    session_button_size = Size(width=800, height=100)
    page_button_size = Size(width=200, height=100)

    def __init__(self, *, settings: Settings, screen_info: ScreenInfo, db: TabulaDb):
        super().__init__(
            settings=settings,
            screen_info=screen_info,
        )
        self.db = db
        self.offset = 0

    def make_buttons(self):
        timestamp = now()
        screen_size = self.screen_info.size
        min_skip_height = math.floor(self.button_size.height * 0.75)
        usable_height = screen_size.height - (min_skip_height + self.button_size.height)
        num_session_buttons = usable_height // (min_skip_height + self.button_size.height)
        session_page = self.sessions[self.offset : self.offset + num_session_buttons]

        button_x = math.floor((screen_size.width - self.session_button_size.width) / 2)
        button_total_height = self.button_size.height * num_session_buttons
        whitespace_height = usable_height - button_total_height
        skip_height = math.floor(whitespace_height / (num_session_buttons + 1))
        button_y = skip_height

        menu_buttons = []
        for session in session_page:
            button_origin = Point(x=button_x, y=button_y)
            session_delta = session.updated_at - timestamp
            button_text = f"{humanized_delta(session_delta)} - {session.wordcount}"
            if session.needs_export:
                button_text += " \ue0a7"
            else:
                button_text += " \ue0a2"
            menu_buttons.append(
                Button.create(
                    pango=self.pango,
                    button_text=button_text,
                    button_size=self.session_button_size,
                    font="B612 8",
                    corner_radius=50,
                    screen_location=button_origin,
                    button_value=functools.partial(self.select_session, session),
                )
            )
            button_y += self.button_size.height + skip_height

        if self.offset > 0:
            # back button
            prev_page_offset = max(0, self.offset - num_session_buttons)
            menu_buttons.append(
                Button.create(
                    pango=self.pango,
                    button_text="\ue0a9 Prev",
                    button_size=self.page_button_size,
                    font="B612 8",
                    corner_radius=50,
                    screen_location=Point(x=50, y=usable_height),
                    button_value=functools.partial(self.change_page, prev_page_offset),
                )
            )

        next_page_offset = self.offset + num_session_buttons
        if len(self.sessions[next_page_offset:]) > 0:
            # next button
            menu_buttons.append(
                Button.create(
                    pango=self.pango,
                    button_text="Next \ue0a8",
                    button_size=self.page_button_size,
                    font="B612 8",
                    corner_radius=50,
                    screen_location=Point(
                        x=screen_size.width - (50 + self.page_button_size.width),
                        y=usable_height,
                    ),
                    button_value=functools.partial(self.change_page, next_page_offset),
                )
            )

        # return button
        menu_buttons.append(
            Button.create(
                pango=self.pango,
                button_text="Back",
                button_size=self.page_button_size,
                font="B612 8",
                corner_radius=50,
                screen_location=Point(
                    x=math.floor((screen_size.width - self.page_button_size.width) / 2),
                    y=usable_height,
                ),
                button_value=self.close_menu,
            )
        )
        self.menu_buttons = menu_buttons

    def render(self):
        with Cairo(self.screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            for menu_button in self.menu_buttons:
                menu_button.paste_onto_cairo(cairo)

            rendered = cairo.get_rendered(origin=Point.zeroes())
        return rendered

    def refresh_sessions(self):
        self.sessions = self.db.list_sessions()

    async def become_responder(self):
        self.refresh_sessions()
        return await super().become_responder()

    async def select_session(self, selected_session: Session):
        app = TABULA.get()
        await app.change_screen(TargetScreen.SessionActions, session=selected_session)

    async def change_page(self, new_offset: int):
        self.offset = new_offset
        self.render_screen()

    async def close_menu(self):
        app = TABULA.get()
        await app.change_screen(TargetScreen.SystemMenu)

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        if event.key is KeyCode.KEY_ESC:
            await self.close_menu()
        else:
            await super().handle_key_event(event)


class SessionActions(ButtonMenu):
    session_button_size = Size(width=800, height=100)
    page_button_size = Size(width=200, height=100)

    def __init__(self, *, settings: Settings, screen_info: ScreenInfo, db: TabulaDb, document: DocumentModel, session: Session):
        super().__init__(
            settings=settings,
            screen_info=screen_info,
        )
        self.db = db
        self.document = document
        self.offset = 0
        self.selected_session = session

        timestamp = now()
        edit_cutoff = timestamp - self.settings.max_editable_age
        self.can_resume_drafting = self.selected_session.updated_at >= edit_cutoff
        self.session_delta = self.selected_session.updated_at - timestamp

    def make_buttons(self):
        button_top = 225 if self.can_resume_drafting else 525
        specs = []
        if self.can_resume_drafting:
            specs.append(
                ButtonSpec(
                    button_text="Load Session",
                    button_value=self.load_session,
                )
            )
        if self.selected_session.needs_export:
            specs.append(
                ButtonSpec(
                    button_text="Export Session",
                    button_value=self.export_session,
                )
            )
        specs.append(
            ButtonSpec(
                button_text="Delete Session",
                button_value=self.delete_session,
            )
        )
        specs.append(
            ButtonSpec(
                button_text="Back",
                button_value=self.back_to_session_list,
            )
        )

        self.menu_buttons = make_button_stack(
            *specs,
            button_size=self.button_size,
            corner_radius=50,
            screen_area=Rect(
                origin=Point(x=0, y=button_top),
                spread=Size(width=self.screen_info.size.width, height=self.screen_info.size.height - button_top),
            ),
            pango=self.pango,
            default_font="B612 8",
        )

    def render(self):
        with Cairo(self.screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            for menu_button in self.menu_buttons:
                menu_button.paste_onto_cairo(cairo)

            header_text = f"Last edited {humanized_delta(self.session_delta)}\nWordcount: {self.selected_session.wordcount}"
            if self.selected_session.first_paragraph is not None:
                header_text += f"\n{self.selected_session.first_paragraph}"
            Label.create(
                pango=self.pango,
                text=header_text,
                font=f"{SERIF} 12",
                location=Point(x=0, y=10),
                width=self.screen_info.size.width,
                ellipsize=True,
            ).paste_onto_cairo(cairo)

            if not self.can_resume_drafting:
                Label.create(
                    pango=self.pango,
                    text="This session is now locked for editing",
                    font="B612 8",
                    location=Point(x=0, y=180),
                    width=self.screen_info.size.width,
                ).paste_onto_cairo(cairo)

            rendered = cairo.get_rendered(origin=Point.zeroes())
        return rendered

    def refresh_sessions(self):
        self.sessions = self.db.list_sessions()

    async def become_responder(self):
        self.refresh_sessions()
        return await super().become_responder()

    async def load_session(self):
        app = TABULA.get()
        self.document.load_session(self.selected_session.id, self.db)
        await app.change_screen(TargetScreen.Drafting)

    async def export_session(self):
        app = TABULA.get()
        session_document = DocumentModel()
        session_document.load_session(self.selected_session.id, self.db)

        session_document.export_session(self.db, self.settings.export_path)

        future = await app.show_dialog(TargetDialog.Ok, message="Export complete!")
        await future.wait()
        await app.change_screen(TargetScreen.SessionList)

    async def delete_session(self):
        app = TABULA.get()
        future = await app.show_dialog(TargetDialog.YesNo, message="Really delete?")
        result = typing.cast(bool, await future.wait())

        if result:
            if self.selected_session.id == self.document.session_id:
                self.document.delete_session(self.db)
            else:
                self.db.delete_session(self.selected_session.id)
        await app.change_screen(TargetScreen.SessionList)

    async def back_to_session_list(self):
        app = TABULA.get()
        await app.change_screen(TargetScreen.SessionList)

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        if event.key is KeyCode.KEY_ESC:
            await self.back_to_session_list()
        else:
            await super().handle_key_event(event)

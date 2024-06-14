import abc
import collections
import collections.abc
import functools
import math
import typing

import msgspec
import trio

from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, TapPhase, Key
from ..commontypes import Point, Size
from ..rendering.rendertypes import Alignment, CairoColor
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from ..editor.document import DocumentModel
from ..editor.doctypes import Session
from ..util import now, humanized_delta, TABULA
from .widgets import ButtonState, Button

from .numbers import NUMBER_KEYS, B612_CIRCLED_DIGITS
from .base import Screen, TargetScreen, TargetDialog

if typing.TYPE_CHECKING:
    from ..rendering.rendertypes import Rendered
    from ..settings import Settings
    from ..db import TabulaDb
    from ..commontypes import ScreenInfo


class MenuButton(msgspec.Struct):
    button: Button
    handler: collections.abc.Callable[[], collections.abc.Awaitable[None]]
    key: typing.Optional[Key] = None


class ButtonMenu(Screen):
    # Buttons are 400 px wide, 100 px high
    # Spread them as equally as possible along the screen height.
    button_size = Size(width=600, height=100)

    def __init__(
        self,
        *,
        settings: "Settings",
        screen_info: "ScreenInfo",
    ):
        self.settings = settings
        self.screen_info = screen_info
        self.pango = Pango(dpi=screen_info.dpi)

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream(enable_composes=False)
        self.render_screen()

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        app = TABULA.get()
        handler = None

        for menu_button in self.menu_buttons:
            if event.key == menu_button.key:
                handler = menu_button.handler
                app.hardware.display_rendered(menu_button.button.render(override_state=ButtonState.PRESSED))

        if handler is not None:
            await handler()

    async def handle_tap_event(self, event: TapEvent):
        app = TABULA.get()
        handler = None
        if event.phase is TapPhase.COMPLETED:
            for menu_button in self.menu_buttons:
                if event.location in menu_button.button:
                    handler = menu_button.handler
                    app.hardware.display_rendered(menu_button.button.render(override_state=ButtonState.PRESSED))
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
    def render(self) -> "Rendered": ...


class SystemMenu(ButtonMenu):
    def __init__(
        self,
        *,
        settings: "Settings",
        screen_info: "ScreenInfo",
        db: "TabulaDb",
        document: "DocumentModel",
    ):
        super().__init__(
            settings=settings,
            screen_info=screen_info,
        )
        self.db = db
        self.document = document

    def make_buttons(self):
        buttons = [
            {
                "handler": self.new_session,
                "number": 1,
                "title": "New Session",
            },
            {
                "handler": self.previous_session,
                "number": 2,
                "title": "Previous Session",
            },
        ]
        next_number = 3
        if self.document.has_session:
            buttons.append(
                {
                    "handler": self.export_current_session,
                    "number": next_number,
                    "title": "Export Current Session",
                }
            )
            next_number += 1
        buttons.append(
            {
                "handler": self.set_font,
                "number": next_number,
                "title": "Fonts",
            }
        )
        next_number += 1
        if self.document.has_session:
            buttons.append(
                {
                    "handler": self.resume_drafting,
                    "number": 9,
                    "title": "Resume Drafting",
                }
            )
        buttons.append(
            {
                "handler": self.shutdown,
                "number": 0,
                "title": "Shutdown",
            }
        )

        screen_size = self.screen_info.size
        button_x = math.floor((screen_size.width - self.button_size.width) / 2)
        button_total_height = self.button_size.height * len(buttons)
        whitespace_height = screen_size.height - button_total_height
        skip_height = math.floor(whitespace_height / (len(buttons) + 1))
        button_y = skip_height

        for button in buttons:
            button["point"] = Point(x=button_x, y=button_y)
            button_y += self.button_size.height + skip_height

        self.menu_buttons = [
            MenuButton(
                button=Button.create(
                    pango=self.pango,
                    button_text=f"{B612_CIRCLED_DIGITS[b['number']]} — {b['title']}",
                    font="B612 8",
                    corner_radius=50,
                    button_size=self.button_size,
                    screen_location=b["point"],
                ),
                handler=b["handler"],
                key=NUMBER_KEYS[b["number"]],
            )
            for b in buttons
        ]

    def render(self):
        with Cairo(self.screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            for menu_button in self.menu_buttons:
                menu_button.button.paste_onto_cairo(cairo)
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

    def __init__(
        self,
        *,
        settings: "Settings",
        screen_info: "ScreenInfo",
        db: "TabulaDb",
    ):
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
                MenuButton(
                    button=Button.create(
                        pango=self.pango,
                        button_text=button_text,
                        button_size=self.session_button_size,
                        font="B612 8",
                        corner_radius=50,
                        screen_location=button_origin,
                    ),
                    handler=functools.partial(self.select_session, session),
                )
            )
            button_y += self.button_size.height + skip_height

        if self.offset > 0:
            # back button
            prev_page_offset = max(0, self.offset - num_session_buttons)
            menu_buttons.append(
                MenuButton(
                    button=Button.create(
                        pango=self.pango,
                        button_text="\ue0a9 Prev",
                        button_size=self.page_button_size,
                        font="B612 8",
                        corner_radius=50,
                        screen_location=Point(x=50, y=1300),
                    ),
                    handler=functools.partial(self.change_page, prev_page_offset),
                )
            )

        next_page_offset = self.offset + num_session_buttons
        if len(self.sessions[next_page_offset:]) > 0:
            # next button
            menu_buttons.append(
                MenuButton(
                    button=Button.create(
                        pango=self.pango,
                        button_text="Next \ue0a8",
                        button_size=self.page_button_size,
                        font="B612 8",
                        corner_radius=50,
                        screen_location=Point(
                            x=screen_size.width - (50 + self.page_button_size.width),
                            y=1300,
                        ),
                    ),
                    handler=functools.partial(self.change_page, next_page_offset),
                )
            )

        # return button
        menu_buttons.append(
            MenuButton(
                button=Button.create(
                    pango=self.pango,
                    button_text="Back",
                    button_size=self.page_button_size,
                    font="B612 8",
                    corner_radius=50,
                    screen_location=Point(
                        x=math.floor((screen_size.width - self.page_button_size.width) / 2),
                        y=1300,
                    ),
                ),
                handler=self.close_menu,
            )
        )
        self.menu_buttons = menu_buttons

    def render(self):
        with Cairo(self.screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            for menu_button in self.menu_buttons:
                menu_button.button.paste_onto_cairo(cairo)

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


class SessionActions(ButtonMenu):
    session_button_size = Size(width=800, height=100)
    page_button_size = Size(width=200, height=100)

    def __init__(
        self,
        *,
        settings: "Settings",
        screen_info: "ScreenInfo",
        db: "TabulaDb",
        document: "DocumentModel",
        session: Session,
    ):
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
        screen_size = self.screen_info.size

        menu_buttons = []

        button_x = math.floor((screen_size.width - self.button_size.width) / 2)
        if self.can_resume_drafting:
            menu_buttons.append(
                MenuButton(
                    button=Button.create(
                        pango=self.pango,
                        button_text="Load Session",
                        button_size=self.button_size,
                        font="B612 8",
                        corner_radius=50,
                        screen_location=Point(x=button_x, y=150),
                    ),
                    handler=self.load_session,
                )
            )
        if self.selected_session.needs_export or True:
            menu_buttons.append(
                MenuButton(
                    button=Button.create(
                        pango=self.pango,
                        button_text="Export Session",
                        button_size=self.button_size,
                        font="B612 8",
                        corner_radius=50,
                        screen_location=Point(x=button_x, y=450),
                    ),
                    handler=self.export_session,
                )
            )
        menu_buttons.append(
            MenuButton(
                button=Button.create(
                    pango=self.pango,
                    button_text="Delete Session",
                    button_size=self.button_size,
                    font="B612 8",
                    corner_radius=50,
                    screen_location=Point(x=button_x, y=650),
                ),
                handler=self.delete_session,
            )
        )

        menu_buttons.append(
            MenuButton(
                button=Button.create(
                    pango=self.pango,
                    button_text="Back",
                    button_size=self.button_size,
                    font="B612 8",
                    corner_radius=50,
                    screen_location=Point(x=button_x, y=850),
                ),
                handler=self.back_to_session_list,
            )
        )

        self.menu_buttons = menu_buttons

    def render(self):
        with Cairo(self.screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            for menu_button in self.menu_buttons:
                menu_button.button.paste_onto_cairo(cairo)

            header_text = f"Last edited {humanized_delta(self.session_delta)}\nWordcount: {self.selected_session.wordcount}"
            cairo.move_to(Point(x=0, y=10))
            with PangoLayout(
                pango=self.pango,
                width=cairo.size.width,
                alignment=Alignment.CENTER,
            ) as layout:
                layout.set_font("Crimson Pro 12")
                layout.set_content(header_text, is_markup=False)
                layout.render(cairo)

            if not self.can_resume_drafting:
                cairo.move_to(Point(x=0, y=150))
                with PangoLayout(
                    pango=self.pango,
                    width=cairo.size.width,
                    alignment=Alignment.CENTER,
                ) as layout:
                    layout.set_font("B612 8")
                    layout.set_content("This session is now locked for editing", is_markup=False)
                    layout.render(cairo)

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

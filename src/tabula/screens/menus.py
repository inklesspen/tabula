import abc
import collections
import collections.abc
import functools
import math
import typing

import msgspec
import trio

from ..device.hwtypes import (
    AnnotatedKeyEvent,
    TapEvent,
    TapPhase,
    Key,
    KeyboardDisconnect,
)
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import Rendered, Alignment, CairoColor
from ..editor.document import DocumentModel
from ..editor.doctypes import Session
from ..util import checkpoint, now, humanized_delta
from .widgets import ButtonState, Button

from .numbers import NUMBER_KEYS, B612_CIRCLED_DIGITS
from .base import (
    Switch,
    Modal,
    Close,
    Shutdown,
    DialogResult,
    RetVal,
    Screen,
    TargetScreen,
)
from .dialogs import OkDialog, YesNoDialog

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..rendering.renderer import Renderer
    from ..db import TabulaDb


class MenuButton(msgspec.Struct):
    handler: collections.abc.Callable[
        [], collections.abc.Awaitable[typing.Optional[RetVal]]
    ]
    rect: Rect
    text: str
    font: str = "B612 8"
    markup: bool = False
    key: typing.Optional[Key] = None
    inverted: bool = False


class MenuText(msgspec.Struct):
    text: str
    y_top: int
    font: str
    markup: bool = False


MenuItem = MenuButton | MenuText


class ButtonMenu(Screen):
    # Buttons are 400 px wide, 100 px high
    # Spread them as equally as possible along the screen height.
    button_size = Size(width=600, height=100)

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )

    async def run(self, event_channel: trio.abc.ReceiveChannel):
        self.hardware.reset_keystream(enable_composes=False)
        await self.render()
        while True:
            event = await event_channel.receive()
            handler = None
            match event:
                case AnnotatedKeyEvent():
                    for button in self.buttons:
                        if event.key == button.key:
                            handler = button.handler
                # TODO: have a TapInitiated event, and use it to render
                # the tapped button inverse.
                case TapEvent():
                    if event.phase is TapPhase.COMPLETED:
                        for button in self.buttons:
                            if event.location in button.rect:
                                handler = button.handler
                case KeyboardDisconnect():
                    return Modal(TargetScreen.KeyboardDetect)
            if handler is not None:
                result = await handler(event_channel)
                if result is not None:
                    return result
                await self.render()

    async def render(self):
        self.menu = tuple(self.define_menu())
        self.buttons = tuple(b for b in self.menu if isinstance(b, MenuButton))
        screen = self.make_screen()
        await self.hardware.display_pixels(screen.image, screen.extent)

    def make_screen(self):
        screen_size = self.renderer.screen_info.size
        x_center = math.floor(screen_size.width / 2)
        with self.renderer.create_surface(
            screen_size
        ) as surface, self.renderer.create_cairo_context(surface) as cairo_context:
            self.renderer.prepare_background(cairo_context)
            self.renderer.setup_drawing(cairo_context)
            for menuitem in self.menu:
                if isinstance(menuitem, MenuButton):
                    # TODO: support inverted
                    self.renderer.button(
                        cairo_context,
                        text=menuitem.text,
                        font=menuitem.font,
                        rect=menuitem.rect,
                        markup=menuitem.markup,
                    )
                if isinstance(menuitem, MenuText):
                    center_top = Point(x=0, y=menuitem.y_top)
                    self.renderer.move_to(cairo_context, center_top)
                    self.renderer.simple_render(
                        cairo_context,
                        menuitem.font,
                        menuitem.text,
                        markup=menuitem.markup,
                        alignment=Alignment.CENTER,
                        width=screen_size.width,
                        single_par=False,
                    )
            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return Rendered(
            image=buf, extent=Rect(origin=Point.zeroes(), spread=screen_size)
        )

    @abc.abstractmethod
    def define_menu(self) -> collections.abc.Iterable[MenuItem]:
        ...


class SystemMenu(ButtonMenu):
    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
        db: "TabulaDb",
        document: "DocumentModel",
    ):
        super().__init__(settings=settings, renderer=renderer, hardware=hardware)
        self.db = db
        self.document = document

    def define_menu(self):

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

        screen_size = self.renderer.screen_info.size
        button_x = math.floor((screen_size.width - self.button_size.width) / 2)
        button_total_height = self.button_size.height * len(buttons)
        whitespace_height = screen_size.height - button_total_height
        skip_height = math.floor(whitespace_height / (len(buttons) + 1))
        button_y = skip_height

        for button in buttons:
            button_rect = Rect(
                origin=Point(x=button_x, y=button_y), spread=self.button_size
            )
            button["rect"] = button_rect
            button_y += self.button_size.height + skip_height

        return tuple(
            MenuButton(
                handler=b["handler"],
                key=NUMBER_KEYS[b["number"]],
                text=f"{B612_CIRCLED_DIGITS[b['number']]} — {b['title']}",
                rect=b["rect"],
            )
            for b in buttons
        )

    async def new_session(self, event_channel: trio.abc.ReceiveChannel):
        session_id = self.db.new_session()
        self.document.load_session(session_id, self.db)
        await checkpoint()
        return Switch(TargetScreen.Drafting)

    async def previous_session(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Switch(TargetScreen.SessionList)

    async def export_current_session(self, event_channel: trio.abc.ReceiveChannel):
        self.document.export_session(self.db, self.settings.export_path)
        dialog = OkDialog(
            renderer=self.renderer, hardware=self.hardware, message="Export complete!"
        )
        result = await dialog.run(event_channel)
        if not isinstance(result, DialogResult):
            return result

    async def set_font(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Switch(TargetScreen.Fonts)

    async def resume_drafting(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Switch(TargetScreen.Drafting)

    async def shutdown(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Shutdown()


class SessionList(ButtonMenu):
    session_button_size = Size(width=800, height=100)
    page_button_size = Size(width=200, height=100)

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
        db: "TabulaDb",
        document: "DocumentModel",
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.db = db
        self.document = document
        self.offset = 0
        self.selected_session = None

    def refresh_sessions(self):
        self.sessions = self.db.list_sessions()

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.refresh_sessions()
        return await super().run(event_channel)

    def define_menu(self):
        if self.selected_session is None:
            return self.define_buttons_session_list()
        timestamp = now()
        edit_cutoff = timestamp - self.settings.max_editable_age
        screen_size = self.renderer.screen_info.size
        button_x = math.floor((screen_size.width - self.button_size.width) / 2)
        session_delta = self.selected_session.updated_at - timestamp
        header_text = f"Last edited {humanized_delta(session_delta)}\nWordcount: {self.selected_session.wordcount}"
        menuitems = [MenuText(text=header_text, y_top=10, font="Crimson Pro 12")]
        if self.selected_session.updated_at >= edit_cutoff:
            menuitems.append(
                MenuButton(
                    handler=self.load_session,
                    rect=Rect(origin=Point(x=button_x, y=150), spread=self.button_size),
                    text="Load Session",
                )
            )
        else:
            menuitems.append(
                MenuText(
                    text="This session is now locked for editing",
                    y_top=150,
                    font="B612 8",
                )
            )
        if self.selected_session.needs_export:
            menuitems.append(
                MenuButton(
                    handler=self.export_session,
                    rect=Rect(origin=Point(x=button_x, y=450), spread=self.button_size),
                    text="Export Session",
                )
            )
        menuitems.append(
            MenuButton(
                handler=self.delete_session,
                rect=Rect(origin=Point(x=button_x, y=650), spread=self.button_size),
                text="Delete Session",
            )
        )
        menuitems.append(
            MenuButton(
                handler=self.back_to_session_list,
                rect=Rect(origin=Point(x=button_x, y=850), spread=self.button_size),
                text="Back",
            )
        )
        return tuple(menuitems)

    def define_buttons_session_list(self) -> collections.abc.Iterable[MenuButton]:
        timestamp = now()
        screen_size = self.renderer.screen_info.size
        min_skip_height = math.floor(self.button_size.height * 0.75)
        usable_height = screen_size.height - (min_skip_height + self.button_size.height)
        num_session_buttons = usable_height // (
            min_skip_height + self.button_size.height
        )
        session_page = self.sessions[self.offset : self.offset + num_session_buttons]

        button_x = math.floor((screen_size.width - self.session_button_size.width) / 2)
        button_total_height = self.button_size.height * num_session_buttons
        whitespace_height = usable_height - button_total_height
        skip_height = math.floor(whitespace_height / (num_session_buttons + 1))
        button_y = skip_height

        menuitems = []
        for session in session_page:
            button_rect = Rect(
                origin=Point(x=button_x, y=button_y), spread=self.session_button_size
            )
            session_delta = session.updated_at - timestamp
            button_text = f"{humanized_delta(session_delta)} - {session.wordcount}"
            if session.needs_export:
                button_text += " \ue0a7"
            else:
                button_text += " \ue0a2"
            menuitems.append(
                MenuButton(
                    handler=functools.partial(self.select_session, session),
                    rect=button_rect,
                    text=button_text,
                )
            )
            button_y += self.button_size.height + skip_height

        if self.offset > 0:
            # back button
            prev_page_offset = max(0, self.offset - num_session_buttons)
            menuitems.append(
                MenuButton(
                    handler=functools.partial(self.change_page, prev_page_offset),
                    text="\ue0a9 Prev",
                    rect=Rect(
                        origin=Point(x=50, y=1300),
                        spread=self.page_button_size,
                    ),
                )
            )

        next_page_offset = self.offset + num_session_buttons
        if len(self.sessions[next_page_offset:]) > 0:
            # next button
            menuitems.append(
                MenuButton(
                    handler=functools.partial(self.change_page, next_page_offset),
                    text="Next \ue0a8",
                    rect=Rect(
                        origin=Point(
                            x=screen_size.width - (50 + self.page_button_size.width),
                            y=1300,
                        ),
                        spread=self.page_button_size,
                    ),
                )
            )

        # return button
        menuitems.append(
            MenuButton(
                handler=self.close_menu,
                text="Back",
                rect=Rect(
                    origin=Point(
                        x=math.floor(
                            (screen_size.width - self.page_button_size.width) / 2
                        ),
                        y=1300,
                    ),
                    spread=self.page_button_size,
                ),
            )
        )
        return tuple(menuitems)

    async def select_session(
        self, selected_session: Session, event_channel: trio.abc.ReceiveChannel
    ):
        self.selected_session = selected_session
        await checkpoint()
        return

    async def load_session(self, event_channel: trio.abc.ReceiveChannel):
        self.document.load_session(self.selected_session.id, self.db)
        await checkpoint()
        return Switch(TargetScreen.Drafting)

    async def export_session(self, event_channel: trio.abc.ReceiveChannel):
        session_document = DocumentModel()
        session_document.load_session(self.selected_session.id, self.db)

        session_document.export_session(self.db, self.settings.export_path)
        self.selected_session = None
        dialog = OkDialog(
            renderer=self.renderer, hardware=self.hardware, message="Export complete!"
        )
        result = await dialog.run(event_channel)
        if not isinstance(result, DialogResult):
            return result
        return

    async def delete_session(self, event_channel: trio.abc.ReceiveChannel):
        dialog = YesNoDialog(
            renderer=self.renderer, hardware=self.hardware, message="Really delete?"
        )
        result = await dialog.run(event_channel)
        if not isinstance(result, DialogResult):
            return result
        if result.value:
            if self.selected_session.id == self.document.session_id:
                self.document.delete_session(self.db)
            else:
                self.db.delete_session(self.selected_session.id)
            self.selected_session = None
            self.refresh_sessions()
        return

    async def back_to_session_list(self, event_channel: trio.abc.ReceiveChannel):
        self.selected_session = None
        await checkpoint()
        return

    async def change_page(
        self, new_offset: int, event_channel: trio.abc.ReceiveChannel
    ):
        self.offset = new_offset
        await checkpoint()
        return

    async def close_menu(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Switch(TargetScreen.SystemMenu)

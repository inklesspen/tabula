import abc
import collections.abc
import functools
import math
import typing

import msgspec
import trio

from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, Key, KeyboardDisconnect
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import Rendered, Alignment
from ..editor.document import DocumentModel
from ..editor.doctypes import Session
from ..util import checkpoint, now, humanized_delta, TickCaller
from ..editor.layout import LayoutManager, StatusLayout

from .numbers import NUMBER_KEYS, B612_CIRCLED_DIGITS
from .base import Switch, Modal, Close, Shutdown, RetVal, Screen
from .keyboard_detect import KeyboardDetect

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..rendering.renderer import Renderer
    from ..db import TabulaDb
    import pathlib


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
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.db = db
        self.document = document
        self.layout_manager = LayoutManager(self.renderer, self.document)
        self.status_layout = StatusLayout(self.renderer, self.document)

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.hardware.reset_keystream(enable_composes=True)
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
                            return Modal(Help)
                        elif event.key is Key.KEY_F12:
                            if self.document.wordcount == 0:
                                self.document.delete_session(self.db)
                            else:
                                self.document.save_session(self.db)
                            return Switch(SystemMenu)
                        await self.render_status()
                    case KeyboardDisconnect():
                        self.document.save_session(self.db)
                        print("Time to detect keyboard again.")
                        return Modal(KeyboardDetect)

    async def tick(self):
        self.document.save_session(self.db)
        await self.render_status()

    async def render_status(self):
        rendered = self.status_layout.render()
        await self.hardware.display_pixels(
            imagebytes=rendered.image, rect=rendered.extent
        )

    async def render_document(self):
        rendered = self.layout_manager.render_update(self.settings.current_font)
        await self.hardware.display_pixels(
            imagebytes=rendered.image, rect=rendered.extent
        )


def export_session(
    session_document: DocumentModel, db: "TabulaDb", export_path: "pathlib.Path"
):
    # TODO: maybe move this to a method on the db class
    export_path.mkdir(parents=True, exist_ok=True)
    timestamp = now()
    session_id = session_document.session_id
    export_filename = f"{session_id} - {timestamp} - {session_document.wordcount}.md"
    export_file = export_path / export_filename
    with export_file.open(mode="w", encoding="utf-8") as out:
        out.write(session_document.export_markdown())
    db.set_exported_time(session_id, timestamp)


class Button(msgspec.Struct):
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


MenuItem = Button | MenuText


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
                    print(event)
                    for button in self.buttons:
                        if event.location in button.rect:
                            handler = button.handler
                case KeyboardDisconnect():
                    print("Time to detect keyboard again.")
                    return Modal(KeyboardDetect)
            if handler is not None:
                result = await handler()
                if result is not None:
                    return result
                await self.render()

    async def render(self):
        self.menu = tuple(self.define_menu())
        self.buttons = tuple(b for b in self.menu if isinstance(b, Button))
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
                if isinstance(menuitem, Button):
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
            image=buf, extent=Rect(origin=Point(x=0, y=0), spread=screen_size)
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
            Button(
                handler=b["handler"],
                key=NUMBER_KEYS[b["number"]],
                text=f"{B612_CIRCLED_DIGITS[b['number']]} — {b['title']}",
                rect=b["rect"],
            )
            for b in buttons
        )

    async def new_session(self):
        session_id = self.db.new_session()
        self.document.load_session(session_id, self.db)
        await checkpoint()
        return Switch(Drafting)

    async def previous_session(self):
        await checkpoint()
        return Switch(SessionList)

    async def export_current_session(self):
        export_session(self.document, self.db, self.settings.export_path)
        # TODO: add some sort of Confirmation dialog
        await checkpoint()

    async def set_font(self):
        await checkpoint()
        return Switch(Fonts)

    async def resume_drafting(self):
        await checkpoint()
        return Switch(Drafting)

    async def shutdown(self):
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

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.sessions = self.db.list_sessions()
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
                Button(
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
                Button(
                    handler=self.export_session,
                    rect=Rect(origin=Point(x=button_x, y=450), spread=self.button_size),
                    text="Export Session",
                )
            )
        menuitems.append(
            Button(
                handler=self.delete_session,
                rect=Rect(origin=Point(x=button_x, y=650), spread=self.button_size),
                text="Delete Session",
            )
        )
        menuitems.append(
            Button(
                handler=self.back_to_session_list,
                rect=Rect(origin=Point(x=button_x, y=850), spread=self.button_size),
                text="Back",
            )
        )
        return tuple(menuitems)

    def define_buttons_session_list(self) -> collections.abc.Iterable[Button]:
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
                Button(
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
                Button(
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
                Button(
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
            Button(
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

    async def select_session(self, selected_session: Session):
        self.selected_session = selected_session
        await checkpoint()
        return

    async def load_session(self):
        self.document.load_session(self.selected_session.id, self.db)
        await checkpoint()
        return Switch(Drafting)

    async def export_session(self):
        session_document = DocumentModel()
        session_document.load_session(self.selected_session.id, self.db)

        export_session(session_document, self.db, self.settings.export_path)
        await checkpoint()
        self.selected_session = None
        return

    async def delete_session(self):
        self.db.delete_session(self.selected_session.id)
        await checkpoint()
        self.selected_session = None
        return

    async def back_to_session_list(self):
        self.selected_session = None
        await checkpoint()
        return

    async def change_page(self, new_offset: int):
        self.offset = new_offset
        await checkpoint()
        return

    async def close_menu(self):
        await checkpoint()
        return Switch(SystemMenu)


class Fonts(Screen):
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        pass


class Help(Screen):
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        pass

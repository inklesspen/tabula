import abc
import collections.abc
import functools
import math
import typing

import msgspec
import timeflake
import trio

from .hwtypes import AnnotatedKeyEvent, TapEvent, Key, KeyboardDisconnect
from .commontypes import Point, Size, Rect
from ..rendering.rendertypes import (
    Rendered,
    Margins,
    Alignment,
    WrapMode,
)
from ..rendering._cairopango import ffi, lib as clib
from .document import DocumentModel
from .doctypes import Session
from .util import checkpoint, now, humanized_delta
from .layout import LayoutManager

if typing.TYPE_CHECKING:
    from .hardware import Hardware
    from .settings import Settings
    from ..rendering.renderer2 import Renderer
    from .db import TabulaDb
    import pathlib


# https://en.wikipedia.org/wiki/Enclosed_Alphanumerics
# U+24EA is zero; it's out of order from the rest
# U+2460 is 1, U+2468 is 9
# U+24CE is Y; U+24C3 is N
# these are all in Noto Sans Symbols.
# B612 has similar glyphs but in a different block:
# https://en.wikipedia.org/wiki/Dingbats_(Unicode_block)
CIRCLED_ALPHANUMERICS = {
    "0": "\u24ea",
    "1": "\u2460",
    "2": "\u2461",
    "3": "\u2462",
    "4": "\u2463",
    "5": "\u2464",
    "6": "\u2465",
    "7": "\u2466",
    "8": "\u2467",
    "9": "\u2468",
    "Y": "\u24ce",
    "N": "\u24c3",
}

B612_CIRCLED_DIGITS = {
    1: "\u2780",
    2: "\u2781",
    3: "\u2782",
    4: "\u2783",
    5: "\u2784",
    6: "\u2785",
    7: "\u2786",
    8: "\u2787",
    9: "\u2788",
    0: "\u2789",
}

NUMBER_KEYS = {
    1: Key.KEY_1,
    2: Key.KEY_2,
    3: Key.KEY_3,
    4: Key.KEY_4,
    5: Key.KEY_5,
    6: Key.KEY_6,
    7: Key.KEY_7,
    8: Key.KEY_8,
    9: Key.KEY_9,
    0: Key.KEY_0,
}


class Switch(msgspec.Struct, frozen=True):
    new_screen: typing.Type["Screen"]
    kwargs: dict


class Modal(msgspec.Struct, frozen=True):
    modal: typing.Type["Screen"]
    kwargs: dict


class Close(msgspec.Struct, frozen=True):
    pass


class Shutdown(msgspec.Struct, frozen=True):
    pass


RetVal = Switch | Shutdown | Modal | Close


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


class Screen(abc.ABC):
    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
    ):
        self.settings = settings
        self.renderer = renderer
        self.hardware = hardware

    @abc.abstractmethod
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        ...


class KeyboardDetect(Screen):
    """Displays on startup or if the keyboards vanish. User must press a key to continue, or tap a screen button to quit."""

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
        on_startup: bool = False,
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.on_startup = on_startup

    async def run(self, event_channel: trio.abc.ReceiveChannel):
        self.hardware.reset_keystream(enable_composes=False)
        screen, button = self.make_screen()
        await self.hardware.display_pixels(screen.image, screen.extent)
        while True:
            event = await event_channel.receive()
            match event:
                case AnnotatedKeyEvent():
                    if self.on_startup:
                        return Switch(new_screen=SystemMenu, kwargs={"modal": False})
                    return Close()
                case TapEvent():
                    if event.location in button:
                        return Shutdown()

    def make_screen(self):
        screen_size = self.renderer.screen_info.size
        with self.renderer.create_surface(
            screen_size
        ) as surface, self.renderer.create_cairo_context(surface) as cairo_context:
            self.renderer.prepare_background(cairo_context)
            self.renderer.setup_drawing(cairo_context)

            self.renderer.move_to(cairo_context, Point(x=0, y=160))
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 48",
                "Tabula",
                alignment=Alignment.CENTER,
                width=screen_size.width,
            )

            self.renderer.move_to(cairo_context, Point(x=50, y=640))
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 12",
                "Connect a keyboard and press a key to continue, or tap the button to exit.",
                alignment=Alignment.LEFT,
                wrap=WrapMode.WORD,
                width=screen_size.width - 100,
            )

            # Rect(origin=Point(x=336, y=960), spread=Size(width=400, height=100))
            spread = Size(width=400, height=100)
            origin = Point(x=(screen_size.width - spread.width) / 2, y=960)
            button = Rect(origin=origin, spread=spread)
            # need to save the button rect for touch detection
            self.renderer.button(
                cairo_context, text="Exit", font="B612 10", rect=button
            )

            self.renderer.move_to(cairo_context, Point(x=0, y=1280))
            last_text = (
                "Presented by Straylight Labs"
                if self.on_startup
                else "Keyboard was disconnected"
            )
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 8",
                last_text,
                alignment=Alignment.CENTER,
                width=screen_size.width,
            )

            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return (
            Rendered(
                image=buf, extent=Rect(origin=Point(x=0, y=0), spread=screen_size)
            ),
            button,
        )


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
    button_size = Size(width=400, height=100)

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
                case TapEvent():
                    for button in self.buttons:
                        if event.location in button.rect:
                            handler = button.handler
                case KeyboardDisconnect():
                    print("Time to detect keyboard again.")
                    return Modal(KeyboardDetect, kwargs={})
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
        modal: bool = False,
    ):
        super().__init__(settings=settings, renderer=renderer, hardware=hardware)
        self.db = db
        self.document = document
        self.modal = modal

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
        return Switch(Drafting, kwargs={})

    async def previous_session(self):
        await checkpoint()
        return Switch(SessionList, kwargs={})

    async def export_current_session(self):
        export_session(self.document, self.db, self.settings.export_path)
        # TODO: add some sort of Confirmation dialog
        await checkpoint()

    async def set_font(self):
        await checkpoint()
        return Switch(Fonts, kwargs={})

    async def resume_drafting(self):
        await checkpoint()
        if self.modal:
            return Close()
        return Switch(Drafting, kwargs={})

    async def shutdown(self):
        await checkpoint()
        return Shutdown()


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

    # titlebar/statusbar/etc only needs to be shown on drafting screen, so that does not have to be independent
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.hardware.reset_keystream(enable_composes=True)
        await self.hardware.clear_screen()
        await self.handle_dirty_updates(
            [p.id for p in self.document.contents], force=True
        )

        while True:
            event = await event_channel.receive()
            match event:
                case AnnotatedKeyEvent():
                    if self.document.graphical_char(event.character):
                        await self.handle_dirty_updates(
                            self.document.keystroke(event.character)
                        )
                    elif event.key is Key.KEY_ENTER:
                        await self.handle_dirty_updates(self.document.new_para())
                        self.document.save_session(self.db)
                    elif event.key is Key.KEY_BACKSPACE:
                        await self.handle_dirty_updates(self.document.backspace())
                    elif event.key is Key.KEY_F1:
                        return Modal(Help, kwargs={})
                    elif event.key is Key.KEY_F12:
                        if self.document.wordcount == 0:
                            self.document.delete_session(self.db)
                            return Switch(SystemMenu, kwargs={})
                        self.document.save_session(self.db)
                        return Modal(SystemMenu, kwargs={"modal": True})
                case KeyboardDisconnect():
                    self.document.save_session(self.db)
                    print("Time to detect keyboard again.")
                    return Modal(KeyboardDetect, kwargs={})

    async def handle_dirty_updates(
        self,
        dirty_paragraph_ids: collections.abc.Iterable[timeflake.Timeflake],
        force=False,
    ):
        # TODO: remove unused arguments
        # TODO: draw status area
        # Line 1: Sprint status: timer, wordcount, hotkey reminder
        # Line 2: Session wordcount, current time, battery status, capslock, compose
        # TODO: Add various symbols (battery, capslock, compose) to Tabula Quattro
        rendered = self.layout_manager.render_update(self.settings.current_font)
        await self.hardware.display_pixels(
            imagebytes=rendered.image, rect=rendered.extent
        )

        # TODO: update the status line on a tick, instead of just whenever there's a text change
        # that way the clock can be kept up to date
        # TODO: extract into a status line version of LayoutManager
        screen_size = self.renderer.screen_info.size
        status_y_bottom = screen_size.height - 50
        layout = ffi.gc(
            clib.pango_layout_new(self.renderer.context), clib.g_object_unref
        )
        clib.pango_layout_set_auto_dir(layout, False)
        clib.pango_layout_set_ellipsize(layout, clib.PANGO_ELLIPSIZE_NONE)
        clib.pango_layout_set_justify(layout, False)
        clib.pango_layout_set_single_paragraph_mode(layout, False)
        clib.pango_layout_set_wrap(layout, WrapMode.WORD_CHAR)
        clib.pango_layout_set_width(
            layout,
            screen_size.width * clib.PANGO_SCALE,
        )
        clib.pango_layout_set_alignment(layout, Alignment.CENTER)

        with self.renderer._make_font_description(self.status_font) as font_description:
            clib.pango_layout_set_font_description(layout, font_description)

        status_line = "{0:,} words — {1:%H:%M}".format(self.document.wordcount, now())
        clib.pango_layout_set_text(layout, status_line.encode("utf-8"), -1)
        with ffi.new("PangoRectangle *") as logical_rect:
            clib.pango_layout_get_pixel_extents(layout, ffi.NULL, logical_rect)
            status_y_top = status_y_bottom - logical_rect.height
            markup_size = Size(width=screen_size.width, height=logical_rect.height)
        markup_surface = self.renderer.create_surface(markup_size)
        with self.renderer.create_cairo_context(markup_surface) as markup_context:
            clib.cairo_set_operator(markup_context, clib.CAIRO_OPERATOR_SOURCE)
            clib.cairo_set_source_rgba(markup_context, 1, 1, 1, 1)
            clib.cairo_paint(markup_context)
            clib.cairo_set_source_rgba(markup_context, 0, 0, 0, 0)
            clib.pango_cairo_show_layout(markup_context, layout)
        clib.cairo_surface_flush(markup_surface)
        rendered = Rendered(
            image=self.renderer.surface_to_bytes(
                markup_surface, markup_size, skip_inversion=True
            ),
            extent=Rect(origin=Point(x=0, y=status_y_top), spread=markup_size),
        )
        await self.hardware.display_pixels(
            imagebytes=rendered.image, rect=rendered.extent
        )


class SessionList(ButtonMenu):
    # TODO: reuse this class for picking a session to export also.
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
        menuitems = [
            MenuText(
                text="Hello world\nGoodbye cruel world", y_top=10, font="Crimson Pro 12"
            ),
            Button(
                handler=self.load_session,
                rect=Rect(origin=Point(x=button_x, y=150), spread=self.button_size),
                text="Load Session",
            ),
        ]
        # if self.selected_session.needs_export:
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

        button_x = math.floor((screen_size.width - self.button_size.width) / 2)
        button_total_height = self.button_size.height * num_session_buttons
        whitespace_height = usable_height - button_total_height
        skip_height = math.floor(whitespace_height / (num_session_buttons + 1))
        button_y = skip_height

        buttons = []
        for session in session_page:
            button_rect = Rect(
                origin=Point(x=button_x, y=button_y), spread=self.button_size
            )
            session_delta = session.updated_at - timestamp
            button_text = f"{humanized_delta(session_delta)} - {session.wordcount}"
            if session.needs_export:
                button_text += " \ue0a7"
            else:
                button_text += " \ue0a2"
            buttons.append(
                Button(
                    handler=functools.partial(self.select_session, session),
                    rect=button_rect,
                    text=button_text,
                )
            )
            button_y += self.button_size.height + skip_height

        # TODO: add page buttons, export all, back to menu, etc

        return tuple(buttons)

    async def select_session(self, selected_session: Session):
        self.selected_session = selected_session
        await checkpoint()
        return

    async def load_session(self):
        self.document.load_session(self.selected_session.id, self.db)
        await checkpoint()
        return Switch(Drafting, kwargs={})

    async def export_session(self):
        session_document = DocumentModel()
        session_document.load_session(self.selected_session.id, self.db)

        export_session(session_document, self.db, self.settings.export_path)
        await checkpoint()
        self.selected_session = None
        return

    async def delete_session(self):
        await checkpoint()
        self.selected_session = None
        return

    async def back_to_session_list(self):
        self.selected_session = None
        await checkpoint()
        return


class Fonts(Screen):
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        pass


class Help(Screen):
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        pass

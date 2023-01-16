import abc
import collections.abc
import math
import typing

import msgspec
import timeflake
import trio

from .hwtypes import AnnotatedKeyEvent, ScreenRect, TapEvent, Key, KeyboardDisconnect
from .commontypes import Point, Size, Rect, ScreenInfo
from ..rendering.rendertypes import (
    Rendered,
    Margins,
    AffineTransform,
    Alignment,
    WrapMode,
)
from .doctypes import Renderable
from .util import checkpoint
from . import draft_rendering

if typing.TYPE_CHECKING:
    from .hardware import Hardware
    from .settings import Settings
    from ..rendering.renderer2 import Renderer
    from .db import TabulaDb
    from .document import DocumentModel


# https://en.wikipedia.org/wiki/Enclosed_Alphanumerics
# U+24EA is zero; it's out of order from the rest
# U+2460 is 1, U+2468 is 9
# U+24CE is Y; U+24C3 is N
# these are all in Noto Sans Symbols.
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
        await self.hardware.display_pixels(
            screen.image,
            ScreenRect(
                x=screen.extent.origin.x,
                y=screen.extent.origin.y,
                width=screen.extent.spread.width,
                height=screen.extent.spread.height,
            ),
        )
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
                cairo_context, text="Exit", font="Crimson Pro 10", rect=button
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


class ButtonMenu(Screen):
    # Buttons are 400 px wide, 100 px high
    # Spread them as equally as possible along the screen height.
    button_size = Size(width=400, height=100)


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
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.db = db
        self.document = document
        self.modal = modal
        self.button_rects = {}
        buttons = [
            {
                "handler": "new_session",
                "number": 1,
                "title": "New Session",
                "key": Key.KEY_1,
            },
            {
                "handler": "resume_session",
                "number": 2,
                "title": "Resume Session",
                "key": Key.KEY_2,
            },
            {"handler": "set_font", "number": 3, "title": "Set Font", "key": Key.KEY_3},
            {
                "handler": "export",
                "number": 4,
                "title": "Export Markdown",
                "key": Key.KEY_4,
            },
            {"handler": "shutdown", "number": 0, "title": "Shutdown", "key": Key.KEY_0},
        ]
        if self.modal:
            buttons.insert(
                -1,
                {
                    "handler": "close_modal",
                    "number": 9,
                    "title": "Resume Drafting",
                    "key": Key.KEY_9,
                },
            )

        self.buttons_by_handler = {button["handler"]: button for button in buttons}
        self.buttons_by_key = {button["key"]: button for button in buttons}

    async def run(self, event_channel: trio.abc.ReceiveChannel):
        self.hardware.reset_keystream(enable_composes=False)
        screen = self.make_screen()
        await self.hardware.display_pixels(
            screen.image,
            ScreenRect(
                x=screen.extent.origin.x,
                y=screen.extent.origin.y,
                width=screen.extent.spread.width,
                height=screen.extent.spread.height,
            ),
        )
        while True:
            event = await event_channel.receive()
            handler = None
            match event:
                case AnnotatedKeyEvent():
                    if event.key in self.buttons_by_key:
                        button = self.buttons_by_key[event.key]
                        handler = getattr(self, button["handler"])
                case TapEvent():
                    for button_handler, button_rect in self.button_rects.items():
                        if event.location in button_rect:
                            button = self.buttons_by_handler[button_handler]
                            handler = getattr(self, button["handler"])
            if handler is not None:
                return await handler()

    def make_screen(self):
        screen_size = self.renderer.screen_info.size
        button_x = math.floor((screen_size.width - self.button_size.width) / 2)
        button_total_height = self.button_size.height * len(self.buttons_by_handler)
        whitespace_height = screen_size.height - button_total_height
        skip_height = math.floor(whitespace_height / (len(self.buttons_by_handler) + 1))
        button_y = skip_height
        with self.renderer.create_surface(
            screen_size
        ) as surface, self.renderer.create_cairo_context(surface) as cairo_context:
            self.renderer.prepare_background(cairo_context)
            self.renderer.setup_drawing(cairo_context)
            for button in self.buttons_by_handler.values():
                button_rect = Rect(
                    origin=Point(x=button_x, y=button_y), spread=self.button_size
                )
                self.button_rects[button["handler"]] = button_rect
                button_title = f"<span font=\"Noto Sans Symbols 8\">{CIRCLED_ALPHANUMERICS[str(button['number'])]}</span> — {button['title']}"
                # button_title = f"{button['number']} — {button['title']}"
                self.renderer.button(
                    cairo_context,
                    text=button_title,
                    font="Noto Serif 8",
                    rect=button_rect,
                    markup=True,
                )
                button_y += self.button_size.height + skip_height
            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return Rendered(
            image=buf, extent=Rect(origin=Point(x=0, y=0), spread=screen_size)
        )

    async def new_session(self):
        session_id = self.db.new_session()
        self.document.load_session(session_id)
        await checkpoint()
        return Switch(Drafting, kwargs={})

    async def resume_session(self):
        await checkpoint()
        return Switch(SessionList, kwargs={})

    async def set_font(self):
        await checkpoint()
        return Switch(Fonts, kwargs={})

    async def close_modal(self):
        await checkpoint()
        return Close()

    async def shutdown(self):
        await checkpoint()
        return Shutdown()


class Drafting(Screen):
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
        self.draft_screen = draft_rendering.Screen(self.renderer, self.settings)

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
                    dirties = tuple()
                    if self.document.graphical_char(event.character):
                        dirties = self.document.keystroke(event.character)
                    elif event.key is Key.KEY_ENTER:
                        dirties = self.document.new_para()
                    elif event.key is Key.KEY_BACKSPACE:
                        dirties = self.document.backspace()
                    elif event.key is Key.KEY_F1:
                        return Modal(Help, kwargs={})
                    elif event.key is Key.KEY_F12:
                        return Modal(SystemMenu, kwargs={"modal": True})
                    if dirties:
                        await self.handle_dirty_updates(dirties)
                case KeyboardDisconnect():
                    print("Time to detect keyboard again.")
                    return Modal(KeyboardDetect, kwargs={})

    async def handle_dirty_updates(
        self,
        dirty_paragraph_ids: collections.abc.Iterable[timeflake.Timeflake],
        force=False,
    ):
        paras = [self.document[para_id] for para_id in dirty_paragraph_ids]
        renderables = [
            Renderable(
                index=para.index,
                markup=para.markup,
                has_cursor=(para.id == self.document.cursor_para_id),
            )
            for para in paras
        ]
        # renderer
        framelets = self.draft_screen.render_update(renderables, force=force)
        # hardware
        # there are only ever 0 or 1 framelets, so…
        for framelet in framelets:
            await self.hardware.display_pixels(
                imagebytes=bytes(framelet.image), rect=framelet.rect
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

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.sessions = self.db.list_sessions()
        self.hardware.reset_keystream(enable_composes=False)
        screen = self.make_screen()

    def make_screen(self):
        screen_size = self.renderer.screen_info.size


class Fonts(Screen):
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        pass


class Help(Screen):
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        pass

import abc
import math
import typing

import msgspec
import trio

from .hwtypes import AnnotatedKeyEvent, TouchReport, ScreenRect, TapEvent
from .commontypes import Point, Size, Rect, ScreenInfo
from ..rendering.rendertypes import (
    Rendered,
    Margins,
    AffineTransform,
    Alignment,
    WrapMode,
)

if typing.TYPE_CHECKING:
    from .hardware import Hardware
    from .settings import Settings
    from ..rendering.renderer2 import Renderer


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


class SystemMenu(Screen):
    # Buttons are 400 px wide, 100 px high
    # Spread them as equally as possible along the screen height.
    button_size: Size(width=400, height=100)
    buttons = (
        f"{CIRCLED_ALPHANUMERICS['1']} New Session",
        f"{CIRCLED_ALPHANUMERICS['2']} Resume Session",
        f"{CIRCLED_ALPHANUMERICS['3']} Set Font",
        f"{CIRCLED_ALPHANUMERICS['4']} Export Markdown",
        f"{CIRCLED_ALPHANUMERICS['0']} Shutdown",
    )

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
        modal: bool = False,
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.modal = modal

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
            match event:
                case AnnotatedKeyEvent():
                    print(event)
                case TouchReport():
                    print(event)

    def make_screen(self):
        screen_size = self.renderer.screen_info.size
        button_x = math.floor((screen_size.width - self.button_size.width) / 2)
        button_total_height = self.button_size.height * len(self.buttons)
        whitespace_height = screen_size.height - button_total_height
        skip_height = math.floor(whitespace_height / (len(self.buttons) + 1))
        button_y = skip_height
        with self.renderer.create_surface(
            screen_size
        ) as surface, self.renderer.create_cairo_context(surface) as cairo_context:
            self.renderer.prepare_background(cairo_context)
            self.renderer.setup_drawing(cairo_context)
            for button in self.buttons:
                button_rect = Rect(
                    origin=Point(x=button_x, y=button_y), spread=self.button_size
                )
                print(f"{button} - {button_rect}")
                self.renderer.button(
                    cairo_context, text=button, font="Crimson Pro 10", rect=button
                )
            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return Rendered(
            image=buf, extent=Rect(origin=Point(x=0, y=0), spread=screen_size)
        )


class Drafting(Screen):
    # titlebar/statusbar/etc only needs to be shown on drafting screen, so that does not have to be independent
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        pass


class Help(Screen):
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        pass

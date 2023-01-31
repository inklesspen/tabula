import typing

import trio

from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, TapPhase
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import (
    Rendered,
    Alignment,
    WrapMode,
)

from .base import Close, Shutdown, Screen

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..rendering.renderer import Renderer


class KeyboardDetect(Screen):
    """Displays on startup or if the keyboards vanish. User must press a key to continue, or tap a screen button to quit."""

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
    ):
        super().__init__(settings=settings, renderer=renderer, hardware=hardware)
        screen_size = self.renderer.screen_info.size
        spread = Size(width=400, height=100)
        origin = Point(x=(screen_size.width - spread.width) / 2, y=960)
        self.button_rect = Rect(origin=origin, spread=spread)
        self.button_inverted = False

    async def run(self, event_channel: trio.abc.ReceiveChannel):
        self.hardware.reset_keystream(enable_composes=False)
        screen = None
        while True:
            if screen is None:
                screen = self.make_screen()
                await self.hardware.display_pixels(screen.image, screen.extent)
            event = await event_channel.receive()
            match event:
                case AnnotatedKeyEvent():
                    return Close()
                case TapEvent():
                    match event.phase:
                        case TapPhase.INITIATED:
                            if event.location in self.button_rect:
                                self.button_inverted = True
                                screen = None
                        case TapPhase.CANCELED:
                            if self.button_inverted:
                                self.button_inverted = False
                                screen = None
                        case TapPhase.COMPLETED:
                            if event.location in self.button_rect:
                                return Shutdown()
                            if self.button_inverted:
                                self.button_inverted = False
                                screen = None

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

            self.renderer.button(
                cairo_context,
                text="Exit",
                font="B612 10",
                rect=self.button_rect,
                inverted=self.button_inverted,
            )

            self.renderer.move_to(cairo_context, Point(x=0, y=1280))
            last_text = "Presented by Straylight Labs"
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 8",
                last_text,
                alignment=Alignment.CENTER,
                width=screen_size.width,
            )

            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return Rendered(
            image=buf, extent=Rect(origin=Point(x=0, y=0), spread=screen_size)
        )

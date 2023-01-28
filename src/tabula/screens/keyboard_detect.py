import trio

from ..device.hwtypes import AnnotatedKeyEvent, TapEvent
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import (
    Rendered,
    Alignment,
    WrapMode,
)

from .base import Close, Shutdown, Screen


class KeyboardDetect(Screen):
    """Displays on startup or if the keyboards vanish. User must press a key to continue, or tap a screen button to quit."""

    async def run(self, event_channel: trio.abc.ReceiveChannel):
        self.hardware.reset_keystream(enable_composes=False)
        screen, button = self.make_screen()
        await self.hardware.display_pixels(screen.image, screen.extent)
        while True:
            event = await event_channel.receive()
            match event:
                case AnnotatedKeyEvent():
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
            last_text = "Presented by Straylight Labs"
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

import logging
import typing

import outcome

from ..device.hwtypes import TapEvent, TapPhase
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import Rendered, Alignment, WrapMode
from ..util import TABULA, Future
from .base import Responder

if typing.TYPE_CHECKING:
    from ..rendering.renderer import Renderer


logger = logging.getLogger(__name__)


class Dialog(Responder):
    future: Future


class OkDialog(Dialog):
    def __init__(
        self,
        *,
        renderer: "Renderer",
        message: str,
    ):
        self.renderer = renderer
        self.message = message
        self.future = Future()

        screen_size = self.renderer.screen_info.size
        spread = Size(width=400, height=100)
        origin = Point(x=(screen_size.width - spread.width) / 2, y=960)
        self.button_rect = Rect(origin=origin, spread=spread)

    async def become_responder(self):
        app = TABULA.get()
        screen = self.make_screen()
        app.hardware.display_pixels(screen.image, screen.extent)

    async def handle_tap_event(self, event: TapEvent):
        if event.location in self.button_rect and event.phase is TapPhase.COMPLETED:
            self.future.finalize(outcome.Value(None))

    def make_screen(self):
        # TODO: consider making it smaller and adding a border box?
        screen_size = self.renderer.screen_info.size
        with self.renderer.create_surface(screen_size) as surface, self.renderer.create_cairo_context(surface) as cairo_context:
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

            self.renderer.move_to(cairo_context, Point(x=0, y=640))
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 12",
                self.message,
                alignment=Alignment.CENTER,
                wrap=WrapMode.WORD,
                width=screen_size.width,
            )

            self.renderer.button(cairo_context, text="OK", font="B612 10", rect=self.button_rect)

            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return Rendered(image=buf, extent=Rect(origin=Point.zeroes(), spread=screen_size))


class YesNoDialog(Dialog):
    def __init__(
        self,
        *,
        renderer: "Renderer",
        message: str,
    ):
        self.renderer = renderer
        self.message = message
        self.future = Future()

        button_size = Size(width=400, height=100)
        self.no_rect = Rect(origin=Point(x=100, y=960), spread=button_size)
        self.yes_rect = Rect(
            origin=Point(x=self.renderer.screen_info.size.width - 500, y=960),
            spread=button_size,
        )

    async def become_responder(self):
        app = TABULA.get()
        screen = self.make_screen()
        app.hardware.display_pixels(screen.image, screen.extent)

    async def handle_tap_event(self, event: TapEvent):
        if event.phase is TapPhase.COMPLETED:
            if event.location in self.no_rect:
                self.future.finalize(outcome.Value(False))
            if event.location in self.yes_rect:
                self.future.finalize(outcome.Value(True))

    def make_screen(self):
        # TODO: consider making it smaller and adding a border box?
        screen_size = self.renderer.screen_info.size
        with self.renderer.create_surface(screen_size) as surface, self.renderer.create_cairo_context(surface) as cairo_context:
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

            self.renderer.move_to(cairo_context, Point(x=0, y=640))
            self.renderer.simple_render(
                cairo_context,
                "Crimson Pro 12",
                self.message,
                alignment=Alignment.CENTER,
                wrap=WrapMode.WORD,
                width=screen_size.width,
            )

            self.renderer.button(cairo_context, text="No", font="B612 10", rect=self.no_rect)
            self.renderer.button(cairo_context, text="Yes", font="B612 10", rect=self.yes_rect)

            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return Rendered(image=buf, extent=Rect(origin=Point.zeroes(), spread=screen_size))

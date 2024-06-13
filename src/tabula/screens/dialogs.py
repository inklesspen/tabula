import logging
import typing

import outcome

from ..device.hwtypes import TapEvent, TapPhase
from ..commontypes import Point, Size
from ..rendering.fonts import SERIF
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from ..rendering.rendertypes import Alignment, WrapMode, CairoColor
from ..util import TABULA, Future
from .base import Responder
from .widgets import Button

if typing.TYPE_CHECKING:
    from ..commontypes import ScreenInfo


logger = logging.getLogger(__name__)


class Dialog(Responder):
    future: Future


class OkDialog(Dialog):
    def __init__(self, *, screen_info: "ScreenInfo", message: str):
        self.screen_info = screen_info
        self.message = message
        self.future = Future()

        self.pango = Pango(dpi=screen_info.dpi)
        button_spread = Size(width=400, height=100)
        button_origin = Point(x=(screen_info.size.width - button_spread.width) / 2, y=960)

        self.button = Button(
            self.pango,
            button_text="Exit",
            button_size=button_spread,
            corner_radius=50,
            font="B612 10",
            screen_location=button_origin,
        )

    async def become_responder(self):
        app = TABULA.get()
        screen = self.make_screen()
        app.hardware.display_pixels(screen.image, screen.extent)

    async def handle_tap_event(self, event: TapEvent):
        if event.location in self.button and event.phase is TapPhase.COMPLETED:
            self.future.finalize(outcome.Value(None))

    def make_screen(self):
        # TODO: consider making it smaller and adding a border box?
        with Cairo(self.screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            cairo.move_to(Point(x=0, y=160))
            with PangoLayout(pango=self.pango, width=self.screen_info.size.width, alignment=Alignment.CENTER) as layout:
                layout.set_font(f"{SERIF} 48")
                layout.set_content("Tabula")
                layout.render(cairo)

            cairo.move_to(Point(x=0, y=640))
            with PangoLayout(pango=self.pango, width=self.screen_info.size.width, alignment=Alignment.CENTER, wrap=WrapMode.WORD) as layout:
                layout.set_font(f"{SERIF} 12")
                layout.set_content(self.message)
                layout.render(cairo)

            self.button.paste_onto_cairo(cairo)

            screen = cairo.get_rendered(origin=Point.zeroes())
        return screen


class YesNoDialog(Dialog):
    def __init__(self, *, screen_info: "ScreenInfo", message: str):
        self.screen_info = screen_info
        self.message = message
        self.future = Future()

        self.pango = Pango(dpi=screen_info.dpi)
        button_size = Size(width=400, height=100)

        self.no_button = Button(
            self.pango,
            button_text="No",
            button_size=button_size,
            corner_radius=50,
            font="B612 10",
            screen_location=Point(x=100, y=960),
        )
        self.yes_button = Button(
            self.pango,
            button_text="Yes",
            button_size=button_size,
            corner_radius=50,
            font="B612 10",
            screen_location=Point(x=screen_info.size.width - 500, y=960),
        )

    async def become_responder(self):
        app = TABULA.get()
        screen = self.make_screen()
        app.hardware.display_pixels(screen.image, screen.extent)

    async def handle_tap_event(self, event: TapEvent):
        if event.phase is TapPhase.COMPLETED:
            if event.location in self.no_button:
                self.future.finalize(outcome.Value(False))
            if event.location in self.yes_button:
                self.future.finalize(outcome.Value(True))

    def make_screen(self):
        # TODO: consider making it smaller and adding a border box?
        with Cairo(self.screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            cairo.move_to(Point(x=0, y=160))
            with PangoLayout(pango=self.pango, width=self.screen_info.size.width, alignment=Alignment.CENTER) as layout:
                layout.set_font(f"{SERIF} 48")
                layout.set_content("Tabula")
                layout.render(cairo)

            cairo.move_to(Point(x=0, y=640))
            with PangoLayout(pango=self.pango, width=self.screen_info.size.width, alignment=Alignment.CENTER, wrap=WrapMode.WORD) as layout:
                layout.set_font(f"{SERIF} 12")
                layout.set_content(self.message)
                layout.render(cairo)

            self.no_button.paste_onto_cairo(cairo)
            self.yes_button.paste_onto_cairo(cairo)

            screen = cairo.get_rendered(origin=Point.zeroes())
        return screen

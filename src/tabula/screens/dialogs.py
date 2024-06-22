from __future__ import annotations

import logging
import math
import typing

import outcome

from ..device.hwtypes import TapEvent, TapPhase
from ..commontypes import Point, Size
from ..rendering.fonts import SERIF
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango
from ..rendering.rendertypes import WrapMode, CairoColor
from ..util import TABULA, Future
from .base import Responder
from .widgets import Button, Label, ButtonSpec, make_button_row

if typing.TYPE_CHECKING:
    from ..commontypes import ScreenInfo


logger = logging.getLogger(__name__)


class Dialog(Responder):
    future: Future


class OkDialog(Dialog):
    def __init__(self, *, message: str):
        self.message = message
        self.future = Future()

    async def become_responder(self):
        app = TABULA.get()
        screen = self.make_screen(app.screen_info)
        app.hardware.display_rendered(screen)

    async def handle_tap_event(self, event: TapEvent):
        if event.location in self.button and event.phase is TapPhase.COMPLETED:
            self.future.finalize(outcome.Value(None))

    def make_screen(self, screen_info: ScreenInfo):
        pango = Pango(dpi=screen_info.dpi)
        button_size = Size(width=400, height=100)
        button_origin = Point(x=(screen_info.size.width - button_size.width) / 2, y=math.floor(screen_info.size.height * 0.65))

        self.button = Button.create(
            pango,
            button_text="OK",
            button_size=button_size,
            corner_radius=50,
            font="B612 10",
            screen_location=button_origin,
        )

        app_label = Label.create(
            pango=pango,
            text="Tabula",
            font=f"{SERIF} 48",
            location=Point(x=0, y=math.floor(screen_info.size.height * 0.15)),
            width=screen_info.size.width,
        )
        directions_label = Label.create(
            pango=pango,
            text=self.message,
            font=f"{SERIF} 12",
            location=Point(x=0, y=math.floor(screen_info.size.height * 0.45)),
            width=screen_info.size.width,
            wrap=WrapMode.WORD,
        )

        with Cairo(screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)

            app_label.paste_onto_cairo(cairo)
            directions_label.paste_onto_cairo(cairo)
            self.button.paste_onto_cairo(cairo)

            screen = cairo.get_rendered(origin=Point.zeroes())
        return screen


class YesNoDialog(Dialog):
    def __init__(self, *, message: str):
        self.message = message
        self.future = Future()

    async def become_responder(self):
        app = TABULA.get()
        screen = self.make_screen(app.screen_info)
        app.hardware.display_rendered(screen)

    async def handle_tap_event(self, event: TapEvent):
        if event.phase is TapPhase.COMPLETED:
            if event.location in self.no_button:
                self.future.finalize(outcome.Value(False))
            if event.location in self.yes_button:
                self.future.finalize(outcome.Value(True))

    def make_screen(self, screen_info: ScreenInfo):
        pango = Pango(dpi=screen_info.dpi)
        button_size = Size(width=400, height=100)
        self.no_button, self.yes_button = make_button_row(
            (ButtonSpec(button_text="No", button_value=False),),
            (ButtonSpec(button_text="Yes", button_value=True),),
            button_size=button_size,
            corner_radius=50,
            default_font="B612 10",
            pango=pango,
            row_width=screen_info.size.width,
            button_y=math.floor(screen_info.size.height * 0.65),
        )
        app_label = Label.create(
            pango=pango,
            text="Tabula",
            font=f"{SERIF} 48",
            location=Point(x=0, y=math.floor(screen_info.size.height * 0.15)),
            width=screen_info.size.width,
        )
        directions_label = Label.create(
            pango=pango,
            text=self.message,
            font=f"{SERIF} 12",
            location=Point(x=0, y=math.floor(screen_info.size.height * 0.45)),
            width=screen_info.size.width,
            wrap=WrapMode.WORD,
        )

        with Cairo(screen_info.size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            app_label.paste_onto_cairo(cairo)
            directions_label.paste_onto_cairo(cairo)

            self.no_button.paste_onto_cairo(cairo)
            self.yes_button.paste_onto_cairo(cairo)

            screen = cairo.get_rendered(origin=Point.zeroes())
        return screen

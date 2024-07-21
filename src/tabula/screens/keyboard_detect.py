from __future__ import annotations

import logging
import math
import typing

from ..commontypes import Point, Size
from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, TapPhase
from ..rendering.cairo import Cairo
from ..rendering.fonts import SERIF
from ..rendering.pango import Pango
from ..rendering.rendertypes import CairoColor
from ..util import TABULA, Future
from .dialogs import Dialog
from .widgets import Button, ButtonState, Label

if typing.TYPE_CHECKING:
    from ..commontypes import ScreenInfo
    from ..settings import Settings


logger = logging.getLogger(__name__)


class KeyboardDetectDialog(Dialog):
    def __init__(self, *, settings: Settings, screen_info: ScreenInfo):
        self.settings = settings
        self.future = Future()

        self.screen = self.render(screen_info)

    def render(self, screen_info: ScreenInfo):
        self.screen_info = screen_info
        pango = Pango(dpi=screen_info.dpi)
        screen_size = screen_info.size
        button_size = Size(width=400, height=100)
        self.shutdown_button = Button.create(
            pango,
            button_text="Exit",
            button_size=button_size,
            corner_radius=50,
            font="B612 10",
            screen_location=Point(x=(screen_size.width - button_size.width) // 2, y=math.floor(screen_size.height * 0.65)),
        )
        self.rotate_button = Button.create(
            pango,
            button_text="\ue1c1",
            button_size=Size(width=100, height=100),
            corner_radius=25,
            font="Material Symbols 16",
            screen_location=Point(x=screen_size.width - 150, y=screen_size.height - 150),
        )

        self.app_label = Label.create(
            pango=pango,
            text="Tabula",
            font=f"{SERIF} 48",
            location=Point(x=0, y=math.floor(screen_size.height * 0.15)),
            width=screen_size.width,
        )
        self.credit_label = Label.create(
            pango=pango,
            text="Presented by Straylight Labs",
            font=f"{SERIF} 8",
            location=Point(x=0, y=math.floor(screen_size.height * 0.85)),
            width=screen_size.width,
        )
        self.directions_label = Label.create(
            pango=pango,
            text="Connect a keyboard and press a key to continue, or tap the button to exit.",
            font=f"{SERIF} 12",
            location=Point(x=50, y=math.floor(screen_size.height * 0.45)),
            width=screen_size.width - 100,
        )

        with Cairo(screen_size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            self.app_label.paste_onto_cairo(cairo)
            self.credit_label.paste_onto_cairo(cairo)
            self.directions_label.paste_onto_cairo(cairo)
            self.shutdown_button.paste_onto_cairo(cairo)
            self.rotate_button.paste_onto_cairo(cairo)
            return cairo.get_rendered(origin=Point.zeroes())

    def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream()
        if self.screen_info != app.screen_info:
            self.screen = self.render(app.screen_info)
        app.hardware.display_rendered(self.screen)

    def screen_size_changed(self):
        self.become_responder()

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        self.future.finalize(None)

    async def handle_tap_event(self, event: TapEvent):
        app = TABULA.get()
        if event.phase is TapPhase.COMPLETED:
            if event.location in self.shutdown_button:
                app.hardware.display_rendered(self.shutdown_button.render(override_state=ButtonState.PRESSED))
                await app.shutdown()
            elif event.location in self.rotate_button:
                app.hardware.display_rendered(self.rotate_button.render(override_state=ButtonState.PRESSED))
                app.rotate()
                # force rerender; this is the only screen where rotation can happen while the screen is active
                self.become_responder()

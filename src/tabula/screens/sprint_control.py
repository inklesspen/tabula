from __future__ import annotations

import logging
import typing

from ..commontypes import Point, Size
from ..device.eventsource import KeyCode
from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, TapPhase
from ..durations import format_duration
from ..rendering.cairo import Cairo
from ..rendering.fonts import SERIF
from ..rendering.pango import Pango
from ..rendering.rendertypes import CairoColor
from ..util import TABULA, Future, now
from .dialogs import Dialog
from .widgets import Button, ButtonState, Label, make_button_row

if typing.TYPE_CHECKING:
    from ..commontypes import ScreenInfo
    from ..settings import Settings

logger = logging.getLogger(__name__)


class SprintControl(Dialog):
    action_buttons: list[Button]
    length_buttons: list[Button]

    def __init__(
        self,
        *,
        settings: Settings,
        screen_info: ScreenInfo,
    ):
        self.settings = settings
        self.pango = Pango(dpi=screen_info.dpi)
        self.screen_size = screen_info.size
        self.lengths = self.settings.sprint_lengths
        self.selected_index = None
        self.future = Future()

    @property
    def sprint_length(self):
        if self.selected_index is None:
            return None
        length = self.lengths[self.selected_index]
        return length

    @property
    def sprint_end(self):
        length = self.sprint_length
        if length is not None:
            return now() + length

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream()
        self.pango = Pango(dpi=app.screen_info.dpi)
        self.screen_size = app.screen_info.size
        self.render_screen()

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        if event.key is KeyCode.KEY_ESC:
            self.future.finalize(False)

    async def handle_tap_event(self, event: TapEvent):
        app = TABULA.get()
        if event.phase is TapPhase.COMPLETED:
            for index, length_button in enumerate(self.length_buttons):
                if event.location in length_button:
                    self.selected_index = index
                    self.render_sprint_time_info()
            for button in self.action_buttons:
                if event.location in button:
                    app.hardware.display_rendered(button.render(override_state=ButtonState.PRESSED))
                    match button.button_value:
                        case "cancel":
                            return self.future.finalize(False)
                        case "begin":
                            if self.sprint_length is not None:
                                return self.future.finalize(self.sprint_length)

                            return self.future.finalize(False)
            self.update_button_state()

    def make_buttons(self):
        sprint_specs = [({"button_text": format_duration(length)},) for length in self.lengths]
        self.length_buttons = make_button_row(
            *sprint_specs,
            button_size=Size(width=80, height=80),
            corner_radius=25,
            default_font="B612 8",
            pango=self.pango,
            button_y=650,
            row_width=self.screen_size.width,
        )
        if self.selected_index is not None:
            self.length_buttons[self.selected_index].update_state(ButtonState.SELECTED)

        button_size = Size(width=400, height=100)
        button_x = (self.screen_size.width - button_size.width) // 2
        self.action_buttons = []
        self.action_buttons.append(
            Button.create(
                self.pango,
                button_text="Begin Sprint",
                button_size=button_size,
                corner_radius=50,
                font="B612 8",
                screen_location=Point(x=button_x, y=800),
                button_value="begin",
            )
        )
        self.action_buttons.append(
            Button.create(
                self.pango,
                button_text="Cancel",
                button_size=button_size,
                corner_radius=50,
                font="B612 8",
                screen_location=Point(x=button_x, y=950),
                button_value="cancel",
            )
        )

    def update_button_state(self):
        app = TABULA.get()
        for index, length_button in enumerate(self.length_buttons):
            render_needed = length_button.update_state(ButtonState.SELECTED if self.selected_index == index else ButtonState.NORMAL)
            if render_needed:
                app.hardware.display_rendered(length_button.render())
        for action_button in self.action_buttons:
            if action_button.needs_render():
                app.hardware.display_rendered(action_button.render())

    def render_sprint_time_info(self):
        if self.sprint_length is None:
            return
        app = TABULA.get()

        end_time = self.sprint_end.strftime("%H:%M")
        time_info = f"{format_duration(self.sprint_length)} sprint\nWill end at {end_time}"

        with Cairo(Size(width=self.screen_size.width - 100, height=200)) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            Label.create(
                pango=self.pango, width=cairo.size.width, font=f"{SERIF} 12", text=time_info, location=Point.zeroes()
            ).paste_onto_cairo(cairo)
            rendered = cairo.get_rendered(origin=Point(x=50, y=100))
        app.hardware.display_rendered(rendered)

    def render_screen(self):
        app = TABULA.get()
        app.hardware.clear_screen()
        self.make_buttons()
        for button in self.length_buttons + self.action_buttons:
            app.hardware.display_rendered(button.render())
        self.render_sprint_time_info()

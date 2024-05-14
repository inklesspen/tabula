import collections
import collections.abc
import typing

import trio

from ..device.hwtypes import (
    AnnotatedKeyEvent,
    TapEvent,
    TapPhase,
    Key,
    KeyboardDisconnect,
)
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import Rendered, CairoColor
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from .widgets import ButtonState, Button

from .base import (
    ChangeScreen,
    ScreenStackBehavior,
    Close,
    RetVal,
    Screen,
    TargetScreen,
)
from ..durations import format_duration
from ..util import now

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..commontypes import ScreenInfo
    from ..editor.document import DocumentModel


class SprintControl(Screen):
    def __init__(
        self,
        *,
        settings: "Settings",
        hardware: "Hardware",
        screen_info: "ScreenInfo",
        document: "DocumentModel",
    ):
        self.settings = settings
        self.hardware = hardware
        self.pango = Pango(dpi=screen_info.dpi)
        self.screen_size = screen_info.size
        self.document = document
        self.lengths = self.settings.sprint_lengths
        self.selected_index = None

    @property
    def sprint_length(self):
        if self.document.has_sprint:
            pass  # TODO: need to be able to actually get at the sprint
        else:
            if self.selected_index is None:
                return None
            length = self.lengths[self.selected_index]
            return length

    @property
    def sprint_end(self):
        if self.document.has_sprint:
            pass  # TODO: need to be able to actually get at the sprint
        else:
            length = self.sprint_length
            if length is not None:
                return now() + length

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.hardware.reset_keystream(enable_composes=False)
        screen = self.render()
        await self.hardware.display_rendered(screen)
        while True:
            event = await event_channel.receive()
            match event:
                case AnnotatedKeyEvent():
                    if event.key is Key.KEY_ESC:
                        return Close()
                case KeyboardDisconnect():
                    return ChangeScreen(
                        TargetScreen.KeyboardDetect,
                        screen_stack_behavior=ScreenStackBehavior.APPEND,
                    )

    def make_buttons(self):
        button_size = Size(width=80, height=80)
        self.length_buttons = []
        between = 50
        button_x = 106
        for index, sprint_length in enumerate(self.lengths):
            button_origin = Point(x=button_x, y=650)
            button = Button(
                self.pango,
                format_duration(sprint_length),
                button_size,
                corner_radius=25,
                font="B612 8",
                screen_location=button_origin,
                button_value=index,
                state=ButtonState.SELECTED
                if self.selected_index == index
                else ButtonState.NORMAL,
            )
            button_x += button_size.width + between
            self.length_buttons.append(button)

        button_size = Size(width=400, height=100)
        button_x = (self.screen_size.width - button_size.width) // 2
        self.action_buttons = []
        if self.document.has_sprint:
            self.action_buttons.append(
                Button(
                    self.pango,
                    button_text="End Sprint",
                    button_size=button_size,
                    corner_radius=50,
                    font="B612 8",
                    screen_location=Point(x=button_x, y=800),
                    button_value="end",
                )
            )
        else:
            self.action_buttons.append(
                Button(
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
                Button(
                    self.pango,
                    button_text="Cancel",
                    button_size=button_size,
                    corner_radius=50,
                    font="B612 8",
                    screen_location=Point(x=button_x, y=950),
                    button_value="cancel",
                )
            )

    async def update_button_state(self):
        for length_button in self.length_buttons:
            render_needed = length_button.update_state(
                ButtonState.SELECTED
                if self.selected_index == length_button.button_value
                else ButtonState.NORMAL
            )
            if render_needed:
                await self.hardware.display_rendered(length_button.render())
        for action_button in self.action_buttons:
            if action_button.needs_render():
                await self.hardware.display_rendered(action_button.render())

    async def render_sample(self):
        sample_size = Size(width=900, height=400)
        with Cairo(sample_size) as smaller_cairo:
            smaller_cairo.fill_with_color(CairoColor.WHITE)

            text_cairo = smaller_cairo.with_border(2, CairoColor.BLACK)
            text_width = text_cairo.size.width - 4

            with PangoLayout(pango=self.pango, width=text_width) as layout:
                layout.set_font(self.current_font)
                layout.set_content(self.samples[0], is_markup=True)
                text_cairo.move_to(Point(x=2, y=2))
                text_cairo.set_draw_color(CairoColor.BLACK)
                layout.set_line_spacing(self.line_spacing)
                layout.render(text_cairo)

            smaller_x = (self.screen_size.width - smaller_cairo.size.width) // 2
            rendered = Rendered(
                image=smaller_cairo.get_image_bytes(),
                extent=Rect(origin=Point(x=smaller_x, y=100), spread=sample_size),
            )
        await self.hardware.display_rendered(rendered)

    async def render_screen(self):
        await self.hardware.clear_screen()
        self.make_buttons()
        await self.render_sample()
        for button in self.length_buttons + self.action_buttons:
            await self.hardware.display_rendered(button.render())

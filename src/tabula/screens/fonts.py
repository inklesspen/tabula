from __future__ import annotations

import collections
import collections.abc
import dataclasses
import logging
import typing

from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, TapPhase, Key
from ..commontypes import Point, Size
from ..rendering.rendertypes import CairoColor
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from .widgets import ButtonState, Button, make_button_row
from ..util import TABULA

from .base import Screen, TargetScreen

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..commontypes import ScreenInfo
    from numbers import Number

logger = logging.getLogger(__name__)

PANGRAM = "Sphinx of black quartz, judge my vow.\nSPHINX OF BLACK QUARTZ, JUDGE MY VOW.\nsphinx of black quartz, judge my vow."
MOBY = """Call me Ishmael. Some years ago⁠—never mind how long precisely⁠—having little or no money in my purse, and nothing particular to interest me on shore, I thought I would sail about a little and see the watery part of the world. It is a way I have of driving off the spleen and regulating the circulation. Whenever I find myself growing grim about the mouth; whenever it is a damp, drizzly November in my soul; whenever I find myself involuntarily pausing before coffin warehouses, and bringing up the rear of every funeral I meet; and especially whenever my hypos get such an upper hand of me, that it requires a strong moral principle to prevent me from deliberately stepping into the street, and methodically knocking people’s hats off⁠—then, I account it high time to get to sea as soon as I can. This is my substitute for pistol and ball. With a philosophical flourish Cato throws himself upon his sword; I quietly take to the ship. There is nothing surprising in this. If they but knew it, almost all men in their degree, some time or other, cherish very nearly the same feelings towards the ocean with me."""  # noqa: E501
HUCK_FINN = """You don’t know about me without you have read a book by the name of <i>_The Adventures of Tom Sawyer_</i>; but that ain’t no matter. That book was made by Mr. Mark Twain, and he told the truth, mainly. There was things which he stretched, but mainly he told the truth. That is nothing. I never seen anybody but lied one time or another, without it was Aunt Polly, or the widow, or maybe Mary. Aunt Polly⁠—Tom’s Aunt Polly, she is⁠—and Mary, and the Widow Douglas is all told about in that book, which is mostly a true book, with some stretchers, as I said before."""  # noqa: E501
TI = """Squire Trelawney, Doctor Livesey, and the rest of these gentlemen having asked me to write down the whole particulars about Treasure Island, from the beginning to the end, keeping nothing back but the bearings of the island, and that only because there is still treasure not yet lifted, I take up my pen in the year of grace 17⁠—, and go back to the time when my father kept the Admiral Benbow Inn, and the brown old seaman, with the saber cut, first took up his lodging under our roof."""  # noqa: E501
DRACULA = """<i>_3 May. Bistritz._</i>⁠—Left Munich at 8:35 p.m., on 1st May, arriving at Vienna early next morning; should have arrived at 6:46, but train was an hour late. Buda-Pesth seems a wonderful place, from the glimpse which I got of it from the train and the little I could walk through the streets. I feared to go very far from the station, as we had arrived late and would start as near the correct time as possible. The impression I had was that we were leaving the West and entering the East; the most western of splendid bridges over the Danube, which is here of noble width and depth, took us among the traditions of Turkish rule."""  # noqa: E501

CONFIRM_GLYPH = "\u2713"
ABORT_GLYPH = "\u2169"
NEXT_SAMPLE_GLYPH = "\ue0b2"

DEFAULT_FONT = "Tabula Quattro"
DEFAULT_ASCENT_SIZE = 36
DEFAULT_LINE_SPACING = 1.0


@dataclasses.dataclass
class DrawLineSpacing:
    ascent: Number
    line_height: Number

    def __call__(self, button_cairo: Cairo):
        current_point = button_cairo.current_point
        assert current_point is not None
        baseline = current_point.y + self.ascent
        button_cairo.move_to(Point(x=current_point.x + 20, y=baseline))
        button_cairo.line_to(Point(x=current_point.x + 60, y=baseline))
        button_cairo.draw_path()
        button_cairo.move_to(Point(x=current_point.x + 20, y=baseline - self.line_height))
        button_cairo.line_to(Point(x=current_point.x + 60, y=baseline - self.line_height))
        button_cairo.draw_path()


class Fonts(Screen):
    size_buttons: list[Button]
    font_buttons: list[Button]
    action_buttons: list[Button]

    def __init__(
        self,
        *,
        settings: Settings,
        hardware: Hardware,
        screen_info: ScreenInfo,
    ):
        self.settings = settings
        self.hardware = hardware
        self.pango = Pango(dpi=screen_info.dpi)
        self.drafting_fonts = self.pango.list_drafting_fonts()
        if self.settings.current_font in self.drafting_fonts:
            self.current_font = self.settings.current_font
            self.current_font_size = self.settings.current_font_size
            self.current_line_spacing = self.settings.current_line_spacing
        else:
            self.current_font = DEFAULT_FONT
            self.current_font_size = self.pango.find_size_for_desired_ascent(DEFAULT_FONT, DEFAULT_ASCENT_SIZE)
            self.current_line_spacing = DEFAULT_LINE_SPACING

        self.current_font_ascent = self.pango.calculate_ascent(self.sized_font)
        self.screen_size = screen_info.size
        self.samples = collections.deque([PANGRAM, MOBY, HUCK_FINN, TI, DRACULA])

    @property
    def sized_font(self):
        return f"{self.current_font} {self.current_font_size}"

    async def become_responder(self):
        app = TABULA.get()
        app.hardware.reset_keystream(enable_composes=False)
        await self.render_screen()

    async def handle_key_event(self, event: AnnotatedKeyEvent):
        app = TABULA.get()
        if event.key is Key.KEY_ESC:
            return await app.change_screen(TargetScreen.SystemMenu)

    async def handle_tap_event(self, event: TapEvent):
        app = TABULA.get()
        font_changed = False
        if event.phase is TapPhase.COMPLETED:
            for button in self.font_buttons:
                if event.location in button:
                    self.current_font = button.button_value
                    self.current_font_size = self.pango.find_size_for_desired_ascent(self.current_font, self.current_font_ascent)
                    self.current_line_spacing = DEFAULT_LINE_SPACING
                    font_changed = True
            for button in self.action_buttons:
                if event.location in button:
                    app.hardware.display_rendered(button.render(override_state=ButtonState.PRESSED))
                    match button.button_value:
                        case "size_smaller":
                            self.current_font_ascent = max(10, self.current_font_ascent - 2)
                            self.current_font_size = self.pango.find_size_for_desired_ascent(self.current_font, self.current_font_ascent)
                            font_changed = True
                        case "size_larger":
                            self.current_font_ascent = min(60, self.current_font_ascent + 2)
                            self.current_font_size = self.pango.find_size_for_desired_ascent(self.current_font, self.current_font_ascent)
                            font_changed = True
                        case "decrease_line_spacing":
                            self.current_line_spacing -= 0.1
                            font_changed = True
                        case "increase_line_spacing":
                            self.current_line_spacing += 0.1
                            font_changed = True
                        case "confirm":
                            self.settings.set_current_font(self.current_font, self.current_font_size)
                            return await app.change_screen(TargetScreen.SystemMenu)
                        case "abort":
                            return await app.change_screen(TargetScreen.SystemMenu)
                        case "next_sample":
                            self.samples.rotate(-1)
                            font_changed = True
            await self.update_button_state()
            if font_changed:
                await self.render_sample()

    def make_buttons(self):
        ascent = self.pango.calculate_ascent("B612 8")
        line_height = self.pango.calculate_line_height("B612 8")
        smaller_line_height = ascent
        larger_line_height = line_height

        font_size_buttons = make_button_row(
            (
                {"button_text": "A", "font": "B612 6", "button_value": "size_smaller"},
                {"button_text": "A", "font": "B612 10", "button_value": "size_larger"},
            ),
            (
                {
                    "button_text": "A",
                    "button_value": "decrease_line_spacing",
                    "draw_callback": DrawLineSpacing(ascent, smaller_line_height),
                },
                {"button_text": "A", "button_value": "increase_line_spacing", "draw_callback": DrawLineSpacing(ascent, larger_line_height)},
            ),
            button_size=Size(width=80, height=80),
            corner_radius=25,
            button_y=650,
            row_width=self.screen_size.width,
            pango=self.pango,
            default_font="B612 8",
        )

        button_size = Size(width=400, height=100)
        button_x = (self.screen_size.width - button_size.width) // 2
        button_y = 800
        between = 50
        self.font_buttons = []
        for font in self.drafting_fonts:
            button_font_size = self.pango.find_size_for_desired_ascent(font, DEFAULT_ASCENT_SIZE)
            font_str = f"{font} {button_font_size}"
            button_origin = Point(x=button_x, y=button_y)
            button = Button.create(
                self.pango,
                button_text=font,
                button_size=button_size,
                corner_radius=50,
                font=font_str,
                screen_location=button_origin,
                state=ButtonState.SELECTED if self.current_font == font else ButtonState.NORMAL,
            )
            button_y += button_size.height + between
            self.font_buttons.append(button)
        button_size = Size(width=100, height=100)
        action_button_font = "B612 Mono 8"
        self.action_buttons = font_size_buttons + [
            Button.create(
                self.pango,
                button_text=CONFIRM_GLYPH,
                button_size=button_size,
                corner_radius=50,
                font=action_button_font,
                button_value="confirm",
                screen_location=Point(x=800, y=1200),
            ),
            Button.create(
                self.pango,
                button_text=ABORT_GLYPH,
                button_size=button_size,
                corner_radius=50,
                font=action_button_font,
                button_value="abort",
                screen_location=Point(x=200, y=1200),
            ),
            Button.create(
                self.pango,
                button_text=NEXT_SAMPLE_GLYPH,
                button_size=button_size,
                corner_radius=50,
                font=action_button_font,
                button_value="next_sample",
                screen_location=Point(x=800, y=800),
            ),
        ]

    async def update_button_state(self):
        app = TABULA.get()
        for font_button in self.font_buttons:
            render_needed = font_button.update_state(
                ButtonState.SELECTED if self.current_font == font_button.button_value else ButtonState.NORMAL
            )
            if render_needed:
                app.hardware.display_rendered(font_button.render())
        for action_button in self.action_buttons:
            if action_button.needs_render():
                app.hardware.display_rendered(action_button.render())

    async def render_sample(self):
        sample_size = Size(width=900, height=400)
        with Cairo(sample_size) as smaller_cairo:
            smaller_cairo.fill_with_color(CairoColor.WHITE)

            text_cairo = smaller_cairo.with_border(2, CairoColor.BLACK)
            text_width = text_cairo.size.width - 4

            with PangoLayout(pango=self.pango, width=text_width) as layout:
                layout.set_font(self.sized_font)
                layout.set_content(self.samples[0], is_markup=True)
                text_cairo.move_to(Point(x=2, y=2))
                text_cairo.set_draw_color(CairoColor.BLACK)
                layout.set_line_spacing(self.current_line_spacing)
                layout.render(text_cairo)

            smaller_x = (self.screen_size.width - smaller_cairo.size.width) // 2
            rendered = smaller_cairo.get_rendered(origin=Point(x=smaller_x, y=100))
        app = TABULA.get()
        app.hardware.display_rendered(rendered)

    async def render_screen(self):
        app = TABULA.get()
        app.hardware.clear_screen()
        self.make_buttons()
        await self.render_sample()
        for button in self.font_buttons + self.action_buttons:
            app.hardware.display_rendered(button.render())

import collections
import collections.abc
import typing

from ..device.hwtypes import AnnotatedKeyEvent, TapEvent, TapPhase, Key
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import Rendered, CairoColor
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from .widgets import ButtonState, Button
from ..util import TABULA

from .base import Screen, TargetScreen

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..commontypes import ScreenInfo


PANGRAM = "Sphinx of black quartz, judge my vow.\nSPHINX OF BLACK QUARTZ, JUDGE MY VOW.\nsphinx of black quartz, judge my vow."
MOBY = """Call me Ishmael. Some years ago⁠—never mind how long precisely⁠—having little or no money in my purse, and nothing particular to interest me on shore, I thought I would sail about a little and see the watery part of the world. It is a way I have of driving off the spleen and regulating the circulation. Whenever I find myself growing grim about the mouth; whenever it is a damp, drizzly November in my soul; whenever I find myself involuntarily pausing before coffin warehouses, and bringing up the rear of every funeral I meet; and especially whenever my hypos get such an upper hand of me, that it requires a strong moral principle to prevent me from deliberately stepping into the street, and methodically knocking people’s hats off⁠—then, I account it high time to get to sea as soon as I can. This is my substitute for pistol and ball. With a philosophical flourish Cato throws himself upon his sword; I quietly take to the ship. There is nothing surprising in this. If they but knew it, almost all men in their degree, some time or other, cherish very nearly the same feelings towards the ocean with me."""  # noqa: E501
HUCK_FINN = """You don’t know about me without you have read a book by the name of <i>_The Adventures of Tom Sawyer_</i>; but that ain’t no matter. That book was made by Mr. Mark Twain, and he told the truth, mainly. There was things which he stretched, but mainly he told the truth. That is nothing. I never seen anybody but lied one time or another, without it was Aunt Polly, or the widow, or maybe Mary. Aunt Polly⁠—Tom’s Aunt Polly, she is⁠—and Mary, and the Widow Douglas is all told about in that book, which is mostly a true book, with some stretchers, as I said before."""  # noqa: E501
TI = """Squire Trelawney, Doctor Livesey, and the rest of these gentlemen having asked me to write down the whole particulars about Treasure Island, from the beginning to the end, keeping nothing back but the bearings of the island, and that only because there is still treasure not yet lifted, I take up my pen in the year of grace 17⁠—, and go back to the time when my father kept the Admiral Benbow Inn, and the brown old seaman, with the saber cut, first took up his lodging under our roof."""  # noqa: E501
DRACULA = """<i>_3 May. Bistritz._</i>⁠—Left Munich at 8:35 p.m., on 1st May, arriving at Vienna early next morning; should have arrived at 6:46, but train was an hour late. Buda-Pesth seems a wonderful place, from the glimpse which I got of it from the train and the little I could walk through the streets. I feared to go very far from the station, as we had arrived late and would start as near the correct time as possible. The impression I had was that we were leaving the West and entering the East; the most western of splendid bridges over the Danube, which is here of noble width and depth, took us among the traditions of Turkish rule."""  # noqa: E501

CONFIRM_GLYPH = "\u2713"
ABORT_GLYPH = "\u2169"
NEXT_SAMPLE_GLYPH = "\ue0b2"


class Fonts(Screen):
    size_buttons: list[Button]
    font_buttons: list[Button]
    action_buttons: list[Button]

    def __init__(
        self,
        *,
        settings: "Settings",
        hardware: "Hardware",
        screen_info: "ScreenInfo",
    ):
        self.settings = settings
        self.hardware = hardware
        self.current_face = self.settings.current_font
        self.sizes = self.settings.drafting_fonts[self.current_face]
        self.selected_index = self.settings.current_font_size
        self.font_button_index = 2
        self.pango = Pango(dpi=screen_info.dpi)
        self.screen_size = screen_info.size
        # TODO: get line spacing from settings
        self.line_spacing = 1.0
        self.samples = collections.deque([PANGRAM, MOBY, HUCK_FINN, TI, DRACULA])

    @property
    def current_font(self):
        return " ".join([self.current_face, self.sizes[self.selected_index]])

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
            for button in self.size_buttons:
                if event.location in button:
                    self.selected_index = button.button_value
                    font_changed = True
            for button in self.font_buttons:
                if event.location in button:
                    self.current_face = button.button_value
                    self.sizes = self.settings.drafting_fonts[self.current_face]
                    font_changed = True
            for button in self.action_buttons:
                if event.location in button:
                    app.hardware.display_rendered(button.render(override_state=ButtonState.PRESSED))
                    match button.button_value:
                        case "confirm":
                            self.settings.set_current_font(self.current_face, self.selected_index)
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
        button_size = Size(width=80, height=80)
        self.size_buttons = []
        between = 50
        button_x = 106
        for index, font_size in enumerate(self.sizes):
            button_origin = Point(x=button_x, y=650)
            button = Button(
                self.pango,
                "A",
                button_size,
                corner_radius=25,
                font=f"{self.current_face} {font_size}",
                screen_location=button_origin,
                button_value=index,
                state=ButtonState.SELECTED if self.selected_index == index else ButtonState.NORMAL,
            )
            button_x += button_size.width + between
            self.size_buttons.append(button)
        button_size = Size(width=400, height=100)
        button_x = (self.screen_size.width - button_size.width) // 2
        button_y = 800
        self.font_buttons = []
        for font, font_sizes in self.settings.drafting_fonts.items():
            font_str = f"{font} {font_sizes[self.font_button_index]}"
            button_origin = Point(x=button_x, y=button_y)
            button = Button(
                self.pango,
                button_text=font,
                button_size=button_size,
                corner_radius=50,
                font=font_str,
                screen_location=button_origin,
                state=ButtonState.SELECTED if self.current_face == font else ButtonState.NORMAL,
            )
            button_y += button_size.height + between
            self.font_buttons.append(button)
        button_size = Size(width=100, height=100)
        action_button_font = "B612 Mono 8"
        self.action_buttons = [
            Button(
                self.pango,
                button_text=CONFIRM_GLYPH,
                button_size=button_size,
                corner_radius=50,
                font=action_button_font,
                button_value="confirm",
                screen_location=Point(x=800, y=1200),
            ),
            Button(
                self.pango,
                button_text=ABORT_GLYPH,
                button_size=button_size,
                corner_radius=50,
                font=action_button_font,
                button_value="abort",
                screen_location=Point(x=200, y=1200),
            ),
            Button(
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
        for size_button in self.size_buttons:
            render_needed = size_button.update_state(
                ButtonState.SELECTED if self.selected_index == size_button.button_value else ButtonState.NORMAL
            )
            if render_needed:
                app.hardware.display_rendered(size_button.render())
        for font_button in self.font_buttons:
            render_needed = font_button.update_state(
                ButtonState.SELECTED if self.current_face == font_button.button_value else ButtonState.NORMAL
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
        app = TABULA.get()
        app.hardware.display_rendered(rendered)

    async def render_screen(self):
        app = TABULA.get()
        app.hardware.clear_screen()
        self.make_buttons()
        await self.render_sample()
        for button in self.size_buttons + self.font_buttons + self.action_buttons:
            app.hardware.display_rendered(button.render())

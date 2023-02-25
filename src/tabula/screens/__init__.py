import abc
import collections
import collections.abc
import functools
import math
import typing

import msgspec
import trio

from ..device.hwtypes import (
    AnnotatedKeyEvent,
    TapEvent,
    TapPhase,
    Key,
    KeyboardDisconnect,
)
from ..commontypes import Point, Size, Rect
from ..rendering.rendertypes import Rendered, Alignment, WrapMode, CairoColor
from ..editor.document import DocumentModel
from ..editor.doctypes import Session
from ..util import checkpoint, now, humanized_delta, TickCaller, maybe_int
from ..rendering.layout import LayoutManager, StatusLayout
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from .widgets import ButtonState, Button

from .numbers import NUMBER_KEYS, B612_CIRCLED_DIGITS
from .base import Switch, Modal, Close, Shutdown, DialogResult, RetVal, Screen
from .keyboard_detect import KeyboardDetect
from .dialogs import OkDialog, YesNoDialog

if typing.TYPE_CHECKING:
    from ..device.hardware import Hardware
    from ..settings import Settings
    from ..rendering.renderer import Renderer
    from ..db import TabulaDb
    import pathlib


class Drafting(Screen):
    status_font = "Crimson Pro 12"

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
        db: "TabulaDb",
        document: "DocumentModel",
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.db = db
        self.document = document
        self.layout_manager = LayoutManager(self.renderer, self.document)
        self.status_layout = StatusLayout(self.renderer, self.document)

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.hardware.reset_keystream(enable_composes=True)
        await self.hardware.clear_screen()
        await self.render_document()
        await self.render_status()

        async with TickCaller(15, self.tick):
            while True:
                event = await event_channel.receive()
                match event:
                    case AnnotatedKeyEvent():
                        if event.is_led_able:
                            self.status_layout.set_leds(
                                capslock=event.annotation.capslock,
                                compose=event.annotation.compose,
                            )
                        if self.document.graphical_char(event.character):
                            self.document.keystroke(event.character)
                            await self.render_document()
                        elif event.key is Key.KEY_ENTER:
                            self.document.new_para()
                            await self.render_document()
                            self.document.save_session(self.db)
                        elif event.key is Key.KEY_BACKSPACE:
                            self.document.backspace()
                            await self.render_document()
                        elif event.key is Key.KEY_F1:
                            return Modal(Help)
                        elif event.key is Key.KEY_F12:
                            if self.document.wordcount == 0:
                                self.document.delete_session(self.db)
                            else:
                                self.document.save_session(self.db)
                            return Switch(SystemMenu)
                        await self.render_status()
                    case KeyboardDisconnect():
                        self.document.save_session(self.db)
                        print("Time to detect keyboard again.")
                        return Modal(KeyboardDetect)

    async def tick(self):
        self.document.save_session(self.db)
        await self.render_status()

    async def render_status(self):
        await self.hardware.display_rendered(self.status_layout.render())

    async def render_document(self):
        current_font = self.settings.current_font
        font_size = self.settings.drafting_fonts[current_font][
            self.settings.current_font_size
        ]
        font_spec = f"{current_font} {font_size}"
        rendered = self.layout_manager.render_update(font_spec)
        await self.hardware.display_rendered(rendered)


def export_session(
    session_document: DocumentModel, db: "TabulaDb", export_path: "pathlib.Path"
):
    # TODO: maybe move this to a method on the db class
    export_path.mkdir(parents=True, exist_ok=True)
    timestamp = now()
    session_id = session_document.session_id
    export_filename = (
        f"{session_id} - {timestamp} - {session_document.wordcount} words.md"
    )
    export_file = export_path / export_filename
    with export_file.open(mode="w", encoding="utf-8") as out:
        out.write(session_document.export_markdown())
    db.set_exported_time(session_id, timestamp)


class MenuButton(msgspec.Struct):
    handler: collections.abc.Callable[
        [], collections.abc.Awaitable[typing.Optional[RetVal]]
    ]
    rect: Rect
    text: str
    font: str = "B612 8"
    markup: bool = False
    key: typing.Optional[Key] = None
    inverted: bool = False


class MenuText(msgspec.Struct):
    text: str
    y_top: int
    font: str
    markup: bool = False


MenuItem = MenuButton | MenuText


class ButtonMenu(Screen):
    # Buttons are 400 px wide, 100 px high
    # Spread them as equally as possible along the screen height.
    button_size = Size(width=600, height=100)

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )

    async def run(self, event_channel: trio.abc.ReceiveChannel):
        self.hardware.reset_keystream(enable_composes=False)
        await self.render()
        while True:
            event = await event_channel.receive()
            handler = None
            match event:
                case AnnotatedKeyEvent():
                    for button in self.buttons:
                        if event.key == button.key:
                            handler = button.handler
                # TODO: have a TapInitiated event, and use it to render
                # the tapped button inverse.
                case TapEvent():
                    print(event)
                    if event.phase is TapPhase.COMPLETED:
                        for button in self.buttons:
                            if event.location in button.rect:
                                handler = button.handler
                case KeyboardDisconnect():
                    print("Time to detect keyboard again.")
                    return Modal(KeyboardDetect)
            if handler is not None:
                result = await handler(event_channel)
                if result is not None:
                    return result
                await self.render()

    async def render(self):
        self.menu = tuple(self.define_menu())
        self.buttons = tuple(b for b in self.menu if isinstance(b, MenuButton))
        screen = self.make_screen()
        await self.hardware.display_pixels(screen.image, screen.extent)

    def make_screen(self):
        screen_size = self.renderer.screen_info.size
        x_center = math.floor(screen_size.width / 2)
        with self.renderer.create_surface(
            screen_size
        ) as surface, self.renderer.create_cairo_context(surface) as cairo_context:
            self.renderer.prepare_background(cairo_context)
            self.renderer.setup_drawing(cairo_context)
            for menuitem in self.menu:
                if isinstance(menuitem, MenuButton):
                    # TODO: support inverted
                    self.renderer.button(
                        cairo_context,
                        text=menuitem.text,
                        font=menuitem.font,
                        rect=menuitem.rect,
                        markup=menuitem.markup,
                    )
                if isinstance(menuitem, MenuText):
                    center_top = Point(x=0, y=menuitem.y_top)
                    self.renderer.move_to(cairo_context, center_top)
                    self.renderer.simple_render(
                        cairo_context,
                        menuitem.font,
                        menuitem.text,
                        markup=menuitem.markup,
                        alignment=Alignment.CENTER,
                        width=screen_size.width,
                        single_par=False,
                    )
            buf = self.renderer.surface_to_bytes(surface, screen_size)
        return Rendered(
            image=buf, extent=Rect(origin=Point.zeroes(), spread=screen_size)
        )

    @abc.abstractmethod
    def define_menu(self) -> collections.abc.Iterable[MenuItem]:
        ...


class SystemMenu(ButtonMenu):
    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
        db: "TabulaDb",
        document: "DocumentModel",
    ):
        super().__init__(settings=settings, renderer=renderer, hardware=hardware)
        self.db = db
        self.document = document

    def define_menu(self):

        buttons = [
            {
                "handler": self.new_session,
                "number": 1,
                "title": "New Session",
            },
            {
                "handler": self.previous_session,
                "number": 2,
                "title": "Previous Session",
            },
        ]
        next_number = 3
        if self.document.has_session:
            buttons.append(
                {
                    "handler": self.export_current_session,
                    "number": next_number,
                    "title": "Export Current Session",
                }
            )
            next_number += 1
        buttons.append(
            {
                "handler": self.set_font,
                "number": next_number,
                "title": "Fonts",
            }
        )
        next_number += 1
        if self.document.has_session:
            buttons.append(
                {
                    "handler": self.resume_drafting,
                    "number": 9,
                    "title": "Resume Drafting",
                }
            )
        buttons.append(
            {
                "handler": self.shutdown,
                "number": 0,
                "title": "Shutdown",
            }
        )

        screen_size = self.renderer.screen_info.size
        button_x = math.floor((screen_size.width - self.button_size.width) / 2)
        button_total_height = self.button_size.height * len(buttons)
        whitespace_height = screen_size.height - button_total_height
        skip_height = math.floor(whitespace_height / (len(buttons) + 1))
        button_y = skip_height

        for button in buttons:
            button_rect = Rect(
                origin=Point(x=button_x, y=button_y), spread=self.button_size
            )
            button["rect"] = button_rect
            button_y += self.button_size.height + skip_height

        return tuple(
            MenuButton(
                handler=b["handler"],
                key=NUMBER_KEYS[b["number"]],
                text=f"{B612_CIRCLED_DIGITS[b['number']]} — {b['title']}",
                rect=b["rect"],
            )
            for b in buttons
        )

    async def new_session(self, event_channel: trio.abc.ReceiveChannel):
        session_id = self.db.new_session()
        self.document.load_session(session_id, self.db)
        await checkpoint()
        return Switch(Drafting)

    async def previous_session(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Switch(SessionList)

    async def export_current_session(self, event_channel: trio.abc.ReceiveChannel):
        export_session(self.document, self.db, self.settings.export_path)
        dialog = OkDialog(
            renderer=self.renderer, hardware=self.hardware, message="Export complete!"
        )
        result = await dialog.run(event_channel)
        if not isinstance(result, DialogResult):
            return result

    async def set_font(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Switch(Fonts)

    async def resume_drafting(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Switch(Drafting)

    async def shutdown(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Shutdown()


class SessionList(ButtonMenu):
    session_button_size = Size(width=800, height=100)
    page_button_size = Size(width=200, height=100)

    def __init__(
        self,
        *,
        settings: "Settings",
        renderer: "Renderer",
        hardware: "Hardware",
        db: "TabulaDb",
        document: "DocumentModel",
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.db = db
        self.document = document
        self.offset = 0
        self.selected_session = None

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.sessions = self.db.list_sessions()
        return await super().run(event_channel)

    def define_menu(self):
        if self.selected_session is None:
            return self.define_buttons_session_list()
        timestamp = now()
        edit_cutoff = timestamp - self.settings.max_editable_age
        screen_size = self.renderer.screen_info.size
        button_x = math.floor((screen_size.width - self.button_size.width) / 2)
        session_delta = self.selected_session.updated_at - timestamp
        header_text = f"Last edited {humanized_delta(session_delta)}\nWordcount: {self.selected_session.wordcount}"
        menuitems = [MenuText(text=header_text, y_top=10, font="Crimson Pro 12")]
        if self.selected_session.updated_at >= edit_cutoff:
            menuitems.append(
                MenuButton(
                    handler=self.load_session,
                    rect=Rect(origin=Point(x=button_x, y=150), spread=self.button_size),
                    text="Load Session",
                )
            )
        else:
            menuitems.append(
                MenuText(
                    text="This session is now locked for editing",
                    y_top=150,
                    font="B612 8",
                )
            )
        if self.selected_session.needs_export:
            menuitems.append(
                MenuButton(
                    handler=self.export_session,
                    rect=Rect(origin=Point(x=button_x, y=450), spread=self.button_size),
                    text="Export Session",
                )
            )
        menuitems.append(
            MenuButton(
                handler=self.delete_session,
                rect=Rect(origin=Point(x=button_x, y=650), spread=self.button_size),
                text="Delete Session",
            )
        )
        menuitems.append(
            MenuButton(
                handler=self.back_to_session_list,
                rect=Rect(origin=Point(x=button_x, y=850), spread=self.button_size),
                text="Back",
            )
        )
        return tuple(menuitems)

    def define_buttons_session_list(self) -> collections.abc.Iterable[MenuButton]:
        timestamp = now()
        screen_size = self.renderer.screen_info.size
        min_skip_height = math.floor(self.button_size.height * 0.75)
        usable_height = screen_size.height - (min_skip_height + self.button_size.height)
        num_session_buttons = usable_height // (
            min_skip_height + self.button_size.height
        )
        session_page = self.sessions[self.offset : self.offset + num_session_buttons]

        button_x = math.floor((screen_size.width - self.session_button_size.width) / 2)
        button_total_height = self.button_size.height * num_session_buttons
        whitespace_height = usable_height - button_total_height
        skip_height = math.floor(whitespace_height / (num_session_buttons + 1))
        button_y = skip_height

        menuitems = []
        for session in session_page:
            button_rect = Rect(
                origin=Point(x=button_x, y=button_y), spread=self.session_button_size
            )
            session_delta = session.updated_at - timestamp
            button_text = f"{humanized_delta(session_delta)} - {session.wordcount}"
            if session.needs_export:
                button_text += " \ue0a7"
            else:
                button_text += " \ue0a2"
            menuitems.append(
                MenuButton(
                    handler=functools.partial(self.select_session, session),
                    rect=button_rect,
                    text=button_text,
                )
            )
            button_y += self.button_size.height + skip_height

        if self.offset > 0:
            # back button
            prev_page_offset = max(0, self.offset - num_session_buttons)
            menuitems.append(
                MenuButton(
                    handler=functools.partial(self.change_page, prev_page_offset),
                    text="\ue0a9 Prev",
                    rect=Rect(
                        origin=Point(x=50, y=1300),
                        spread=self.page_button_size,
                    ),
                )
            )

        next_page_offset = self.offset + num_session_buttons
        if len(self.sessions[next_page_offset:]) > 0:
            # next button
            menuitems.append(
                MenuButton(
                    handler=functools.partial(self.change_page, next_page_offset),
                    text="Next \ue0a8",
                    rect=Rect(
                        origin=Point(
                            x=screen_size.width - (50 + self.page_button_size.width),
                            y=1300,
                        ),
                        spread=self.page_button_size,
                    ),
                )
            )

        # return button
        menuitems.append(
            MenuButton(
                handler=self.close_menu,
                text="Back",
                rect=Rect(
                    origin=Point(
                        x=math.floor(
                            (screen_size.width - self.page_button_size.width) / 2
                        ),
                        y=1300,
                    ),
                    spread=self.page_button_size,
                ),
            )
        )
        return tuple(menuitems)

    async def select_session(
        self, selected_session: Session, event_channel: trio.abc.ReceiveChannel
    ):
        self.selected_session = selected_session
        await checkpoint()
        return

    async def load_session(self, event_channel: trio.abc.ReceiveChannel):
        self.document.load_session(self.selected_session.id, self.db)
        await checkpoint()
        return Switch(Drafting)

    async def export_session(self, event_channel: trio.abc.ReceiveChannel):
        session_document = DocumentModel()
        session_document.load_session(self.selected_session.id, self.db)

        export_session(session_document, self.db, self.settings.export_path)
        self.selected_session = None
        dialog = OkDialog(
            renderer=self.renderer, hardware=self.hardware, message="Export complete!"
        )
        result = await dialog.run(event_channel)
        if not isinstance(result, DialogResult):
            return result
        return

    async def delete_session(self, event_channel: trio.abc.ReceiveChannel):
        dialog = YesNoDialog(
            renderer=self.renderer, hardware=self.hardware, message="Really delete?"
        )
        result = await dialog.run(event_channel)
        if not isinstance(result, DialogResult):
            return result
        if result.value:
            self.db.delete_session(self.selected_session.id)
            self.selected_session = None
        return

    async def back_to_session_list(self, event_channel: trio.abc.ReceiveChannel):
        self.selected_session = None
        await checkpoint()
        return

    async def change_page(
        self, new_offset: int, event_channel: trio.abc.ReceiveChannel
    ):
        self.offset = new_offset
        await checkpoint()
        return

    async def close_menu(self, event_channel: trio.abc.ReceiveChannel):
        await checkpoint()
        return Switch(SystemMenu)


PANGRAM = "Sphinx of black quartz, judge my vow.\nSPHINX OF BLACK QUARTZ, JUDGE MY VOW.\nsphinx of black quartz, judge my vow."
MOBY = """Call me Ishmael. Some years ago⁠—never mind how long precisely⁠—having little or no money in my purse, and nothing particular to interest me on shore, I thought I would sail about a little and see the watery part of the world. It is a way I have of driving off the spleen and regulating the circulation. Whenever I find myself growing grim about the mouth; whenever it is a damp, drizzly November in my soul; whenever I find myself involuntarily pausing before coffin warehouses, and bringing up the rear of every funeral I meet; and especially whenever my hypos get such an upper hand of me, that it requires a strong moral principle to prevent me from deliberately stepping into the street, and methodically knocking people’s hats off⁠—then, I account it high time to get to sea as soon as I can. This is my substitute for pistol and ball. With a philosophical flourish Cato throws himself upon his sword; I quietly take to the ship. There is nothing surprising in this. If they but knew it, almost all men in their degree, some time or other, cherish very nearly the same feelings towards the ocean with me."""
HUCK_FINN = """You don’t know about me without you have read a book by the name of <i>_The Adventures of Tom Sawyer_</i>; but that ain’t no matter. That book was made by Mr. Mark Twain, and he told the truth, mainly. There was things which he stretched, but mainly he told the truth. That is nothing. I never seen anybody but lied one time or another, without it was Aunt Polly, or the widow, or maybe Mary. Aunt Polly⁠—Tom’s Aunt Polly, she is⁠—and Mary, and the Widow Douglas is all told about in that book, which is mostly a true book, with some stretchers, as I said before."""
TI = """Squire Trelawney, Doctor Livesey, and the rest of these gentlemen having asked me to write down the whole particulars about Treasure Island, from the beginning to the end, keeping nothing back but the bearings of the island, and that only because there is still treasure not yet lifted, I take up my pen in the year of grace 17⁠—, and go back to the time when my father kept the Admiral Benbow Inn, and the brown old seaman, with the saber cut, first took up his lodging under our roof."""
DRACULA = """<i>_3 May. Bistritz._</i>⁠—Left Munich at 8:35 p.m., on 1st May, arriving at Vienna early next morning; should have arrived at 6:46, but train was an hour late. Buda-Pesth seems a wonderful place, from the glimpse which I got of it from the train and the little I could walk through the streets. I feared to go very far from the station, as we had arrived late and would start as near the correct time as possible. The impression I had was that we were leaving the West and entering the East; the most western of splendid bridges over the Danube, which is here of noble width and depth, took us among the traditions of Turkish rule."""

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
        renderer: "Renderer",
        hardware: "Hardware",
    ):
        super().__init__(
            settings=settings,
            renderer=renderer,
            hardware=hardware,
        )
        self.current_face = self.settings.current_font
        self.sizes = self.settings.drafting_fonts[self.current_face]
        self.selected_index = self.settings.current_font_size
        self.font_button_index = 2
        self.pango = Pango(dpi=renderer.screen_info.dpi)
        self.screen_size = self.renderer.screen_info.size
        # TODO: get line spacing from settings
        self.line_spacing = 1.0
        self.samples = collections.deque([PANGRAM, MOBY, HUCK_FINN, TI, DRACULA])

    @property
    def current_font(self):
        return " ".join([self.current_face, self.sizes[self.selected_index]])

    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        self.hardware.reset_keystream(enable_composes=False)
        await self.render_screen()
        while True:
            font_changed = False
            event = await event_channel.receive()
            match event:
                case KeyboardDisconnect():
                    print("Time to detect keyboard again.")
                    return Modal(KeyboardDetect)
                case AnnotatedKeyEvent():
                    if event.key is Key.KEY_ESC:
                        return Switch(SystemMenu)
                case TapEvent():
                    if event.phase is TapPhase.COMPLETED:
                        for button in self.size_buttons:
                            if event.location in button:
                                self.selected_index = button.button_value
                                font_changed = True
                        for button in self.font_buttons:
                            if event.location in button:
                                self.current_face = button.button_value
                                self.sizes = self.settings.drafting_fonts[
                                    self.current_face
                                ]
                                font_changed = True
                        for button in self.action_buttons:
                            if event.location in button:
                                await self.hardware.display_rendered(
                                    button.render(state=ButtonState.PRESSED)
                                )
                                match button.button_value:
                                    case "confirm":
                                        self.settings.set_current_font(
                                            self.current_face, self.selected_index
                                        )
                                        return Switch(SystemMenu)
                                    case "abort":
                                        return Switch(SystemMenu)
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
            )
            if self.selected_index == index:
                button.static_state = ButtonState.SELECTED
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
            )
            if self.current_face == font:
                button.static_state = ButtonState.SELECTED
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
        for size_button in self.size_buttons:
            render_needed = size_button.update_static_state(
                ButtonState.SELECTED
                if self.selected_index == size_button.button_value
                else ButtonState.NORMAL
            )
            if render_needed:
                await self.hardware.display_rendered(size_button.render())
        for font_button in self.font_buttons:
            render_needed = font_button.update_static_state(
                ButtonState.SELECTED
                if self.current_face == font_button.button_value
                else ButtonState.NORMAL
            )
            if render_needed:
                await self.hardware.display_rendered(font_button.render())
        for action_button in self.action_buttons:
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
        for button in self.size_buttons + self.font_buttons + self.action_buttons:
            await self.hardware.display_rendered(button.render())


class Help(Screen):
    async def run(self, event_channel: trio.abc.ReceiveChannel) -> RetVal:
        pass

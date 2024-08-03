from __future__ import annotations

import logging
import math
import typing

import msgspec

from ..commontypes import Point, Rect, Size
from ..durations import timer_display
from ..editor.wordcount import format_wordcount
from ..util import now
from ._cairopango import ffi, lib  # type: ignore  # noqa: F401
from .cairo import Cairo
from .fonts import SERIF
from .markup import CURSOR, escape_for_markup
from .pango import Pango, PangoLayout
from .rendertypes import Alignment, CairoColor, Rendered

if typing.TYPE_CHECKING:
    from ..commontypes import ScreenInfo
    from ..editor.document import DocumentModel

logger = logging.getLogger(__name__)


class RenderedMarkup(msgspec.Struct, frozen=True):
    markup: str
    cairo: Cairo


class Chunk(msgspec.Struct, frozen=True):
    index: int
    markup: str


class LaidOut(msgspec.Struct):
    rendered: RenderedMarkup
    y_top: int
    y_bottom: int

    def paste_onto_cairo(self, cairo: Cairo):
        cairo.paste_other(self.rendered.cairo, Point(x=0, y=self.y_top), Rect(origin=Point.zeroes(), spread=self.rendered.cairo.size))


class LayoutManager:
    rendered_markups: dict[str, RenderedMarkup]
    skip_height: int

    def __init__(
        self,
        screen_info: ScreenInfo,
        document: DocumentModel,
    ):
        self.screen_info = screen_info
        self.pango = Pango(dpi=screen_info.dpi)
        self.document = document
        self.render_width = self.screen_info.size.width
        self.cursor_y = self.screen_info.size.height // 2
        self.render_height = self.cursor_y
        self.layout = PangoLayout(pango=self.pango, width=self.render_width)
        self.rendered_markups = {}
        self.rendered_font = None
        self.rendered_line_spacing = None
        self.skip_height = 0
        self.render_size = Size(self.render_width, self.render_height)
        self.target_cairo = Cairo(self.render_size)
        self.target_cairo.setup()

    def set_font(self, font: str):
        if font != self.rendered_font:
            self.rendered_markups = {}
            self.skip_height = math.floor(self.pango.calculate_line_height(font))
            self.layout.set_font(font)
            self.rendered_font = font
        return self

    def set_line_spacing(self, factor: float):
        if factor != self.rendered_line_spacing:
            self.rendered_markups = {}
            self.layout.set_line_spacing(factor)
            self.rendered_line_spacing = factor
        return self

    def render_to_image_surface(self, markup: str):
        self.layout.set_content(markup, is_markup=True)
        markup_size = self.layout.get_layout_rects().logical.spread
        # don't use the context manager approach because we keep the surface around
        # alternatively, use cairo_surface_reference and a CairoRendered class (which needs to know its Size)
        markup_cairo = Cairo(markup_size)
        markup_cairo.setup()
        markup_cairo.fill_with_color(CairoColor.WHITE)
        markup_cairo.set_draw_color(CairoColor.BLACK)
        markup_cairo.move_to(Point.zeroes())
        self.layout.render(markup_cairo)
        rendered = RenderedMarkup(markup=markup, cairo=markup_cairo)
        self.rendered_markups[markup] = rendered

    def render_update(self, *, composing_chars: str):
        if composing_chars:
            at_end = f'<span underline="single">{escape_for_markup(composing_chars)}{CURSOR}</span>'
        else:
            at_end = CURSOR

        laidouts: list[LaidOut] = []
        used_rendereds = {}
        cursor_para_id = self.document.cursor_para_id
        current_y = self.cursor_y
        current_i = len(self.document) - 1
        while current_i >= 0 and current_y >= 0:
            para = self.document[current_i]
            markup = para.markup
            if cursor_para_id == para.id:
                markup += at_end
            if markup not in self.rendered_markups:
                self.render_to_image_surface(markup)
            rendered = self.rendered_markups[markup]
            used_rendereds[markup] = rendered
            rendered_height = rendered.cairo.size.height
            top = current_y - rendered_height
            laidouts.append(LaidOut(rendered=rendered, y_top=top, y_bottom=current_y))
            current_y -= rendered_height + self.skip_height
            current_i -= 1

        self.target_cairo.fill_with_color(CairoColor.WHITE)

        for laidout in laidouts:
            laidout.paste_onto_cairo(self.target_cairo)

        if CURSOR in self.rendered_markups:
            # Worth keeping around
            used_rendereds[CURSOR] = self.rendered_markups[CURSOR]
        self.rendered_markups = used_rendereds

        return self.target_cairo.get_rendered(origin=Point.zeroes())


def render_compose_symbol(cairo: Cairo, origin: Point, scale: float, linewidth: float):
    # scale 40 produces width=60, height=40; width is 1.5x scale
    lib.cairo_new_path(cairo.context)
    cairo.set_draw_color(CairoColor.BLACK)
    cairo.set_line_width(linewidth)
    lib.cairo_rectangle(
        cairo.context,
        origin.x + scale * 0.02,
        origin.y + scale * 0.02,
        scale * 0.75,
        scale * 0.96,
    )
    lib.cairo_stroke(cairo.context)
    lib.cairo_arc(
        cairo.context,
        origin.x + scale * 0.75,
        origin.y + scale * 0.5,
        scale * 0.48,
        math.radians(0),
        math.radians(360),
    )
    lib.cairo_stroke(cairo.context)
    return Rect(origin=origin, spread=Size(width=scale * 1.5, height=scale))


def render_capslock_symbol(cairo: Cairo, origin: Point, scale: float, linewidth: float):
    # scale 40 produces width=32, height=40; width is .8x scale
    lib.cairo_new_path(cairo.context)
    cairo.set_draw_color(CairoColor.BLACK)
    cairo.set_line_width(linewidth)
    cairo.move_to(origin + Point(scale * 0.26, scale * 0.73))
    cairo.line_to(origin + Point(scale * 0.26, scale * 0.355))
    cairo.line_to(origin + Point(scale * 0.07, scale * 0.355))
    cairo.line_to(origin + Point(scale * 0.415, scale * 0.015))
    cairo.line_to(origin + Point(scale * 0.76, scale * 0.355))
    cairo.line_to(origin + Point(scale * 0.57, scale * 0.355))
    cairo.line_to(origin + Point(scale * 0.57, scale * 0.73))
    lib.cairo_close_path(cairo.context)
    lib.cairo_stroke(cairo.context)
    lib.cairo_rectangle(
        cairo.context,
        origin.x + scale * 0.26,
        origin.y + scale * 0.82,
        scale * 0.31,
        scale * 0.18,
    )
    lib.cairo_stroke(cairo.context)
    return Rect(origin=origin, spread=Size(width=scale * 0.8, height=scale))


class StatusLayout:
    status_font = f"{SERIF} 12"

    def __init__(self, screen_info: ScreenInfo, document: DocumentModel):
        self.screen_info = screen_info
        self.pango = Pango(dpi=screen_info.dpi)
        self.document = document
        self.render_width = self.screen_info.size.width
        screen_size = self.screen_info.size
        self.status_y_bottom = screen_size.height - 50
        self.capslock = False
        self.compose = False

    def set_leds(self, capslock: bool, compose: bool):
        self.capslock = capslock
        self.compose = compose

    def render(self):
        status_lines = []
        inner_margin = 25
        # Line 1: Sprint status: timer, wordcount, hotkey reminder
        # Line 2: Session wordcount, current time
        # Line 3: capslock, "Tabula", compose
        # Line 3 is drawn separately to work with the glyphs
        if self.document.has_sprint:
            sprint_wordcount = self.document.sprint_wordcount
            sprint_line = " — ".join(
                (f"{format_wordcount(sprint_wordcount)} in sprint", f"Ends in {timer_display(self.document.sprint.remaining)}")
            )
            status_lines.append(sprint_line)

        wordcount_time_line = " — ".join((format_wordcount(self.document.wordcount), now().strftime("%H:%M")))
        status_lines.append(wordcount_time_line)
        status_line = "\n".join(status_lines)
        with PangoLayout(pango=self.pango, width=self.render_width, alignment=Alignment.CENTER) as layout:
            layout.set_font(self.status_font)
            layout.set_content(status_line)
            status_rects = layout.get_layout_rects()

            # TODO: Use a Label for this one.
            layout.set_content("Tabula")
            line_3_rects = layout.get_layout_rects()

            line_3_top = status_rects.logical.spread.height + inner_margin
            full_status_height = line_3_top + line_3_rects.logical.spread.height
            symbol_y_top = line_3_top + line_3_rects.ink.origin.y
            symbol_scale = line_3_rects.ink.spread.height

            status_y_top = self.status_y_bottom - full_status_height
            markup_size = Size(width=self.render_width, height=full_status_height)

            with Cairo(markup_size) as cairo:
                cairo.fill_with_color(CairoColor.WHITE)
                cairo.set_draw_color(CairoColor.BLACK)

                layout.set_content(status_line)
                layout.render(cairo)

                cairo.move_to(Point(x=0, y=line_3_top))
                layout.set_content("Tabula")
                layout.render(cairo)

                if self.capslock:
                    render_capslock_symbol(
                        cairo,
                        origin=Point(x=200, y=symbol_y_top),
                        scale=symbol_scale,
                        linewidth=2,
                    )
                if self.compose:
                    compose_x = self.render_width - (200 + 1.5 * symbol_scale)
                    render_compose_symbol(
                        cairo,
                        origin=Point(x=compose_x, y=symbol_y_top),
                        scale=symbol_scale,
                        linewidth=2,
                    )

                rendered = Rendered(
                    image=cairo.get_image_bytes(),
                    extent=Rect(origin=Point(x=0, y=status_y_top), spread=cairo.size),
                )
        return rendered

from __future__ import annotations

import contextlib
import logging
import math
import typing

import msgspec
import timeflake

from ..commontypes import Point, Rect, Size
from ..durations import timer_display
from ..editor.wordcount import format_wordcount
from ..util import now
from ._cairopango import ffi, lib  # type: ignore
from .cairo import Cairo, CairoSurfaceReference
from .fonts import SERIF
from .pango import Pango, PangoLayout
from .rendertypes import Alignment, CairoColor, Rendered

if typing.TYPE_CHECKING:
    from ..commontypes import ScreenInfo
    from ..editor.doctypes import Paragraph
    from ..editor.document import DocumentModel

logger = logging.getLogger(__name__)
MARGIN = 10

# _p stands in for *; it's a pointer. the type is actually ffi.CData but this gains us nothing over typing.Any
g_string_p = typing.NewType("g_string_p", typing.Any)
markdown_state_p = typing.NewType("markdown_state_p", typing.Any)
pango_attr_list_p = typing.NewType("pango_attr_list_p", typing.Any)


def split_attr_string(attrstring):
    return [attr.strip() for attr in attrstring.splitlines()]


def get_split_attrs(attr_list: pango_attr_list_p):
    return split_attr_string(ffi.string(ffi.gc(lib.pango_attr_list_to_string(attr_list), lib.g_free)).decode("utf-8"))


def new_g_string(contents: str, extra_capacity: typing.Optional[int] = None):
    encoded = contents.encode("utf-8")
    size = len(encoded)
    if extra_capacity:
        assert isinstance(extra_capacity, int), "Non-integer extra_capacity specified."
        size += extra_capacity
    it = g_string_p(ffi.gc(lib.g_string_sized_new(size), lib.fully_free_g_string))
    lib.g_string_append_len(it, encoded, len(encoded))
    return it


def new_markdown_state(g_string: g_string_p):
    return markdown_state_p(ffi.gc(lib.markdown_state_new(g_string), lib.markdown_state_free))


class Renderable(msgspec.Struct, frozen=True, kw_only=True):
    para_id: timeflake.Timeflake
    g_string: g_string_p
    markdown_state: markdown_state_p

    @classmethod
    def for_para(cls, para: Paragraph):
        gstr = new_g_string(para.markdown, extra_capacity=256)
        mstate = new_markdown_state(gstr)
        lib.markdown_attrs(mstate, gstr)
        return cls(para_id=para.id, g_string=gstr, markdown_state=mstate)

    def append_chars(self, chars: str):
        if len(chars) == 1:
            lib.g_string_append_unichar(self.g_string, ord(chars))
        else:
            charsbytes = chars.encode("utf-8")
            lib.g_string_append_len(self.g_string, charsbytes, len(charsbytes))
        lib.markdown_attrs(self.markdown_state, self.g_string)

    def backspace(self):
        lib.markdown_attrs_backspace(self.markdown_state, self.g_string)

    @contextlib.contextmanager
    def composing_chars(self, composing_chars):
        initial_len = self.g_string.len
        assert initial_len == len(ffi.string(self.g_string.str))
        if composing_chars:
            charsbytes = composing_chars.encode("utf-8")
            lib.g_string_append_len(self.g_string, charsbytes, len(charsbytes))
            with_compose_len = self.g_string.len
            lib.setup_compose(self.markdown_state, initial_len, with_compose_len)
        yield
        if composing_chars:
            lib.cleanup_compose(self.markdown_state)
            lib.g_string_truncate(self.g_string, initial_len)

    @contextlib.contextmanager
    def cursor(self):
        lib.setup_cursor(self.markdown_state, self.g_string)
        yield
        lib.cleanup_cursor(self.markdown_state, self.g_string)


class LaidOut(msgspec.Struct):
    surface: CairoSurfaceReference
    y_top: int
    y_bottom: int

    def paste_onto_cairo(self, cairo: Cairo):
        cairo.paste_other(self.surface, Point(x=MARGIN, y=self.y_top), Rect(origin=Point.zeroes(), spread=self.surface.size))


class LayoutManager:
    rendered_markups: dict[str, CairoSurfaceReference]
    skip_height: int
    only_cursor_para_rendered: typing.Optional[CairoSurfaceReference]
    active_renderable: typing.Optional[Renderable]

    def __init__(
        self,
        screen_info: ScreenInfo,
        document: DocumentModel,
    ):
        self.screen_info = screen_info
        self.pango = Pango(dpi=screen_info.dpi)
        self.document = document
        self.render_width = self.screen_info.size.width - (MARGIN * 2)
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
        # Contains nothing but the cursor; we'll be using this a LOT
        self.only_cursor_para = ffi.gc(lib.cursor_para_new(), lib.cursor_para_free)
        self.only_cursor_para_rendered = None
        self.active_renderable = None

    def set_font(self, font: str):
        if font != self.rendered_font:
            self.rendered_markups = {}
            self.only_cursor_para_rendered = None
            self.skip_height = math.floor(self.pango.calculate_line_height(font))
            self.layout.set_font(font)
            self.rendered_font = font
        return self

    def set_line_spacing(self, factor: float):
        if factor != self.rendered_line_spacing:
            self.rendered_markups = {}
            self.only_cursor_para_rendered = None
            self.layout.set_line_spacing(factor)
            self.rendered_line_spacing = factor
        return self

    def _render(self, g_string: g_string_p, attr_list: pango_attr_list_p):
        lib.pango_layout_set_text(self.layout.layout, g_string.str, g_string.len)
        lib.pango_layout_set_attributes(self.layout.layout, attr_list)
        render_size = self.layout.get_logical_layout_rect().spread
        with Cairo(render_size) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            cairo.move_to(Point.zeroes())
            self.layout.render(cairo)
            surface_reference = CairoSurfaceReference.from_cairo(cairo)
        return surface_reference

    def render_to_image_surface(self, para: Paragraph):
        with new_g_string(para.markdown) as g_string, new_markdown_state(g_string) as markdown_state:
            lib.markdown_attrs(markdown_state, g_string)
            surface_reference = self._render(g_string, markdown_state.attr_list)

        self.rendered_markups[para.markdown] = surface_reference

    def ensure_only_cursor_para_rendered(self):
        if self.only_cursor_para_rendered is None:
            lib.pango_layout_set_text(self.layout.layout, self.only_cursor_para.para, 1)
            lib.pango_layout_set_attributes(self.layout.layout, self.only_cursor_para.attr_list)
            render_size = self.layout.get_logical_layout_rect().spread
            with Cairo(render_size) as cairo:
                cairo.fill_with_color(CairoColor.WHITE)
                cairo.set_draw_color(CairoColor.BLACK)
                cairo.move_to(Point.zeroes())
                self.layout.render(cairo)
                self.only_cursor_para_rendered = CairoSurfaceReference.from_cairo(cairo)
        return self.only_cursor_para_rendered

    def render_document(self, *, composing_chars: str):
        laidouts: list[LaidOut] = []
        used_rendereds = {}
        cursor_para_id = self.document.cursor_para_id
        current_y = self.cursor_y
        current_i = len(self.document) - 1
        while current_i >= 0 and current_y >= 0:
            para = self.document[current_i]
            if cursor_para_id != para.id:
                # non-active, simple path
                if para.markdown not in self.rendered_markups:
                    self.render_to_image_surface(para)
                surface = self.rendered_markups[para.markdown]
                used_rendereds[para.markdown] = surface
            else:
                if self.active_renderable is None or self.active_renderable.para_id != para.id:
                    self.active_renderable = Renderable.for_para(para)
                if para.markdown == "" and composing_chars == "":
                    # just the cursor
                    surface = self.ensure_only_cursor_para_rendered()
                else:
                    # we shall assume that the active_renderable is up to date
                    with self.active_renderable.composing_chars(composing_chars):
                        with self.active_renderable.cursor():
                            surface = self._render(self.active_renderable.g_string, self.active_renderable.markdown_state.attr_list)

            rendered_height = surface.size.height
            top = current_y - rendered_height
            laidouts.append(LaidOut(surface=surface, y_top=top, y_bottom=current_y))
            current_y -= rendered_height + self.skip_height
            current_i -= 1

        self.target_cairo.fill_with_color(CairoColor.WHITE)

        for laidout in laidouts:
            laidout.paste_onto_cairo(self.target_cairo)

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

    def clear(self):
        half_height = self.screen_info.size.height // 2
        status_area = Rect(origin=Point(x=0, y=half_height), spread=Size(width=self.screen_info.size.width, height=half_height))
        with Cairo(status_area.spread) as cairo:
            cairo.fill_with_color(CairoColor.WHITE)
            rendered = cairo.get_rendered(status_area.origin)
            return rendered

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

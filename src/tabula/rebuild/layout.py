import math
import typing

import msgspec

from .commontypes import Size
from .hwtypes import ScreenRect
from ..rendering._cairopango import ffi, lib as clib
from ..rendering.rendertypes import Alignment, WrapMode

if typing.TYPE_CHECKING:
    from ..rendering.renderer2 import Renderer
    from .document import DocumentModel


# https://en.wikipedia.org/wiki/Macron_below
# https://en.wikipedia.org/wiki/Underscore
CURSOR = '<span alpha="50%">_</span>'


class Framelet(msgspec.Struct, frozen=True):
    rect: ScreenRect
    image: bytes


class RenderedMarkup(msgspec.Struct, frozen=True):
    markup: str
    size: Size
    image_surface: ffi.CData


class Chunk(msgspec.Struct, frozen=True):
    index: int
    markup: str


class LaidOut(msgspec.Struct):
    rendered: RenderedMarkup
    y_top: int
    y_bottom: int


class LayoutManager:
    rendered_markups: dict[str, RenderedMarkup]
    skip_height: int

    def __init__(
        self,
        renderer: "Renderer",
        document: "DocumentModel",
        full_height=False,
    ):
        self.renderer = renderer
        self.document = document
        self.render_width = renderer.screen_info.size.width
        self.cursor_y = renderer.screen_info.size.height // 2
        self.render_height = (
            renderer.screen_info.size.height if full_height else self.cursor_y
        )
        self.layout = ffi.gc(
            clib.pango_layout_new(renderer.context), clib.g_object_unref
        )
        self.setup_layout()
        self.rendered_markups = {}
        self.renderer.set_fontmap_resolution(self.renderer.screen_info.dpi)
        self.rendered_font = None
        self.skip_height = 0
        self.render_size = Size(self.render_width, self.render_height)
        self.target_surface = self.renderer.create_surface(self.render_size)

    def setup_layout(self):
        clib.pango_layout_set_auto_dir(self.layout, False)
        clib.pango_layout_set_ellipsize(self.layout, clib.PANGO_ELLIPSIZE_NONE)
        clib.pango_layout_set_justify(self.layout, False)
        clib.pango_layout_set_single_paragraph_mode(self.layout, False)
        clib.pango_layout_set_wrap(self.layout, WrapMode.WORD_CHAR)
        clib.pango_layout_set_width(
            self.layout,
            self.render_width * clib.PANGO_SCALE,
        )
        clib.pango_layout_set_alignment(self.layout, Alignment.LEFT)

    def setup_layout_font(self, font: str):
        with ffi.gc(
            clib.pango_font_description_from_string(font.encode("utf-8")),
            clib.pango_font_description_free,
        ) as font_description, ffi.gc(
            clib.pango_font_map_load_font(
                self.renderer.fontmap, self.renderer.context, font_description
            ),
            clib.g_object_unref,
        ) as loaded_font, ffi.gc(
            clib.pango_font_get_metrics(loaded_font, self.renderer.language),
            clib.pango_font_metrics_unref,
        ) as font_metrics:
            clib.pango_layout_set_font_description(self.layout, font_description)
            font_height = (
                clib.pango_font_metrics_get_height(font_metrics) / clib.PANGO_SCALE
            )
            self.skip_height = math.floor(font_height)

    def set_font(self, font: str):
        self.rendered_markups = {}
        self.setup_layout_font(font)
        self.rendered_font = font

    def render_to_image_surface(self, markup: str):
        clib.pango_layout_set_markup(self.layout, markup.encode("utf-8"), -1)
        with ffi.new("PangoRectangle *") as logical_rect:
            clib.pango_layout_get_pixel_extents(self.layout, ffi.NULL, logical_rect)
            markup_size = Size(width=self.render_width, height=logical_rect.height)
        markup_surface = self.renderer.create_surface(markup_size)
        with self.renderer.create_cairo_context(markup_surface) as markup_context:
            clib.cairo_set_operator(markup_context, clib.CAIRO_OPERATOR_SOURCE)
            clib.cairo_set_source_rgba(markup_context, 1, 1, 1, 1)
            clib.cairo_paint(markup_context)
            clib.cairo_set_source_rgba(markup_context, 0, 0, 0, 0)
            clib.pango_cairo_show_layout(markup_context, self.layout)
        clib.cairo_surface_flush(markup_surface)
        rendered = RenderedMarkup(
            markup=markup, size=markup_size, image_surface=markup_surface
        )
        self.rendered_markups[markup] = rendered

    def render_update(self, font: str):
        if font != self.rendered_font:
            self.set_font(font)

        laidouts: list[LaidOut] = []
        used_rendereds = {}
        cursor_para_id = self.document.cursor_para_id
        current_y = self.cursor_y
        current_i = len(self.document) - 1
        while current_i >= 0 and current_y >= 0:
            para = self.document[current_i]
            markup = para.markup
            if cursor_para_id == para.id:
                markup += CURSOR
            if markup not in self.rendered_markups:
                self.render_to_image_surface(markup)
            rendered = self.rendered_markups[markup]
            used_rendereds[markup] = rendered
            rendered_height = rendered.size.height
            top = current_y - rendered_height
            # set_into(laidouts, current_i, LaidOut(rendered=rendered, y_top=top, y_bottom=current_y))
            laidouts.append(LaidOut(rendered=rendered, y_top=top, y_bottom=current_y))
            current_y -= rendered_height + self.skip_height
            current_i -= 1

        with self.renderer.create_cairo_context(self.target_surface) as target_context:
            clib.cairo_set_operator(target_context, clib.CAIRO_OPERATOR_SOURCE)
            clib.cairo_set_source_rgba(target_context, 1, 1, 1, 1)
            clib.cairo_paint(target_context)

            for laidout in laidouts:
                clib.cairo_set_operator(target_context, clib.CAIRO_OPERATOR_SOURCE)
                clib.cairo_set_source_surface(
                    target_context, laidout.rendered.image_surface, 0, laidout.y_top
                )
                clib.cairo_rectangle(
                    target_context,
                    0,
                    laidout.y_top,
                    laidout.rendered.size.width,
                    laidout.rendered.size.height,
                )
                clib.cairo_clip(target_context)
                clib.cairo_paint(target_context)
                clib.cairo_reset_clip(target_context)

        clib.cairo_surface_flush(self.target_surface)

        if CURSOR in self.rendered_markups:
            # Worth keeping around
            used_rendereds[CURSOR] = self.rendered_markups[CURSOR]
        self.rendered_markups = used_rendereds

        return Framelet(
            rect=ScreenRect(
                x=0, y=0, width=self.render_width, height=self.render_height
            ),
            image=self.renderer.surface_to_bytes(
                self.target_surface, self.render_size, skip_inversion=True
            ),
        )

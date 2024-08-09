from __future__ import annotations

import typing
from contextlib import AbstractContextManager

from ..commontypes import Rect
from ..util import golden_section_search
from ._cairopango import ffi, lib  # type: ignore
from .fontconfig import NON_DRAFTING_FONTS
from .rendertypes import (
    Alignment,
    Antialias,
    HintMetrics,
    HintMode,
    LayoutRects,
    SubpixelOrder,
    WrapMode,
)

if typing.TYPE_CHECKING:
    from .cairo import Cairo

glib_alloc = ffi.new_allocator(alloc=lib.g_malloc0, free=lib.g_free, should_clear_after_alloc=False)


class PangoLayout(AbstractContextManager):
    def __init__(
        self,
        *,
        pango: Pango,
        width: float,
        justify: bool = False,
        alignment: Alignment = Alignment.LEFT,
        single_par: bool = False,
        wrap: WrapMode = WrapMode.WORD_CHAR,
    ):
        self.pango = pango
        self.layout = ffi.gc(lib.pango_layout_new(self.pango.context), lib.g_object_unref)
        self.layout_ink_rect = glib_alloc("PangoRectangle *")
        self.layout_logical_rect = glib_alloc("PangoRectangle *")
        self._setup_layout(
            width=width,
            justify=justify,
            alignment=alignment,
            single_par=single_par,
            wrap=wrap,
        )

    def _setup_layout(
        self,
        width: float,
        justify: bool,
        alignment: Alignment,
        single_par: bool,
        wrap: WrapMode,
    ):
        # don't try auto-detecting text direction
        lib.pango_layout_set_auto_dir(self.layout, False)
        lib.pango_layout_set_ellipsize(self.layout, lib.PANGO_ELLIPSIZE_NONE)
        lib.pango_layout_set_justify(self.layout, justify)
        lib.pango_layout_set_single_paragraph_mode(self.layout, single_par)
        lib.pango_layout_set_wrap(self.layout, wrap)
        lib.pango_layout_set_width(
            self.layout,
            width * lib.PANGO_SCALE,
        )
        lib.pango_layout_set_alignment(self.layout, alignment)

    def set_font(self, font: str):
        with Pango._make_font_description(font) as font_description:
            lib.pango_layout_set_font_description(self.layout, font_description)

    def set_content(self, text: str, is_markup: bool = False):
        textbytes = text.encode("utf-8")
        if is_markup:
            lib.pango_layout_set_markup(self.layout, textbytes, len(textbytes))
        else:
            self.clear_attributes()
            lib.pango_layout_set_text(self.layout, textbytes, len(textbytes))

    def clear_attributes(self):
        lib.pango_layout_set_attributes(self.layout, ffi.NULL)

    def render(self, cairo: Cairo):
        lib.pango_cairo_show_layout(cairo.context, self.layout)

    def __enter__(self):
        return self

    def __exit__(self, *ignored):
        ffi.release(self.layout)
        del self.layout

    def get_layout_rects(self):
        # The Pango docs say the resulting rects are owned by the layout instance, which means we shouldn't free them.
        # Therefore we simply use rects with the same lifetime as the layout instance.
        lib.pango_layout_get_pixel_extents(self.layout, self.layout_ink_rect, self.layout_logical_rect)
        return LayoutRects(ink=Rect.from_pango_rect(self.layout_ink_rect), logical=Rect.from_pango_rect(self.layout_logical_rect))

    def get_logical_layout_rect(self):
        lib.pango_layout_get_pixel_extents(self.layout, ffi.NULL, self.layout_logical_rect)
        return Rect.from_pango_rect(self.layout_logical_rect)

    def set_line_spacing(self, factor: float):
        lib.pango_layout_set_line_spacing(self.layout, factor)


class Pango:
    def __init__(
        self,
        *,
        dpi: int = 300,
        language: str = "en-us",
        hinting: HintMode = HintMode.DEFAULT,
        hint_metrics: HintMetrics = HintMetrics.DEFAULT,
        subpixel_order: SubpixelOrder = SubpixelOrder.DEFAULT,
        antialias: Antialias = Antialias.DEFAULT,
    ):
        # language must be a valid RFC-3066 code, but currently this isn't validated

        # This fontmap is owned by Pango, not by us; we must not free it.
        self.fontmap = lib.pango_cairo_font_map_get_default()
        lib.pango_cairo_font_map_set_resolution(ffi.cast("PangoCairoFontMap *", self.fontmap), dpi)

        self.fontoptions = ffi.gc(lib.cairo_font_options_create(), lib.cairo_font_options_destroy)
        if hinting is not HintMode.DEFAULT:
            lib.cairo_font_options_set_hint_style(self.fontoptions, hinting.value)

        if subpixel_order is not SubpixelOrder.DEFAULT:
            lib.cairo_font_options_set_subpixel_order(self.fontoptions, subpixel_order.value)

        if hint_metrics is not HintMetrics.DEFAULT:
            lib.cairo_font_options_set_hint_metrics(self.fontoptions, hint_metrics.value)

        if antialias is not Antialias.DEFAULT:
            lib.cairo_font_options_set_antialias(self.fontoptions, antialias.value)

        self.context = ffi.gc(lib.pango_font_map_create_context(self.fontmap), lib.g_object_unref)
        lib.pango_cairo_context_set_font_options(self.context, self.fontoptions)

        self.language = lib.pango_language_from_string(language.encode("ascii"))
        lib.pango_context_set_language(self.context, self.language)
        lib.pango_context_set_base_dir(self.context, lib.PANGO_DIRECTION_LTR)
        lib.pango_context_set_base_gravity(self.context, lib.PANGO_GRAVITY_SOUTH)
        lib.pango_context_set_gravity_hint(self.context, lib.PANGO_GRAVITY_HINT_NATURAL)

    @staticmethod
    def _make_font_description(font: str):
        return ffi.gc(
            lib.pango_font_description_from_string(font.encode("utf-8")),
            lib.pango_font_description_free,
        )

    def calculate_line_height(self, font: str) -> float:
        with (
            self._make_font_description(font) as font_description,
            ffi.gc(
                lib.pango_context_get_metrics(self.context, font_description, ffi.NULL),
                lib.pango_font_metrics_unref,
            ) as font_metrics,
        ):
            return lib.pango_font_metrics_get_height(font_metrics) / lib.PANGO_SCALE

    def calculate_ascent(self, font: str) -> float:
        with (
            self._make_font_description(font) as font_description,
            ffi.gc(
                lib.pango_context_get_metrics(self.context, font_description, ffi.NULL),
                lib.pango_font_metrics_unref,
            ) as font_metrics,
        ):
            return lib.pango_font_metrics_get_ascent(font_metrics) / lib.PANGO_SCALE

    def find_size_for_desired_ascent(self, unsized_font: str, desired_ascent: float):
        return round(golden_section_search(lambda x: abs(self.calculate_ascent(f"{unsized_font} {x}") - desired_ascent), 1, 100), 1)

    def list_available_fonts(self) -> list[str]:
        with glib_alloc("int *") as size_p, glib_alloc("PangoFontFamily***") as families_p:
            lib.pango_font_map_list_families(self.fontmap, families_p, size_p)
            with ffi.gc(families_p[0], lib.g_free) as families:
                font_names = [
                    ffi.string(lib.pango_font_family_get_name(family)).decode("utf-8") for family in ffi.unpack(families, size_p[0])
                ]
        return sorted(font_names)

    def list_drafting_fonts(self):
        return sorted(set(self.list_available_fonts()) - NON_DRAFTING_FONTS)

from contextlib import AbstractContextManager
import typing

from ..commontypes import Rect
from ._cairopango import ffi, lib as clib  # type: ignore
from .rendertypes import (
    HintMode,
    HintMetrics,
    SubpixelOrder,
    Antialias,
    Alignment,
    WrapMode,
    LayoutRects,
)

if typing.TYPE_CHECKING:
    from .cairo import Cairo


class PangoLayout(AbstractContextManager):
    def __init__(
        self,
        *,
        pango: "Pango",
        width: float,
        justify: bool = False,
        alignment: Alignment = Alignment.LEFT,
        single_par: bool = False,
        wrap: WrapMode = WrapMode.WORD_CHAR,
    ):
        self.pango = pango
        self.layout = ffi.gc(clib.pango_layout_new(self.pango.context), clib.g_object_unref)
        self.setup_layout(
            width=width,
            justify=justify,
            alignment=alignment,
            single_par=single_par,
            wrap=wrap,
        )

    def setup_layout(
        self,
        width: float,
        justify: bool,
        alignment: Alignment,
        single_par: bool,
        wrap: WrapMode,
    ):
        # don't try auto-detecting text direction
        clib.pango_layout_set_auto_dir(self.layout, False)
        clib.pango_layout_set_ellipsize(self.layout, clib.PANGO_ELLIPSIZE_NONE)
        clib.pango_layout_set_justify(self.layout, justify)
        clib.pango_layout_set_single_paragraph_mode(self.layout, single_par)
        clib.pango_layout_set_wrap(self.layout, wrap)
        clib.pango_layout_set_width(
            self.layout,
            width * clib.PANGO_SCALE,
        )
        clib.pango_layout_set_alignment(self.layout, alignment)

    def set_font(self, font: str):
        with Pango._make_font_description(font) as font_description:
            clib.pango_layout_set_font_description(self.layout, font_description)

    def set_content(self, text: str, is_markup: bool = False):
        setter = clib.pango_layout_set_markup if is_markup else clib.pango_layout_set_text
        # -1 means null-terminated, which cffi will automatically do for us
        setter(self.layout, text.encode("utf-8"), -1)

    def render(self, cairo: "Cairo"):
        clib.pango_cairo_show_layout(cairo.context, self.layout)

    def __enter__(self):
        return self

    def __exit__(self, *ignored):
        ffi.release(self.layout)
        del self.layout

    def get_layout_rects(self):
        with ffi.new("PangoRectangle *") as ink, ffi.new("PangoRectangle *") as logical:
            clib.pango_layout_get_pixel_extents(self.layout, ink, logical)
            return LayoutRects(
                ink=Rect.from_pango_rect(ink),
                logical=Rect.from_pango_rect(logical),
            )

    def set_line_spacing(self, factor: float):
        clib.pango_layout_set_line_spacing(self.layout, factor)


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
        self.fontmap = clib.pango_cairo_font_map_get_default()
        clib.pango_cairo_font_map_set_resolution(ffi.cast("PangoCairoFontMap *", self.fontmap), dpi)

        self.fontoptions = ffi.gc(clib.cairo_font_options_create(), clib.cairo_font_options_destroy)
        if hinting is not HintMode.DEFAULT:
            clib.cairo_font_options_set_hint_style(self.fontoptions, hinting.value)

        if subpixel_order is not SubpixelOrder.DEFAULT:
            clib.cairo_font_options_set_subpixel_order(self.fontoptions, subpixel_order.value)

        if hint_metrics is not HintMetrics.DEFAULT:
            clib.cairo_font_options_set_hint_metrics(self.fontoptions, hint_metrics.value)

        if antialias is not Antialias.DEFAULT:
            clib.cairo_font_options_set_antialias(self.fontoptions, antialias.value)

        self.context = ffi.gc(clib.pango_font_map_create_context(self.fontmap), clib.g_object_unref)
        clib.pango_cairo_context_set_font_options(self.context, self.fontoptions)

        self.language = clib.pango_language_from_string(language.encode("ascii"))
        clib.pango_context_set_language(self.context, self.language)
        clib.pango_context_set_base_dir(self.context, clib.PANGO_DIRECTION_LTR)
        clib.pango_context_set_base_gravity(self.context, clib.PANGO_GRAVITY_SOUTH)
        clib.pango_context_set_gravity_hint(self.context, clib.PANGO_GRAVITY_HINT_NATURAL)

    @staticmethod
    def _make_font_description(font: str):
        return ffi.gc(
            clib.pango_font_description_from_string(font.encode("utf-8")),
            clib.pango_font_description_free,
        )

    def calculate_line_height(self, font: str) -> float:
        with (
            self._make_font_description(font) as font_description,
            ffi.gc(
                clib.pango_context_get_metrics(self.context, font_description, ffi.NULL),
                clib.pango_font_metrics_unref,
            ) as font_metrics,
        ):
            return clib.pango_font_metrics_get_height(font_metrics) / clib.PANGO_SCALE

    def list_available_fonts(self) -> list[str]:
        with ffi.new("int *") as size_p, ffi.new("PangoFontFamily***") as families_p:
            clib.pango_font_map_list_families(self.fontmap, families_p, size_p)
            font_names = [
                ffi.string(clib.pango_font_family_get_name(family)).decode("utf-8")
                for family in ffi.unpack(ffi.gc(families_p[0], clib.g_free), size_p[0])
            ]
        return sorted(font_names)

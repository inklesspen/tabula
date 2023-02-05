# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import math

from ._cairopango import ffi, lib as clib
from .rendertypes import (
    Antialias,
    HintMetrics,
    HintMode,
    SubpixelOrder,
    Point,
    Size,
    Rect,
    Alignment,
    WrapMode,
    Margins,
    AffineTransform,
    ScreenInfo,
    CairoOp,
)


class Renderer:
    screen_info: ScreenInfo

    def __init__(
        self,
        screen_info: ScreenInfo,
        *,
        language: str = "en-us",
        hinting: HintMode = HintMode.DEFAULT,
        hint_metrics: HintMetrics = HintMetrics.DEFAULT,
        subpixel_order: SubpixelOrder = SubpixelOrder.DEFAULT,
        antialias: Antialias = Antialias.DEFAULT,
    ):
        self.screen_info = screen_info
        # language must be a valid RFC-3066 code, but there is currently no validation for this

        # This fontmap is owned by Pango, not by us; we must not free it.
        self.fontmap = clib.pango_cairo_font_map_get_default()

        self.fontoptions = ffi.gc(
            clib.cairo_font_options_create(), clib.cairo_font_options_destroy
        )
        if hinting != HintMode.DEFAULT:
            clib.cairo_font_options_set_hint_style(self.fontoptions, hinting.value)

        if subpixel_order != SubpixelOrder.DEFAULT:
            clib.cairo_font_options_set_subpixel_order(
                self.fontoptions, subpixel_order.value
            )

        if hint_metrics != HintMetrics.DEFAULT:
            clib.cairo_font_options_set_hint_metrics(
                self.fontoptions, hint_metrics.value
            )

        if antialias != Antialias.DEFAULT:
            clib.cairo_font_options_set_antialias(self.fontoptions, antialias.value)

        self.context = ffi.gc(
            clib.pango_font_map_create_context(self.fontmap), clib.g_object_unref
        )
        clib.pango_cairo_context_set_font_options(self.context, self.fontoptions)

        self.language = clib.pango_language_from_string(language.encode("ascii"))
        clib.pango_context_set_language(self.context, self.language)
        clib.pango_context_set_base_dir(self.context, clib.PANGO_DIRECTION_LTR)
        clib.pango_context_set_base_gravity(self.context, clib.PANGO_GRAVITY_SOUTH)
        clib.pango_context_set_gravity_hint(
            self.context, clib.PANGO_GRAVITY_HINT_NATURAL
        )

    def destroy(self):
        # optional; call for more efficient memory cleanup
        ffi.release(self.context)
        self.context = None
        ffi.release(self.fontoptions)
        self.fontoptions = None

    def set_fontmap_resolution(self, dpi: float):
        cast = ffi.cast("PangoCairoFontMap *", self.fontmap)
        clib.pango_cairo_font_map_set_resolution(cast, dpi)

    def create_surface(self, size: Size = None):
        if size is None:
            size = self.screen_info.size
        return ffi.gc(
            clib.cairo_image_surface_create(
                clib.CAIRO_FORMAT_A8, size.width, size.height
            ),
            clib.cairo_surface_destroy,
        )

    @staticmethod
    def create_cairo_context(surface):
        return ffi.gc(clib.cairo_create(surface), clib.cairo_destroy)

    @staticmethod
    @contextlib.contextmanager
    def cairo_save_restore(cairo_context):
        clib.cairo_save(cairo_context)
        try:
            yield cairo_context
        finally:
            clib.cairo_restore(cairo_context)

    @staticmethod
    def _surface_to_buffer(surface, size):
        dataptr = clib.cairo_image_surface_get_data(surface)
        buf = ffi.buffer(dataptr, size.total())
        return buf

    def surface_to_bytes(self, surface, size, skip_inversion=False):
        if not skip_inversion:
            # The A8 surface type is treated by cairo as an alpha channel.
            # To use it as a grayscale channel, we need to invert the bytes.
            clib.cairo_surface_flush(surface)
            clib.invert_a8_surface(surface)
            # Technically this call is not necessary, as long as we immediately
            # dispose of the surface. But better safe than sorry.
            clib.cairo_surface_mark_dirty(surface)
        return bytes(self._surface_to_buffer(surface, size))

    @staticmethod
    def _paint_background(cr, alpha: float = 0):
        clib.cairo_set_operator(cr, clib.CAIRO_OPERATOR_SOURCE)
        clib.cairo_set_source_rgba(cr, 1, 1, 1, alpha)
        clib.cairo_paint(cr)

    def _set_cairo_transform(self, cairo, matrix: AffineTransform):
        with ffi.new("cairo_matrix_t *") as cairo_matrix:
            clib.cairo_matrix_init(
                cairo_matrix,
                matrix.xx,
                matrix.yx,
                matrix.xy,
                matrix.yy,
                matrix.x0,
                matrix.y0,
            )

            clib.cairo_set_matrix(cairo, cairo_matrix)
            # https://gitlab.gnome.org/GNOME/pango/-/blob/main/pango/pangocairo-context.c#L93
            # This sets the pango context matrix based on the cairo matrix
            clib.pango_cairo_update_context(cairo, self.context)

    def prepare_background(self, cairo_context):
        self._set_cairo_transform(cairo_context, AffineTransform.identity())
        self._paint_background(cairo_context)

    def calculate_line_height(self, font: str, dpi: float = None) -> float:
        if dpi is None:
            dpi = self.screen_info.dpi
        self.set_fontmap_resolution(dpi)
        with self._make_font_description(font) as font_description, ffi.gc(
            clib.pango_font_map_load_font(self.fontmap, self.context, font_description),
            clib.g_object_unref,
        ) as loaded_font, ffi.gc(
            clib.pango_font_get_metrics(loaded_font, self.language),
            clib.pango_font_metrics_unref,
        ) as font_metrics:
            return clib.pango_font_metrics_get_height(font_metrics) / clib.PANGO_SCALE

    def describe_loaded_font(self, font: str):
        with self._make_font_description(font) as font_description, ffi.gc(
            clib.pango_font_map_load_font(self.fontmap, self.context, font_description),
            clib.g_object_unref,
        ) as loaded_font, ffi.gc(
            clib.pango_font_describe(loaded_font), clib.pango_font_description_free
        ) as loaded_font_description, ffi.gc(
            clib.pango_font_description_to_string(loaded_font_description), clib.g_free
        ) as loaded_font_string:
            return ffi.string(loaded_font_string).decode("utf-8")

    def list_available_fonts(self) -> list[str]:
        with ffi.new("int *") as size_p, ffi.new("PangoFontFamily***") as families_p:
            clib.pango_font_map_list_families(self.fontmap, families_p, size_p)
            font_names = [
                ffi.string(clib.pango_font_family_get_name(family)).decode("utf-8")
                for family in ffi.unpack(ffi.gc(families_p[0], clib.g_free), size_p[0])
            ]
        return sorted(font_names)

    def render_border(self, surface, size: Size) -> Size:
        # could use clib.cairo_image_surface_get_width (and height) instead of size param
        with self.create_cairo_context(surface) as cairo:
            # ensure identity matrix
            self._set_cairo_transform(cairo, AffineTransform.identity())
            clib.cairo_set_line_width(cairo, 1)
            clib.cairo_rectangle(
                cairo,
                1.5,
                1.5,
                size.width - 2,
                size.height - 2,
            )
            clib.cairo_stroke(cairo)
        return size

    @staticmethod
    def move_to(cairo_context, point: Point):
        clib.cairo_move_to(cairo_context, point.x, point.y)

    def roundrect(
        self,
        cairo_context,
        rect: Rect,
        radius: float,
        line_width: float = 2.0,
        op: CairoOp = CairoOp.STROKE,
    ):
        clib.cairo_new_sub_path(cairo_context)
        # This basically just draws the corners, and relies on cairo_arc to draw line segments connecting them.
        # Angles are given in radians; see https://www.cairographics.org/manual/cairo-Paths.html#cairo-arc for more info.
        # upper left
        clib.cairo_arc(
            cairo_context,
            rect.origin.x + radius,
            rect.origin.y + radius,
            radius,
            math.radians(180),
            math.radians(270),
        )
        # upper right
        clib.cairo_arc(
            cairo_context,
            rect.origin.x + rect.spread.width - radius,
            rect.origin.y + radius,
            radius,
            math.radians(270),
            math.radians(0),
        )
        # lower right
        clib.cairo_arc(
            cairo_context,
            rect.origin.x + rect.spread.width - radius,
            rect.origin.y + rect.spread.height - radius,
            radius,
            math.radians(0),
            math.radians(90),
        )
        # lower left
        clib.cairo_arc(
            cairo_context,
            rect.origin.x + radius,
            rect.origin.y + rect.spread.height - radius,
            radius,
            math.radians(90),
            math.radians(180),
        )
        clib.cairo_close_path(cairo_context)
        clib.cairo_set_line_width(cairo_context, line_width)
        match op:
            case CairoOp.STROKE:
                clib.cairo_stroke(cairo_context)
            case CairoOp.FILL:
                clib.cairo_fill(cairo_context)

    def button(
        self,
        cairo_context,
        *,
        text: str,
        font: str,
        rect: Rect,
        markup: bool = False,
        dpi: float = None,
        inverted: bool = False,
    ):
        if dpi is None:
            dpi = self.screen_info.dpi
        rects = self.calculate_rendered_rects(
            font=font,
            text=text,
            markup=markup,
            alignment=Alignment.CENTER,
            width=rect.spread.width,
            dpi=dpi,
        )
        ink_rect = rects["ink_rect"]

        self.roundrect(
            cairo_context,
            rect=rect,
            radius=50,
            line_width=2.5,
            op=CairoOp.FILL if inverted else CairoOp.STROKE,
        )
        text_x = rect.origin.x
        text_y = math.floor(
            rect.origin.y
            + rect.spread.height / 2
            - ink_rect.origin.y
            - ink_rect.spread.height / 2
        )

        self.move_to(cairo_context, Point(x=text_x, y=text_y))
        if inverted:
            self.set_draw_color_white(cairo_context)
        self.simple_render(
            cairo_context,
            font,
            text,
            markup=markup,
            alignment=Alignment.CENTER,
            width=rect.spread.width,
        )
        if inverted:
            self.set_draw_color_black(cairo_context)

    def _setup_layout(
        self,
        pango_layout,
        width: float,
        font: str,
        text: str,
        markup: bool = False,
        justify: bool = False,
        alignment: Alignment = Alignment.LEFT,
        single_par: bool = False,
        wrap: WrapMode = WrapMode.WORD_CHAR,
    ):
        utf8bytes = text.encode("utf-8")
        if markup:
            # -1 means null-terminated
            clib.pango_layout_set_markup(pango_layout, utf8bytes, -1)
        else:
            clib.pango_layout_set_text(pango_layout, utf8bytes, -1)

        # don't try auto-detecting text direction
        clib.pango_layout_set_auto_dir(pango_layout, False)
        clib.pango_layout_set_ellipsize(pango_layout, clib.PANGO_ELLIPSIZE_NONE)
        clib.pango_layout_set_justify(pango_layout, justify)
        clib.pango_layout_set_single_paragraph_mode(pango_layout, single_par)
        clib.pango_layout_set_wrap(pango_layout, wrap)

        with self._make_font_description(font) as font_description:
            clib.pango_layout_set_font_description(pango_layout, font_description)

        clib.pango_layout_set_width(
            pango_layout,
            width * clib.PANGO_SCALE,
        )

        clib.pango_layout_set_alignment(pango_layout, alignment)

    def setup_drawing(self, cairo_context):
        clib.cairo_set_operator(cairo_context, clib.CAIRO_OPERATOR_SOURCE)
        clib.cairo_set_source_rgba(cairo_context, 0, 0, 0, 1)

    def set_draw_color_black(self, cairo_context):
        clib.cairo_set_source_rgba(cairo_context, 0, 0, 0, 1)

    def set_draw_color_white(self, cairo_context):
        clib.cairo_set_source_rgba(cairo_context, 0, 0, 0, 0)

    def calculate_rendered_rects(
        self,
        font: str,
        text: str,
        markup: bool = False,
        justify: bool = False,
        alignment: Alignment = Alignment.LEFT,
        wrap: WrapMode = WrapMode.CHAR,
        width: float = 0.0,
        dpi: float = None,
    ):
        if dpi is None:
            dpi = self.screen_info.dpi
        self.set_fontmap_resolution(dpi)
        with ffi.gc(clib.pango_layout_new(self.context), clib.g_object_unref) as layout:
            self._setup_layout(
                layout,
                width=width,
                font=font,
                text=text,
                markup=markup,
                justify=justify,
                alignment=alignment,
                single_par=True,
                wrap=wrap,
            )

            with ffi.new("PangoRectangle *") as ink_rect, ffi.new(
                "PangoRectangle *"
            ) as logical_rect:
                clib.pango_layout_get_pixel_extents(layout, ink_rect, logical_rect)
                return {
                    name: Rect(
                        origin=Point(x=pango_rect.x, y=pango_rect.y),
                        spread=Size(width=pango_rect.width, height=pango_rect.height),
                    )
                    for name, pango_rect in {
                        "ink_rect": ink_rect,
                        "logical_rect": logical_rect,
                    }.items()
                }

    def simple_render(
        self,
        cairo_context,
        font: str,
        text: str,
        markup: bool = False,
        justify: bool = False,
        alignment: Alignment = Alignment.LEFT,
        wrap: WrapMode = WrapMode.CHAR,
        width: float = 0.0,
        single_par: bool = True,
        dpi: float = None,
    ):
        if dpi is None:
            dpi = self.screen_info.dpi
        self.set_fontmap_resolution(dpi)

        with ffi.gc(clib.pango_layout_new(self.context), clib.g_object_unref) as layout:
            self._setup_layout(
                layout,
                width=width,
                font=font,
                text=text,
                markup=markup,
                justify=justify,
                alignment=alignment,
                single_par=single_par,
                wrap=wrap,
            )
            clib.pango_cairo_show_layout(cairo_context, layout)
        clib.cairo_surface_flush(clib.cairo_get_target(cairo_context))

    def render(
        self,
        surface,
        font: str = "",
        text: str = "",
        markup: bool = False,
        draw_border: bool = False,
        justify: bool = False,
        alignment: Alignment = Alignment.LEFT,
        single_par: bool = False,
        wrap: WrapMode = WrapMode.WORD_CHAR,
        margins: Margins = Margins(top=10, bottom=10, left=10, right=10),
        clear_before_render: bool = True,
        render_size: Size = Size(width=0, height=0),
        dpi: float = None,
    ) -> Size:
        if dpi is None:
            dpi = self.screen_info.dpi
        self.set_fontmap_resolution(dpi)
        with self.create_cairo_context(surface) as cairo_context:
            self._set_cairo_transform(cairo_context, AffineTransform.identity())

            if clear_before_render:
                self._paint_background(cairo_context)

            self.setup_drawing(cairo_context)

            self._set_cairo_transform(
                cairo_context,
                AffineTransform.translation(margins.left, margins.top),
            )

            with ffi.gc(
                clib.pango_layout_new(self.context), clib.g_object_unref
            ) as layout:
                self._setup_layout(
                    layout,
                    width=(render_size.width - (margins.left + margins.right)),
                    font=font,
                    text=text,
                    markup=markup,
                    justify=justify,
                    alignment=alignment,
                    single_par=single_par,
                    wrap=wrap,
                )

                with ffi.new("PangoRectangle *") as logical_rect:
                    clib.pango_layout_get_pixel_extents(layout, ffi.NULL, logical_rect)

                    clib.cairo_save(cairo_context)
                    # Does this even do anything? Probably not.
                    clib.cairo_translate(cairo_context, 0, 0)

                    clib.cairo_move_to(cairo_context, 0, 0)
                    clib.pango_cairo_show_layout(cairo_context, layout)

                    clib.cairo_restore(cairo_context)

                    clib.cairo_surface_flush(clib.cairo_get_target(cairo_context))

                    logical_rect_width = logical_rect.x + logical_rect.width
                    pango_layout_width = clib.pango_pixels(
                        clib.pango_layout_get_width(layout)
                    )

                    # pango_layout_get_height is always zero, since ellipsization is disabled.
                    logical_rect_height = logical_rect.y + logical_rect.height

                    rendered_size = Size(
                        width=max(logical_rect_width, pango_layout_width),
                        height=logical_rect_height,
                    )

                size_with_margin = Size(
                    width=rendered_size.width + margins.left + margins.right,
                    height=rendered_size.height + margins.top + margins.bottom,
                )

                size = size_with_margin

                if draw_border:
                    # Not sure what my original intent here was… but maybe this should use
                    # size_with_margin instead of render_size.
                    size = self.render_border(surface, render_size)

        return size

    @staticmethod
    def _make_font_description(font: str):
        # https://gnome.pages.gitlab.gnome.org/pango/Pango/struct.FontDescription.html
        # perhaps we should use pango_font_description_new instead, and the various set functions
        return ffi.gc(
            clib.pango_font_description_from_string(font.encode("utf-8")),
            clib.pango_font_description_free,
        )

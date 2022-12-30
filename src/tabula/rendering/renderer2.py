# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
# SPDX-License-Identifier: GPL-3.0-or-later
from ._cairopango import ffi, lib as clib
from .rendertypes import (
    Antialias,
    HintMetrics,
    HintMode,
    SubpixelOrder,
    Size,
    Alignment,
    WrapMode,
    Margins,
    AffineTransform,
)


# TODO: augment ffi.gc calls with size arguments


class Renderer:
    def __init__(
        self,
        *,
        language: str = "en-us",
        hinting: HintMode = HintMode.DEFAULT,
        hint_metrics: HintMetrics = HintMetrics.DEFAULT,
        subpixel_order: SubpixelOrder = SubpixelOrder.DEFAULT,
        antialias: Antialias = Antialias.DEFAULT,
    ):
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

    def create_surface(self, size: Size):
        return ffi.gc(
            clib.cairo_image_surface_create(
                clib.CAIRO_FORMAT_A8, size.width, size.height
            ),
            clib.cairo_surface_destroy,
        )

    def _surface_to_buffer(self, surface, size):
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

    def _paint_background(self, cr):
        clib.cairo_set_operator(cr, clib.CAIRO_OPERATOR_SOURCE)
        clib.cairo_set_source_rgba(cr, 1, 1, 1, 0)
        clib.cairo_paint(cr)

    def _set_cairo_transform_old(self, cairo, matrix):
        # in the C version, this struct is stack allocated
        with ffi.new("cairo_matrix_t *") as cairo_matrix:
            if matrix:
                clib.cairo_matrix_init(
                    cairo_matrix,
                    matrix.xx,
                    matrix.yx,
                    matrix.xy,
                    matrix.yy,
                    matrix.x0,
                    matrix.y0,
                )
            else:
                clib.cairo_matrix_init_identity(cairo_matrix)

            clib.cairo_set_matrix(cairo, cairo_matrix)
            # https://gitlab.gnome.org/GNOME/pango/-/blob/main/pango/pangocairo-context.c#L93
            # This sets the pango context matrix based on the cairo matrix
            clib.pango_cairo_update_context(cairo, self.context)

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

    def calculate_line_height(self, font: str, dpi: float):
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
        font_description_strings = []
        with ffi.new("int *") as size_p, ffi.new(
            "PangoFontFamily***"
        ) as families_p, ffi.new("PangoFontFace***") as faces_p:
            clib.pango_font_map_list_families(self.fontmap, families_p, size_p)
            families = ffi.unpack(ffi.gc(families_p[0], clib.g_free), size_p[0])
            for family in families:
                clib.pango_font_family_list_faces(family, faces_p, size_p)
                faces = ffi.unpack(ffi.gc(faces_p[0], clib.g_free), size_p[0])
                for face in faces:
                    with ffi.gc(
                        clib.pango_font_face_describe(face),
                        clib.pango_font_description_free,
                    ) as face_description, ffi.gc(
                        clib.pango_font_description_to_string(face_description),
                        clib.g_free,
                    ) as face_description_cstring:
                        font_description_string = ffi.string(
                            face_description_cstring
                        ).decode("utf-8")
                        # print(font_description_string)
                        font_description_strings.append(font_description_string)
        return sorted(font_description_strings)

    def render_border(self, surface, size: Size) -> Size:
        # could use clib.cairo_image_surface_get_width (and height) instead of size param
        with ffi.gc(clib.cairo_create(surface), clib.cairo_destroy) as cairo:
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
        dpi: float = 96.0,
    ) -> Size:
        self.set_fontmap_resolution(dpi)
        with ffi.gc(clib.cairo_create(surface), clib.cairo_destroy) as cairo_context:
            self._set_cairo_transform(cairo_context, AffineTransform.identity())

            if clear_before_render:
                self._paint_background(cairo_context)

            clib.cairo_set_operator(cairo_context, clib.CAIRO_OPERATOR_OVER)
            clib.cairo_set_source_rgba(cairo_context, 0, 0, 0, 1)

            self._set_cairo_transform(
                cairo_context,
                AffineTransform.translation(margins.left, margins.top),
            )

            with ffi.gc(
                clib.pango_layout_new(self.context), clib.g_object_unref
            ) as layout:
                utf8bytes = text.encode("utf-8")
                if markup:
                    # -1 means null-terminated
                    clib.pango_layout_set_markup(layout, utf8bytes, -1)
                else:
                    clib.pango_layout_set_text(layout, utf8bytes, -1)

                # don't try auto-detecting text direction
                clib.pango_layout_set_auto_dir(layout, False)
                clib.pango_layout_set_ellipsize(layout, clib.PANGO_ELLIPSIZE_NONE)
                clib.pango_layout_set_justify(layout, justify)
                clib.pango_layout_set_single_paragraph_mode(layout, single_par)
                clib.pango_layout_set_wrap(layout, wrap)

                with self._make_font_description(font) as font_description:
                    clib.pango_layout_set_font_description(layout, font_description)

                clib.pango_layout_set_width(
                    layout,
                    (render_size.width - (margins.left + margins.right))
                    * clib.PANGO_SCALE,
                )

                clib.pango_layout_set_alignment(layout, alignment)
                with ffi.new("PangoRectangle *") as logical_rect:
                    clib.pango_layout_get_pixel_extents(layout, ffi.NULL, logical_rect)

                    clib.cairo_save(cairo_context)
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

    def _make_font_description(self, font: str):
        # https://gnome.pages.gitlab.gnome.org/pango/Pango/struct.FontDescription.html
        # perhaps we should use pango_font_description_new instead, and the various set functions
        return ffi.gc(
            clib.pango_font_description_from_string(font.encode("utf-8")),
            clib.pango_font_description_free,
        )

# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
# SPDX-FileCopyrightText: 1999,2004,2005 Red Hat, Inc.
# SPDX-FileCopyrightText: 2001 Sun Microsystems
#
# SPDX-License-Identifier: GPL-3.0-or-later

# The code in this file began as a Python-cffi port of the 'pango-view' utility included with Pango.
# I ported the utility and PangoCairo backend, and then set about stripping out all the pieces I didn't need.
# The license of the original pango-view source is LGPL-2.0-or-later, which allows "converting" to GPL.
# The copyright notice in the pango-view source files is more or less as follows:
# Copyright (C) 1999,2004,2005 Red Hat, Inc.
# Copyright (C) 2001 Sun Microsystems
# (the specific years vary in some of the files)
from __future__ import annotations

from ._cairopango import ffi, lib as clib
from .types import (
    Antialias,
    HintMetrics,
    HintMode,
    SubpixelOrder,
    Rect,
    Size,
    Point,
    Opts,
    RenderOpts,
    Alignment,
    WrapMode,
)


class Renderer:
    def __init__(self, *, screen_size: Size, dpi: int):
        # Screen dimensions must divide evenly by 4, to fit neatly with cairo's stride.
        if screen_size.width % 4 > 0:
            raise ValueError("Screen width must be evenly divisible by 4.")
        if screen_size.height % 4 > 0:
            raise ValueError("Screen height must be evenly divisible by 4.")
        self.screen_size = screen_size
        self.dpi = dpi
        opts = Opts(dpi=self.dpi, screen_size=self.screen_size)
        self.instance = PangoCairoRenderer(opts)

    def render_border(self):
        with self.instance.create_surface() as surface:
            rendered_size = self.instance.render_border(surface)
            return (
                self.instance.surface_to_bytes(surface, rendered_size),
                rendered_size,
            )

    def _render(self, render_opts):
        with self.instance.create_surface() as surface:
            rendered_size = self.instance.render(surface, render_opts)
            return (
                self.instance.surface_to_bytes(surface, rendered_size),
                rendered_size,
            )

    def render_to_bytes(
        self,
        markup: str,
        font: str,
        margin_lr: int = 10,
        margin_tb: int = 0,
        alignment: Alignment = Alignment.LEFT,
    ):
        render_opts = RenderOpts(
            font=font,
            markup=True,
            text=markup,
            alignment=alignment,
            margin_t=margin_tb,
            margin_b=margin_tb,
            margin_l=margin_lr,
            margin_r=margin_lr,
        )
        return self._render(render_opts)

    def calculate_line_height(self, font: str) -> float:
        return self.instance.calculate_line_height(font)


class PangoCairoRenderer:
    def __init__(self, opts: Opts):
        self.opts = opts

        # This fontmap is owned by Pango, not by us; we must not free it.
        self.fontmap = clib.pango_cairo_font_map_get_default()

        self.fontoptions = ffi.gc(
            clib.cairo_font_options_create(), clib.cairo_font_options_destroy
        )
        if self.opts.hinting != HintMode.DEFAULT:
            clib.cairo_font_options_set_hint_style(
                self.fontoptions, self.opts.hinting.value
            )

        if self.opts.subpixel_order != SubpixelOrder.DEFAULT:
            clib.cairo_font_options_set_subpixel_order(
                self.fontoptions, self.opts.subpixel_order.value
            )

        if self.opts.hint_metrics != HintMetrics.DEFAULT:
            clib.cairo_font_options_set_hint_metrics(
                self.fontoptions, self.opts.hint_metrics.value
            )

        if self.opts.antialias != Antialias.DEFAULT:
            clib.cairo_font_options_set_antialias(
                self.fontoptions, self.opts.antialias.value
            )

        self.context = ffi.gc(
            clib.pango_font_map_create_context(self.fontmap), clib.g_object_unref
        )
        clib.pango_cairo_context_set_font_options(self.context, self.fontoptions)

        self.language = clib.pango_language_from_string(b"en-us")
        clib.pango_context_set_language(self.context, self.language)
        clib.pango_context_set_base_dir(self.context, clib.PANGO_DIRECTION_LTR)
        clib.pango_context_set_base_gravity(self.context, clib.PANGO_GRAVITY_SOUTH)
        clib.pango_context_set_gravity_hint(
            self.context, clib.PANGO_GRAVITY_HINT_NATURAL
        )

    def destroy(self):
        ffi.release(self.context)
        self.context = None
        ffi.release(self.fontoptions)
        self.fontoptions = None

    def set_fontmap_resolution(self, dpi):
        cast = ffi.cast("PangoCairoFontMap *", self.fontmap)
        clib.pango_cairo_font_map_set_resolution(cast, dpi)

    def create_surface(self):
        size = self.opts.screen_size
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

    def _set_cairo_transform(self, cairo, matrix):
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
            clib.pango_cairo_update_context(cairo, self.context)

    def calculate_line_height(self, font: str):
        self.set_fontmap_resolution(self.opts.dpi)
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

    def render_border(self, surface) -> Size:
        with ffi.gc(clib.cairo_create(surface), clib.cairo_destroy) as cairo:
            # ensure identity matrix
            self._set_cairo_transform(cairo, None)
            clib.cairo_set_line_width(cairo, 1)
            clib.cairo_rectangle(
                cairo,
                1.5,
                1.5,
                self.opts.screen_size.width - 2,
                self.opts.screen_size.height - 2,
            )
            clib.cairo_stroke(cairo)
            size = self.opts.screen_size
        return size

    def render(self, surface, render_opts: RenderOpts) -> Size:
        self.set_fontmap_resolution(self.opts.dpi)
        with ffi.gc(clib.cairo_create(surface), clib.cairo_destroy) as cairo:
            # sets identity matrix
            self._set_cairo_transform(cairo, None)

            if render_opts.clear_before_render:
                self._paint_background(cairo)

            clib.cairo_set_operator(cairo, clib.CAIRO_OPERATOR_OVER)
            clib.cairo_set_source_rgba(cairo, 0, 0, 0, 1)

            size = self._do_output(cairo, render_opts)

            if render_opts.draw_border:
                size = self.render_border(surface)

        return size

    def _make_font_description(self, font: str):
        # https://gnome.pages.gitlab.gnome.org/pango/Pango/struct.FontDescription.html
        # perhaps we should use pango_font_description_new instead, and the various set functions
        return ffi.gc(
            clib.pango_font_description_from_string(font.encode("utf-8")),
            clib.pango_font_description_free,
        )

    def _do_output(self, cairo, render_opts: RenderOpts) -> Size:
        orig_matrix = ffi.gc(
            clib.pango_matrix_copy(clib.pango_context_get_matrix(self.context)),
            clib.pango_matrix_free,
        )
        #   /* If the backend sets an all-zero matrix on the context,
        #    * means that it doesn't support transformations.
        #    */
        supports_matrix = not orig_matrix or (
            orig_matrix.xx != 0
            or orig_matrix.xy != 0
            or orig_matrix.yx != 0
            or orig_matrix.yy != 0
            or orig_matrix.x0 != 0
            or orig_matrix.y0 != 0
        )
        # We'll just assume supports_matrix is true, tbh
        if not supports_matrix:
            raise Exception("backend doesn't support matrix")

        # start as identity
        # xx, xy, yx, yy, x0, y0
        # x_device = x_user * matrix->xx + y_user * matrix->xy + matrix->x0;
        # y_device = x_user * matrix->yx + y_user * matrix->yy + matrix->y0;
        with ffi.new("PangoMatrix *", [1, 0, 0, 1, 0, 0]) as matrix:
            matrix.x0 = render_opts.margin_l
            matrix.y0 = render_opts.margin_t

            clib.pango_context_set_matrix(self.context, matrix)
            self._set_cairo_transform(cairo, matrix)

        with self._make_layout(render_opts) as layout:
            rendered_size = self._output_body(layout, cairo)

        size_with_margin = Size(
            width=rendered_size.width + render_opts.margin_l + render_opts.margin_r,
            height=rendered_size.height + render_opts.margin_t + render_opts.margin_b,
        )

        clib.pango_context_set_matrix(self.context, orig_matrix)
        ffi.release(orig_matrix)
        return size_with_margin

    def _make_layout(self, render_opts: RenderOpts):
        layout = ffi.gc(clib.pango_layout_new(self.context), clib.g_object_unref)
        utf8bytes = render_opts.text.encode("utf-8")
        if render_opts.markup:
            # -1 means null-terminated
            clib.pango_layout_set_markup(layout, utf8bytes, -1)
        else:
            clib.pango_layout_set_text(layout, utf8bytes, -1)

        # don't try auto-detecting text direction
        clib.pango_layout_set_auto_dir(layout, False)
        clib.pango_layout_set_ellipsize(layout, clib.PANGO_ELLIPSIZE_NONE)
        clib.pango_layout_set_justify(layout, render_opts.justify)
        clib.pango_layout_set_single_paragraph_mode(layout, render_opts.single_par)
        clib.pango_layout_set_wrap(layout, render_opts.wrap)

        with self._make_font_description(render_opts.font) as font_description:
            clib.pango_layout_set_font_description(layout, font_description)

        clib.pango_layout_set_width(
            layout,
            (
                self.opts.screen_size.width
                - (render_opts.margin_l + render_opts.margin_r)
            )
            * clib.PANGO_SCALE,
        )

        clib.pango_layout_set_alignment(layout, render_opts.alignment)

        return layout

    def _output_body(self, layout, cairo) -> Size:
        logical_rect = ffi.new("PangoRectangle *")
        clib.pango_layout_get_pixel_extents(layout, ffi.NULL, logical_rect)

        clib.cairo_save(cairo)
        clib.cairo_translate(cairo, 0, 0)

        clib.cairo_move_to(cairo, 0, 0)
        clib.pango_cairo_show_layout(cairo, layout)

        clib.cairo_restore(cairo)

        clib.cairo_surface_flush(clib.cairo_get_target(cairo))

        logical_rect_width = logical_rect.x + logical_rect.width
        pango_layout_width = clib.pango_pixels(clib.pango_layout_get_width(layout))

        # pango_layout_get_height is always zero, since ellipsization is disabled.
        logical_rect_height = logical_rect.y + logical_rect.height

        return Size(
            width=max(logical_rect_width, pango_layout_width),
            height=logical_rect_height,
        )

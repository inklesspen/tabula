from __future__ import annotations

import typing
from contextlib import AbstractContextManager, contextmanager

import msgspec

from ..commontypes import Point, Rect, Size
from ._cairopango import ffi, lib  # type: ignore
from .rendertypes import CairoColor, Rendered

cairo_surface_t_p = typing.NewType("cairo_surface_t_p", typing.Any)

glib_alloc = ffi.new_allocator(alloc=lib.g_malloc0, free=lib.g_free, should_clear_after_alloc=False)


class CairoSurfaceReference(msgspec.Struct, frozen=True, kw_only=True):
    surface: cairo_surface_t_p
    size: Size

    def get_image_bytes(self) -> bytes:
        dataptr = lib.cairo_image_surface_get_data(self.surface)
        buf = ffi.buffer(dataptr, self.size.total())
        return bytes(buf)

    def get_rendered(self, origin: Point):
        return Rendered(image=self.get_image_bytes(), extent=Rect(origin=origin, spread=self.size))

    @classmethod
    def from_cairo(cls, cairo: Cairo):
        surface = cairo_surface_t_p(ffi.gc(lib.cairo_surface_reference(cairo.surface), lib.cairo_surface_destroy))
        return cls(surface=surface, size=cairo.size)


class Cairo(AbstractContextManager):
    surface: cairo_surface_t_p

    def __init__(self, surface_size: Size):
        self.size = surface_size

    def setup(self):
        self.surface = cairo_surface_t_p(
            ffi.gc(lib.cairo_image_surface_create(lib.CAIRO_FORMAT_A8, self.size.width, self.size.height), lib.cairo_surface_destroy)
        )
        self.context = ffi.gc(lib.cairo_create(self.surface), lib.cairo_destroy)

    def teardown(self):
        ffi.release(self.context)
        ffi.release(self.surface)
        del self.context
        del self.surface

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.teardown()

    @contextmanager
    def cairo_save_restore(self):
        lib.cairo_save(self.context)
        try:
            yield
        finally:
            lib.cairo_restore(self.context)

    def fill_with_color(self, color: CairoColor):
        self.set_draw_color(color)
        lib.cairo_paint(self.context)

    def with_border(self, border_width: int, border_color: CairoColor):
        if not hasattr(self, "surface"):
            raise TypeError("with_border can only be used with an active surface")

        # Draw border
        with self.cairo_save_restore():
            lib.cairo_new_path(self.context)
            lib.cairo_rectangle(self.context, 0, 0, self.size.width, self.size.height)
            self.set_draw_color(border_color)
            lib.cairo_set_line_width(self.context, border_width)
            lib.cairo_stroke(self.context)

        # Return sub-surface
        sub_size = Size(
            width=self.size.width - (border_width * 2),
            height=self.size.height - (border_width * 2),
        )
        sub_cairo = type(self)(sub_size)
        sub_cairo.surface = ffi.gc(
            lib.cairo_surface_create_for_rectangle(
                self.surface,
                border_width,
                border_width,
                sub_size.width,
                sub_size.height,
            ),
            lib.cairo_surface_destroy,
            size=sub_size.total(),
        )
        sub_cairo.context = ffi.gc(lib.cairo_create(sub_cairo.surface), lib.cairo_destroy)
        return sub_cairo

    def set_draw_color(self, color: CairoColor):
        lib.cairo_set_operator(self.context, lib.CAIRO_OPERATOR_SOURCE)
        lib.cairo_set_source_rgba(self.context, 0, 0, 0, int(color))

    def set_line_width(self, line_width: float):
        lib.cairo_set_line_width(self.context, line_width)

    @property
    def current_point(self):
        if not lib.cairo_has_current_point(self.context):
            return None
        point_p = glib_alloc("double[]", 2)
        lib.cairo_get_current_point(self.context, point_p, point_p + 1)
        return Point(x=point_p[0], y=point_p[1])

    def move_to(self, point: Point):
        lib.cairo_move_to(self.context, point.x, point.y)

    def line_to(self, point: Point):
        lib.cairo_line_to(self.context, point.x, point.y)

    def roundrect(self, *, rect: Rect, radius: float, line_width: float = 2.0, fill_color=None, stroke_color=CairoColor.BLACK):
        colormapping = {None: lib.DRAW_COLOR_NONE, CairoColor.BLACK: lib.DRAW_COLOR_BLACK, CairoColor.WHITE: lib.DRAW_COLOR_WHITE}
        with glib_alloc(
            "cairo_rectangle_t *", {"x": rect.origin.x, "y": rect.origin.y, "width": rect.spread.width, "height": rect.spread.height}
        ) as c_rect:
            lib.draw_roundrect(self.context, c_rect, radius, line_width, colormapping[fill_color], colormapping[stroke_color])

    def draw_path(self):
        lib.cairo_stroke(self.context)

    def paste_other(self, other: Cairo | CairoSurfaceReference, location: Point, other_rect: Rect):
        with self.cairo_save_restore():
            lib.cairo_set_operator(self.context, lib.CAIRO_OPERATOR_SOURCE)
            offset = location - other_rect.origin
            lib.cairo_set_source_surface(self.context, other.surface, offset.x, offset.y)
            lib.cairo_rectangle(
                self.context,
                location.x,
                location.y,
                other_rect.spread.width,
                other_rect.spread.height,
            )
            lib.cairo_fill(self.context)

    def get_image_bytes(self) -> bytes:
        dataptr = lib.cairo_image_surface_get_data(self.surface)
        buf = ffi.buffer(dataptr, self.size.total())
        return bytes(buf)

    def get_rendered(self, origin: Point):
        return Rendered(image=self.get_image_bytes(), extent=Rect(origin=origin, spread=self.size))

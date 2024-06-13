import collections.abc
from contextlib import AbstractContextManager, contextmanager
import math

from ..commontypes import Size, Rect, Point
from ._cairopango import ffi, lib as clib  # type: ignore
from .rendertypes import CairoOp, CairoColor, CairoPathOp, Rendered


class Cairo(AbstractContextManager):
    def __init__(self, surface_size: Size):
        self.size = surface_size

    def setup(self):
        self.surface = ffi.gc(
            clib.cairo_image_surface_create(clib.CAIRO_FORMAT_A8, self.size.width, self.size.height),
            clib.cairo_surface_destroy,
            size=self.size.total(),
        )
        self.context = ffi.gc(clib.cairo_create(self.surface), clib.cairo_destroy)

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
        clib.cairo_save(self.context)
        try:
            yield
        finally:
            clib.cairo_restore(self.context)

    def fill_with_color(self, color: CairoColor):
        self.set_draw_color(color)
        clib.cairo_paint(self.context)

    def with_border(self, border_width: int, border_color: CairoColor):
        if not hasattr(self, "surface"):
            raise TypeError("with_border can only be used with an active surface")

        # Draw border
        with self.cairo_save_restore():
            clib.cairo_new_path(self.context)
            clib.cairo_rectangle(self.context, 0, 0, self.size.width, self.size.height)
            self.set_draw_color(border_color)
            clib.cairo_set_line_width(self.context, border_width)
            clib.cairo_stroke(self.context)

        # Return sub-surface
        sub_size = Size(
            width=self.size.width - (border_width * 2),
            height=self.size.height - (border_width * 2),
        )
        sub_cairo = type(self)(sub_size)
        sub_cairo.surface = ffi.gc(
            clib.cairo_surface_create_for_rectangle(
                self.surface,
                border_width,
                border_width,
                sub_size.width,
                sub_size.height,
            ),
            clib.cairo_surface_destroy,
            size=sub_size.total(),
        )
        sub_cairo.context = ffi.gc(clib.cairo_create(sub_cairo.surface), clib.cairo_destroy)
        return sub_cairo

    def set_draw_color(self, color: CairoColor):
        clib.cairo_set_operator(self.context, clib.CAIRO_OPERATOR_SOURCE)
        clib.cairo_set_source_rgba(self.context, 0, 0, 0, int(color))

    def set_line_width(self, line_width: float):
        clib.cairo_set_line_width(self.context, line_width)

    @property
    def current_point(self):
        if clib.cairo_has_current_point(self.context):
            xp = ffi.new("double *")
            yp = ffi.new("double *")
            clib.cairo_get_current_point(self.context, xp, yp)
            return Point(x=xp[0], y=yp[0])

    def move_to(self, point: Point):
        clib.cairo_move_to(self.context, point.x, point.y)

    def line_to(self, point: Point):
        clib.cairo_line_to(self.context, point.x, point.y)

    def roundrect(
        self,
        rect: Rect,
        radius: float,
        line_width: float = 2.0,
        path_ops: collections.abc.Sequence[CairoPathOp] = (CairoPathOp(op=CairoOp.STROKE, color=CairoColor.BLACK),),
    ):
        # This basically just draws the corners, and relies on cairo_arc to draw line segments connecting them.
        # Angles are given in radians; see https://www.cairographics.org/manual/cairo-Paths.html#cairo-arc for more info.
        clib.cairo_new_sub_path(self.context)
        # upper left
        clib.cairo_arc(
            self.context,
            rect.origin.x + radius,
            rect.origin.y + radius,
            radius,
            math.radians(180),
            math.radians(270),
        )
        # upper right
        clib.cairo_arc(
            self.context,
            rect.origin.x + rect.spread.width - radius,
            rect.origin.y + radius,
            radius,
            math.radians(270),
            math.radians(0),
        )
        # lower right
        clib.cairo_arc(
            self.context,
            rect.origin.x + rect.spread.width - radius,
            rect.origin.y + rect.spread.height - radius,
            radius,
            math.radians(0),
            math.radians(90),
        )
        # lower left
        clib.cairo_arc(
            self.context,
            rect.origin.x + radius,
            rect.origin.y + rect.spread.height - radius,
            radius,
            math.radians(90),
            math.radians(180),
        )
        clib.cairo_close_path(self.context)
        path_data = ffi.gc(clib.cairo_copy_path(self.context), clib.cairo_path_destroy)
        clib.cairo_set_line_width(self.context, line_width)
        for i, path_op in enumerate(path_ops):
            self.set_draw_color(path_op.color)
            is_last = i == len(path_ops) - 1
            match path_op.op:
                case CairoOp.STROKE:
                    verb = clib.cairo_stroke if is_last else clib.cairo_stroke_preserve
                case CairoOp.FILL:
                    verb = clib.cairo_fill if is_last else clib.cairo_fill_preserve
            verb(self.context)
        return path_data

    def draw_path(self):
        clib.cairo_stroke(self.context)

    def paste_other(self, other: "Cairo", location: Point, other_rect: Rect):
        with self.cairo_save_restore():
            clib.cairo_set_operator(self.context, clib.CAIRO_OPERATOR_SOURCE)
            offset = location - other_rect.origin
            clib.cairo_set_source_surface(self.context, other.surface, offset.x, offset.y)
            clib.cairo_rectangle(
                self.context,
                location.x,
                location.y,
                other_rect.spread.width,
                other_rect.spread.height,
            )
            clib.cairo_fill(self.context)

    def get_image_bytes(self) -> bytes:
        dataptr = clib.cairo_image_surface_get_data(self.surface)
        buf = ffi.buffer(dataptr, self.size.total())
        return bytes(buf)

    def get_rendered(self, origin: Point):
        return Rendered(image=self.get_image_bytes(), extent=Rect(origin=origin, spread=self.size))

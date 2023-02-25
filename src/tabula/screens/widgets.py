import enum
import math

from typing import Any, Optional

import attrs

from ..commontypes import Size, Rect, Point
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from ..rendering.rendertypes import (
    CairoPathOp,
    CairoOp,
    CairoColor,
    Alignment,
    Rendered,
)


class ButtonState(enum.Enum):
    NORMAL = enum.auto()
    PRESSED = enum.auto()
    SELECTED = enum.auto()


@attrs.define(init=False)
class Button:
    normal: Cairo
    inverted: Cairo
    outlined: Cairo
    bounds: Rect
    button_value: Any
    static_state: ButtonState
    pressed: bool

    def __init__(
        self,
        pango: Pango,
        button_text: str,
        button_size: Size,
        corner_radius: int,
        font: str,
        screen_location: Point,
        button_value: Optional[Any] = None,
        align_baseline: bool = False,
    ):
        if button_value is None:
            button_value = button_text
        layout = PangoLayout(
            pango=pango, width=button_size.width, alignment=Alignment.CENTER
        )
        layout.set_font(font)
        layout.set_content(button_text)
        rects = layout.get_layout_rects()
        if align_baseline:
            text_y = math.floor(
                button_size.height / 2 - rects.logical.spread.height / 2
            )
        else:
            text_y = math.floor(
                button_size.height / 2
                - rects.ink.origin.y
                - rects.ink.spread.height / 2
            )
        text_origin = Point(x=0, y=text_y)

        roundrect_bounds = Rect(
            origin=Point(x=2, y=2),
            spread=button_size - Size(width=4, height=4),
        )

        normal = Button._draw_button(
            button_size,
            layout,
            roundrect_bounds,
            corner_radius,
            text_origin,
            inverted=False,
        )
        inverted = Button._draw_button(
            button_size,
            layout,
            roundrect_bounds,
            corner_radius,
            text_origin,
            inverted=True,
        )
        outlined = Button._draw_button(
            button_size,
            layout,
            roundrect_bounds,
            corner_radius,
            text_origin,
            inverted=True,
        )
        outline_bounds = Rect(
            origin=Point(x=4, y=4), spread=button_size - Size(width=8, height=8)
        )
        outlined.roundrect(
            rect=outline_bounds,
            radius=corner_radius,
            line_width=2,
            path_ops=(CairoPathOp(op=CairoOp.STROKE, color=CairoColor.WHITE),),
        )
        origin = screen_location if screen_location is not None else Point.zeroes()
        self.__attrs_init__(
            normal=normal,
            inverted=inverted,
            outlined=outlined,
            bounds=Rect(origin=origin, spread=button_size),
            button_value=button_value,
            static_state=ButtonState.NORMAL,
            pressed=False,
        )

    @property
    def state(self):
        if self.pressed:
            return ButtonState.PRESSED
        return self.static_state

    def update_static_state(self, new_static_state):
        current = self.static_state
        self.static_state = new_static_state
        render_needed = current is not new_static_state and not self.pressed
        return render_needed

    def _surface_for_state(self, state: Optional[ButtonState] = None):
        if state is None:
            state = self.state
        match state:
            case ButtonState.NORMAL:
                return self.normal
            case ButtonState.SELECTED:
                return self.outlined
            case ButtonState.PRESSED:
                return self.inverted

    def paste_onto_cairo(self, cairo: Cairo, state: Optional[ButtonState] = None):
        cairo.paste_other(
            self._surface_for_state(state),
            self.bounds.origin,
            Rect(origin=Point.zeroes(), spread=self.bounds.spread),
        )

    def render(self, state: Optional[ButtonState] = None):
        return Rendered(
            image=self._surface_for_state(state).get_image_bytes(), extent=self.bounds
        )

    def __contains__(self, item):
        if not isinstance(item, Point):
            return NotImplemented
        return item in self.bounds

    @staticmethod
    def _draw_button(
        button_size: Size,
        layout: PangoLayout,
        rect: Rect,
        radius: int,
        layout_origin: Point,
        inverted: bool,
    ) -> Cairo:
        cairo = Cairo(button_size)
        cairo.setup()
        cairo.fill_with_color(CairoColor.WHITE)
        cairo.roundrect(
            rect=rect,
            radius=radius,
            line_width=2,
            path_ops=(
                CairoPathOp(op=CairoOp.FILL, color=CairoColor.BLACK),
                CairoPathOp(op=CairoOp.STROKE, color=CairoColor.BLACK),
            )
            if inverted
            else (
                CairoPathOp(op=CairoOp.FILL, color=CairoColor.WHITE),
                CairoPathOp(op=CairoOp.STROKE, color=CairoColor.BLACK),
            ),
        )

        cairo.move_to(layout_origin)
        cairo.set_draw_color(CairoColor.WHITE if inverted else CairoColor.BLACK)
        layout.render(cairo)
        cairo.set_draw_color(CairoColor.BLACK)
        return cairo

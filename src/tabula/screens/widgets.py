import enum
import math

from typing import Any, Optional, Protocol

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


class DrawCallback(Protocol):
    def __call__(self, cairo: Cairo): ...


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
    state: ButtonState
    last_rendered_state: Optional[ButtonState]

    def __init__(
        self,
        pango: Pango,
        button_text: str,
        button_size: Size,
        corner_radius: int,
        font: str,
        screen_location: Point,
        state=ButtonState.NORMAL,
        button_value: Optional[Any] = None,
        align_baseline: bool = False,
        draw_callback: Optional[DrawCallback] = None,
    ):
        if button_value is None:
            button_value = button_text
        layout = PangoLayout(pango=pango, width=button_size.width, alignment=Alignment.CENTER)
        layout.set_font(font)
        layout.set_content(button_text)
        rects = layout.get_layout_rects()
        if align_baseline:
            text_y = math.floor(button_size.height / 2 - rects.logical.spread.height / 2)
        else:
            text_y = math.floor(button_size.height / 2 - rects.ink.origin.y - rects.ink.spread.height / 2)
        text_origin = Point(x=0, y=text_y)

        roundrect_bounds = Rect(
            origin=Point(x=2, y=2),
            spread=button_size - Size(width=4, height=4),
        )

        normal = Button._draw_button(
            button_size, layout, roundrect_bounds, corner_radius, text_origin, inverted=False, draw_callback=draw_callback
        )
        inverted = Button._draw_button(
            button_size, layout, roundrect_bounds, corner_radius, text_origin, inverted=True, draw_callback=draw_callback
        )
        outlined = Button._draw_button(
            button_size, layout, roundrect_bounds, corner_radius, text_origin, inverted=True, draw_callback=draw_callback
        )
        outline_bounds = Rect(origin=Point(x=4, y=4), spread=button_size - Size(width=8, height=8))
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
            state=state,
            last_rendered_state=None,
        )

    def needs_render(self, override_state: Optional[ButtonState] = None):
        state = self._render_state(override_state)
        return state is not self.last_rendered_state

    def update_state(self, new_state):
        self.state = new_state
        return self.needs_render()

    def _render_state(self, override_state: Optional[ButtonState] = None):
        if override_state is not None:
            return override_state
        return self.state

    def _surface_for_state(self, state: ButtonState):
        match state:
            case ButtonState.NORMAL:
                return self.normal
            case ButtonState.SELECTED:
                return self.outlined
            case ButtonState.PRESSED:
                return self.inverted

    def paste_onto_cairo(self, cairo: Cairo, override_state: Optional[ButtonState] = None):
        state = self._render_state(override_state)
        cairo.paste_other(
            self._surface_for_state(state),
            self.bounds.origin,
            Rect(origin=Point.zeroes(), spread=self.bounds.spread),
        )
        self.last_rendered_state = state

    def render(self, override_state: Optional[ButtonState] = None):
        state = self._render_state(override_state)
        rendered = Rendered(image=self._surface_for_state(state).get_image_bytes(), extent=self.bounds)
        self.last_rendered_state = state
        return rendered

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
        draw_callback: Optional[DrawCallback],
    ) -> Cairo:
        cairo = Cairo(button_size)
        cairo.setup()
        cairo.fill_with_color(CairoColor.WHITE)
        cairo.roundrect(
            rect=rect,
            radius=radius,
            line_width=2,
            path_ops=(
                (
                    CairoPathOp(op=CairoOp.FILL, color=CairoColor.BLACK),
                    CairoPathOp(op=CairoOp.STROKE, color=CairoColor.BLACK),
                )
                if inverted
                else (
                    CairoPathOp(op=CairoOp.FILL, color=CairoColor.WHITE),
                    CairoPathOp(op=CairoOp.STROKE, color=CairoColor.BLACK),
                )
            ),
        )

        cairo.move_to(layout_origin)
        cairo.set_draw_color(CairoColor.WHITE if inverted else CairoColor.BLACK)
        layout.render(cairo)
        if draw_callback is not None:
            draw_callback(cairo)
        cairo.set_draw_color(CairoColor.BLACK)
        return cairo

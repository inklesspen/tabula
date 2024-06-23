from __future__ import annotations

import dataclasses
import enum
import math

from typing import Protocol, TypedDict, NotRequired, TYPE_CHECKING

from ..commontypes import Size, Rect, Point
from ..rendering.cairo import Cairo
from ..rendering.pango import Pango, PangoLayout
from ..rendering.rendertypes import (
    CairoPathOp,
    CairoOp,
    CairoColor,
    Alignment,
    WrapMode,
    Rendered,
)

if TYPE_CHECKING:
    from typing import Any, Optional
    from ..device.hwtypes import Key


@dataclasses.dataclass(kw_only=True)
class Label:
    bounds: Rect
    cairo: Cairo

    @classmethod
    def create(
        cls,
        *,
        pango: Pango,
        text: str,
        font: str,
        location: Point,
        size: Size = None,
        width: int = None,
        alignment: Alignment = Alignment.CENTER,
        wrap: WrapMode = WrapMode.WORD_CHAR,
    ):
        layout_width = size.width if size is not None else width
        with PangoLayout(pango=pango, width=layout_width, alignment=alignment, wrap=wrap) as layout:
            layout.set_font(font)
            layout.set_content(text)
            if size is None:
                if width is None:
                    raise ValueError("Must specify either size or width")
                rects = layout.get_layout_rects()
                height = rects.logical.spread.height
                size = Size(width=width, height=height)
            cairo = Cairo(size)
            cairo.setup()
            cairo.fill_with_color(CairoColor.WHITE)
            cairo.set_draw_color(CairoColor.BLACK)
            cairo.move_to(Point.zeroes())
            layout.render(cairo)
        return cls(bounds=Rect(origin=location, spread=size), cairo=cairo)

    def paste_onto_cairo(self, cairo: Cairo):
        cairo.paste_other(self.cairo, self.bounds.origin, Rect(origin=Point.zeroes(), spread=self.bounds.spread))


class DrawCallback(Protocol):
    def __call__(self, cairo: Cairo): ...


class ButtonState(enum.Enum):
    NORMAL = enum.auto()
    PRESSED = enum.auto()
    SELECTED = enum.auto()


@dataclasses.dataclass(kw_only=True)
class Button:
    normal: Cairo
    inverted: Cairo
    outlined: Cairo
    bounds: Rect
    button_value: Any
    state: ButtonState
    last_rendered_state: Optional[ButtonState]
    hotkey: Optional[Key]

    @classmethod
    def create(
        cls,
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
        hotkey: Optional[Key] = None,
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
        return cls(
            normal=normal,
            inverted=inverted,
            outlined=outlined,
            bounds=Rect(origin=origin, spread=button_size),
            button_value=button_value,
            state=state,
            last_rendered_state=None,
            hotkey=hotkey,
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


class ButtonSpec(TypedDict):
    button_text: str
    font: NotRequired[str]
    button_value: NotRequired[Any]
    draw_callback: NotRequired[DrawCallback]
    hotkey: NotRequired[Key]
    state: NotRequired[ButtonState]


def make_button_row(
    *button_spec_groups: tuple[ButtonSpec],
    button_size: Size,
    corner_radius: int,
    button_y: int | float,
    row_width: int | float,
    pango: Pango,
    default_font: Optional[str] = None,
    align_baseline: bool = False,
) -> list[Button]:
    # big space between groups, small space between items within groups. maybe divide up the screen width by the number of groups?
    # that doesn't play well when we haven't got even numbers though
    buffer = button_size.width * 2 / 3
    group_widths: list[int | float] = []
    for group in button_spec_groups:
        if len(group) == 0:
            group_widths.append(0)
            continue
        group_widths.append(button_size.width * len(group) + buffer * (len(group) - 1))
        for button_spec in group:
            if button_spec.get("font") is None and default_font is None:
                raise ValueError("Cannot omit button font if default_font is None")
    total_button_widths = sum(group_widths)
    min_inter_group_buffer = buffer * (len(button_spec_groups) - 1)
    if total_button_widths + min_inter_group_buffer > row_width:
        raise ValueError(f"Cannot fit this many buttons (total width {total_button_widths}) into row width {row_width}.")

    # it's N rather than N-1 because we want half a buffer at the beginning and half a buffer at the end.
    inter_group_buffer = (row_width - total_button_widths) / len(button_spec_groups)
    buttons = []
    button_x = inter_group_buffer / 2
    for group in button_spec_groups:
        if len(group) == 0:
            continue
        for button_spec in group:
            buttons.append(
                Button.create(
                    pango=pango,
                    button_text=button_spec["button_text"],
                    button_size=button_size,
                    corner_radius=corner_radius,
                    font=button_spec.get("font", default_font),
                    screen_location=Point(button_x, button_y),
                    button_value=button_spec.get("button_value"),
                    align_baseline=align_baseline,
                    draw_callback=button_spec.get("draw_callback"),
                    hotkey=button_spec.get("hotkey"),
                    state=button_spec.get("state", ButtonState.NORMAL),
                )
            )
            button_x += button_size.width
            button_x += buffer
        # remove the buffer added after the last button in the group
        button_x -= buffer
        # but add the inter-group buffer
        button_x += inter_group_buffer
    return buttons


def _make_centered_button_stack_positions(
    *specs: ButtonSpec,
    button_size: Size,
    available_space: Size,
) -> list[Point]:
    row_buffer = button_size.height * 2 / 3
    height_needed = button_size.height * len(specs) + row_buffer * len(specs)
    if height_needed > available_space.height:
        raise ValueError("Not enough available height for a single centered stack")

    # screen_size = self.screen_info.size
    # button_x = math.floor((screen_size.width - self.button_size.width) / 2)
    # button_total_height = self.button_size.height * len(buttons)
    # whitespace_height = screen_size.height - button_total_height
    # skip_height = math.floor(whitespace_height / (len(buttons) + 1))
    # button_y = skip_height

    # for button in buttons:
    #     button["point"] = Point(x=button_x, y=button_y)
    #     button_y += self.button_size.height + skip_height

    button_x = available_space.width / 2 - button_size.width / 2
    button_y = row_buffer / 2
    button_positions = []
    for _ in specs:
        button_positions.append(Point(x=math.floor(button_x), y=math.floor(button_y)))
        button_y += button_size.height + row_buffer
    return button_positions


def _make_centered_row_button_stack_positions(
    *specs: ButtonSpec,
    button_size: Size,
    available_space: Size,
) -> list[Point]:
    col_buffer = button_size.width * 2 / 3
    row_buffer = button_size.height * 2 / 3
    buffer = min(col_buffer, row_buffer)
    left_x = buffer / 2
    rows = []
    current_row = None
    for spec in specs:
        if current_row is None:
            current_row = []
            rows.append(current_row)
            button_x = left_x
        current_row.append(spec)
        button_x += button_size.width
        if (button_x + left_x) >= available_space.width:
            current_row = None
        else:
            button_x += buffer
    needed_height = (button_size.height + buffer) * len(rows)
    if needed_height > available_space.height:
        raise ValueError("Not enough available height for the necessary number of rows")

    button_positions = []
    button_y = buffer / 2
    for current_row in rows:
        needed_width = len(current_row) * (button_size.width + buffer) - buffer
        button_x = (available_space.width - needed_width) // 2
        for _ in current_row:
            button_positions.append(Point(x=math.floor(button_x), y=math.floor(button_y)))
            button_x += button_size.width + buffer
        button_y += button_size.height + buffer
    return button_positions


def _make_columnular_button_stack_positions(
    *specs: ButtonSpec,
    button_size: Size,
    available_space: Size,
) -> list[Point]:
    col_buffer = button_size.width * 2 / 3
    row_buffer = button_size.height * 2 / 3
    buffer = min(col_buffer, row_buffer)

    top_y = buffer / 2
    columns = []
    current_column = None
    for spec in specs:
        if current_column is None:
            current_column = []
            columns.append(current_column)
            button_y = top_y
        current_column.append(spec)
        button_y += button_size.height
        if (button_y + top_y) >= available_space.height:
            current_column = None
        else:
            button_y += buffer
    needed_width = (button_size.width + buffer) * len(columns)
    if needed_width > available_space.width:
        raise ValueError("Not enough available width for the necessary number of columns")

    button_positions = []
    button_x = buffer / 2
    for current_column in columns:
        button_y = top_y
        for _ in current_column:
            button_positions.append(Point(x=math.floor(button_x), y=math.floor(button_y)))
            button_y += button_size.height + buffer
        button_x += button_size.width + buffer
    return button_positions


def make_button_stack(
    *specs: ButtonSpec,
    button_size: Size,
    corner_radius: int,
    screen_area: Rect,
    pango: Pango,
    default_font: Optional[str] = None,
    align_baseline: bool = False,
) -> list[Button]:
    # col_buffer = button_size.width * 2 / 3
    # row_buffer = button_size.height * 2 / 3
    # try one centered stack first
    positions = None
    place_error = None
    for placer in [
        _make_centered_button_stack_positions,
        _make_centered_row_button_stack_positions,
        _make_columnular_button_stack_positions,
    ]:
        try:
            positions = placer(*specs, button_size=button_size, available_space=screen_area.spread)
            if positions is not None:
                break
        except ValueError as e:
            place_error = e
    if positions is None:
        raise place_error
    return [
        Button.create(
            pango=pango,
            button_text=button_spec["button_text"],
            button_size=button_size,
            corner_radius=corner_radius,
            font=button_spec.get("font", default_font),
            screen_location=position + screen_area.origin,
            button_value=button_spec.get("button_value"),
            align_baseline=align_baseline,
            draw_callback=button_spec.get("draw_callback"),
            hotkey=button_spec.get("hotkey"),
            state=button_spec.get("state", ButtonState.NORMAL),
        )
        for button_spec, position in zip(specs, positions)
    ]

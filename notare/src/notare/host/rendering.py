# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import typing

import attr
import numpy as np
import numpy.typing as npt

import stilus.markdown
import stilus.pango_render
import stilus.types

from .types import (
    Renderable,
    ArrayRect,
)
from ..protocol import Framelet, Rect

# https://en.wikipedia.org/wiki/Macron_below
# https://en.wikipedia.org/wiki/Underscore
CURSOR = '<span alpha="50%">_</span>'
FONT = "iA Writer Quattro V 8"


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class RenderPara:
    rendered: npt.ArrayLike
    size: stilus.types.Size


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class LaidOutPara:
    index: int
    screen_top: int
    screen_bottom: int


def bbox(img: npt.ArrayLike) -> ArrayRect:
    rows = np.any(img, axis=1)
    cols = np.any(img, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    return ArrayRect(top=rmin, bottom=rmax, left=cmin, right=cmax)


class Screen:
    def __init__(self, screen_size: stilus.types.Size, dpi: int):
        self.screen_size = screen_size
        self.renderer = stilus.pango_render.Renderer(
            screen_size=self.screen_size, dpi=dpi
        )
        self.cursor_y = self.screen_size.height // 2
        self.renders: typing.List[RenderPara] = []

    def set_font(self, font: str):
        # TODO: trigger a rerender if we change after the start
        self.font = font
        self.skip_height = int(self.renderer.instance.calculate_line_height(font))

    @staticmethod
    def set_into(list, index, item):
        if index >= len(list):
            list.append(item)
        else:
            list[index] = item

    def render_update(self, renderables: typing.List[Renderable]):
        before_render = tuple(self.renders)
        for renderable in renderables:
            markup = renderable.markup
            if renderable.has_cursor:
                markup += CURSOR
            (buf, render_size) = self.renderer.render_to_bytes(markup, self.font)
            new_rendered = np.ndarray(
                render_size.as_numpy_shape(), dtype=np.uint8, buffer=buf
            )
            self.set_into(
                self.renders,
                renderable.index,
                RenderPara(rendered=new_rendered, size=render_size),
            )

        # It's possible this might fail to reflow if the font has changed
        # but all the paragraph heights remain the same.
        need_to_reflow = (len(self.renders) > len(before_render)) or any(
            [
                before.size != after.size
                for before, after in zip(before_render, self.renders)
            ]
        )
        if not need_to_reflow:
            # Only the last paragraph needs to be rerendered.
            relative_top = self.cursor_y - self.renders[-1].size.height
            old_image = before_render[-1].rendered
            new_image = self.renders[-1].rendered
            # if the images are identical after all, bbox will error
            # this might happen if we load the currently-active session
            # in that case, there's nothing to send.
            if old_image.data == new_image.data:
                return []
            render_diff = new_image - old_image
            changed_box = bbox(render_diff)
            changed: npt.ArrayLike = new_image[
                changed_box.top : changed_box.bottom,
                changed_box.left : changed_box.right,
            ]
            framelet = Framelet(
                rect=changed_box.to_protocol_rect(relative_top),
                image=Framelet.encode_bytes(changed.tobytes()),
            )

        else:
            # we gotta reflow everything on screen
            laidouts: typing.List[typing.Optional[LaidOutPara]] = [
                None for _ in self.renders
            ]
            current_y = self.cursor_y
            current_i = len(self.renders) - 1
            while current_i >= 0 and current_y >= 0:
                size = self.renders[current_i].size
                top = current_y - size.height
                laidouts[current_i] = LaidOutPara(
                    index=current_i, screen_bottom=current_y, screen_top=top
                )
                current_y -= size.height + self.skip_height
                current_i -= 1

            half_screen = np.full(
                (self.cursor_y, self.screen_size.width), 255, dtype=np.uint8
            )
            for laidout in laidouts:
                if laidout is not None:
                    rendered = self.renders[laidout.index].rendered
                    if laidout.screen_top < 0:
                        half_screen[0 : laidout.screen_bottom] = rendered[
                            -laidout.screen_top :
                        ]
                    else:
                        half_screen[
                            laidout.screen_top : laidout.screen_bottom
                        ] = rendered
            framelet = Framelet(
                rect=Rect(
                    x=0,
                    y=0,
                    width=self.screen_size.width,
                    height=self.cursor_y,
                ),
                image=Framelet.encode_bytes(half_screen.tobytes()),
            )

        return [framelet]


def make_dialog_dimension(screen_dimension: int):
    # round to nearest multiple of 4
    return math.trunc(screen_dimension * 0.2 + 0.5) * 4


# We use a modal dialog to render help and menu screens. The dialog should be 80% of the screen,
# centered (that is, offset by 10% of the screen size), with a 1px border.
# add a border option to pango_render and draw it with cairo! don't try to do it with numpy twiddling
# https://www.cairographics.org/FAQ/#sharp_lines
class ModalDialog:
    def __init__(
        self,
        screen_size: stilus.types.Size,
        dpi: int,
    ):
        self.screen_size = screen_size
        self.dialog_size = stilus.types.Size(
            width=make_dialog_dimension(screen_size.width),
            height=make_dialog_dimension(screen_size.height),
        )
        self.renderer = stilus.pango_render.Renderer(
            screen_size=self.dialog_size, dpi=dpi
        )

    def frame_offset(self) -> stilus.types.Point:
        return stilus.types.Point(
            x=(self.screen_size.width - self.dialog_size.width) // 2,
            y=(self.screen_size.height - self.dialog_size.height) // 2,
        )

    def render_frame(self) -> Framelet:
        frame_offset = self.frame_offset()
        rendered, size = self.renderer.render_border()
        return Framelet(
            rect=Rect(
                x=frame_offset.x, y=frame_offset.y, width=size.width, height=size.height
            ),
            image=Framelet.encode_bytes(rendered),
        )

    def render_header(self) -> Framelet:
        frame_offset = self.frame_offset()
        (buf, render_size) = self.renderer.render_to_bytes(
            markup="Tabula",
            font="Noto Serif Display 12",
            margin_lr=10,
            margin_tb=10,
            alignment=stilus.types.Alignment.CENTER,
        )
        rendered = np.ndarray(render_size.as_numpy_shape(), dtype=np.uint8, buffer=buf)
        cropped: npt.ArrayLike = rendered[10:-10, 10:-10]
        size = stilus.types.Size.from_numpy_shape(cropped.shape)
        return Framelet(
            rect=Rect(
                x=frame_offset.x + (self.dialog_size.width - size.width) // 2,
                y=frame_offset.y + 10,
                width=size.width,
                height=size.height,
            ),
            image=Framelet.encode_bytes(cropped.tobytes()),
        )

    def render_dialog(self, markup, font, margin_lr=10) -> typing.List[Framelet]:
        frame_offset = self.frame_offset()

        frame_op = self.render_frame()
        header_op = self.render_header()
        (buf, render_size) = self.renderer.render_to_bytes(
            markup=markup, font=font, margin_lr=margin_lr, margin_tb=10
        )
        rendered = np.ndarray(render_size.as_numpy_shape(), dtype=np.uint8, buffer=buf)

        cropped: npt.ArrayLike = rendered[10:-10, margin_lr:-margin_lr]
        size = stilus.types.Size.from_numpy_shape(cropped.shape)
        body_op = Framelet(
            rect=Rect(
                x=frame_offset.x + margin_lr,
                y=header_op.rect.y + header_op.rect.height + 14,
                width=size.width,
                height=size.height,
            ),
            image=Framelet.encode_bytes(cropped.tobytes()),
        )
        return [frame_op, header_op, body_op]


# Line 1: Sprint status: timer, wordcount, hotkey reminder
# Line 2: Session wordcount, current time, battery status
class StatusDisplay:
    def __init__(
        self,
        width: int,
        dpi: int,
    ):
        # TODO: use https://github.com/polarsys/b612
        self.font = "Literata-Regular 8"
        line_height = math.ceil(
            stilus.pango_render.Renderer.calculate_line_height(self.font, 300)
        )
        self.status_size = stilus.types.Size(width=width, height=line_height * 3)
        self.renderer = stilus.pango_render.Renderer(
            screen_size=self.status_size, dpi=dpi
        )

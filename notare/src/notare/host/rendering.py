# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import typing

import attr
import numpy as np
import numpy.typing as npt
import trio

import stilus.markdown
import stilus.pango_render
import stilus.types

from .types import (
    Renderable,
    ArrayRect,
)
from ..protocol import (
    Framelet,
    Rect,
)

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
    def __init__(
        self,
        font: str,
        screen_size: stilus.types.Size,
        dpi: int,
        dispatch_channel: trio.abc.SendChannel,
        get_markup: typing.Callable[[int], str],
    ):
        self.screen_size = screen_size
        self.dispatch_channel = dispatch_channel
        self.get_markup = get_markup
        self.renderer = stilus.pango_render.Renderer(
            screen_size=self.screen_size, dpi=dpi
        )
        self.set_font(font)
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

    async def render_update(self, renderables: typing.List[Renderable]):
        before_render = tuple(self.renders)
        for renderable in renderables:
            markup = self.get_markup(renderable.paragraph)
            if renderable.has_cursor:
                markup += CURSOR
            new_rendered: npt.ArrayLike = self.renderer.render_to_numpy(
                markup, self.font
            )
            new_size = stilus.types.Size.from_numpy_shape(new_rendered.shape)
            self.set_into(
                self.renders,
                renderable.paragraph,
                RenderPara(rendered=new_rendered, size=new_size),
            )

        need_to_reflow = len(self.renders) > len(before_render) or any(
            [
                before.size != after.size
                for before, after in zip(before_render, self.renders)
            ]
        )
        if not need_to_reflow:
            # Only the last paragraph needs to be rerendered.
            relative_top = self.cursor_y - self.renders[-1].size.height
            new_image = self.renders[-1].rendered
            render_diff = new_image - before_render[-1].rendered
            changed_box = bbox(render_diff)
            changed: npt.ArrayLike = new_image[
                changed_box.top : changed_box.bottom,
                changed_box.left : changed_box.right,
            ]
            framelet = Framelet(
                rect=changed_box.to_protocol_rect(relative_top), image=changed.tobytes()
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
                rect=Rect(x=0, y=0, width=self.screen_size.width, height=self.cursor_y),
                image=half_screen.tobytes(),
            )

        await self.dispatch_channel.send(framelet)

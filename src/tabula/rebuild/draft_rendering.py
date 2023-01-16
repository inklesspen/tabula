import math
import typing

import attrs
import numpy as np
import numpy.typing as npt

from .doctypes import Renderable
from .hwtypes import ScreenRect
from ..rendering.rendertypes import Size

if typing.TYPE_CHECKING:
    from .settings import Settings
    from ..rendering.renderer2 import Renderer

# https://en.wikipedia.org/wiki/Macron_below
# https://en.wikipedia.org/wiki/Underscore
CURSOR = '<span alpha="50%">_</span>'


@attrs.define(kw_only=True, frozen=True)
class RenderPara:
    rendered: npt.ArrayLike
    size: Size


@attrs.define(kw_only=True, frozen=True)
class LaidOutPara:
    index: int
    screen_top: int
    screen_bottom: int


@attrs.define(kw_only=True, frozen=True)
class ArrayRect:
    top: int
    bottom: int
    left: int
    right: int

    def to_protocol_rect(self, y_adjust: int = 0) -> ScreenRect:
        return ScreenRect(
            x=self.left,
            y=self.top + y_adjust,
            width=self.right - self.left,
            height=self.bottom - self.top,
        )


@attrs.define(kw_only=True, frozen=True)
class Framelet:
    rect: ScreenRect
    image: bytes


def bbox(img: npt.ArrayLike) -> ArrayRect:
    rows = np.any(img, axis=1)
    cols = np.any(img, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    return ArrayRect(top=int(rmin), bottom=int(rmax), left=int(cmin), right=int(cmax))


class Screen:
    def __init__(self, renderer: "Renderer", settings: "Settings"):
        self.renderer = renderer
        self.settings = settings
        self.screen_size = renderer.screen_info.size
        self.cursor_y = self.screen_size.height // 2
        self.renders: list[RenderPara] = []

    @staticmethod
    def set_into(list, index, item):
        if index >= len(list):
            list.append(item)
        else:
            list[index] = item

    def render_to_bytes(self, markup: str):
        with self.renderer.create_surface() as surface:
            rendered_size = self.renderer.render(
                surface,
                font=self.settings.current_font,
                text=markup,
                markup=True,
                # margins=Margins(top=0, bottom=0, left=10, right=10),
                render_size=self.screen_size,
            )
            buf = self.renderer.surface_to_bytes(surface, rendered_size)
            return buf, rendered_size

    def render_update(self, renderables: list[Renderable], force=False):
        skip_height = math.floor(
            self.renderer.calculate_line_height(self.settings.current_font)
        )
        before_render = tuple() if force else tuple(self.renders)
        for renderable in renderables:
            markup = renderable.markup
            if renderable.has_cursor:
                markup += CURSOR
            (buf, render_size) = self.render_to_bytes(markup)
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
            framelet_bytes = changed.tobytes()
            framelet = Framelet(
                rect=changed_box.to_protocol_rect(relative_top),
                image=framelet_bytes,
            )

        else:
            # we gotta reflow everything on screen
            laidouts: list[typing.Optional[LaidOutPara]] = [None for _ in self.renders]
            current_y = self.cursor_y
            current_i = len(self.renders) - 1
            while current_i >= 0 and current_y >= 0:
                size = self.renders[current_i].size
                top = current_y - size.height
                laidouts[current_i] = LaidOutPara(
                    index=current_i, screen_bottom=current_y, screen_top=top
                )
                current_y -= size.height + skip_height
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
            framelet_bytes = half_screen.tobytes()
            framelet = Framelet(
                rect=ScreenRect(
                    x=0,
                    y=0,
                    width=self.screen_size.width,
                    height=self.cursor_y,
                ),
                image=framelet_bytes,
            )

        return [framelet]

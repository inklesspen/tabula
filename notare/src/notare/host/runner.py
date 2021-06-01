# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import enum
import json
import os
import typing
import unicodedata

import attr
import numpy as np
import numpy.typing as npt
import trio
from trio_jsonrpc import (
    open_jsonrpc_ws,
    JsonRpcConnection,
)
from trio_util import RepeatedEvent

import stilus.markdown
import stilus.pango_render
import stilus.types

from . import term
from ..protocol import (
    Framelet,
    Rect,
    BatteryState,
    KoboTime,
    Protocol,
    TABULA_IP,
    TABULA_PORT,
)


class Stub(Protocol):
    def __init__(self, client: JsonRpcConnection):
        self.client = client

    async def update_display(self, framelet: Framelet) -> None:
        await self.client.request(
            "update_display", {"framelet": json.loads(framelet.json())}
        )

    async def get_battery_state(self) -> BatteryState:
        response = await self.client.request("get_battery_state", {})
        return BatteryState.parse_raw(json.dumps(response))

    async def get_current_time(self) -> KoboTime:
        response = await self.client.request("get_current_time", {})
        return KoboTime.parse_raw(json.dumps(response))

    async def shutdown(self) -> None:
        print("shutting down")
        await self.client.request("shutdown", {})


# At this point it's model view controller, just like papa used to make.


def graphical_char(c: typing.Text):
    category = unicodedata.category(c)
    return category == "Zs" or category[0] in ("L", "M", "N", "P", "S")


# https://gankra.github.io/blah/text-hates-you/
# Cursor movement is fairly complicated. If we were gonna do everything the proper way, our
# document model would need to know about Unicode scalars, grapheme clusters, and all that jazz.
# After all, if I have a grapheme cluster composed of U+0065 (LATIN SMALL LETTER E) and U+0301
# (COMBINING ACCUTE ACCENT), these render as é (LATIN SMALL LETTER E WITH ACUTE). However, if I
# insert U+0302 (COMBINING CIRCUMFLEX ACCENT) into the middle of this cluster, I instead get ế
# (LATIN SMALL LETTER E WITH CIRCUMFLEX AND ACUTE). This example may sound contrived, but it
# happens all the time with non-Latin scripts.
# Notare currently handles attributed text by wrapping portions of the Markdown text in
# Pango Markup (HTML-ish tags). If we wanted to know about the grapheme clusters and glyphs,
# we'd have to switch to using PangoAttrList. So we're not going to do that.
# The cursor is always at the end of the final paragraph. That's it. That's all there is.

# https://en.wikipedia.org/wiki/Macron_below
# https://en.wikipedia.org/wiki/Underscore
CURSOR = '<span alpha="50%">_</span>'
FONT = "iA Writer Quattro V 8"


class UpdateKind(enum.Enum):
    NEW = enum.auto()
    CHANGE = enum.auto()


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class ParagraphUpdate:
    paragraph: int
    kind: UpdateKind


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class Renderable:
    paragraph: int
    has_cursor: bool


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class RenderPara:
    rendered: npt.ArrayLike
    size: stilus.types.Size


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class LaidOutPara:
    index: int
    screen_top: int
    screen_bottom: int


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class ArrayRect:
    top: int
    bottom: int
    left: int
    right: int

    def to_protocol_rect(self, y_adjust: int = 0) -> Rect:
        return Rect(
            x=self.left,
            y=self.top + y_adjust,
            width=self.right - self.left,
            height=self.bottom - self.top,
        )


class DocumentModel:
    def __init__(self, dispatch_channel: trio.abc.SendChannel):
        self.dispatch_channel = dispatch_channel
        self.currently = None
        self.contents: list[stilus.markdown.Paragraph] = []

    async def keystroke(self, keystroke):
        self.currently.markdown += keystroke
        self.currently.make_markup()
        message = ParagraphUpdate(
            paragraph=len(self.contents) - 1, kind=UpdateKind.CHANGE
        )
        await self.dispatch_channel.send(message)

    async def backspace(self):
        if len(self.currently.markdown) == 0:
            # no going back
            return
        self.currently.markdown = self.currently.markdown[:-1]
        self.currently.make_markup()
        message = ParagraphUpdate(
            paragraph=len(self.contents) - 1, kind=UpdateKind.CHANGE
        )
        await self.dispatch_channel.send(message)

    async def new_para(self):
        if self.currently and len(self.currently.markdown) == 0:
            return
        self.currently = stilus.markdown.Paragraph.empty()
        self.contents.append(self.currently)
        message = ParagraphUpdate(paragraph=len(self.contents) - 1, kind=UpdateKind.NEW)
        await self.dispatch_channel.send(message)

    def get_markups(self):
        return [p.markup for p in self.contents]

    def get_markup(self, i: int) -> str:
        return self.contents[i].markup


def bbox(img: npt.ArrayLike) -> ArrayRect:
    rows = np.any(img, axis=1)
    cols = np.any(img, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    return ArrayRect(top=rmin, bottom=rmax, left=cmin, right=cmax)


class Screen:
    def __init__(
        self,
        dispatch_channel: trio.abc.SendChannel,
        get_markup: typing.Callable[[int], str],
    ):
        self.dispatch_channel = dispatch_channel
        self.get_markup = get_markup
        self.screen_size = stilus.types.Size(width=1072, height=1448)
        self.renderer = stilus.pango_render.Renderer(
            screen_size=self.screen_size, dpi=300
        )
        self.set_font(FONT)
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


class Application:
    def __init__(
        self,
        keystroke_receive_channel: trio.abc.ReceiveChannel,
        stub: Stub,
        nursery: trio.Nursery,
    ):
        self.keystroke_receive_channel = keystroke_receive_channel
        self.stub = stub
        document_send_channel, self.document_receive_channel = trio.open_memory_channel(
            0
        )
        self.document_update = RepeatedEvent()
        self.document = DocumentModel(document_send_channel)
        screen_send_channel, self.screen_receive_channel = trio.open_memory_channel(0)
        self.screen = Screen(screen_send_channel, self.document.get_markup)
        self.nursery = nursery
        nursery.start_soon(self.document.new_para)

    async def handle_keystrokes(self):
        async with self.keystroke_receive_channel:
            async for value in self.keystroke_receive_channel:
                if len(value) == 1 and graphical_char(value):
                    await self.document.keystroke(value)
                elif value == "enter":
                    await self.document.new_para()
                elif value == "backspace":
                    await self.document.backspace()
                # elif value == "f1":
                #     print("This is when we would show help.")
                # elif value == "f10":
                #     print("This is when we would show the menu.")
                elif value == "shutdown":
                    await self.stub.shutdown()
                    self.nursery.cancel_scope.cancel()

    async def handle_document_updates(self):
        async with self.document_receive_channel:
            update: ParagraphUpdate
            async for update in self.document_receive_channel:
                renderables: typing.List[Renderable] = []
                if update.kind == UpdateKind.NEW:
                    # gotta rerender the previous paragraph to remove the cursor
                    # as well as the new one
                    prev = update.paragraph - 1
                    if prev >= 0:
                        renderables.append(Renderable(paragraph=prev, has_cursor=False))
                renderables.append(
                    Renderable(paragraph=update.paragraph, has_cursor=True)
                )
                await self.screen.render_update(renderables)

    async def handle_screen_updates(self):
        async with self.screen_receive_channel:
            update: Framelet
            async for update in self.screen_receive_channel:
                await self.stub.update_display(update)


async def main(url):
    async with trio.open_nursery() as nursery, open_jsonrpc_ws(url) as client:
        stub = Stub(client)
        kt = await stub.get_current_time()
        keystroke_send_channel, keystroke_receive_channel = trio.open_memory_channel(0)
        application = Application(keystroke_receive_channel, stub, nursery)
        nursery.start_soon(application.handle_keystrokes)
        nursery.start_soon(application.handle_document_updates)
        nursery.start_soon(application.handle_screen_updates)
        nursery.start_soon(
            term.input_loop, ("f12",), kt.now, keystroke_send_channel, nursery
        )
        await trio.sleep_forever()


if __name__ == "__main__":
    tabula_ip = os.environ.get("TABULA_IP", TABULA_IP)
    tabula_post = os.environ.get("TABULA_PORT", TABULA_PORT)
    tabula_url = f"ws://{tabula_ip}:{tabula_post}"
    trio.run(main, tabula_url)

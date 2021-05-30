# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import typing
import unicodedata

from PIL import Image
import pydantic
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

    async def update_display(self, framelet: Framelet) -> BatteryState:
        response = await self.client.request(
            "update_display", {"framelet": json.loads(framelet.json())}
        )
        return BatteryState.parse_raw(json.dumps(response))

    async def get_current_time(self) -> KoboTime:
        response = await self.client.request("get_current_time", {})
        return KoboTime.parse_raw(json.dumps(response))


def graphical_char(c: typing.Text):
    category = unicodedata.category(c)
    return category == "Zs" or category[0] in ("L", "M", "N", "P", "S")


# https://en.wikipedia.org/wiki/Macron_below
# https://en.wikipedia.org/wiki/Underscore
CURSOR = '<span alpha="25%">_</span>'
FONT = "iA Writer Quattro V 8"


class DocumentModel:
    def __init__(self, dispatch_event: RepeatedEvent):
        self.dispatch_event = dispatch_event
        self.currently = None
        self.contents: list[stilus.markdown.Paragraph] = []
        self.new_para()

    def keystroke(self, keystroke):
        self.currently.markdown += keystroke
        self.currently.make_markup()
        self.dispatch_event.set()

    def backspace(self):
        self.currently.markdown = self.currently.markdown[:-1]
        self.currently.make_markup()
        self.dispatch_event.set()

    def new_para(self):
        if self.currently and len(self.currently.markdown) == 0:
            return
        self.currently = stilus.markdown.Paragraph.empty()
        self.contents.append(self.currently)
        self.dispatch_event.set()

    def get_markups(self):
        return [p.markup for p in self.contents]


class RenderPara(pydantic.BaseModel):
    markup: str
    top_px: int
    bottom_px: int
    image: Image.Image

    class Config:
        arbitrary_types_allowed = True


class Screen:
    def __init__(self, dispatch_event: RepeatedEvent):
        self.dispatch_event = dispatch_event
        self.screen_size = stilus.types.Size(width=1072, height=1448)
        self.renderer = stilus.pango_render.Renderer(
            screen_size=self.screen_size, dpi=300
        )
        self.refresh_screenbuffer()
        self.cursor_y = self.screen_size.height // 2
        self.top_margin = 10
        self.renders: list[RenderPara] = []

    def refresh_screenbuffer(self):
        self.screenbuffer = Image.new("L", self.screen_size.as_tuple(), 255)

    async def update_paras(self, markups: typing.List[str]):
        skip_height = int(self.renderer.instance.calculate_line_height(FONT))
        markups[-1] += CURSOR
        self.renders = []
        y = self.top_margin
        for markup in markups:
            await trio.sleep(0)  # checkpoint
            image = self.renderer.render(markup, FONT)
            height = stilus.types.Size.from_tuple(image.size).height
            self.renders.append(
                RenderPara(markup=markup, top_px=y, bottom_px=y + height, image=image)
            )
            y += height + skip_height
        y -= skip_height  # take it back off after the last one

        screen_top = y - self.cursor_y
        self.refresh_screenbuffer()
        for rendered in self.renders:
            self.screenbuffer.paste(rendered.image, (0, rendered.top_px - screen_top))

        self.dispatch_event.set()


class Application:
    def __init__(self, keystroke_in_channel: trio.abc.ReceiveChannel, stub: Stub):
        self.keystroke_in_channel = keystroke_in_channel
        self.stub = stub
        self.document_update = RepeatedEvent()
        self.document = DocumentModel(self.document_update)
        self.screen_update = RepeatedEvent()
        self.screen = Screen(self.screen_update)

    async def handle_keystrokes(self):
        async with self.keystroke_in_channel:
            async for value in self.keystroke_in_channel:
                if len(value) == 1 and graphical_char(value):
                    self.document.keystroke(value)
                elif value == "enter":
                    self.document.new_para()
                elif value == "backspace":
                    self.document.backspace()

    async def handle_document_updates(self):
        async for _ in self.document_update.events():
            await self.screen.update_paras(self.document.get_markups())

    async def handle_screen_updates(self):
        async for _ in self.screen_update.events():
            # TODO: optimize
            im = self.screen.screenbuffer
            rect = Rect(x=0, y=0, width=im.width, height=im.height)
            fr = Framelet(image=im.tobytes("raw"), rect=rect)
            response = await self.stub.update_display(fr)
            # print("Battery {}".format(response))


async def main(url):
    async with trio.open_nursery() as nursery, open_jsonrpc_ws(url) as client:
        stub = Stub(client)
        kt = await stub.get_current_time()
        keystroke_send_channel, keystroke_receive_channel = trio.open_memory_channel(0)
        application = Application(keystroke_receive_channel, stub)
        nursery.start_soon(application.handle_keystrokes)
        nursery.start_soon(application.handle_document_updates)
        nursery.start_soon(application.handle_screen_updates)
        nursery.start_soon(
            term.input_loop, ("f12",), kt.now, keystroke_send_channel, nursery
        )
        await trio.sleep_forever()


if __name__ == "__main__":
    tabula_url = f"ws://{TABULA_IP}:{TABULA_PORT}"
    trio.run(main, tabula_url)

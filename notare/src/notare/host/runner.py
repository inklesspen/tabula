# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import typing
import unicodedata

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
from .rendering import Screen
from .types import UpdateKind, ParagraphUpdate, Renderable
from ..protocol import (
    Framelet,
    BatteryState,
    KoboTime,
    ScreenInfo,
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

    async def get_screen_info(self) -> ScreenInfo:
        response = await self.client.request("get_screen_info", {})
        return ScreenInfo.parse_raw(json.dumps(response))

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


class Application:
    def __init__(
        self,
        keystroke_receive_channel: trio.abc.ReceiveChannel,
        stub: Stub,
        nursery: trio.Nursery,
        screen_info: ScreenInfo,
    ):
        self.keystroke_receive_channel = keystroke_receive_channel
        self.stub = stub
        self.screen_info = screen_info
        document_send_channel, self.document_receive_channel = trio.open_memory_channel(
            0
        )
        self.document_update = RepeatedEvent()
        self.document = DocumentModel(document_send_channel)
        screen_send_channel, self.screen_receive_channel = trio.open_memory_channel(0)
        screen_size = stilus.types.Size(
            width=screen_info.width, height=screen_info.height
        )
        self.screen = Screen(
            screen_size, screen_info.dpi, screen_send_channel, self.document.get_markup
        )
        self.nursery = nursery
        nursery.start_soon(self.document.new_para)

    async def handle_keystrokes(self):
        log_keys = bool(os.environ.get("LOG_KEYS"))
        async with self.keystroke_receive_channel:
            async for value in self.keystroke_receive_channel:
                if log_keys:
                    print(f"keystroke: {value}")
                if len(value) == 1 and graphical_char(value):
                    await self.document.keystroke(value)
                elif value == "enter":
                    await self.document.new_para()
                elif value == "backspace":
                    await self.document.backspace()
                elif value == "f1":
                    print("This is when we would show help.")
                elif value == "f10":
                    print("This is when we would show the menu.")
                elif value == "f12":
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
        screen_info = await stub.get_screen_info()
        keystroke_send_channel, keystroke_receive_channel = trio.open_memory_channel(0)
        application = Application(keystroke_receive_channel, stub, nursery, screen_info)
        nursery.start_soon(application.handle_keystrokes)
        nursery.start_soon(application.handle_document_updates)
        nursery.start_soon(application.handle_screen_updates)
        nursery.start_soon(term.input_loop, keystroke_send_channel)
        await trio.sleep_forever()


if __name__ == "__main__":
    tabula_ip = os.environ.get("TABULA_IP", TABULA_IP)
    tabula_post = os.environ.get("TABULA_PORT", TABULA_PORT)
    tabula_url = f"ws://{tabula_ip}:{tabula_post}"
    trio.run(main, tabula_url)

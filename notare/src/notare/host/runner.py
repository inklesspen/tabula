# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import typing

import timeflake
import trio
from trio_jsonrpc import open_jsonrpc_ws

from trio_util import periodic

from . import term, loop, wordcount
from .config import Settings
from .db import TabulaDb, make_db
from .document import DocumentModel
from .notify import notify_ready
from .stub import Stub
from ..protocol import DeviceInfo


# At this point it's model view controller, just like papa used to make.


class Application:
    def __init__(
        self,
        settings: Settings,
        device_info: DeviceInfo,
        stub: Stub,
        db: TabulaDb,
    ):
        self.settings = settings
        self.device_info = device_info
        self.stub = stub
        self.db = db
        self.dirty_paras = set()

    async def run(self):
        document_send_channel, document_receive_channel = trio.open_memory_channel(0)
        keystroke_send_channel, keystroke_receive_channel = trio.open_memory_channel(0)

        self.document = DocumentModel(
            document_send_channel, self.db, self.settings.drafting_fonts[0]
        )

        self.loops = {}
        for loopcls in loop.Loop.loops():
            self.loops[loopcls] = loopcls(
                self.device_info,
                self.settings,
                self.db,
                self.document,
            )
        self.current_loop = self.loops[loop.SystemMenu]

        if self.settings.systemd_notify:
            notify_ready()

        # the first time we switch into Drafting, it will try to restore the screen. so we save it here.
        await self.stub.save_screen()

        async with trio.open_nursery() as nursery:
            self.nursery = nursery
            nursery.start_soon(self.handle_keystrokes, keystroke_receive_channel)
            nursery.start_soon(self.handle_document_updates, document_receive_channel)
            nursery.start_soon(term.input_loop, keystroke_send_channel)
            nursery.start_soon(self.current_loop.activate, self.stub)
            nursery.start_soon(self.periodic_save_doc, periodic(5))
            await trio.sleep_forever()

    @property
    def is_drafting(self) -> bool:
        return self.current_loop == self.loops[loop.Drafting]

    async def deliver_dirties(self):
        if self.is_drafting and self.dirty_paras:
            all_dirties = sorted(self.dirty_paras)
            self.dirty_paras.clear()
            await self.current_loop.handle_dirty_updates(all_dirties)

    async def handle_keystrokes(self, keystroke_receive_channel):
        async with keystroke_receive_channel:
            async for value in keystroke_receive_channel:
                if self.settings.log_keys:
                    print(f"keystroke: {value}")

                result = await self.current_loop.handle_keystroke(value)
                cmd = result[0]
                # possible commands are switch_loop, set_time, shutdown, and nothing
                if cmd == "switch_loop":
                    new_loop = self.loops[result[1]]
                    await self.current_loop.deactivate(self.stub)
                    self.current_loop = new_loop
                    await self.current_loop.activate(self.stub)
                    await self.deliver_dirties()
                if cmd == "set_time":
                    print("Was asked to set system time.")
                if cmd == "shutdown":
                    await self.save_doc()
                    await self.stub.shutdown()
                    self.nursery.cancel_scope.cancel()

    async def handle_document_updates(self, document_receive_channel):
        async with document_receive_channel:
            dirties: typing.Tuple[timeflake.Timeflake]
            async for dirties in document_receive_channel:
                self.dirty_paras.update(dirties)
                await self.deliver_dirties()

    async def periodic_save_doc(self, trigger):
        async for _ in trigger:
            await self.save_doc()

    async def save_doc(self):
        if not self.document.has_session:
            return
        await trio.sleep(0)
        paras = self.document.contents
        doc_wc = wordcount.count_plain_text(
            wordcount.make_plain_text("\n".join([p.markdown for p in paras]))
        )
        self.db.save_session(self.document.session_id, doc_wc, paras)


async def run_client(settings: Settings):
    url = f"ws://{settings.ip}:{settings.port}"

    async with open_jsonrpc_ws(url) as client:
        stub = Stub(client)
        db = make_db()
        device_info = await stub.get_device_info()
        application = Application(settings, device_info, stub, db)
        await application.run()


def main():
    settings = Settings()
    trio.run(run_client, settings)


if __name__ == "__main__":
    main()
